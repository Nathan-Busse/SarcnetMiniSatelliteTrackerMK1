#!/usr/bin/env python3
"""
Magnetic Declination Calculator
Uses GeoDude (ADM3 polygon boundaries) for offline reverse geocoding,
GeoDude’s built‑in WMM2025 geomagnetic calculator, and
BeaconDB for free online Wi‑Fi geolocation (no API key required).
Includes a “Submit to BeaconDB” button to contribute local Wi‑Fi scans.
No online address lookup – all offline once location is acquired.
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
# GeoDude setup
# ----------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
GEODUDE_LIB_DIR = (BASE_DIR / ".." / ".." / ".." / "CustomLibraries" / "GeoDudeLibrary").resolve()
sys.path.insert(0, str(GEODUDE_LIB_DIR))

from geodude import fetch_db
from geodude.geomag_calc import declination

try:
    g_instance = fetch_db()
    GEODUDE_AVAILABLE = True
    print("GeoDude loaded and ready.")
except Exception as e:
    print(f"GeoDude could not be loaded: {e}")
    GEODUDE_AVAILABLE = False
    g_instance = None

# ----------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------
APP_TITLE = "Magnetic Declination Calculator"
DEFAULT_APPEARANCE = "Dark"
DEFAULT_THEME = "dark-blue"

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
# BeaconDB geolocation (free, no API key)
# ----------------------------------------------------------------------
def _locate_via_beacondb(bssids):
    """
    Query BeaconDB's free geolocation API.
    Returns (lat, lon, accuracy_m, reason) on success,
    or (None, None, None, reason) on failure.
    """
    url = "https://api.beacondb.net/v1/geolocate"
    wifi_list = [{"macAddress": b, "signalStrength": -60} for b in bssids[:10]]
    payload = {"wifiAccessPoints": wifi_list, "considerIp": False}
    headers = {"User-Agent": "MagneticDeclinationCalculator/1.0"}
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            loc = data.get("location", {})
            if "lat" in loc and "lng" in loc:
                return loc["lat"], loc["lng"], data.get("accuracy", 150.0), "success"
            else:
                return None, None, None, "200 OK but missing location in response"
        elif resp.status_code == 404:
            return None, None, None, "404 – BeaconDB has no data for these Wi‑Fi networks"
        else:
            return None, None, None, f"Error {resp.status_code}"
    except requests.exceptions.Timeout:
        return None, None, None, "Timeout – BeaconDB server did not respond"
    except requests.exceptions.ConnectionError:
        return None, None, None, "Connection error – cannot reach BeaconDB"
    except Exception as e:
        return None, None, None, f"Unexpected error: {str(e)}"


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

        self.geodude = g_instance
        self.use_geodude = GEODUDE_AVAILABLE

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
            self._set_status("GeoDude not loaded. Reverse geocoding unavailable.", "error")
            self.lbl_geodude.configure(text="Offline GeoDude ADM3: Not loaded",
                                       text_color=COLORS["danger"])

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

        method_frame = ctk.CTkFrame(loc_card, fg_color="transparent")
        method_frame.pack(fill="x", padx=15, pady=5)

        self.btn_locate = ctk.CTkButton(method_frame, text="Locate & Calculate Declination",
                                        command=self._on_locate_and_calculate,
                                        width=280, fg_color=COLORS["accent"],
                                        hover_color=COLORS["accent_hover"],
                                        font=("Arial", 13, "bold"))
        self.btn_locate.pack(side="left", padx=(0, 10))
        ToolTip(self.btn_locate, "One‑press: get location (BeaconDB → local DB → IP) and calculate declination")

        self.btn_gps = ctk.CTkButton(method_frame, text="GPS", command=self._toggle_gps,
                                     width=60, fg_color=COLORS["secondary"],
                                     hover_color=COLORS["secondary_hover"],
                                     font=("Arial", 12))
        self.btn_gps.pack(side="left", padx=(0, 5))
        ToolTip(self.btn_gps, "Start/stop live GPS tracking")

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
        ToolTip(self.btn_manual, "Set manual coordinates and validate offline via GeoDude")

        self.btn_calibrate = ctk.CTkButton(method_frame, text="Calibrate Wi‑Fi",
                                           command=self._on_calibrate_wifi,
                                           width=120,
                                           fg_color="transparent",
                                           border_width=1, border_color=COLORS["gold"],
                                           text_color=COLORS["gold"],
                                           hover_color=COLORS["gold"],
                                           font=("Arial", 12))
        self.btn_calibrate.pack(side="left", padx=5)
        ToolTip(self.btn_calibrate, "Use the manual lat/lon as the seed for the Wi‑Fi database (clears old DB)")

        # New: Submit to BeaconDB button
        self.btn_submit = ctk.CTkButton(method_frame, text="Submit to BeaconDB",
                                        command=self._on_submit_beacondb,
                                        width=140,
                                        fg_color="transparent",
                                        border_width=1, border_color=COLORS["accent"],
                                        text_color=COLORS["accent"],
                                        hover_color=COLORS["accent_hover"],
                                        font=("Arial", 12))
        self.btn_submit.pack(side="left", padx=5)
        ToolTip(self.btn_submit, "Upload current Wi‑Fi scan and GPS coordinates to BeaconDB (contribute data)")

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
        This calculator uses BeaconDB (free online Wi‑Fi geolocation),
        an offline Wi‑Fi database, or manual coordinates to obtain your
        location, then calculates magnetic declination using GeoDude's
        built‑in WMM2025 model.

        Locate & Calculate – One‑press button:
           1. Tries BeaconDB (free, no API key, ~150 m accuracy)
           2. Falls back to offline Wi‑Fi database
           3. Falls back to IP geolocation

        Calibrate Wi‑Fi – seed the offline database with manual coordinates.
        Manual – enter coordinates directly, validated by GeoDude.
        GPS – live serial GPS tracking.

        Submit to BeaconDB – contribute your Wi‑Fi scan and GPS coordinates
        to the BeaconDB database so others (and you) can benefit later.

        No online address lookup is performed.
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
    # Reverse geocoding – direct call to geodude singleton
    # ------------------------------------------------------------------
    def _reverse_geocode(self, lat, lon):
        self.console.append(f"Reverse geocoding {lat:.6f}, {lon:.6f}...")
        if self.use_geodude and self.geodude:
            place = self.geodude.get_nearest(lat, lon)
            if place:
                addr = place["address"]
                self.console.append(f"GeoDude ADM3 returned: {addr}")
                return addr
        self.console.append("No address found (GeoDude unavailable or no result).")
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
    # Manual location setting
    # ------------------------------------------------------------------
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
        self._set_status("Validating address via GeoDude...", "info")
        addr = self._reverse_geocode(lat, lon)
        if addr:
            detail, level = self._extract_address_detail(addr)
            self._set_precision("Exact (manual input)", f"Validated: {detail[:100]}")
            self._set_status(f"Coordinates validated. Nearest: {addr}", "success")
        else:
            self._set_precision("Exact (manual input)", "Address not found")
            self._set_status("Coordinates set. No address found.", "info")

    # ------------------------------------------------------------------
    # IP location (fallback)
    # ------------------------------------------------------------------
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
    # Submit to BeaconDB
    # ------------------------------------------------------------------
    def _on_submit_beacondb(self):
        """Upload current Wi‑Fi scan + coordinates to BeaconDB."""
        if self.latitude is None or self.longitude is None:
            self._set_status("First set coordinates (Manual or GPS) before submitting.", "error")
            return
        scanner = WiFiScanner(self)
        bssids = scanner.scan()
        if not bssids:
            self._set_status("No Wi‑Fi networks visible to submit.", "error")
            return
        self._set_status("Submitting to BeaconDB...", "info")
        threading.Thread(target=self._submit_to_beacondb_worker, args=(bssids,), daemon=True).start()

    def _submit_to_beacondb_worker(self, bssids):
        url = "https://api.beacondb.net/v2/geosubmit"
        payload = {
            "items": [{
                "timestamp": int(time.time() * 1000),
                "position": {
                    "latitude": self.latitude,
                    "longitude": self.longitude,
                    "accuracy": 5.0
                },
                "wifiAccessPoints": [
                    {"macAddress": b, "signalStrength": -60} for b in bssids
                ]
            }]
        }
        headers = {"User-Agent": "MagneticDeclinationCalculator/1.0",
                   "Content-Type": "application/json"}
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            if resp.status_code == 200:
                self.after(0, lambda: self.console.append("BeaconDB submission accepted. Thank you!"))
                self.after(0, lambda: self._set_status("Submission successful.", "success"))
            else:
                self.after(0, lambda: self.console.append(f"BeaconDB submission failed (HTTP {resp.status_code})"))
                self.after(0, lambda: self._set_status(f"Submission failed (HTTP {resp.status_code})", "error"))
        except Exception as e:
            self.after(0, lambda: self.console.append(f"BeaconDB submission error: {e}"))
            self.after(0, lambda: self._set_status("Submission error. See console.", "error"))

    # ------------------------------------------------------------------
    # Calibrate Wi‑Fi button
    # ------------------------------------------------------------------
    def _on_calibrate_wifi(self):
        try:
            lat = float(self.entry_lat.get().strip())
            lon = float(self.entry_lon.get().strip())
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError
        except:
            self._set_status("Enter valid manual lat/lon first.", "error")
            return

        if WIFI_DB_PATH.exists():
            try:
                WIFI_DB_PATH.unlink()
                self.console.append("Old wifi_location.db deleted.")
            except Exception as e:
                self.console.append(f"Warning: could not delete wifi db: {e}")

        self._set_coordinates(lat, lon, "Calibrating Wi‑Fi", "Manual seed – rebuilding…")
        self._set_status("Rebuilding Wi‑Fi database with your manual coordinates…", "info")

        def rebuild():
            scanner = WiFiScanner(self)
            bssids = scanner.scan()
            if bssids:
                self._build_update_wifi_db(bssids, lat, lon)
                self.console.append("Wi‑Fi database rebuilt successfully.")
                self.after(0, lambda: self._set_status("Wi‑Fi database calibrated. You may now use Locate & Calculate.", "success"))
            else:
                self.after(0, lambda: self.console.append("No BSSIDs found; could not calibrate."))
                self.after(0, lambda: self._set_status("Calibration failed – no networks found.", "error"))

        threading.Thread(target=rebuild, daemon=True).start()

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

            scanner = WiFiScanner(self)
            bssids = scanner.scan()
            if bssids:
                self.console.append(f"Scanned {len(bssids)} BSSIDs.")

                # 1a. Try BeaconDB first (free, accurate)
                lat_b, lon_b, acc_b, reason = _locate_via_beacondb(bssids)
                if lat_b is not None:
                    self.console.append(f"BeaconDB returned: {lat_b:.6f}, {lon_b:.6f} (accuracy {acc_b:.0f} m)")
                    self.after(0, lambda: self._set_coordinates(lat_b, lon_b,
                                                            f"BeaconDB ({acc_b:.0f} m)",
                                                            "Wi‑Fi geolocation – BeaconDB"))
                    self.after(0, lambda: self._set_status(
                        f"Location via BeaconDB: {lat_b:.6f}, {lon_b:.6f} (±{acc_b:.0f} m)", "success"))
                    self.after(0, self._on_calculate)
                    self.after(0, self._finish_processing)
                    return
                else:
                    self.console.append(f"BeaconDB lookup failed: {reason}")

                # 1b. Try local Wi‑Fi database
                if WIFI_DB_PATH.exists():
                    location = scanner.get_location(WIFI_DB_PATH)
                    if location:
                        lat, lon = location
                        self.after(0, lambda: self._set_coordinates(lat, lon, "Wi‑Fi Location (100‑500 m)", "Offline database"))
                        self.after(0, lambda: self._set_status(f"Location via offline Wi‑Fi DB: {lat:.6f}, {lon:.6f}", "success"))
                        self.console.append(f"Offline Wi‑Fi DB returned: {lat:.6f}, {lon:.6f}")
                        self.after(0, self._on_calculate)
                        self.after(0, self._finish_processing)
                        return

            # 2. Fallback to IP geolocation
            ip_loc = self._get_ip_location()
            if ip_loc:
                lat, lon, desc = ip_loc
                self.after(0, lambda: self._set_coordinates(lat, lon, "IP (5‑50 km)", desc))
                self.after(0, lambda: self._set_status(f"Using IP location: {lat:.6f}, {lon:.6f}", "warning"))
                self.console.append(f"IP geolocation returned: {lat:.6f}, {lon:.6f}")
                self.after(0, self._on_calculate)
            else:
                self.console.append("All location methods failed.")
                self.after(0, lambda: self._set_status("Unable to determine location. Try manual input.", "error"))
            self.after(0, self._finish_processing)
        except Exception as e:
            self.console.append(f"Fatal error in workflow: {e}")
            self.after(0, lambda: self._set_status("An error occurred. See console.", "error"))
            self.after(0, self._finish_processing)

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

    def _finish_processing(self):
        self.btn_locate.configure(state="normal", text="Locate & Calculate Declination")
        self.processing = False

    def _on_calculate(self):
        if self.latitude is None or self.longitude is None:
            self._set_status("Please set a location first.", "error")
            return
        self._set_status("Calculating declination...", "info")
        try:
            d = declination(self.latitude, self.longitude, 0)
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
        import customtkinter, requests
    except ImportError as e:
        print(f"Missing dependency: {e}", file=sys.stderr)
        print("pip install customtkinter requests", file=sys.stderr)
        sys.exit(1)
    app = App()
    app.mainloop()