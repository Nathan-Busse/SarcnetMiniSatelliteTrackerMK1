#!/usr/bin/env python3
"""Helper to ensure the database exists and return a Geodude instance."""

from importlib.resources import files
from geodude import create_db

def fetch_db():
    """Return a Geodude instance, building the database if necessary."""
    data_dir = files("geodude.data")
    if not (data_dir / "data.db").exists() or not (data_dir / "geo-boundaries.csv").exists():
        print("GeoDude data files missing. Running installer…")
        create_db()
        print("Installer finished.")