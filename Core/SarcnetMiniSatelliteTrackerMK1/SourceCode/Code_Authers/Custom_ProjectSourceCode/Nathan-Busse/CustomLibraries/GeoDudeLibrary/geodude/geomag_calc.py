#!/usr/bin/env python3
"""
WMM2025 geomagnetic calculator – part of the GeoDude library.

Implements the World Magnetic Model (default WMM2025, valid 2025‑2029).
Automatically downloads updated coefficients when they become available.
"""

import math
import numpy as np
from pathlib import Path
from datetime import datetime
from importlib.resources import files
from typing import NamedTuple, Optional, Union

# ---------------------------------------------------------------------------
# Auto‑updater helper
# ---------------------------------------------------------------------------
from .wmm_updater import ensure_wmm_coefficients

# ---------------------------------------------------------------------------
# WGS‑84 ellipsoid parameters used for coordinate conversion
# ---------------------------------------------------------------------------
WGS84_A = 6378.137           # equatorial radius (km)
WGS84_B = 6356.7523142       # polar radius (km)
WGS84_A2 = WGS84_A**2
WGS84_B2 = WGS84_B**2
WGS84_E2 = (WGS84_A2 - WGS84_B2) / WGS84_A2   # squared eccentricity

# ---------------------------------------------------------------------------
# Magnetic field result container
# ---------------------------------------------------------------------------
class MagneticField(NamedTuple):
    """Result of a WMM computation."""
    declination: float       # degrees, positive east
    inclination: float       # degrees, positive down
    total_intensity: float   # nT
    horizontal_intensity: float  # nT
    north: float             # X component (nT, +ve north)
    east: float              # Y component (nT, +ve east)
    down: float              # Z component (nT, +ve down)
    declination_error: float # approximate ±error (deg)


# ---------------------------------------------------------------------------
# Coefficient loader – now uses self‑updating file
# ---------------------------------------------------------------------------
class _WMCModel:
    """Loads and stores WMM Gauss coefficients (internal singleton)."""
    def __init__(self, coeff_path: Optional[Path] = None):
        if coeff_path is None:
            coeff_path = ensure_wmm_coefficients()   # <-- auto‑update
        self.epoch, self.model_name, self.release = self._load(coeff_path)
        self.max_degree = 12

    def _load(self, path: Path):
        with open(path, 'r') as fh:
            lines = fh.readlines()

        # Header:  epoch   modelname   releasedate
        parts = lines[0].split()
        epoch = float(parts[0])
        model = parts[1] if len(parts) > 1 else ""
        release = parts[2] if len(parts) > 2 else ""

        # Initialise arrays for degree 12
        N = self.max_degree
        self.g = {}
        self.h = {}
        self.g_dot = {}
        self.h_dot = {}
        for n in range(1, N + 1):
            self.g[n] = {}
            self.h[n] = {}
            self.g_dot[n] = {}
            self.h_dot[n] = {}

        # Parse the coefficient block
        for line in lines[1:]:
            line = line.rstrip()
            if not line or line.startswith("999"):
                break
            n = int(line[0:3].strip())
            m = int(line[3:6].strip())
            gnm = float(line[6:16].strip())
            hnm = float(line[16:26].strip())
            g_dot_nm = float(line[26:37].strip())
            h_dot_nm = float(line[37:48].strip())

            self.g[n][m] = gnm
            self.h[n][m] = hnm
            self.g_dot[n][m] = g_dot_nm
            self.h_dot[n][m] = h_dot_nm

        return epoch, model, release


# ---------------------------------------------------------------------------
# Helper: decimal year from datetime
# ---------------------------------------------------------------------------
def _decimal_year(year, month, day):
    days_in_year = 366 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 365
    month_days = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if days_in_year == 366:
        month_days[2] = 29
    doy = sum(month_days[:month]) + day
    return year + (doy - 1) / days_in_year


# ---------------------------------------------------------------------------
# Geodetic → Spherical coordinate conversion
# ---------------------------------------------------------------------------
def _geodetic_to_spherical(lat_deg, lon_deg, alt_km):
    lat_rad = math.radians(lat_deg)
    lon_rad = math.radians(lon_deg)
    cos_lat = math.cos(lat_rad)
    sin_lat = math.sin(lat_rad)
    rho = WGS84_A / math.sqrt(1.0 - WGS84_E2 * sin_lat * sin_lat)
    x = (rho + alt_km) * cos_lat * math.cos(lon_rad)
    y = (rho + alt_km) * cos_lat * math.sin(lon_rad)
    z = (rho * (1 - WGS84_E2) + alt_km) * sin_lat
    r = math.sqrt(x*x + y*y + z*z)
    theta = math.acos(z / r) if r > 0 else 0.0
    phi = lon_rad
    return r, theta, phi, sin_lat, cos_lat


