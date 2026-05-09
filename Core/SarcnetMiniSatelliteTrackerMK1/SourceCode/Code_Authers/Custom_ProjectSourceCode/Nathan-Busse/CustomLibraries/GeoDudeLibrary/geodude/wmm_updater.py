#!/usr/bin/env python3
"""
WMM coefficient file updater for GeoDude.
Automatically fetches the latest WMM.COF from NOAA if it is missing or expired.
"""

import os
import tempfile
import shutil
import urllib.request
from pathlib import Path
from datetime import datetime
from importlib.resources import files

# Official NOAA URL for the legacy‑format WMM coefficients (WMM2025 as of 2025)
NOAA_WMM_URL = (
    "https://www.ncei.noaa.gov/data/world-magnetic-model/access/wmm/WMM.COF"
)

# How many years after the epoch is the model considered “expired”?
# NOAA releases a new model every 5 years. We allow a 1‑year grace period.
MAX_AGE_YEARS = 6       # epoch year + MAX_AGE_YEARS < current year → update


def _get_epoch_from_file(path: Path) -> float | None:
    """Read the epoch year from the first line of a WMM.COF file."""
    try:
        with open(path, 'r') as f:
            first_line = f.readline()
            return float(first_line.split()[0])
    except Exception:
        return None


def _current_decimal_year() -> float:
    """Return current decimal year (approximate)."""
    now = datetime.utcnow()
    # quick day‑of‑year approximation
    days_in_year = 366 if (now.year % 4 == 0 and (now.year % 100 != 0 or now.year % 400 == 0)) else 365
    doy = now.timetuple().tm_yday
    return now.year + (doy - 1) / days_in_year


def ensure_wmm_coefficients(force: bool = False) -> Path:
    """
    Guarantee an up‑to‑date WMM.COF file is present in geodude/data/.
    
    Parameters
    ----------
    force : bool
        If True, download even if the current file appears valid.
    
    Returns
    -------
    Path to the coefficient file.
    """
    data_dir = files("geodude.data")          # resolves to geodude/data/
    target = data_dir / "WMM.COF"

    # Check if we need to update
    need_update = force
    if target.exists():
        epoch = _get_epoch_from_file(target)
        if epoch is None:
            need_update = True
        else:
            current_yr = _current_decimal_year()
            if current_yr > epoch + MAX_AGE_YEARS:
                need_update = True
    else:
        need_update = True

    if not need_update:
        return target

    print(f"Updating WMM coefficients (epoch {_get_epoch_from_file(target)})...")
    # Download to a temporary file, then replace atomically
    data_dir.mkdir(parents=True, exist_ok=True)

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".cof", prefix="wmm_")
    os.close(tmp_fd)
    tmp_path = Path(tmp_path)

    try:
        urllib.request.urlretrieve(NOAA_WMM_URL, tmp_path)
        # Validate the downloaded file (it must start with a 4‑digit year)
        with open(tmp_path, 'r') as f:
            first_line = f.readline()
            try:
                float(first_line.split()[0])
            except Exception:
                raise ValueError("Downloaded file does not look like a valid WMM.COF")

        # Atomic replacement
        shutil.move(str(tmp_path), str(target))
        print(f"Successfully updated to {target}")
    except Exception as e:
        if tmp_path.exists():
            tmp_path.unlink()
        raise RuntimeError(f"Failed to fetch or validate WMM coefficients: {e}") from e

    return target