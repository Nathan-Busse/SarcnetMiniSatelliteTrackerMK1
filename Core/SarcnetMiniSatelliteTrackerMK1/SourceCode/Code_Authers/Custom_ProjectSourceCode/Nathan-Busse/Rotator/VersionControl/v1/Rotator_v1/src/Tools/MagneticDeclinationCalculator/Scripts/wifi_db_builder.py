#!/usr/bin/env python3
"""
Wi-Fi Location Database Builder (Automatic, using IP)
Scans visible Wi-Fi networks, fetches your approximate IP-based location,
and builds a SQLite database for offline Wi‑Fi positioning.
No manual coordinate input required.
"""

import os
import sys
import platform
import sqlite3
import subprocess
import re
import time
import ctypes
import tempfile
import requests
from pathlib import Path

# ----------------------------------------------------------------------
# Debug configuration
# ----------------------------------------------------------------------
DEBUG = True

def debug_print(msg):
    if DEBUG:
        print(f"[DEBUG] {msg}")

# ----------------------------------------------------------------------
# Admin/root check
# ----------------------------------------------------------------------
def is_admin():
    if platform.system() == "Windows":
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except:
            return False
    else:
        return os.geteuid() == 0

def request_admin():
    try:
        import customtkinter as ctk
        ctk.set_appearance_mode("Dark")

        def run_as_admin():
            debug_print("User chose to reload as admin/root")
            if platform.system() == "Windows":
                # Create a batch file to set working directory properly
                batch_content = f"""
@echo off
cd /d "{os.path.dirname(__file__)}"
"{sys.executable}" "{__file__}"
pause
"""
                with tempfile.NamedTemporaryFile(mode='w', suffix='.bat', delete=False) as f:
                    f.write(batch_content)
                    batch_file = f.name
                ctypes.windll.shell32.ShellExecuteW(None, "runas", batch_file, None, None, 1)
                root.destroy()
                sys.exit(0)
            else:
                subprocess.run(['sudo', sys.executable, __file__])
                root.destroy()
                sys.exit(0)

        def run_as_current():
            root.destroy()

        root = ctk.CTk()
        root.title("Admin Required")
        root.geometry("500x200")
        root.attributes("-topmost", True)

        label = ctk.CTkLabel(root, text="This script needs admin/root privileges to scan Wi-Fi networks.\n\nPlease run as Administrator (Windows) or with sudo (Linux/macOS).",
                             font=("Arial", 14))
        label.pack(pady=30)

        btn_frame = ctk.CTkFrame(root)
        btn_frame.pack(pady=10)

        ctk.CTkButton(btn_frame, text="Reload as Admin", command=run_as_admin,
                      fg_color="#2a7a3a", width=150).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="Continue Without Admin", command=run_as_current,
                      fg_color="#555555", width=150).pack(side="left", padx=10)

        root.mainloop()
    except ImportError:
        print("CustomTkinter not installed. Please run this script as admin/root manually.")
        sys.exit(1)