# ---------------------------------------------------------------------------
# Schmidt semi‑normalised Legendre functions (recursion)
# ---------------------------------------------------------------------------
def _compute_legendre(theta, max_n):
    cos_theta = math.cos(theta)
    sin_theta = math.sin(theta)
    P = {n: {} for n in range(1, max_n+1)}
    dP = {n: {} for n in range(1, max_n+1)}

    # Initial values
    P[1][0] = cos_theta
    P[1][1] = sin_theta
    dP[1][0] = -sin_theta
    dP[1][1] = cos_theta

    # Schmidt normalisation factors
    s = {n: {m: (math.sqrt(2) if m > 0 else 1.0) * math.sqrt(math.factorial(n-m)/math.factorial(n+m))
              for m in range(n+1)} for n in range(1, max_n+1)}

    for n in range(2, max_n+1):
        for m in range(0, n):
            if m <= n-2:
                P[n][m] = ((2*n-1)*cos_theta*P[n-1][m] - (n+m-1)*P[n-2][m]) / (n-m)
                dP[n][m] = ((2*n-1)*(cos_theta*dP[n-1][m] - sin_theta*P[n-1][m]) - (n+m-1)*dP[n-2][m]) / (n-m)
            else:
                P[n][m] = ((2*n-1)*cos_theta*P[n-1][m]) / (n-m)
                dP[n][m] = ((2*n-1)*(cos_theta*dP[n-1][m] - sin_theta*P[n-1][m])) / (n-m)
        # Diagonal
        P[n][n] = sin_theta * P[n-1][n-1]
        dP[n][n] = sin_theta * dP[n-1][n-1] + cos_theta * P[n-1][n-1]

    for n in range(1, max_n+1):
        for m in range(n+1):
            P[n][m] *= s[n][m]
            dP[n][m] *= s[n][m]

    return P, dP


# ---------------------------------------------------------------------------
# Model singleton
# ---------------------------------------------------------------------------
_model = None
def _get_model():
    global _model
    if _model is None:
        _model = _WMCModel()
    return _model


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def declination(lat, lon, alt_km=0.0, year=None, month=1, day=1):
    return magnetic_field(lat, lon, alt_km, year, month, day).declination


def magnetic_field(lat, lon, alt_km=0.0, year=None, month=1, day=1):
    model = _get_model()
    # Resolve decimal year
    if year is None:
        now = datetime.utcnow()
        t = _decimal_year(now.year, now.month, now.day)
    elif isinstance(year, float):
        t = year
    else:
        t = _decimal_year(year, month, day)

    r, theta, phi, sin_lat, cos_lat = _geodetic_to_spherical(lat, lon, alt_km)
    dt = t - model.epoch
    Nmax = model.max_degree
    P, dP = _compute_legendre(theta, Nmax)

    X = Y = Z = 0.0
    a_ratio = WGS84_A / r

    for n in range(1, Nmax+1):
        scale = a_ratio ** (n+2)
        for m in range(0, n+1):
            g_nm = model.g[n][m] + model.g_dot[n][m] * dt
            h_nm = model.h[n].get(m, 0) + model.h_dot[n].get(m, 0) * dt
            cos_m = math.cos(m * phi)
            sin_m = math.sin(m * phi)
            g_term = g_nm * cos_m + h_nm * sin_m
            h_term = g_nm * sin_m - h_nm * cos_m

            X += scale * g_term * dP[n][m]
            if m > 0:
                sin_theta = math.sin(theta)
                if sin_theta > 1e-10:
                    Y += scale * h_term * (m * P[n][m] / sin_theta)
            Z -= (n+1) * scale * g_term * P[n][m]

    # Rotate to geodetic frame
    psi = math.radians(lat) - (math.pi/2 - theta)
    sin_psi = math.sin(psi)
    cos_psi = math.cos(psi)
    X_geo = X * cos_psi - Z * sin_psi
    Z_geo = X * sin_psi + Z * cos_psi
    H = math.sqrt(X_geo**2 + Y**2)
    F = math.sqrt(H**2 + Z_geo**2)
    decl = math.degrees(math.atan2(Y, X_geo))
    incl = math.degrees(math.atan2(Z_geo, H))

    lat_abs = abs(lat) if lat is not None else 0
    if lat_abs < 55:
        decl_err = 0.5
    elif lat_abs < 70:
        decl_err = 1.0
    else:
        decl_err = 2.0

    return MagneticField(decl, incl, F, H, X_geo, Y, Z_geo, decl_err)


def batch_declination(lats, lons, alt_km=0.0, year=None):
    result = np.empty(len(lats), dtype=float)
    for i in range(len(lats)):
        result[i] = declination(lats[i], lons[i], alt_km, year)
    return result