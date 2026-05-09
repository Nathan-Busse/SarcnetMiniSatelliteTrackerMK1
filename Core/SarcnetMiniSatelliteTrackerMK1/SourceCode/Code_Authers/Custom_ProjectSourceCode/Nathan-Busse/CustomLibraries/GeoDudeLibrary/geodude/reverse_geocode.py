#!/usr/bin/env python3
"""
Magnetic Declination Calculator
Uses GeoDude (ADM3 polygon boundaries) for offline reverse geocoding.
No admin required – Wi‑Fi scanning works without elevation on Windows.
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
# GeoDude setup (your own library)
# ----------------------------------------------------------------------
BASE_DIR = Path(__file__).parent

# Adjust this to the folder that CONTAINS the 'geodude' package
CUSTOM_LIBS = BASE_DIR / ".." / "CustomLibraries" / "GeoDudeLibrary"
CUSTOM_LIBS = CUSTOM_LIBS.resolve()
sys.path.insert(0, str(CUSTOM_LIBS))

GEODUDE_AVAILABLE = False
geodude = None

try:
    from geodude import geodude as geodude_singleton

    # One‑time data installation (download + build)
    from importlib.resources import files
    DATA_DIR = files("geodude.data")          # resolves to geodude/data/
    if not (DATA_DIR / "data.db").exists() or not (DATA_DIR / "geo-boundaries.csv").exists():
        print("GeoDude data files missing. Running installer…")
        from geodude import install as install_data
        print("Installer finished.")

    # Thin adapter that gives the app its expected interface
    class GeodudeAdapter:
        def __init__(self):
            self.g = geodude_singleton()

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

    geodude = GeodudeAdapter()
    GEODUDE_AVAILABLE = True
    print("GeoDude loaded and ready.")
except Exception as e:
    print(f"GeoDude could not be loaded: {e}")
    GEODUDE_AVAILABLE = False
    geodude = None

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
# Wi‑Fi Scanner (unchanged)
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
# GPS Reader (unchanged)
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

        self.geodude = geodude
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
            self._set_status("Online reverse geocoding only (GeoDude not loaded).", "warning")
            self.lbl_geodude.configure(text="Offline GeoDude ADM3: Not loaded (using online)",
                                       text_color=COLORS["gold"])

    # ------------------------------------------------------------------
    # (Window management, UI creation, Geocoding, Workflow etc. –
    #  identical to previous clean version, using self.geodude and self.use_geodude)
    # ------------------------------------------------------------------
    #
    #  The full implementation of _maximize_window, _toggle_fullscreen,
    #  _create_widgets, _set_status, _set_precision, _set_coordinates,
    #  _show_help, _nominatim_forward, _nominatim_reverse, _forward_geocode,
    #  _reverse_geocode, _extract_address_detail, _on_get_from_address,
    #  _on_set_manual, _get_ip_location, _check_wifi_adapter_status,
    #  _toggle_gps, _on_gps_update, _on_locate_and_calculate,
    #  _locate_workflow, _try_wifi_location, _build_update_wifi_db,
    #  _after_location, _finish_processing, _on_calculate, _highlight_result
    #  is exactly the same as in the last full clean script.
    #
    #  For brevity, I am not repeating them here – they are unchanged.
    #  Just copy them from any of the recent “full clean script” responses.

    # ... [rest of App methods unchanged] ...

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