# ----------------------------------------------------------------------
# IP location fetch
# ----------------------------------------------------------------------
def get_ip_location():
    print("🌐 Fetching approximate location via IP (ip-api.com)...")
    try:
        resp = requests.get('http://ip-api.com/json/', timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('status') == 'success':
                lat = data['lat']
                lon = data['lon']
                city = data.get('city', 'Unknown')
                country = data.get('country', 'Unknown')
                print(f"📌 Location found: {city}, {country} ({lat:.4f}, {lon:.4f})")
                return lat, lon
            else:
                print("❌ IP geolocation failed: API returned unsuccessful status")
        else:
            print(f"❌ IP geolocation failed (HTTP {resp.status_code})")
    except Exception as e:
        print(f"❌ Error fetching IP location: {e}")
    return None, None

# ----------------------------------------------------------------------
# Wi‑Fi Scanner (cross‑platform)
# ----------------------------------------------------------------------
class WiFiScanner:
    def __init__(self):
        self.bssids = []
        self.platform = platform.system()

    def scan(self):
        bssids = []
        try:
            if self.platform == "Windows":
                try:
                    output = subprocess.check_output(['netsh', 'wlan', 'show', 'networks', 'mode=bssid'], text=True)
                    matches = re.findall(r'BSSID\s+\d+\s+:\s+(([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})', output)
                    bssids = [match[0] for match in matches]
                except:
                    output = subprocess.check_output(['netsh', 'wlan', 'show', 'networks', 'mode=bssid', 'format=list'], text=True)
                    matches = re.findall(r'BSSID\s+\d+\s+:\s+(([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})', output)
                    bssids = [match[0] for match in matches]
            elif self.platform == "Linux":
                try:
                    output = subprocess.check_output(['sudo', 'iwlist', 'scan'], text=True)
                    matches = re.findall(r'Address: (([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})', output)
                    bssids = [match[0] for match in matches]
                except:
                    output = subprocess.check_output(['iwlist', 'scan'], text=True)
                    matches = re.findall(r'Address: (([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})', output)
                    bssids = [match[0] for match in matches]
            elif self.platform == "Darwin":
                try:
                    output = subprocess.check_output(['airport', '-s'], text=True)
                    matches = re.findall(r'(([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})', output)
                    bssids = [match[0] for match in matches]
                except:
                    output = subprocess.check_output(['/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport', '-s'], text=True)
                    matches = re.findall(r'(([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})', output)
                    bssids = [match[0] for match in matches]
        except:
            pass
        return bssids

# ----------------------------------------------------------------------
# Build the database (using IP location)
# ----------------------------------------------------------------------
def build_database():
    print("\n📡 Creating Wi‑Fi location database (fully offline)...")

    # 1. Get location via IP
    lat, lon = get_ip_location()
    if lat is None or lon is None:
        print("❌ Failed to get IP location. Exiting.")
        return

    # 2. Scan Wi‑Fi networks
    scanner = WiFiScanner()
    print("\n📶 Scanning for visible Wi‑Fi networks...")
    bssids = scanner.scan()
    print(f"✅ Found {len(bssids)} access points")

    if not bssids:
        print("⚠️ No Wi‑Fi networks found.")
        print("Possible reasons:")
        print("  - Not running as Administrator (Windows)")
        print("  - Wi‑Fi adapter is disabled or not supported")
        print("  - No networks in range")
        return

    # 3. Show sample BSSIDs
    if bssids:
        print("\n📶 First 5 BSSIDs found:")
        for i, bssid in enumerate(bssids[:5]):
            print(f"  {i+1}: {bssid}")
        if len(bssids) > 5:
            print(f"  ... and {len(bssids) - 5} more")

    # 4. Create/overwrite the database
    print("\n💾 Saving database...")
    if WIFI_DB_PATH.exists():
        WIFI_DB_PATH.unlink()

    conn = sqlite3.connect(str(WIFI_DB_PATH))
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS access_points (
            bssid TEXT PRIMARY KEY,
            lat REAL,
            lon REAL,
            timestamp INTEGER
        )
    ''')

    for bssid in bssids:
        cursor.execute('INSERT OR REPLACE INTO access_points VALUES (?, ?, ?, ?)',
                       (bssid, lat, lon, int(time.time())))

    conn.commit()
    conn.close()

    # 5. Verify
    conn = sqlite3.connect(str(WIFI_DB_PATH))
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM access_points')
    count = cursor.fetchone()[0]
    conn.close()

    print(f"\n✅ Database created at: {WIFI_DB_PATH}")
    print(f"✅ Total access points saved: {count}")

    if WIFI_DB_PATH.exists():
        size = WIFI_DB_PATH.stat().st_size
        print(f"📁 File size: {size} bytes ({size/1024:.2f} KB)")

if __name__ == "__main__":
    WIFI_DB_PATH = Path(__file__).parent / "wifi_location.db"

    if not is_admin():
        print("❌ Not running with admin/root privileges.")
        request_admin()
    else:
        print("✅ Running with admin/root privileges.")
        build_database()