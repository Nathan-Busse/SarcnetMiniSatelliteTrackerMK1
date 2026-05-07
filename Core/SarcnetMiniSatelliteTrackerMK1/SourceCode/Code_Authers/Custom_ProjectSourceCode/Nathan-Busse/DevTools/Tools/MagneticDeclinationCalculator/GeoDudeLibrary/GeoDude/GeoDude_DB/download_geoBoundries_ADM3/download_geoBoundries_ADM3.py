#!/usr/bin/env python3
"""
Download all geoBoundaries ADM3 (county / municipality) simplified GeoJSON files.
Creates:  ./geoBoundaries_ADM3/{ISO}_{name}.geojson
"""

import json
import time
import urllib.request
from pathlib import Path

API_URL = "https://www.geoboundaries.org/api/current/gbOpen/ALL/ADM3/"
OUT_DIR = Path("geoBoundaries_ADM3")
OUT_DIR.mkdir(exist_ok=True)

# 1. Fetch metadata for all countries ADM3
print("Fetching ADM3 metadata for all countries ...")
with urllib.request.urlopen(API_URL) as resp:
    countries = json.loads(resp.read())

print(f"Found {len(countries)} countries with ADM3 data\n")

# 2. Download simplified GeoJSON for each country
downloaded = 0
skipped = 0
failed = 0

for entry in countries:
    iso = entry["boundaryISO"]
    name = entry["boundaryName"]
    gj_url = entry.get("simplifiedGeometryGeoJSON")

    if not gj_url:
        print(f"  {iso} ({name}): no simplified GeoJSON – skipping")
        skipped += 1
        continue

    out_path = OUT_DIR / f"{iso}_{name.replace(' ','_')}.geojson"
    if out_path.exists():
        print(f"  {iso} ({name}): already exists – skipping")
        skipped += 1
        continue

    try:
        print(f"  Downloading {iso} ({name}) ...", end="", flush=True)
        urllib.request.urlretrieve(gj_url, out_path)
        print(" done")
        downloaded += 1
    except Exception as e:
        print(f" FAILED ({e})")
        failed += 1

    time.sleep(0.3)   # be polite to the server

print(f"\nDone – {downloaded} downloaded, {skipped} skipped, {failed} failed")
print(f"Files are in: {OUT_DIR.resolve()}")