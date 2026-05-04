#!/usr/bin/env python3

import os
import sys
import locale

os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"
try:
    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
except:
    pass

import builtins
original_open = builtins.open
def utf8_open(file, mode='r', buffering=-1, encoding=None, errors=None, newline=None, closefd=True, opener=None):
    if 'b' not in mode and encoding is None:
        encoding = 'utf-8'
    return original_open(file, mode, buffering, encoding, errors, newline, closefd, opener)
builtins.open = utf8_open

# ----------------------------------------------------------------------
# Regular imports
# ----------------------------------------------------------------------
import sys
import datetime
import customtkinter as ctk
import geocoder
import geomag
import requests
import platform
import tempfile
import shutil
import urllib.request
import threading
import queue
import ctypes
import time
from pathlib import Path

# ----------------------------------------------------------------------
# Optional GPS libraries – will not crash if missing
# ----------------------------------------------------------------------
try:
    import serial
    import serial.tools.list_ports
    import pynmea2
    GPS_AVAILABLE = True
except ImportError:
    GPS_AVAILABLE = False

# ----------------------------------------------------------------------
# Optional Wi‑Fi scanning – cross‑platform
# ----------------------------------------------------------------------
try:
    import subprocess
    import re
    import sqlite3
    WIFI_AVAILABLE = True
except ImportError:
    WIFI_AVAILABLE = False

# ----------------------------------------------------------------------
# Gazetteer import (optional – falls back to online if missing)
# ----------------------------------------------------------------------
try:
    from gazetteer import Gazetteer
    GAZETTEER_AVAILABLE = True
except ImportError:
    GAZETTEER_AVAILABLE = False
    print("python-gazetteer not installed. Will use online fallback.")

# ----------------------------------------------------------------------
# Constants & colour palette
# ----------------------------------------------------------------------
APP_TITLE = "Magnetic Declination Calculator"
DEFAULT_APPEARANCE = "Dark"
DEFAULT_THEME = "dark-blue"
NOMINAT_USER_AGENT = "MagneticDeclinationCalculator/1.0"

BASE_DIR = Path(__file__).parent
GAZETTEER_DB_PATH = BASE_DIR / "geonames.db"
GAZETTEER_DATA_URL = "https://github.com/SOORAJTS2001/gazetteer/raw/refs/heads/main/gazetteer/data/data.db"
WIFI_DB_PATH = BASE_DIR / "wifi_location.db"

COLORS = {
    "bg": "#1a1a1a",
    "card_bg": "#242424",
    "card_border": "#3a3a3a",
    "accent": "#2a7a3a",
    "accent_hover": "#1e5e2e",
    "secondary": "#8a2be2",
    "secondary_hover": "#6a1fa0",
    "gold": "#f0c040",
    "text_primary": "#ffffff",
    "text_secondary": "#b0b0b0",
    "danger": "#d32f2f",
    "danger_hover": "#b71c1c"
}

