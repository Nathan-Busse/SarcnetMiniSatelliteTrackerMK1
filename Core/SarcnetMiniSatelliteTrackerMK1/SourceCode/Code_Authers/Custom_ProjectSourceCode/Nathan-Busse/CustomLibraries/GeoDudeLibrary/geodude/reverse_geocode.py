import csv
import sqlite3
import sys
from collections.abc import Iterable
from importlib.resources import files

import numpy as np
from pydantic import BaseModel, Field
from shapely import wkb
from shapely.geometry import Point

if sys.platform == "win32":
    csv.field_size_limit(2**31 - 1)
else:
    csv.field_size_limit(sys.maxsize)
from scipy.spatial import KDTree

from . import KD_Tree

# Schema of the geo_boundaries file created by this library
RG_COLUMNS: list = ["name", "shape_id", "lon", "lat", "admin1", "admin2"]

DB_PATH: str = str(files("geodude.data") / "data.db")
FILENAME: str = str(files("geodude.data") / "geo-boundaries.csv")

DEFAULT_K: int = 3


class LocationBaseModel(BaseModel):
    lat: float = Field(..., description="Centroid latitude of the nearest neighbor")
    lon: float = Field(..., description="Centroid longitude of the nearest neighbor")
    name: str = Field(..., description="Name of the nearest neighbour(")
    admin1: str = Field(..., description="Name of the primary administrative division (e.g., country)")
    admin2: str = Field(
        ...,
        description="Name of the secondary administrative division (e.g., state or province)",
    )


class GeocoderResultBaseModel(BaseModel):
    lat: float = Field(..., description="Given latitude")
    lon: float = Field(..., description="Given longitude")
    result: LocationBaseModel | None


def singleton(cls):
    instances = {}
    def getinstance(**kwargs):
        if cls not in instances:
            instances[cls] = cls(**kwargs)
        return instances[cls]
    return getinstance


@singleton
class geodude:
    """
    The main reverse geocoder class
    """

    def __init__(self, mode: int = 1):
        """Class Instantiation
        params:
        mode (int): Library supports the following two modes:
                    - 1 = Single-process K-D Tree (Default)
                    - 2 = Multi-process K-D Tree for large dataset
        """
        self.mode = mode
        coordinates, self.locations = self._load()
        self.conn = sqlite3.connect(DB_PATH)
        self.curr = self.conn.cursor()
        if self.mode == 1:
            self.tree = KDTree(coordinates)
        else:
            self.tree = KD_Tree.cKDTree_MP(coordinates)

    def _load(self):
        with open(FILENAME, newline="", encoding="utf-8") as file:
            stream_reader = csv.DictReader(file)
            header = stream_reader.fieldnames
            if header != RG_COLUMNS:
                raise csv.Error(f"Inputs should contain the columns defined in {RG_COLUMNS}")

            geo_coords, locations = [], []
            for row in stream_reader:
                geo_coords.append((row["lon"], row["lat"]))
                locations.append(row)
            return geo_coords, locations

    def _safe_load(self, blob):
        geom = wkb.loads(blob)
        return geom[0] if isinstance(geom, np.ndarray) else geom

    def _query_shape(self, filters: list[str]) -> list:
        placeholders = ",".join(["(?)"] * len(filters))
        query = f"""
            SELECT name, shape_id, coordinates
            FROM location_data
            WHERE shape_id IN ({placeholders});
        """
        self.curr.execute(query, filters)
        rows = self.curr.fetchall()
        lookup = {shape_id: self._safe_load(blob) for name, shape_id, blob in rows}
        return [lookup.get(shape_id) for shape_id in filters]

    def geo_contains(self, search_location: tuple[float, float], indexes: list[int]) -> GeocoderResultBaseModel:
        search_location = Point(*search_location)
        filters = [self.locations[index].get("shape_id") for index in indexes]
        for index, geometry in zip(indexes, self._query_shape(filters), strict=True):
            if geometry.contains(search_location):
                return GeocoderResultBaseModel(
                    lat=search_location.y,
                    lon=search_location.x,
                    result=LocationBaseModel(**self.locations[index]),
                )
        return GeocoderResultBaseModel(lat=search_location.y, lon=search_location.x, result=None)

    def query(self, coordinates: list[tuple[float, float]]) -> Iterable[GeocoderResultBaseModel]:
        if self.mode == 1:
            _, indices = self.tree.query(coordinates, k=DEFAULT_K)
        else:
            _, indices = self.tree.pquery(coordinates, k=DEFAULT_K)

        def _iter():
            for position, indexes_ in enumerate(indices):
                yield self.geo_contains(coordinates[position], indexes_)
        return _iter()

    def search(self, geo_coords) -> Iterable[GeocoderResultBaseModel]:
        if not geo_coords:
            raise TypeError("Coordinates cannot be empty")
        if not isinstance(geo_coords, list) and not isinstance(geo_coords[0], tuple):
            raise TypeError(f"Coordinates must be a list of tuples {type(geo_coords)}: {geo_coords}")
        return self.query(geo_coords)

    # ------- NEW: simple get_nearest for the main app -------
    def get_nearest(self, lat: float, lon: float) -> dict | None:
        """
        Return the nearest ADM3 administrative area as a dictionary,
        or None if no data is loaded.
        Falls back to the nearest centroid if no polygon contains the point.
        """
        # 1. Try exact polygon containment
        results = list(self.search([(lon, lat)]))
        if results and results[0].result:
            r = results[0].result
            return self._format_result(r.name, r.admin1, r.admin2, lat, lon)

        # 2. Fallback to nearest centroid
        try:
            _, idx = self.tree.query([(lon, lat)], k=1)
            idx_val = idx[0] if hasattr(idx, '__iter__') else idx
            loc = self.locations[idx_val]
            name = loc.get('name', '')
            admin1 = loc.get('admin1', '')
            admin2 = loc.get('admin2', '')
            return self._format_result(name, admin1, admin2, lat, lon)
        except Exception:
            return None

    @staticmethod
    def _format_result(name: str, admin1: str, admin2: str, lat: float, lon: float) -> dict:
        parts = [name]
        if admin2:
            parts.append(admin2)
        if admin1:
            parts.append(admin1)
        address = ', '.join(parts) if parts else name
        return {
            'name': name,
            'admin1': admin1 or '',
            'admin2': admin2 or '',
            'country': '',
            'lat': lat,
            'lon': lon,
            'address': address
        }