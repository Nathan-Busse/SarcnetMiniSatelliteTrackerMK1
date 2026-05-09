#!/usr/bin/env python3
"""
Build the SQLite DB and CSV required by geodude from GeoJSON ADM3 files.
"""

import csv
import json
import sqlite3
from pathlib import Path
from shapely.geometry import shape

def build_files(data_dir: Path):
    """
    data_dir : Path to the geodude data folder (e.g. geodude/data/).
    Expects a sub‑directory `geoBoundaries_ADM3` containing *.geojson files.
    Creates `data.db` and `geo-boundaries.csv` in `data_dir`.
    """
    geojson_dir = data_dir / "geoBoundaries_ADM3"
    db_path = data_dir / "data.db"
    csv_path = data_dir / "geo-boundaries.csv"

    conn = sqlite3.connect(str(db_path))
    conn.execute("DROP TABLE IF EXISTS location_data")
    conn.execute("""
        CREATE TABLE location_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            shape_id TEXT,
            coordinates BLOB
        )
    """)
    conn.commit()

    with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["name", "shape_id", "lon", "lat", "admin1", "admin2"])

        geojson_files = sorted(geojson_dir.glob("*.geojson"))
        print(f"Found {len(geojson_files)} GeoJSON files.")

        for gj_path in geojson_files:
            iso = gj_path.stem.split('_')[0]
            print(f"Processing {iso} …", end="", flush=True)
            with open(gj_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            features = data.get('features', [])
            count = 0
            for feat in features:
                geom = shape(feat['geometry'])
                wkb = geom.wkb
                centroid = geom.centroid
                props = feat.get('properties', {})
                shapeName = props.get('shapeName', '')
                shapeID = props.get('shapeID', '')
                country = props.get('shapeGroup', '')
                admin1 = country
                admin2 = shapeName

                conn.execute(
                    "INSERT INTO location_data (name, shape_id, coordinates) VALUES (?, ?, ?)",
                    (shapeName, shapeID, sqlite3.Binary(wkb))
                )

                writer.writerow([shapeName, shapeID, centroid.x, centroid.y, admin1, admin2])
                count += 1
            conn.commit()
            print(f" {count} features")

    conn.close()
    print(f"\nDatabase created: {db_path}")
    print(f"CSV created: {csv_path}")