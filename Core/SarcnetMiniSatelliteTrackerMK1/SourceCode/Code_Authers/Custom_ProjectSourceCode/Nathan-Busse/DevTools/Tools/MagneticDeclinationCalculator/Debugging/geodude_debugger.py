'''
python -m GeoDudeLibrary.geodude.debug
'''

import csv
import sqlite3
import time
from pathlib import Path
from typing import List, Tuple, Optional, Union, Iterator

import numpy as np
from shapely import wkb
from shapely.geometry import Point

import geodude
from geodude import (
    GeocoderResultBaseModel,
    reverse_geocode,    
    LocationBaseModel,
    DB_PATH,
    RG_COLUMNS,
    DEFAULT_K,

    )

class GeoDudeDebugger:
    """
    Comprehensive diagnostic wrapper around a geodude instance.
    Covers:
      - data loading summary
      - CSV / DB consistency
      - step‑by‑step query debugging
      - shape geometry inspection
      - performance benchmarking
    """

    def __init__(self, mode: int = 1):
        """
        mode: 1 = single‑process KD‑Tree, 2 = multi‑process (for large data)
        """
        self.gd = geodude(mode=mode)
        self.db_path = DB_PATH


    # ------------------------------------------------------------------
    # DATA SUMMARY & INTEGRITY
    # ------------------------------------------------------------------
    def data_summary(self) -> None:
        """Print essential information about the loaded dataset."""
        print(f"\n{'='*60}")
        print("DATA SUMMARY")
        print(f"{'='*60}")
        print(f"Mode:             {'single' if self.gd.mode == 1 else 'multi'}‑process KD‑Tree")
        print(f"Locations loaded: {len(self.gd.locations)}")
        print(f"Tree size (n):    {getattr(self.gd.tree, 'n', 'N/A')}")
        print(f"Database path:    {self.db_path}")

    def csv_schema_ok(self) -> bool:
        """Verify the CSV file uses the expected columns."""
        try:
            with open(self.gd.FILENAME, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                actual = reader.fieldnames
        except Exception as e:
            print(f" Cannot open CSV: {e}")
            return False
        if actual is None:
            print(" CSV has no header.")
            return False
        if actual != RG_COLUMNS:
            print(f" Column mismatch!\n  Expected: {RG_COLUMNS}\n  Actual  : {actual}")
            return False
        print(" CSV schema matches expected columns.")
        return True

    def check_db_integrity(self) -> bool:
        """
        Ensure every shape_id in the CSV exists in the SQLite database,
        and vice‑versa.
        """
        if not Path(self.db_path).exists():
            print(f" Database file not found: {self.db_path}")
            return False

        # Collect shape_ids from CSV
        csv_ids = set()
        try:
            with open(self.gd.FILENAME, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                csv_ids = {row["shape_id"] for row in reader}
        except Exception as e:
            print(f" Error reading CSV: {e}")
            return False

        # Collect shape_ids from DB
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        try:
            cur.execute("SELECT shape_id FROM location_data")
            db_ids = {row[0] for row in cur.fetchall()}
        except sqlite3.Error as e:
            print(f" DB query failed: {e}")
            conn.close()
            return False
        finally:
            conn.close()

        only_csv = csv_ids - db_ids
        only_db = db_ids - csv_ids

        if only_csv:
            print(f"  {len(only_csv)} id(s) in CSV but missing from DB: {list(only_csv)[:5]}...")
        if only_db:
            print(f"  {len(only_db)} id(s) in DB but missing from CSV: {list(only_db)[:5]}...")

        if not only_csv and not only_db:
            print(" All shape_ids are consistent between CSV and DB.")
            return True
        return False

    # ------------------------------------------------------------------
    # QUERY DEBUGGING
    # ------------------------------------------------------------------
    def debug_query(
        self,
        coords: List[Tuple[float, float]],
        k: int = DEFAULT_K,
        verbose: bool = True,
    ) -> List[GeocoderResultBaseModel]:
        """
        For every point in `coords`, show:
          - the k nearest neighbours and their distances
          - whether the point is contained in any of those neighbours
          - the final result returned by geo_contains()

        coords: list of (longitude, latitude)
        """
        if not isinstance(coords, list) or not all(isinstance(c, tuple) for c in coords):
            raise ValueError("coords must be a list of (lon, lat) tuples")

        # ---- Step 1: query the KD‑Tree directly to get distances & indices ----
        if self.gd.mode == 1:
            distances, indices = self.gd.tree.query(coords, k=k)
        else:
            distances, indices = self.gd.tree.pquery(coords, k=k)

        results = []
        for i, (lon, lat) in enumerate(coords):
            if verbose:
                print(f"\n{'─'*50}")
                print(f"Point {i}: lon = {lon:.6f}, lat = {lat:.6f}")
                print(f"{'─'*50}")

            # distances & indices are 1D if k==1, else 2D
            if k == 1:
                dist_row = [distances[i]]
                idx_row = [indices[i]]
            else:
                dist_row = distances[i]
                idx_row = indices[i]

            # Gather top-k info
            topk_info: List[Tuple[int, float]] = []
            for rank in range(k):
                dist = dist_row[rank]
                idx = idx_row[rank]
                topk_info.append((idx, dist))

            # Show neighbours
            if verbose:
                for rank, (idx, dist) in enumerate(topk_info, 1):
                    loc = self.gd.locations[idx]
                    print(
                        f"  #{rank} idx={idx:<6} dist={dist:.4f}° "
                        f"name='{loc['name']}' shape_id='{loc['shape_id']}' "
                        f"admin1='{loc.get('admin1','')}' admin2='{loc.get('admin2','')}'"
                    )

            # ---- Step 2: use the official geo_contains method ----
            idx_list = [info[0] for info in topk_info]
            final = self.gd.geo_contains((lon, lat), idx_list)

            if verbose:
                if final.result is not None:
                    print(f" RESULT: {final.result.name} ({final.result.lat}, {final.result.lon})")
                else:
                    print("  No containing shape found. Result is None.")

            results.append(final)

        return results

    # ------------------------------------------------------------------
    # SHAPE INSPECTOR
    # ------------------------------------------------------------------
    def inspect_shape(self, shape_id: str) -> Optional[object]:
        """
        Load a shape from the SQLite database and print its properties.
        Returns the Shapely geometry object, or None if not found.
        """
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT name, shape_id, coordinates FROM location_data WHERE shape_id = ?",
                (shape_id,),
            )
            row = cur.fetchone()
        except sqlite3.Error as e:
            print(f" DB error: {e}")
            row = None
        finally:
            conn.close()

        if row is None:
            print(f" Shape with id '{shape_id}' not found in database.")
            return None

        name, sid, blob = row
        geom = wkb.loads(blob)
        # WKB may return a numpy array of geometries – we take the first
        if isinstance(geom, np.ndarray):
            geom = geom[0]

        print(f"\nShape ID   : {sid}")
        print(f"Name       : {name}")
        print(f"Type       : {type(geom).__name__}")
        print(f"Bounds     : {geom.bounds}")
        print(f"Area (°²)  : {geom.area:.6f}")
        return geom

    # ------------------------------------------------------------------
    # PERFORMANCE BENCHMARKING
    # ------------------------------------------------------------------
    def benchmark(
        self,
        n: int = 1000,
        coords: Optional[List[Tuple[float, float]]] = None,
    ) -> float:
        """
        Time `n` reverse geocoding queries (random points if none given).
        Prints elapsed time and queries per second. Returns total seconds.
        """
        if coords is None:
            import random
            coords = [(random.uniform(-180, 180), random.uniform(-90, 90)) for _ in range(n)]
        else:
            n = len(coords)

        print(f"\nBenchmarking {n} queries...")
        start = time.perf_counter()
        # consume the iterator to force all work
        _ = list(self.gd.search(coords))
        elapsed = time.perf_counter() - start
        qps = n / elapsed if elapsed > 0 else float("inf")
        print(f"  Elapsed: {elapsed:.4f}s  |  {qps:.1f} queries/sec")
        return elapsed


# ------------------------------------------------------------------
# ALL‑IN‑ONE DIAGNOSTIC RUNNER
# ------------------------------------------------------------------
def quick_diagnose(mode: int = 1) -> None:
    """Run a full health check on the GeoDude library and print a report."""
    print("=" * 60)
    print("   GeoDude Library Diagnostics")
    print("=" * 60)

    debugger = GeoDudeDebugger(mode)
    debugger.data_summary()

    print("\n--- CSV Schema ---")
    debugger.csv_schema_ok()

    print("\n--- Database Integrity ---")
    debugger.check_db_integrity()

    print("\n--- Quick Query Test ---")
    # Example coordinates – replace with a location known to be inside your dataset.
    test_point = (-73.9857, 40.7484)  # NYC area (lon, lat)
    debugger.debug_query([test_point])

    print("\n--- Performance Test (100 random queries) ---")
    debugger.benchmark(100)

    print("\nAll checks completed.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="GeoDude library debugger")
    parser.add_argument(
        "--mode",
        type=int,
        default=1,
        choices=[1, 2],
        help="1 = single‑process KD‑Tree, 2 = multi‑process (default: 1)",
    )
    parser.add_argument(
        "--benchmark",
        type=int,
        default=0,
        help="Run a benchmark with N random queries instead of the full diag.",
    )
    args = parser.parse_args()

    if args.benchmark > 0:
        debugger = GeoDudeDebugger(args.mode)
        debugger.benchmark(args.benchmark)
    else:
        quick_diagnose(args.mode)