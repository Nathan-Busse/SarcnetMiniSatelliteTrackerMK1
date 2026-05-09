#!/usr/bin/env python3
"""Helper to ensure the database exists and return a Geodude instance."""

from importlib.resources import files
from geodude.reverse_geocode import geodude as GeodudeClass

def fetch_db():
    """Return a Geodude (singleton) instance, building the database if necessary."""
    data_dir = files("geodude.data")
    if not (data_dir / "data.db").exists() or not (data_dir / "geo-boundaries.csv").exists():
        print("GeoDude data files missing. Running installer…")
        from geodude import create_db      # your installer that builds the data
        create_db()
        print("Installer finished.")
    return GeodudeClass()   # <-- the singleton that loads data.db & geo-boundaries.csv automatically