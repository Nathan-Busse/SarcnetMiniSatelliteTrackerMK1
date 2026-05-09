#!/usr/bin/env python3
"""
Single‑call installer that is used to create and build geodude's database from scratch.
Usage:  from geodude import create_db
        create_db()
"""

import time
import urllib.request
from pathlib import Path
from importlib.resources import files

# Path to the geodude package's data directory
DATA_DIR = files("geodude.data")   # automatically resolves to geodude/data/

def create_db():
    """Download ADM3 GeoJSON files and build the geodude database."""
    # 1. Download GeoJSON files into DATA_DIR / geoBoundaries_ADM3
    geojson_dir = DATA_DIR / "geoBoundaries_ADM3"
    geojson_dir.mkdir(parents=True, exist_ok=True)

    API_URL = "https://www.geoboundaries.org/api/current/gbOpen/ALL/ADM3/"
    print("Fetching ADM3 metadata …")
    with urllib.request.urlopen(API_URL) as resp:
        import json
        countries = json.loads(resp.read())

    total = len(countries)
    print(f"Found {total} countries with ADM3 data")

    for idx, entry in enumerate(countries, 1):
        iso = entry["boundaryISO"]
        name = entry["boundaryName"]
        gj_url = entry.get("simplifiedGeometryGeoJSON")
        if not gj_url:
            print(f"  [{idx}/{total}] {iso} ({name}): no GeoJSON – skipping")
            continue
        out_file = geojson_dir / f"{iso}_{name.replace(' ', '_')}.geojson"
        if out_file.exists():
            print(f"  [{idx}/{total}] {iso} ({name}): already exists – skipping")
            continue
        print(f"  [{idx}/{total}] Downloading {iso} ({name}) …", end="", flush=True)
        urllib.request.urlretrieve(gj_url, out_file)
        print(" done")
        time.sleep(0.3)

    print("Downloads complete.\n")

    # 2. Build the database and CSV using the builder script
    from geodude.data.build_adm3_db.build_adm3_db import build_files
    build_files(DATA_DIR)
    print("Data installation complete.")
