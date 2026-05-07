# diagnostic.py
import os, sys, subprocess, re, sqlite3, requests, platform
from pathlib import Path

print("=== Wi-Fi Database Build Diagnostic ===")
print(f"Python: {sys.version}")
print(f"Platform: {platform.system()}")

# 1. Wi-Fi scan test
print("\n[1] Testing Wi-Fi scan...")
try:
    if platform.system() == "Windows":
        out = subprocess.check_output(['netsh', 'wlan', 'show', 'networks', 'mode=bssid'], text=True)
        matches = re.findall(r'BSSID\s+\d+\s+:\s+(([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})', out)
        bssids = [m[0] for m in matches]
        print(f"Found {len(bssids)} BSSIDs")
        if bssids:
            print(f"First 3: {bssids[:3]}")
    else:
        print("Non-Windows – please run on Windows")
except Exception as e:
    print(f"Scan error: {e}")

# 2. IP location test
print("\n[2] Testing IP location...")
try:
    resp = requests.get('http://ip-api.com/json/', timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        if data.get('status') == 'success':
            lat, lon = data['lat'], data['lon']
            print(f"IP location: {lat:.6f}, {lon:.6f}")
        else:
            print("IP API returned failure")
    else:
        print(f"HTTP {resp.status_code}")
except Exception as e:
    print(f"IP error: {e}")

# 3. Database creation test
print("\n[3] Testing database creation...")
db_path = Path(__file__).parent / "wifi_location_test.db"
try:
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE access_points (bssid TEXT PRIMARY KEY, lat REAL, lon REAL, timestamp INTEGER)''')
    conn.commit()
    conn.close()
    print(f"Database created: {db_path}")
    db_path.unlink()
except Exception as e:
    print(f"Database error: {e}")

print("\n=== DIAGNOSTIC COMPLETE ===")