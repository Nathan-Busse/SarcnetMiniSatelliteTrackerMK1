#!/usr/bin/env python3
"""
Magnetic Declination Calculator
Uses GeoDude (ADM3 polygon boundaries) for offline reverse geocoding.
No forced admin – Wi‑Fi scanning works without elevation on Windows.
"""

import os
import sys
import locale
import threading
import time
import datetime
import sqlite3
import subprocess
import re
import tempfile
import json
import platform
from pathlib import Path

# Fixes for Windows environments
os.environ["CHARSET_NORMALIZER_SKIP_CACHE"] = "1"
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"
try:
    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
except:
    pass

# ----------------------------------------------------------------------
# Regular imports
# ----------------------------------------------------------------------
import customtkinter as ctk
import geomag
import requests

# ----------------------------------------------------------------------
# Optional libraries – the app remains functional without them
# ----------------------------------------------------------------------
try:
    import serial
    import serial.tools.list_ports
    import pynmea2
    GPS_AVAILABLE = True
except ImportError:
    GPS_AVAILABLE = False

# ----------------------------------------------------------------------
# GeoDude setup – imports that never trigger circular dependencies
# ----------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
# Adjust this to the folder that CONTAINS your 'geodude' package
GEODUDE_LIB_DIR = (BASE_DIR / ".." / ".." / ".." / "CustomLibraries" / "GeoDudeLibrary").resolve()
sys.path.insert(0, str(GEODUDE_LIB_DIR))

# Import directly from submodules – avoids any circular import
from geodude.reverse_geocode import geodude as GeodudeClass
from geodude import create_db
from geodude import fetch_db

# One‑time data installation – only runs if the package data files are missing
from importlib.resources import files
DATA_DIR = files("geodude.data")          # resolves to geodude/data/
if not (DATA_DIR / "data.db").exists() or not (DATA_DIR / "geo-boundaries.csv").exists():
    print("GeoDude data files missing. Running installer…")
    fetch_db()                          # downloads the latest data
    create_db()                         # builds the database
    print("Installer finished.")

# Create the singleton instance – it loads data.db & geo-boundaries.csv automatically
_g_instance = fetch_db()
# Adapter that provides the simple get_nearest(lat, lon) interface
class GeodudeAdapter:
    def __init__(self, g):
        self.g = g

    def get_nearest(self, lat, lon):
        results = list(self.g.search([(lon, lat)]))
        if results and results[0].result:
            r = results[0].result
            return {
                'name': r.name,
                'admin1': r.admin1,
                'admin2': r.admin2,
                'country': '',
                'lat': lat,
                'lon': lon,
                'address': f"{r.name}, {r.admin2}, {r.admin1}"
            }
        return None

geodude_adapter = GeodudeAdapter(_g_instance)
USE_GEODUDE = True
print("GeoDude loaded and ready.")