# ----------------------------------------------------------------------
# Tooltip helper
# ----------------------------------------------------------------------
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        widget.bind("<Enter>", self.show_tip)
        widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        if self.tip_window:
            return
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        self.tip_window = tw = ctk.CTkToplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = ctk.CTkLabel(tw, text=self.text, justify="left", padx=10, pady=8,
                             fg_color="#333333", text_color="white", corner_radius=8)
        label.pack()

    def hide_tip(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None

# ----------------------------------------------------------------------
# Admin/root check & relaunch
# ----------------------------------------------------------------------
def is_admin():
    """Check if the script is running with admin/root privileges."""
    if platform.system() == "Windows":
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except:
            return False
    else:
        return os.geteuid() == 0

def request_admin_and_restart():
    """Request admin/root privileges via GUI and restart the script."""
    try:
        import customtkinter as ctk
        ctk.set_appearance_mode("Dark")

        def run_as_admin():
            if platform.system() == "Windows":
                # Create a batch file to set working directory properly
                batch_content = f"""
@echo off
cd /d "{os.path.dirname(__file__)}"
"{sys.executable}" "{__file__}"
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

        def exit_app():
            root.destroy()
            sys.exit(0)

        root = ctk.CTk()
        root.title("Admin Required")
        root.geometry("500x200")
        root.attributes("-topmost", True)

        label = ctk.CTkLabel(root, text="This app needs admin/root privileges to scan Wi-Fi networks.\n\nPlease run as Administrator (Windows) or with sudo (Linux/macOS).",
                             font=("Arial", 14))
        label.pack(pady=30)

        btn_frame = ctk.CTkFrame(root)
        btn_frame.pack(pady=10)

        ctk.CTkButton(btn_frame, text="Reload as Admin", command=run_as_admin,
                      fg_color="#2a7a3a", width=150).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="Exit", command=exit_app,
                      fg_color="#555555", width=150).pack(side="left", padx=10)

        root.mainloop()
    except ImportError:
        print("CustomTkinter not installed. Please run this script as admin/root manually.")
        sys.exit(1)

# ----------------------------------------------------------------------
# Gazetteer Manager (handles download, loading, and fallback)
# ----------------------------------------------------------------------
class GazetteerManager:
    def __init__(self, parent_app):
        self.parent_app = parent_app
        self.db_path = GAZETTEER_DB_PATH
        self.gazetteer = None
        self.download_thread = None
        self.progress_window = None
        self.cancel_download = False

    def ensure_database(self):
        """Return Gazetteer instance if available, else None."""
        if self.db_path.exists():
            return self._load_gazetteer()
        if not GAZETTEER_AVAILABLE:
            self.parent_app._set_status("python-gazetteer not installed. Using online fallback.", "warning")
            return None
        choice = self._ask_download()
        if choice == "download":
            self._download_with_progress()
            return self._load_gazetteer()
        else:
            self.parent_app._set_status("Using online reverse geocoding (not offline).", "info")
            return None

    def _ask_download(self):
        dialog = ctk.CTkToplevel(self.parent_app)
        dialog.title("Gazetteer Database")
        dialog.geometry("500x280")
        dialog.attributes("-topmost", True)
        dialog.grab_set()
        dialog.configure(fg_color=COLORS["bg"])
        ctk.CTkLabel(dialog, text="Download Gazetteer Database?", font=("Arial", 18, "bold"),
                     text_color=COLORS["text_primary"]).pack(pady=(25,10))
        ctk.CTkLabel(dialog, text="Size: ~80 MB\nOffline reverse geocoding is strongly recommended.\n\nYou can skip and use online reverse geocoding (Nominatim).",
                     font=("Arial", 13), text_color=COLORS["text_secondary"]).pack(pady=10)
        result = ["skip"]
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=25)
        ctk.CTkButton(btn_frame, text="✅ Download Now",
                      command=lambda: [result.__setitem__(0, "download"), dialog.destroy()],
                      width=140, fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                      font=("Arial", 13)).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="⏩ Skip (Use Online)",
                      command=lambda: [result.__setitem__(0, "skip"), dialog.destroy()],
                      width=140, fg_color=COLORS["secondary"], hover_color=COLORS["secondary_hover"],
                      font=("Arial", 13)).pack(side="left", padx=10)
        self.parent_app.wait_window(dialog)
        return result[0]

    def _download_with_progress(self):
        self.progress_window = ctk.CTkToplevel(self.parent_app)
        self.progress_window.title("Downloading Gazetteer Database")
        self.progress_window.geometry("450x220")
        self.progress_window.attributes("-topmost", True)
        self.progress_window.grab_set()
        self.progress_window.configure(fg_color=COLORS["bg"])
        self.status_label = ctk.CTkLabel(self.progress_window, text="Initializing...",
                                         font=("Arial", 13), text_color=COLORS["text_secondary"])
        self.status_label.pack(pady=(25,10))
        self.progress_bar = ctk.CTkProgressBar(self.progress_window, width=350, progress_color=COLORS["accent"])
        self.progress_bar.pack(pady=5)
        self.progress_bar.set(0)
        self.percent_label = ctk.CTkLabel(self.progress_window, text="0%",
                                          font=("Arial", 11), text_color=COLORS["text_secondary"])
        self.percent_label.pack(pady=5)
        self.cancel_btn = ctk.CTkButton(self.progress_window, text="Cancel",
                                        command=self._cancel_download,
                                        fg_color=COLORS["danger"], hover_color=COLORS["danger_hover"],
                                        width=80, font=("Arial", 11))
        self.cancel_btn.pack(pady=10)
        self.cancel_download = False
        self.download_thread = threading.Thread(target=self._download_worker, daemon=True)
        self.download_thread.start()
        self.parent_app.wait_window(self.progress_window)

    def _download_worker(self):
        temp = None
        try:
            self.parent_app.after(0, lambda: self.status_label.configure(text="Downloading database... (80 MB)"))
            with tempfile.NamedTemporaryFile(delete=False) as f:
                temp = Path(f.name)
            def report(count, block, total):
                if self.cancel_download:
                    raise Exception("Cancelled")
                percent = count * block * 100 / total
                self.parent_app.after(0, lambda: self.progress_bar.set(percent / 100))
                self.parent_app.after(0, lambda: self.percent_label.configure(text=f"{percent:.0f}%"))
            urllib.request.urlretrieve(GAZETTEER_DATA_URL, str(temp), report)
            self.db_path.parent.mkdir(exist_ok=True)
            shutil.move(str(temp), str(self.db_path))
            self.parent_app.after(0, lambda: self.status_label.configure(text="✅ Complete!", text_color=COLORS["accent"]))
            self.parent_app.after(0, lambda: self.progress_bar.set(1))
            self.parent_app.after(0, lambda: self.percent_label.configure(text="100%"))
            self.parent_app.after(0, lambda: self.cancel_btn.configure(state="disabled"))
            self.parent_app.after(1500, self.progress_window.destroy)
        except Exception as e:
            if temp and temp.exists(): temp.unlink()
            if str(e) == "Cancelled":
                self.parent_app.after(0, lambda: self.status_label.configure(text="⛔ Cancelled", text_color=COLORS["text_secondary"]))
                self.parent_app.after(2000, self.progress_window.destroy)
            else:
                self.parent_app.after(0, lambda: self.status_label.configure(text=f"❌ Error: {str(e)}", text_color=COLORS["danger"]))
                self.parent_app.after(3000, self.progress_window.destroy)

    def _cancel_download(self):
        self.cancel_download = True

    def _load_gazetteer(self):
        if not self.db_path.exists():
            return None
        try:
            self.gazetteer = Gazetteer()
            return self.gazetteer
        except Exception as e:
            print(f"Failed to load Gazetteer: {e}")
            return None

# ----------------------------------------------------------------------
# Wi‑Fi Scanner (cross‑platform)
# ----------------------------------------------------------------------
class WiFiScanner:
    def __init__(self):
        self.bssids = []
        self.platform = platform.system()

    def scan(self):
        """Scan visible Wi‑Fi access points. Returns list of BSSIDs."""
        self.bssids = []
        if not WIFI_AVAILABLE:
            return []
        try:
            if self.platform == "Linux":
                # Linux: requires root/sudo
                output = subprocess.check_output(['sudo', 'iwlist', 'scan'], text=True)
                matches = re.findall(r'Address: (([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})', output)
                self.bssids = [match[0] for match in matches]
            elif self.platform == "Windows":
                # Windows: requires admin
                output = subprocess.check_output(['netsh', 'wlan', 'show', 'networks', 'mode=bssid'], text=True)
                matches = re.findall(r'BSSID\s+:\s+(([0-9A-Fa-f]{2}-){5}[0-9A-Fa-f]{2})', output)
                self.bssids = [match.replace('-', ':') for match in matches]
            elif self.platform == "Darwin":
                # macOS
                output = subprocess.check_output(['airport', '-s'], text=True)
                matches = re.findall(r'(([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})', output)
                self.bssids = [match[0] for match in matches]
        except:
            pass
        return self.bssids

    def get_location(self, db_path):
        """Match scanned BSSIDs against a local database and return centroid."""
        if not self.bssids:
            return None
        if not db_path.exists():
            return None
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            locations = []
            for bssid in self.bssids:
                cursor.execute('SELECT lat, lon FROM access_points WHERE bssid = ?', (bssid,))
                row = cursor.fetchone()
                if row:
                    locations.append((row[0], row[1]))
            conn.close()
            if not locations:
                return None
            # Centroid
            avg_lat = sum(lat for lat, lon in locations) / len(locations)
            avg_lon = sum(lon for lat, lon in locations) / len(locations)
            return avg_lat, avg_lon
        except:
            return None

# ----------------------------------------------------------------------
# Wi‑Fi Database Builder (self‑calibrating)
# ----------------------------------------------------------------------
class WiFiDatabaseBuilder:
    def __init__(self, parent_app):
        self.parent_app = parent_app
        self.db_path = WIFI_DB_PATH

    def build_or_update_database(self):
        """Build or update Wi‑Fi database using IP location + Wi‑Fi scanning."""
        # 1. Get IP location
        self.parent_app._set_status("DEBUG: Fetching IP location...", "info")
        try:
            resp = requests.get('http://ip-api.com/json/', timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('status') == 'success':
                    lat = data['lat']
                    lon = data['lon']
                    city = data.get('city', 'Unknown')
                    country = data.get('country', 'Unknown')
                    self.parent_app._set_status(f"DEBUG: IP location found: {city}, {country} ({lat:.4f}, {lon:.4f})", "info")
                else:
                    self.parent_app._set_status("DEBUG: IP geolocation failed - API status not success", "error")
                    return False
            else:
                self.parent_app._set_status(f"DEBUG: IP geolocation failed - HTTP {resp.status_code}", "error")
                return False
        except Exception as e:
            self.parent_app._set_status(f"DEBUG: Error fetching IP location: {e}", "error")
            return False

        # 2. Scan Wi‑Fi networks
        self.parent_app._set_status("DEBUG: Scanning for Wi‑Fi networks...", "info")
        scanner = WiFiScanner()
        bssids = scanner.scan()
        self.parent_app._set_status(f"DEBUG: Found {len(bssids)} access points", "info")

        if not bssids:
            self.parent_app._set_status("DEBUG: No Wi‑Fi networks found", "error")
            return False

        # 3. Build/update database
        self.parent_app._set_status("DEBUG: Creating/updating database...", "info")
        try:
            if self.db_path.exists():
                self.parent_app._set_status("DEBUG: Database already exists. Updating...", "info")
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                # Create table if it doesn't exist
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS access_points (
                        bssid TEXT PRIMARY KEY,
                        lat REAL,
                        lon REAL,
                        timestamp INTEGER
                    )
                ''')
                # Add new BSSIDs
                for bssid in bssids:
                    try:
                        cursor.execute('INSERT OR REPLACE INTO access_points VALUES (?, ?, ?, ?)',
                                      (bssid, lat, lon, int(time.time())))
                    except Exception as e:
                        self.parent_app._set_status(f"DEBUG: Error inserting BSSID {bssid}: {e}", "error")
                        return False
                conn.commit()
                conn.close()
                self.parent_app._set_status("DEBUG: Database updated successfully", "success")
            else:
                self.parent_app._set_status("DEBUG: Creating new database...", "info")
                conn = sqlite3.connect(str(self.db_path))
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
                    try:
                        cursor.execute('INSERT OR REPLACE INTO access_points VALUES (?, ?, ?, ?)',
                                      (bssid, lat, lon, int(time.time())))
                    except Exception as e:
                        self.parent_app._set_status(f"DEBUG: Error inserting BSSID {bssid}: {e}", "error")
                        return False
                conn.commit()
                conn.close()
                self.parent_app._set_status("DEBUG: New database created successfully", "success")
            return True
        except Exception as e:
            self.parent_app._set_status(f"DEBUG: Error creating/updating database: {e}", "error")
            return False

# ----------------------------------------------------------------------
# GPS Reader (cross‑platform via pyserial)
# ----------------------------------------------------------------------
class GPSReader:
    def __init__(self, parent_app):
        self.parent_app = parent_app
        self.serial_port = None
        self.reading = False
        self.latitude = None
        self.longitude = None
        self.fix_quality = 0

    def find_gps_port(self):
        """Automatically find the GPS COM port."""
        if not GPS_AVAILABLE:
            return None
        try:
            ports = list(serial.tools.list_ports.comports())
            for port in ports:
                try:
                    ser = serial.Serial(port.device, 9600, timeout=1)
                    for _ in range(10):
                        line = ser.readline().decode('ascii', errors='replace').strip()
                        if line.startswith('$GPGGA') or line.startswith('$GNGGA'):
                            ser.close()
                            return port.device
                    ser.close()
                except:
                    continue
        except:
            pass
        return None

    def start_reading(self, callback):
        """Start reading GPS data in a background thread."""
        if not GPS_AVAILABLE:
            self.parent_app._set_status("GPS libraries not installed. Run: pip install pyserial pynmea2", "error")
            return False

        port = self.find_gps_port()
        if not port:
            self.parent_app._set_status("No GPS device found.", "error")
            return False

        try:
            self.serial_port = serial.Serial(port, 9600, timeout=2)
            self.reading = True
            thread = threading.Thread(target=self._read_loop, args=(callback,), daemon=True)
            thread.start()
            self.parent_app._set_status(f"GPS connected on {port}", "success")
            return True
        except Exception as e:
            self.parent_app._set_status(f"GPS error: {str(e)}", "error")
            return False

    def _read_loop(self, callback):
        while self.reading:
            try:
                line = self.serial_port.readline().decode('ascii', errors='replace').strip()
                if line.startswith('$GPGGA') or line.startswith('$GNGGA'):
                    msg = pynmea2.parse(line)
                    if msg.latitude and msg.longitude:
                        self.latitude = msg.latitude
                        self.longitude = msg.longitude
                        self.fix_quality = msg.gps_qual
                        lat = float(self.latitude)
                        lon = float(self.longitude)
                        callback(lat, lon, self.fix_quality)
            except (pynmea2.ParseError, UnicodeDecodeError, ValueError, TypeError):
                continue
            except serial.SerialException:
                break

    def stop_reading(self):
        self.reading = False
        if self.serial_port:
            try:
                self.serial_port.close()
            except:
                pass

# ----------------------------------------------------------------------
# Main Application
# ----------------------------------------------------------------------
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("800x650")
        self.configure(fg_color=COLORS["bg"])
        ctk.set_appearance_mode(DEFAULT_APPEARANCE)
        ctk.set_default_color_theme(DEFAULT_THEME)
        self._maximize_window()
        self.bind("<F11>", self._toggle_fullscreen)
        self.bind("<Configure>", self._on_configure)
        self.latitude = None
        self.longitude = None
        self.is_fullscreen = False

        # Check admin and restart if needed
        if not is_admin():
            request_admin_and_restart()

        self.gazetteer_manager = GazetteerManager(self)
        self.gazetteer = None
        self.use_gazetteer = False

        self.wifi_scanner = WiFiScanner()
        self.wifi_builder = WiFiDatabaseBuilder(self)
        self.gps_reader = GPSReader(self)

        self._create_widgets()
        self.after(100, self._initialize_gazetteer)

    def _maximize_window(self):
        s = platform.system()
        if s == "Windows":
            self.state('zoomed')
        elif s == "Darwin":
            self.attributes('-zoomed', True)
        else:
            self.state('zoomed')

    def _on_configure(self, e):
        if not self.is_fullscreen and e.widget == self:
            self.after(100, self._maximize_window)

    def _toggle_fullscreen(self, e=None):
        if self.is_fullscreen:
            self.attributes('-fullscreen', False)
            self.is_fullscreen = False
            self._maximize_window()
        else:
            self.attributes('-fullscreen', True)
            self.is_fullscreen = True

    def _create_widgets(self):
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=30, pady=30)

        # Header
        header_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0,20))
        title = ctk.CTkLabel(header_frame, text="🧭 Magnetic Declination Calculator",
                             font=("Arial", 24, "bold"), text_color=COLORS["text_primary"])
        title.pack(side="left")
        ToolTip(title, "Calculate magnetic declination for any location on Earth")
        self.btn_help = ctk.CTkButton(header_frame, text="❓ Help", command=self._show_help,
                                      width=80, fg_color="transparent", hover_color=COLORS["card_bg"],
                                      text_color=COLORS["text_secondary"], font=("Arial", 12))
        self.btn_help.pack(side="right")

        # Card: Location Input
        loc_card = ctk.CTkFrame(main_frame, fg_color=COLORS["card_bg"], corner_radius=12,
                                border_width=1, border_color=COLORS["card_border"])
        loc_card.pack(fill="x", pady=(0,15))
        ctk.CTkLabel(loc_card, text="📍 Location Input", font=("Arial", 14, "bold"),
                     text_color=COLORS["text_primary"]).pack(anchor="w", padx=20, pady=(15,5))

        addr_frame = ctk.CTkFrame(loc_card, fg_color="transparent")
        addr_frame.pack(fill="x", padx=20, pady=5)
        self.entry_address = ctk.CTkEntry(addr_frame, placeholder_text="Street address, city, country",
                                          width=400, font=("Arial", 12))
        self.entry_address.pack(side="left", padx=(0,10))
        ToolTip(self.entry_address, "Type a full address and click 'Get from Address'")
        self.btn_address = ctk.CTkButton(addr_frame, text="📍 Get from Address",
                                         command=self._on_get_from_address,
                                         width=150, fg_color=COLORS["accent"],
                                         hover_color=COLORS["accent_hover"],
                                         font=("Arial", 12))
        self.btn_address.pack(side="left")
        ToolTip(self.btn_address, "Forward geocode the address (online)")

        ctk.CTkFrame(loc_card, height=1, fg_color=COLORS["card_border"]).pack(fill="x", padx=20, pady=10)

        method_frame = ctk.CTkFrame(loc_card, fg_color="transparent")
        method_frame.pack(fill="x", padx=20, pady=5)

        # Main button: Locate & Calculate (single press)
        self.btn_locate = ctk.CTkButton(method_frame, text="📍 Locate & Calculate Declination",
                                        command=self._on_locate_and_calculate,
                                        width=400, fg_color=COLORS["accent"],
                                        hover_color=COLORS["accent_hover"],
                                        font=("Arial", 14, "bold"))
        self.btn_locate.pack(side="left", padx=(0,10))
        ToolTip(self.btn_locate, "One‑press: get location (IP → Wi‑Fi if available) and calculate declination")

        # Manual entry
        ctk.CTkLabel(method_frame, text="Manual:", font=("Arial", 12),
                     text_color=COLORS["text_secondary"]).pack(side="left", padx=(10,5))
        self.entry_lat = ctk.CTkEntry(method_frame, placeholder_text="Lat", width=100,
                                      font=("Arial", 12))
        self.entry_lat.pack(side="left", padx=2)
        ToolTip(self.entry_lat, "Latitude between -90 and 90")
        self.entry_lon = ctk.CTkEntry(method_frame, placeholder_text="Lon", width=100,
                                      font=("Arial", 12))
        self.entry_lon.pack(side="left", padx=2)
        ToolTip(self.entry_lon, "Longitude between -180 and 180")
        self.btn_manual = ctk.CTkButton(method_frame, text="Set Manual",
                                        command=self._on_set_manual,
                                        width=100, fg_color="transparent",
                                        border_width=1, border_color=COLORS["secondary"],
                                        text_color=COLORS["secondary"],
                                        hover_color=COLORS["secondary_hover"],
                                        font=("Arial", 12))
        self.btn_manual.pack(side="left", padx=5)
        ToolTip(self.btn_manual, "Set manual coordinates and validate offline via Gazetteer")

        # Card: Coordinates & Precision
        coord_card = ctk.CTkFrame(main_frame, fg_color=COLORS["card_bg"], corner_radius=12,
                                  border_width=1, border_color=COLORS["card_border"])
        coord_card.pack(fill="x", pady=(0,15))
        ctk.CTkLabel(coord_card, text="📍 Current Coordinates", font=("Arial", 14, "bold"),
                     text_color=COLORS["text_primary"]).pack(anchor="w", padx=20, pady=(15,5))
        disp_frame = ctk.CTkFrame(coord_card, fg_color="transparent")
        disp_frame.pack(fill="x", padx=20, pady=5)
        self.lbl_coords = ctk.CTkLabel(disp_frame, text="Coordinates: Not set",
                                       font=("Arial", 13), text_color=COLORS["text_secondary"])
        self.lbl_coords.pack(side="left")
        self.lbl_precision = ctk.CTkLabel(disp_frame, text="Precision: Not set",
                                          font=("Arial", 12), text_color="#888888")
        self.lbl_precision.pack(side="right")

        self.lbl_gazetteer = ctk.CTkLabel(coord_card, text="📡 Offline Gazetteer: ⏳ Initializing...",
                                          font=("Arial", 11), text_color="#888888")
        self.lbl_gazetteer.pack(anchor="w", padx=20, pady=(0,15))

        # Card: Result
        result_card = ctk.CTkFrame(main_frame, fg_color=COLORS["card_bg"], corner_radius=12,
                                   border_width=1, border_color=COLORS["card_border"])
        result_card.pack(fill="x", pady=(0,15))
        ctk.CTkLabel(result_card, text="🧮 Declination Result", font=("Arial", 14, "bold"),
                     text_color=COLORS["text_primary"]).pack(anchor="w", padx=20, pady=(15,5))
        self.lbl_result = ctk.CTkEntry(result_card, font=("Arial", 18, "bold"),
                                       text_color=COLORS["gold"], border_width=0,
                                       fg_color=COLORS["card_bg"],
                                       justify="center",
                                       state="readonly", width=450)
        self.lbl_result.insert(0, "Declination: 0.00°")
        self.lbl_result.pack(pady=10)
        self.lbl_result.bind("<Double-Button-1>", lambda e: [self.lbl_result.select_range(0,"end"), "break"])
        ToolTip(self.lbl_result, "Double-click to copy")

        # Bottom status bar
        status_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        status_frame.pack(fill="x")
        self.lbl_status_bottom = ctk.CTkEntry(status_frame, font=("Arial", 11),
                                              text_color="gray", border_width=0,
                                              fg_color="transparent", justify="center",
                                              state="readonly", width=450)
        self.lbl_status_bottom.insert(0, "Ready")
        self.lbl_status_bottom.pack()
        self.lbl_status_bottom.bind("<Double-Button-1>", lambda e: [self.lbl_status_bottom.select_range(0,"end"), "break"])

    def _show_help(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Help")
        dialog.geometry("600x500")
        dialog.attributes("-topmost", True)
        dialog.grab_set()
        dialog.configure(fg_color=COLORS["bg"])
        title = ctk.CTkLabel(dialog, text="🧭 Help – Magnetic Declination Calculator",
                             font=("Arial", 18, "bold"), text_color=COLORS["text_primary"])
        title.pack(pady=(20,10))
        text = """
        📍 Locate & Calculate – One‑press button:
           1. If Wi‑Fi database exists → gets location via Wi‑Fi (100‑500 m)
           2. If no database exists → creates database using IP + Wi‑Fi scan, then uses it
           3. Calculates declination using the final location

        Alternative methods:
        📍 Get from Address – Street level (online Nominatim).
        Manual coordinates – Exact (user input).

        Offline reverse geocoding via Gazetteer: shows nearest city/town/district.
        Double-click any result or status field to copy its content.
        F11 toggles true borderless fullscreen.

        Dependencies: customtkinter, geocoder, geomag, requests, python-gazetteer
        """
        label = ctk.CTkLabel(dialog, text=text, justify="left", font=("Arial", 12),
                             text_color=COLORS["text_secondary"], wraplength=550)
        label.pack(pady=10, padx=20)
        btn_ok = ctk.CTkButton(dialog, text="OK", command=dialog.destroy,
                               width=100, fg_color=COLORS["accent"],
                               hover_color=COLORS["accent_hover"])
        btn_ok.pack(pady=20)

    def _set_status(self, message, msg_type="info"):
        colors = {"info": "#888888", "success": COLORS["accent"], "error": COLORS["danger"], "warning": COLORS["gold"]}
        color = colors.get(msg_type, "#888888")
        self.lbl_status_bottom.configure(state="normal")
        self.lbl_status_bottom.delete(0, "end")
        self.lbl_status_bottom.insert(0, message)
        self.lbl_status_bottom.configure(state="readonly", text_color=color)

    def _initialize_gazetteer(self):
        self.gazetteer = self.gazetteer_manager.ensure_database()
        self.use_gazetteer = self.gazetteer is not None
        if self.use_gazetteer:
            self._set_status("Gazetteer loaded (offline reverse geocoding)", "success")
            self.lbl_gazetteer.configure(text="📡 Offline Gazetteer: ✅ Loaded", text_color=COLORS["accent"])
        else:
            self._set_status("Using online reverse geocoding (Gazetteer not available).", "warning")
            self.lbl_gazetteer.configure(text="📡 Offline Gazetteer: ❌ Not available (using online)", text_color=COLORS["gold"])

    def _set_precision(self, level, detail=""):
        self.lbl_precision.configure(text=f"Precision: {level}" + (f" ({detail})" if detail else ""))

    def _set_coordinates(self, lat, lon, level, detail=""):
        self.latitude = lat
        self.longitude = lon
        self.lbl_coords.configure(text=f"Lat: {lat:.6f}  Lon: {lon:.6f}", text_color=COLORS["text_primary"])
        self._set_precision(level, detail)

    def _forward_geocode(self, address):
        try:
            g = geocoder.nominatim(address, user_agent=NOMINAT_USER_AGENT, limit=1)
            if g.ok:
                return g.lat, g.lng, g.address
        except:
            pass
        return None, None, None

    def _reverse_geocode(self, lat, lon):
        if self.use_gazetteer and self.gazetteer:
            try:
                for place in self.gazetteer.search([(lon, lat)]):  # ← no limit
                    if place:
                        return f"{place.result.name}, {place.result.admin2}, {place.result.admin1}"
            except Exception as e:
                print(f"Gazetteer reverse error: {e}")
        try:
            g = geocoder.reverse((lat, lon), method='nominatim', user_agent=NOMINAT_USER_AGENT)
            if g.ok:
                return g.address
        except Exception as e:
            print(f"Online reverse error: {e}")
        return None

    def _on_clear(self):
        self.latitude = None
        self.longitude = None
        self.lbl_coords.configure(text="Coordinates: Not set", text_color=COLORS["text_secondary"])
        self._set_precision("Not set")
        self.lbl_result.configure(state="normal")
        self.lbl_result.delete(0, "end")
        self.lbl_result.insert(0, "Declination: 0.00°")
        self.lbl_result.configure(state="readonly")
        self.entry_lat.delete(0, "end")
        self.entry_lon.delete(0, "end")
        self.entry_address.delete(0, "end")
        self._set_status("All cleared. Ready.", "info")

    def _on_locate_and_calculate(self):
        """One‑press button: get location (Wi‑Fi or IP) and calculate declination."""
        self._set_status("Locating...", "info")
        self.update_idletasks()

        # Step 1: Check if Wi‑Fi database exists
        db_exists = WIFI_DB_PATH.exists()
        self._set_status(f"Step 1: Wi‑Fi database exists? {db_exists}", "info")

        # Step 2: Get location - TRY Wi‑Fi first if database exists
        if db_exists:
            self._set_status("Step 2: Scanning Wi‑Fi networks...", "info")
            bssids = self.wifi_scanner.scan()
            self._set_status(f"Step 2: Found {len(bssids)} access points", "info")
            
            if bssids:
                self._set_status("Step 2: Matching BSSIDs against database...", "info")
                location = self.wifi_scanner.get_location(WIFI_DB_PATH)
                if location:
                    lat, lon = location
                    address = self._reverse_geocode(lat, lon)
                    address_detail = f"Nearest: {address[:100]}" if address else ""
                    self._set_coordinates(lat, lon, "Wi‑Fi Location (100‑500 m)", f"Based on {len(bssids)} access points")
                    self._set_status(f"✅ Success! Location via Wi‑Fi: {lat:.6f}, {lon:.6f} (100‑500 m accuracy)", "success")
                    self._set_precision("Wi‑Fi Location (100‑500 m)", address_detail)
                    self._on_calculate()
                    return
                else:
                    self._set_status("❌ No matching Wi‑Fi access points in database. Proceeding to rebuild...", "error")
            else:
                self._set_status("❌ No Wi‑Fi networks found. Proceeding to rebuild...", "error")

        # Step 3: If no database or no match, build/update database with IP location
        self._set_status("Step 3: Checking admin privileges...", "info")
        if not is_admin():
            self._set_status("❌ Admin/root required to build Wi‑Fi database.", "error")
            return

        self._set_status("Step 3: Fetching IP location to seed database...", "info")
        ip_lat, ip_lon = None, None
        try:
            resp = requests.get('http://ip-api.com/json/', timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('status') == 'success':
                    ip_lat = data['lat']
                    ip_lon = data['lon']
                    city = data.get('city', 'Unknown')
                    country = data.get('country', 'Unknown')
                    self._set_status(f"Seeding database with IP location: {city}, {country} ({ip_lat:.4f}, {ip_lon:.4f})", "info")
                else:
                    self._set_status("❌ IP geolocation failed. Cannot build database.", "error")
                    return
            else:
                self._set_status(f"❌ IP geolocation failed (HTTP {resp.status_code})", "error")
                return
        except Exception as e:
            self._set_status(f"❌ Error fetching IP location: {e}", "error")
            return

        self._set_status("Step 3: Building/updating Wi‑Fi database...", "info")
        success = self.wifi_builder.build_or_update_database()
        if not success:
            self._set_status("❌ Failed to build Wi‑Fi database. Falling back to IP...", "error")
            if ip_lat is not None:
                self._set_coordinates(ip_lat, ip_lon, "IP (5‑50 km)", "Fallback - Database build failed")
                self._set_status(f"Using IP location: {ip_lat:.6f}, {ip_lon:.6f} (5‑50 km accuracy)", "warning")
                self._on_calculate()
            return

        # Step 4: Use the newly built database
        self._set_status("Step 4: Database built. Getting location via Wi‑Fi...", "info")
        bssids = self.wifi_scanner.scan()
        self._set_status(f"Step 4: Found {len(bssids)} access points", "info")
        
        if bssids:
            self._set_status("Step 4: Matching BSSIDs against new database...", "info")
            location = self.wifi_scanner.get_location(WIFI_DB_PATH)
            if location:
                lat, lon = location
                address = self._reverse_geocode(lat, lon)
                address_detail = f"Nearest: {address[:100]}" if address else ""
                self._set_coordinates(lat, lon, "Wi‑Fi Location (100‑500 m)", f"Based on {len(bssids)} access points")
                self._set_status(f"✅ Success! Location via Wi‑Fi: {lat:.6f}, {lon:.6f} (100‑500 m accuracy)", "success")
                self._set_precision("Wi‑Fi Location (100‑500 m)", address_detail)
                self._on_calculate()
                return
            else:
                self._set_status("❌ No matching access points in new database. Falling back to IP...", "error")
        else:
            self._set_status("❌ No Wi‑Fi networks found. Falling back to IP...", "error")

        # Step 5: Final fallback to IP
        self._set_status("Step 5: Final fallback to IP", "info")
        if ip_lat is not None:
            self._set_coordinates(ip_lat, ip_lon, "IP (5‑50 km)", "Fallback - No Wi‑Fi match")
            self._set_status(f"Using IP location: {ip_lat:.6f}, {ip_lon:.6f} (5‑50 km accuracy)", "warning")
            self._on_calculate()
        else:
            self._set_status("❌ No IP location available. Please set location manually.", "error")

    def _on_get_from_address(self):
        a = self.entry_address.get().strip()
        if not a:
            self._set_status("Please enter an address.", "error")
            return
        self._set_status("Geocoding address via Nominatim...", "info")
        self.update_idletasks()
        lat, lon, name = self._forward_geocode(a)
        if lat:
            level = "Street level" if len(name) > 20 else "City level"
            self._set_coordinates(lat, lon, level, name[:80])
            self._set_status(f"Location found: {name}", "success")
        else:
            self._set_status("Could not geocode address. Check input or internet.", "error")

    def _on_get_ip(self):
        self._set_status("Fetching location via IP...", "info")
        try:
            r = requests.get('http://ip-api.com/json/', timeout=5)
            if r.status_code == 200:
                d = r.json()
                if d.get('status') == 'success':
                    lat, lon = float(d['lat']), float(d['lon'])
                    city, country = d.get('city', 'Unknown'), d.get('country', 'Unknown')
                    self._set_coordinates(lat, lon, "IP (5‑50 km)", f"{city}, {country}")
                    self._set_status(f"IP location: {city}, {country} (accuracy 5‑50 km)", "warning")
                    addr = self._reverse_geocode(lat, lon)
                    if addr:
                        self._set_precision("IP (5‑50 km)", f"Nearest: {addr[:100]}")
                else:
                    self._set_status("IP geolocation failed.", "error")
            else:
                self._set_status(f"IP geolocation failed (HTTP {r.status_code})", "error")
        except Exception as e:
            self._set_status(f"Error: {str(e)}", "error")

    def _on_set_manual(self):
        try:
            lat = float(self.entry_lat.get().strip())
            lon = float(self.entry_lon.get().strip())
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                self._set_status("Invalid coordinates range.", "error")
                return
        except:
            self._set_status("Invalid coordinates. Use numbers only.", "error")
            return
        self.entry_lat.delete(0, "end")
        self.entry_lon.delete(0, "end")
        self._set_coordinates(lat, lon, "Exact (manual input)")
        self._set_status("Validating address...", "info")
        addr = self._reverse_geocode(lat, lon)
        if addr:
            self._set_precision("Exact (manual input)", f"Validated: {addr[:100]}")
            self._set_status(f"Coordinates validated. Nearest address: {addr}", "success")
        else:
            self._set_precision("Exact (manual input)", "Address not found")
            self._set_status("Coordinates set. No address found.", "info")

    def _on_calculate(self):
        if self.latitude is None or self.longitude is None:
            self._set_status("Please set a location first.", "error")
            return
        self._set_status("Calculating declination...", "info")
        try:
            d = geomag.declination(self.latitude, self.longitude, 0)
            text = f"Declination: {d:.2f}°"
            self.lbl_result.configure(state="normal")
            self.lbl_result.delete(0, "end")
            self.lbl_result.insert(0, text)
            self.lbl_result.configure(state="readonly")
            self._set_status("Calculated successfully.", "success")
            self._highlight_result()
        except Exception as e:
            self._set_status(f"Calculation error: {str(e)}", "error")

    def _highlight_result(self):
        orig_color = self.lbl_result.cget("text_color")
        orig_fg = self.lbl_result.cget("fg_color")
        self.lbl_result.configure(fg_color=COLORS["accent"], text_color="white")
        self.update_idletasks()
        self.after(800, lambda: self.lbl_result.configure(fg_color=orig_fg, text_color=orig_color))


if __name__ == "__main__":
    try:
        import customtkinter, geocoder, geomag, requests
        from gazetteer import Gazetteer
    except ImportError as e:
        print(f"Missing dependency: {e}", file=sys.stderr)
        print("pip install customtkinter geocoder geomag requests python-gazetteer", file=sys.stderr)
        sys.exit(1)
    app = App()
    app.mainloop()