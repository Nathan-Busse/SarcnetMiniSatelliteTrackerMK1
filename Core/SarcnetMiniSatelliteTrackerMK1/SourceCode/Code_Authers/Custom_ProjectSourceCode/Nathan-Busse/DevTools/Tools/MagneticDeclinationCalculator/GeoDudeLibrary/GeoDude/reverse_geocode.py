# reverse_geocode.py
import sqlite3
from shapely import wkb
from shapely.geometry import Point
from shapely.strtree import STRtree

class ReverseGeocoder:
    """Offline reverse geocoder using geoBoundaries ADM3 polygons."""

    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._load_features()
        self._build_spatial_index()

    def _load_features(self):
        cursor = self.conn.execute("""
            SELECT f.id, f.iso, f.country_name, f.shapeName, f.shapeID,
                   f.geometry_wkb, b.minx, b.miny, b.maxx, b.maxy
            FROM adm3_features f
            JOIN adm3_bbox b ON f.id = b.id
        """)
        self.rows = cursor.fetchall()
        if not self.rows:
            raise ValueError("No ADM3 features found in database.")

    def _build_spatial_index(self):
        # Build STRtree of bounding boxes (Polygon or just the bbox geometry)
        self.bbox_polygons = [
            wkb.loads(
                f"POLYGON(({r['minx']} {r['miny']},{r['maxx']} {r['miny']},{r['maxx']} {r['maxy']},{r['minx']} {r['maxy']},{r['minx']} {r['miny']}))")
            for r in self.rows
        ]
        self.tree = STRtree(self.bbox_polygons)

    def get_nearest(self, lat, lon):
        """Return dict with ADM3 info, or None if no polygon contains the point."""
        if not self.rows:
            return None
        point = Point(lon, lat)
        # Query tree for candidate bboxes whose bbox contains the point
        candidates = self.tree.query(point)

        # Exact point‑in‑polygon test
        for idx in candidates:
            r = self.rows[idx]
            # Some candidates may have bboxes that contain the point but the polygon itself doesn't
            poly = wkb.loads(r['geometry_wkb'])
            if poly.contains(point):
                parts = []
                if r['shapeName']:
                    parts.append(r['shapeName'])
                if r['country_name']:
                    parts.append(r['country_name'])
                # Optionally add ADM1/ADM2 if available in properties (we didn't store them, but you can extend)
                return {
                    'name': r['shapeName'],
                    'admin1': '',           # could be added from other tables
                    'admin2': '',
                    'country': r['country_name'],
                    'lat': lat,
                    'lon': lon,
                    'address': ', '.join(parts) if parts else r['shapeName']
                }
        return None

    def close(self):
        if self.conn:
            self.conn.close()