# ----------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------
APP_TITLE = "Magnetic Declination Calculator"
DEFAULT_APPEARANCE = "Dark"
DEFAULT_THEME = "dark-blue"
NOMINAT_USER_AGENT = "MagneticDeclinationCalculator/1.0"

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
# Console output panel
# ----------------------------------------------------------------------
class ConsolePanel(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(fg_color=COLORS["card_bg"], corner_radius=12,
                       border_width=1, border_color=COLORS["card_border"])

        title = ctk.CTkLabel(self, text="Console Output", font=("Arial", 12, "bold"),
                             text_color=COLORS["text_primary"])
        title.pack(anchor="w", padx=10, pady=(5, 2))

        self.console_text = ctk.CTkTextbox(self, height=150, font=("Consolas", 10),
                                           fg_color="#1e1e1e", text_color="#d4d4d4",
                                           border_width=0, corner_radius=8)
        self.console_text.pack(fill="both", expand=True, padx=10, pady=5)

        self.copy_btn = ctk.CTkButton(self, text="Copy Console",
                                      command=self._copy_console,
                                      width=100, fg_color="#555555",
                                      hover_color="#666666", font=("Arial", 10))
        self.copy_btn.pack(anchor="e", padx=10, pady=(0, 5))
        self.messages = []

    def append(self, message):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {message}\n"
        self.messages.append(formatted)
        self.console_text.insert("end", formatted)
        self.console_text.see("end")
        self.console_text.update_idletasks()

    def clear(self):
        self.messages.clear()
        self.console_text.delete("1.0", "end")

    def _copy_console(self):
        content = self.console_text.get("1.0", "end")
        self.clipboard_clear()
        self.clipboard_append(content)
        self.copy_btn.configure(text="Copied!", text_color="#4caf50")
        self.after(2000, lambda: self.copy_btn.configure(text="Copy Console", text_color="white"))


# ----------------------------------------------------------------------
# Wi‑Fi Scanner
# ----------------------------------------------------------------------
class WiFiScanner:
    def __init__(self, parent_app):
        self.parent_app = parent_app
        self.bssids = []
        self.platform = platform.system()
        self.raw_output = ""

    def scan(self):
        self.bssids = []
        self.raw_output = ""
        try:
            if self.platform == "Windows":
                cmds = [
                    ['netsh', 'wlan', 'show', 'networks', 'mode=bssid'],
                    ['netsh', 'wlan', 'show', 'networks', 'mode=bssid', 'format=list']
                ]
                for cmd in cmds:
                    try:
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                        if result.returncode == 0:
                            self.raw_output = result.stdout
                            break
                    except (subprocess.TimeoutExpired, FileNotFoundError):
                        continue
                if not self.raw_output:
                    self.parent_app.console.append("Failed to run netsh commands after retries.")
                    return []
            elif self.platform == "Linux":
                cmds = [['sudo', 'iwlist', 'scan'], ['iwlist', 'scan']]
                for cmd in cmds:
                    try:
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                        if result.returncode == 0:
                            self.raw_output = result.stdout
                            break
                    except (subprocess.TimeoutExpired, FileNotFoundError):
                        continue
                if not self.raw_output:
                    self.parent_app.console.append("Failed to run iwlist commands.")
                    return []
            elif self.platform == "Darwin":
                airport_paths = [
                    ['airport', '-s'],
                    ['/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport', '-s']
                ]
                for cmd in airport_paths:
                    try:
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                        if result.returncode == 0:
                            self.raw_output = result.stdout
                            break
                    except (subprocess.TimeoutExpired, FileNotFoundError):
                        continue
                if not self.raw_output:
                    self.parent_app.console.append("Failed to run airport command.")
                    return []
        except Exception as e:
            self.parent_app.console.append(f"Error during Wi‑Fi scan: {e}")
            return []

        self.parent_app.console.append(f"Raw Wi‑Fi scan output (first 500 chars):\n{self.raw_output[:500]}...")

        patterns = [
            r'BSSID\s+\d+\s+:\s+(([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})',
            r'BSSID\s+:\s+(([0-9A-Fa-f]{2}-){5}[0-9A-Fa-f]{2})',
            r'BSSID\s+:\s+(([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})',
            r'Address: (([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})',
            r'(([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})',
            r'(([0-9A-Fa-f]{2}[: -]){5}[0-9A-Fa-f]{2})'
        ]
        for i, pattern in enumerate(patterns, 1):
            matches = re.findall(pattern, self.raw_output)
            if matches:
                self.bssids = [match[0].replace('-', ':') for match in matches]
                self.parent_app.console.append(f"Regex pattern #{i} matched, found {len(self.bssids)} BSSIDs.")
                return self.bssids

        self.parent_app.console.append("No regex patterns matched the output.")
        return []

    def get_location(self, db_path):
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
            avg_lat = sum(lat for lat, lon in locations) / len(locations)
            avg_lon = sum(lon for lat, lon in locations) / len(locations)
            return avg_lat, avg_lon
        except Exception as e:
            self.parent_app.console.append(f"Error reading Wi‑Fi database: {e}")
            return None


# ----------------------------------------------------------------------
# GPS Reader
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
                        self.parent_app.after(0, lambda: callback(
                            float(msg.latitude), float(msg.longitude), msg.gps_qual))
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
        self.geometry("900x800")
        self.minsize(800, 600)
        self.configure(fg_color=COLORS["bg"])
        ctk.set_appearance_mode(DEFAULT_APPEARANCE)
        ctk.set_default_color_theme(DEFAULT_THEME)
        self._maximize_window()
        self.bind("<F11>", self._toggle_fullscreen)
        self.is_fullscreen = False
        self.prev_geometry = ""

        self.latitude = None
        self.longitude = None
        self.processing = False

        self.geodude = geodude_adapter          # the adapter created above
        self.use_geodude = USE_GEODUDE

        self.gps_reader = GPSReader(self)
        self.gps_active = False

        self.ip_location = None

        self._create_widgets()
        self.after(100, self._update_geodude_label)

    def _update_geodude_label(self):
        if self.use_geodude:
            self._set_status("Offline reverse geocoding ready (GeoDude ADM3).", "success")
            self.lbl_geodude.configure(text="Offline GeoDude ADM3: Loaded", text_color=COLORS["accent"])
        else:
            self._set_status("Online reverse geocoding only (GeoDude not loaded).", "warning")
            self.lbl_geodude.configure(text="Offline GeoDude ADM3: Not loaded (using online)",
                                       text_color=COLORS["gold"])

    # ------------------------------------------------------------------
    # Window management
    # ------------------------------------------------------------------
    def _maximize_window(self):
        s = platform.system()
        if s == "Windows":
            self.state('zoomed')
        elif s == "Darwin":
            self.attributes('-zoomed', True)
        else:
            self.state('zoomed')

    def _toggle_fullscreen(self, event=None):
        if self.is_fullscreen:
            self.attributes('-fullscreen', False)
            self.is_fullscreen = False
            if self.prev_geometry:
                self.geometry(self.prev_geometry)
        else:
            self.prev_geometry = self.geometry()
            self.attributes('-fullscreen', True)
            self.is_fullscreen = True

    # ------------------------------------------------------------------
    # UI creation
    # ------------------------------------------------------------------
    def _create_widgets(self):
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Header
        header_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 15))
        title = ctk.CTkLabel(header_frame, text="Magnetic Declination Calculator",
                             font=("Arial", 24, "bold"), text_color=COLORS["text_primary"])
        title.pack(side="left")
        ToolTip(title, "Calculate magnetic declination for any location on Earth")
        self.btn_help = ctk.CTkButton(header_frame, text="Help", command=self._show_help,
                                      width=80, fg_color="transparent",
                                      hover_color=COLORS["card_bg"],
                                      text_color=COLORS["text_secondary"], font=("Arial", 12))
        self.btn_help.pack(side="right")

        # Console
        self.console = ConsolePanel(main_frame)
        self.console.pack(fill="both", expand=True, pady=(0, 10))

        # Location input card
        loc_card = ctk.CTkFrame(main_frame, fg_color=COLORS["card_bg"],
                                corner_radius=12, border_width=1, border_color=COLORS["card_border"])
        loc_card.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(loc_card, text="Location Input", font=("Arial", 14, "bold"),
                     text_color=COLORS["text_primary"]).pack(anchor="w", padx=15, pady=(10, 5))

        addr_frame = ctk.CTkFrame(loc_card, fg_color="transparent")
        addr_frame.pack(fill="x", padx=15, pady=5)
        self.entry_address = ctk.CTkEntry(addr_frame, placeholder_text="Street address, city, country",
                                          width=350, font=("Arial", 12))
        self.entry_address.pack(side="left", padx=(0, 10))
        ToolTip(self.entry_address, "Type a full address and click 'Get from Address'")
        self.btn_address = ctk.CTkButton(addr_frame, text="Get from Address",
                                         command=self._on_get_from_address,
                                         width=120, fg_color=COLORS["accent"],
                                         hover_color=COLORS["accent_hover"], font=("Arial", 12))
        self.btn_address.pack(side="left")
        ToolTip(self.btn_address, "Forward geocode the address (online)")

        ctk.CTkFrame(loc_card, height=1, fg_color=COLORS["card_border"]).pack(fill="x", padx=15, pady=5)

        # Main method buttons
        method_frame = ctk.CTkFrame(loc_card, fg_color="transparent")
        method_frame.pack(fill="x", padx=15, pady=5)

        self.btn_locate = ctk.CTkButton(method_frame, text="Locate & Calculate Declination",
                                        command=self._on_locate_and_calculate,
                                        width=280, fg_color=COLORS["accent"],
                                        hover_color=COLORS["accent_hover"],
                                        font=("Arial", 13, "bold"))
        self.btn_locate.pack(side="left", padx=(0, 10))
        ToolTip(self.btn_locate, "One‑press: get location (Wi‑Fi if possible) and calculate declination")

        # GPS button
        self.btn_gps = ctk.CTkButton(method_frame, text="GPS", command=self._toggle_gps,
                                     width=60, fg_color=COLORS["secondary"],
                                     hover_color=COLORS["secondary_hover"],
                                     font=("Arial", 12))
        self.btn_gps.pack(side="left", padx=(0, 5))
        ToolTip(self.btn_gps, "Start/stop live GPS tracking")

        # Manual coordinates
        ctk.CTkLabel(method_frame, text="Manual:", font=("Arial", 12),
                     text_color=COLORS["text_secondary"]).pack(side="left", padx=(10, 5))
        self.entry_lat = ctk.CTkEntry(method_frame, placeholder_text="Lat", width=100, font=("Arial", 12))
        self.entry_lat.pack(side="left", padx=2)
        ToolTip(self.entry_lat, "Latitude between -90 and 90")
        self.entry_lon = ctk.CTkEntry(method_frame, placeholder_text="Lon", width=100, font=("Arial", 12))
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

        # Coordinates & Precision card
        coord_card = ctk.CTkFrame(main_frame, fg_color=COLORS["card_bg"],
                                  corner_radius=12, border_width=1, border_color=COLORS["card_border"])
        coord_card.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(coord_card, text="Current Coordinates", font=("Arial", 14, "bold"),
                     text_color=COLORS["text_primary"]).pack(anchor="w", padx=15, pady=(10, 5))

        disp_frame = ctk.CTkFrame(coord_card, fg_color="transparent")
        disp_frame.pack(fill="x", padx=15, pady=5)
        self.lbl_coords = ctk.CTkLabel(disp_frame, text="Coordinates: Not set",
                                       font=("Arial", 13), text_color=COLORS["text_secondary"])
        self.lbl_coords.pack(side="left")
        self.lbl_precision = ctk.CTkLabel(disp_frame, text="Precision: Not set",
                                          font=("Arial", 12), text_color="#888888")
        self.lbl_precision.pack(side="right")

        self.lbl_geodude = ctk.CTkLabel(coord_card, text="Offline GeoDude ADM3: Initializing...",
                                        font=("Arial", 11), text_color="#888888")
        self.lbl_geodude.pack(anchor="w", padx=15, pady=(0, 5))

        # Result card
        result_card = ctk.CTkFrame(main_frame, fg_color=COLORS["card_bg"],
                                   corner_radius=12, border_width=1, border_color=COLORS["card_border"])
        result_card.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(result_card, text="Declination Result", font=("Arial", 14, "bold"),
                     text_color=COLORS["text_primary"]).pack(anchor="w", padx=15, pady=(10, 5))
        self.lbl_result = ctk.CTkEntry(result_card, font=("Arial", 18, "bold"),
                                       text_color=COLORS["gold"], border_width=0,
                                       fg_color=COLORS["card_bg"],
                                       justify="center",
                                       state="readonly", width=400)
        self.lbl_result.insert(0, "Declination: 0.00°")
        self.lbl_result.pack(pady=10)
        ToolTip(self.lbl_result, "Double-click to copy")

        # Status bar
        status_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        status_frame.pack(fill="x", pady=(5, 0))
        self.lbl_status = ctk.CTkLabel(status_frame, text="Ready",
                                       font=("Arial", 11), text_color="#888888",
                                       wraplength=600)
        self.lbl_status.pack(side="left", padx=(10, 10))
        self.btn_copy_status = ctk.CTkButton(status_frame, text="Copy", width=50,
                                             fg_color="#555555", hover_color="#666666",
                                             font=("Arial", 10),
                                             command=self._copy_status)
        self.btn_copy_status.pack(side="right", padx=(0, 10))
        ToolTip(self.btn_copy_status, "Copy status text")

    def _copy_status(self):
        text = self.lbl_status.cget("text")
        self.clipboard_clear()
        self.clipboard_append(text)
        self.btn_copy_status.configure(text="Copied", text_color="#4caf50")
        self.after(1500, lambda: self.btn_copy_status.configure(text="Copy", text_color="white"))

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------
    def _set_status(self, message, msg_type="info"):
        colors = {"info": "#888888", "success": COLORS["accent"],
                  "error": COLORS["danger"], "warning": COLORS["gold"]}
        color = colors.get(msg_type, "#888888")
        self.lbl_status.configure(text=message, text_color=color)

    def _set_precision(self, level, detail=""):
        display = f"Precision: {level}"
        if detail:
            display += f" ({detail})"
        self.lbl_precision.configure(text=display)

    def _set_coordinates(self, lat, lon, level, detail=""):
        self.latitude = lat
        self.longitude = lon
        self.lbl_coords.configure(text=f"Lat: {lat:.6f}  Lon: {lon:.6f}",
                                  text_color=COLORS["text_primary"])
        self._set_precision(level, detail)

    # ------------------------------------------------------------------
    # Help dialog
    # ------------------------------------------------------------------
    def _show_help(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Help")
        dialog.geometry("600x500")
        dialog.attributes("-topmost", True)
        dialog.grab_set()
        dialog.configure(fg_color=COLORS["bg"])
        ctk.CTkLabel(dialog, text="Help – Magnetic Declination Calculator",
                     font=("Arial", 18, "bold"), text_color=COLORS["text_primary"]).pack(pady=(20, 10))
        text = """
        Locate & Calculate – One‑press button:
           1. If Wi‑Fi database exists → gets location via Wi‑Fi (100‑500 m)
           2. If no database exists → creates database using IP + Wi‑Fi scan, then uses it
           3. Falls back to IP location if Wi‑Fi fails

        Alternative methods:
        Get from Address – Street level (online Nominatim).
        Manual coordinates – Exact (user input).
        GPS – Live serial GPS tracking.

        Offline reverse geocoding: uses GeoDude with ADM3 polygon boundaries.
        Double-click any result field to copy its content.
        F11 toggles true borderless fullscreen.
        """
        label = ctk.CTkLabel(dialog, text=text, justify="left", font=("Arial", 12),
                             text_color=COLORS["text_secondary"], wraplength=550)
        label.pack(pady=10, padx=20)
        ctk.CTkButton(dialog, text="OK", command=dialog.destroy,
                      width=100, fg_color=COLORS["accent"],
                      hover_color=COLORS["accent_hover"]).pack(pady=20)

    # ------------------------------------------------------------------
    # Direct Nominatim API calls (geocoding)
    # ------------------------------------------------------------------
    @staticmethod
    def _nominatim_forward(address):
        try:
            url = "https://nominatim.openstreetmap.org/search"
            params = {
                "q": address,
                "format": "json",
                "limit": 1,
                "addressdetails": 0
            }
            headers = {"User-Agent": NOMINAT_USER_AGENT}
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data:
                    item = data[0]
                    return float(item["lat"]), float(item["lon"]), item.get("display_name", address)
        except Exception:
            pass
        return None, None, None

    @staticmethod
    def _nominatim_reverse(lat, lon):
        try:
            url = "https://nominatim.openstreetmap.org/reverse"
            params = {
                "lat": lat,
                "lon": lon,
                "format": "json",
                "zoom": 18,
                "addressdetails": 0
            }
            headers = {"User-Agent": NOMINAT_USER_AGENT}
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if "display_name" in data:
                    return data["display_name"]
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # Geocoding helpers
    # ------------------------------------------------------------------
    def _forward_geocode(self, address):
        return self._nominatim_forward(address)

    def _reverse_geocode(self, lat, lon):
        self.console.append(f"Reverse geocoding {lat:.6f}, {lon:.6f}...")
        # Online first (Nominatim)
        addr = self._nominatim_reverse(lat, lon)
        if addr:
            self.console.append(f"Nominatim returned: {addr}")
            return addr
        self.console.append("Nominatim reverse failed (or no result).")

        # Offline fallback: GeoDude ADM3
        if self.use_geodude and self.geodude:
            try:
                place = self.geodude.get_nearest(lat, lon)
                if place:
                    addr = place["address"]
                    self.console.append(f"GeoDude ADM3 returned: {addr}")
                    return addr
            except Exception as e:
                self.console.append(f"GeoDude ADM3 error: {e}")
        self.console.append("No address found.")
        return None

    @staticmethod
    def _extract_address_detail(address):
        if not address:
            return "", "No address"
        parts = address.split(',')
        if len(parts) >= 3:
            first = parts[0].strip()
            if any(c.isdigit() for c in first) or any(word in first.lower() for word in
                    ['street','st','avenue','ave','road','rd','lane','ln','drive','dr','court','ct','place','pl','way']):
                return address, "Street level"
        return address, "City/District level"

    # ------------------------------------------------------------------
    # Location methods
    # ------------------------------------------------------------------
    def _on_get_from_address(self):
        address = self.entry_address.get().strip()
        if not address:
            self._set_status("Please enter an address.", "error")
            return
        self._set_status("Geocoding address...", "info")
        self.update_idletasks()
        lat, lon, name = self._forward_geocode(address)
        if lat:
            detail, level = self._extract_address_detail(name)
            self._set_coordinates(lat, lon, level, detail[:100])
            self._set_status(f"Location found: {name}", "success")
        else:
            self._set_status("Could not geocode address. Check input or internet.", "error")

    def _on_set_manual(self):
        try:
            lat = float(self.entry_lat.get().strip())
            lon = float(self.entry_lon.get().strip())
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError
        except:
            self._set_status("Invalid coordinates. Use numbers only.", "error")
            return
        self.entry_lat.delete(0, "end")
        self.entry_lon.delete(0, "end")
        self._set_coordinates(lat, lon, "Exact (manual input)")
        self._set_status("Validating address...", "info")
        addr = self._reverse_geocode(lat, lon)
        if addr:
            detail, level = self._extract_address_detail(addr)
            self._set_precision("Exact (manual input)", f"Validated: {detail[:100]}")
            self._set_status(f"Coordinates validated. Nearest: {addr}", "success")
        else:
            self._set_precision("Exact (manual input)", "Address not found")
            self._set_status("Coordinates set. No address found.", "info")

    def _get_ip_location(self):
        if self.ip_location is not None:
            return self.ip_location
        self.console.append("Fetching IP location...")
        try:
            resp = requests.get('http://ip-api.com/json/', timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('status') == 'success':
                    lat, lon = float(data['lat']), float(data['lon'])
                    city = data.get('city', 'Unknown')
                    country = data.get('country', 'Unknown')
                    self.ip_location = (lat, lon, f"{city}, {country}")
                    return self.ip_location
                else:
                    self.console.append("IP geolocation API returned 'status' != 'success'")
            else:
                self.console.append(f"IP geolocation failed (HTTP {resp.status_code})")
        except Exception as e:
            self.console.append(f"Error fetching IP location: {e}")
        return None

    def _check_wifi_adapter_status(self):
        cur_os = platform.system()
        try:
            if cur_os == "Windows":
                out = subprocess.check_output(['netsh', 'wlan', 'show', 'interfaces'], text=True)
                for line in out.splitlines():
                    if "State" in line:
                        state = line.split(':')[-1].strip()
                        if state == "connected":
                            return True, "connected"
                        elif state == "disconnected":
                            return True, "disconnected"
                        elif state == "disabled":
                            return False, "disabled"
                return False, "not_found"
            elif cur_os == "Linux":
                out = subprocess.check_output(['ip', 'link'], text=True)
                for line in out.splitlines():
                    if 'wlan' in line or 'wlp' in line:
                        if 'UP' in line:
                            return True, "enabled"
                        else:
                            return True, "down"
                return False, "not_found"
            elif cur_os == "Darwin":
                out = subprocess.check_output(['networksetup', '-getairportpower', 'en0'], text=True)
                if 'On' in out:
                    return True, "enabled"
                return False, "disabled"
        except Exception as e:
            self.console.append(f"Wi‑Fi adapter check error: {e}")
        return False, "unknown"

    # ------------------------------------------------------------------
    # GPS toggle
    # ------------------------------------------------------------------
    def _toggle_gps(self):
        if self.gps_active:
            self.gps_reader.stop_reading()
            self.gps_active = False
            self.btn_gps.configure(text="GPS", fg_color=COLORS["secondary"])
            self._set_status("GPS stopped.", "info")
        else:
            if self.gps_reader.start_reading(self._on_gps_update):
                self.gps_active = True
                self.btn_gps.configure(text="Stop GPS", fg_color=COLORS["danger"])
            else:
                self._set_status("Failed to start GPS.", "error")

    def _on_gps_update(self, lat, lon, quality):
        level = "GPS" if quality > 0 else "GPS (no fix)"
        self._set_coordinates(lat, lon, level, f"Fix quality: {quality}")
        self._set_status(f"GPS live: {lat:.6f}, {lon:.6f} (q{quality})", "success")

    # ------------------------------------------------------------------
    # Core workflow
    # ------------------------------------------------------------------
    def _on_locate_and_calculate(self):
        if self.processing:
            return
        self.processing = True
        self.btn_locate.configure(state="disabled", text="Working...")
        self.console.clear()
        self.console.append("[START] Location & calculation workflow")
        self._set_status("Locating...", "info")
        self.update_idletasks()
        threading.Thread(target=self._locate_workflow, daemon=True).start()

    def _locate_workflow(self):
        try:
            wifi_ok, wifi_status = self._check_wifi_adapter_status()
            if not wifi_ok:
                self.console.append(f"[WIFI_ADAPTER] Status: {wifi_status} – disabling Wi‑Fi.")
            else:
                self.console.append(f"[WIFI_ADAPTER] Status: {wifi_status}")

            db_exists = WIFI_DB_PATH.exists()
            if db_exists:
                try:
                    conn = sqlite3.connect(str(WIFI_DB_PATH))
                    count = conn.execute('SELECT COUNT(*) FROM access_points').fetchone()[0]
                    conn.close()
                    self.console.append(f"[DATABASE] Found with {count} entries.")
                except Exception as e:
                    self.console.append(f"[DATABASE] Corrupted ({e}). Will rebuild.")
                    db_exists = False
            else:
                self.console.append("[DATABASE] Does not exist.")

            if db_exists and wifi_ok:
                lat, lon = self._try_wifi_location()
                if lat is not None:
                    self._after_location(lat, lon, "Wi‑Fi Location (100‑500 m)")
                    return

            if wifi_ok:
                ip_loc = self._get_ip_location()
                if ip_loc:
                    ip_lat, ip_lon, ip_desc = ip_loc
                    self.console.append(f"[IP] Location: {ip_desc} ({ip_lat:.4f}, {ip_lon:.4f})")
                    scanner = WiFiScanner(self)
                    bssids = scanner.scan()
                    self.console.append(f"Scanned {len(bssids)} BSSIDs.")
                    if bssids:
                        self._build_update_wifi_db(bssids, ip_lat, ip_lon)
                        lat, lon = self._try_wifi_location()
                        if lat is not None:
                            self._after_location(lat, lon, "Wi‑Fi Location (100‑500 m, after build)")
                            return
                    else:
                        self.console.append("No BSSIDs found – cannot build database.")
                else:
                    self.console.append("[IP] Failed to get IP location; cannot build database.")

            ip_loc = self._get_ip_location()
            if ip_loc:
                lat, lon, desc = ip_loc
                self._after_location(lat, lon, "IP (5‑50 km)")
            else:
                self.console.append("All location methods failed.")
                self._set_status("Unable to determine location. Try manual input.", "error")
                self._finish_processing()
        except Exception as e:
            self.console.append(f"Fatal error in workflow: {e}")
            self._set_status("An error occurred. See console.", "error")
            self._finish_processing()

    def _try_wifi_location(self):
        self.console.append("[WIFI] Scanning for networks...")
        scanner = WiFiScanner(self)
        bssids = scanner.scan()
        if not bssids:
            self.console.append("No access points found.")
            return None, None
        self.console.append(f"Found {len(bssids)} BSSIDs. Matching against database...")
        location = scanner.get_location(WIFI_DB_PATH)
        if location:
            self.console.append(f"Wi‑Fi location found: {location[0]:.6f}, {location[1]:.6f}")
            return location
        else:
            self.console.append("No matching BSSIDs in database.")
            return None, None

    def _build_update_wifi_db(self, bssids, lat, lon):
        self.console.append("[BUILD] Building/updating Wi‑Fi database...")
        try:
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
            rows = [(bssid, lat, lon, int(time.time())) for bssid in bssids]
            cursor.executemany('INSERT OR REPLACE INTO access_points VALUES (?,?,?,?)', rows)
            conn.commit()
            conn.close()
            self.console.append(f"Database updated with {len(rows)} entries.")
        except Exception as e:
            self.console.append(f"Database update error: {e}")

    def _after_location(self, lat, lon, level):
        addr = self._reverse_geocode(lat, lon)
        detail, addr_level = self._extract_address_detail(addr) if addr else ("", "unknown")
        precision_detail = detail if addr else ""
        if not precision_detail:
            precision_detail = addr_level if addr else ""
        self.after(0, lambda: self._set_coordinates(lat, lon, level, precision_detail))
        status_msg = f"{level}: {lat:.6f}, {lon:.6f}"
        if addr:
            status_msg += f" – {detail}"
        self.after(0, lambda: self._set_status(status_msg, "success"))
        self.after(100, self._on_calculate)
        self.after(200, self._finish_processing)

    def _finish_processing(self):
        self.after(0, lambda: self.btn_locate.configure(state="normal", text="Locate & Calculate Declination"))
        self.processing = False

    # ------------------------------------------------------------------
    # Declination calculation
    # ------------------------------------------------------------------
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


# ----------------------------------------------------------------------
# Main entry point
# ----------------------------------------------------------------------
if __name__ == "__main__":
    try:
        import customtkinter, geomag, requests
    except ImportError as e:
        print(f"Missing dependency: {e}", file=sys.stderr)
        print("pip install customtkinter geomag requests", file=sys.stderr)
        sys.exit(1)
    app = App()
    app.mainloop()