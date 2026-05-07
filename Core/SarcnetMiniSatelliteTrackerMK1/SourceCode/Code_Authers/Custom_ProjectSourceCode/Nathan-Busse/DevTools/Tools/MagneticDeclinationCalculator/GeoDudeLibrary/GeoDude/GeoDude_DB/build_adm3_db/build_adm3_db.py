#!/usr/bin/env python3
"""
Build a SQLite database of ADM3 boundaries with bounding‑box index.
Run after downloading the GeoJSON files.
"""

import sqlite3
import json
from pathlib import Path
from shapely.geometry import shape
from download_geoBoundries_ADM3 import download_geoBoundries_ADM3
import geopandas as gpd

# ─── paths ───────────────────────────────────────────────────
GEOJSON_DIR = Path(__file__).parent          # folder with .geojson files
DB_PATH = Path(__file__).parents[1] / "data" / "adm3_boundaries.db"
DB_PATH.parent.mkdir(exist_ok=True)

# ─── create SQLite tables ────────────────────────────────────
conn = sqlite3.connect(str(DB_PATH))
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("""
    CREATE TABLE IF NOT EXISTS adm3_features (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        iso TEXT,
        country_name TEXT,
        shapeName TEXT,
        shapeID TEXT,
        geometry_wkb BLOB
    )
""")
conn.execute("""
    CREATE TABLE IF NOT EXISTS adm3_bbox (
        id INTEGER PRIMARY KEY,
        minx REAL, miny REAL, maxx REAL, maxy REAL,
        FOREIGN KEY (id) REFERENCES adm3_features(id)
    )
""")
conn.commit()

# ─── process each GeoJSON file ───────────────────────────────
insert_feat_sql = "INSERT INTO adm3_features (iso, country_name, shapeName, shapeID, geometry_wkb) VALUES (?,?,?,?,?)"
insert_bbox_sql = "INSERT INTO adm3_bbox (id, minx, miny, maxx, maxy) VALUES (?,?,?,?,?)"

geojson_files = sorted(GEOJSON_DIR.glob("*.geojson"))
print(f"Found {len(geojson_files)} GeoJSON files.")

for gj_path in geojson_files:
    iso = gj_path.stem.split('_')[0]
    print(f"Processing {iso} ...", end="", flush=True)

    with open(gj_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    features = data.get('features', [])
    count = 0
    with conn:
        for feat in features:
            geom = shape(feat['geometry'])
            wkb = geom.wkb
            props = feat.get('properties', {})
            shapeName = props.get('shapeName', '')
            shapeID = props.get('shapeID', '')
            country_name = props.get('shapeGroup', '')

            cursor = conn.execute(insert_feat_sql, (iso, country_name, shapeName, shapeID, sqlite3.Binary(wkb)))
            fid = cursor.lastrowid
            minx, miny, maxx, maxy = geom.bounds
            conn.execute(insert_bbox_sql, (fid, minx, miny, maxx, maxy))
            count += 1
    print(f" {count} features")

# ─── create indexes ──────────────────────────────────────────
conn.execute("CREATE INDEX IF NOT EXISTS idx_bbox_xy ON adm3_bbox(minx, miny, maxx, maxy)")
conn.commit()
conn.close()
print(f"\nDatabase created: {DB_PATH}")