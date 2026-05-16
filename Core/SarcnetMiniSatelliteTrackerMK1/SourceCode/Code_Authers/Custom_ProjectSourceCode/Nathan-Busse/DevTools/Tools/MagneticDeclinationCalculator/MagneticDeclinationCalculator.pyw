#!/usr/bin/env python3
"""
Rotator7 Control Center v3.0 — Arduino Nano + GY‑511 + WiFi‑IP geolocation
===========================================================================
Full‑featured interface:
  - Real‑time data streaming (debug / monitor / calibration) with live plots
  - Calibration assistant with step‑by‑step guidance
  - EEPROM read / write / clear
  - Macro recording, playback, and editing
  - CSV data logging
  - Declination calculator (offline GeoDude)
  - Wi‑Fi scanning, BeaconDB, offline DB, IP geolocation, manual coords, GPS
  - Custom command terminal with history
  - Persistent configuration, appearance themes
  - Comprehensive error handling and reconnection
"""

import os, sys, locale, threading, time, datetime, sqlite3, subprocess, re, json, platform, queue
from pathlib import Path
import csv
import logging
from logging.handlers import RotatingFileHandler
import webbrowser
from typing import Optional, Tuple, List, Callable, Dict, Any, Union

import customtkinter as ctk
import requests

# -------------------------- Serial / GPS imports --------------------------
try:
    import serial
    import serial.tools.list_ports
    import pynmea2
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

# -------------------------- GeoDude (declination) --------------------------
BASE_DIR = Path(__file__).resolve().parent
GEODUDE_LIB_DIR = (BASE_DIR / ".." / ".." / ".." / "CustomLibraries" / "GeoDudeLibrary").resolve()
sys.path.insert(0, str(GEODUDE_LIB_DIR))
try:
    from geodude import fetch_db
    from geodude.geomag_calc import declination
    g_instance = fetch_db()
    GEODUDE_AVAILABLE = True
except Exception:
    GEODUDE_AVAILABLE = False
    declination = lambda lat, lon, alt: 0.0   # fallback
    g_instance = None

# -------------------------- Matplotlib (live plots) --------------------------
try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    MPL_AVAILABLE = True
except ImportError:
    MPL_AVAILABLE = False

# -------------------------- Constants --------------------------
APP_TITLE = "Rotator7 Control Center v3.0"
DEFAULT_BAUD = 115200
CONFIG_PATH = BASE_DIR / "rotator_config.json"
LOG_DIR = BASE_DIR / "logs"
MACRO_DIR = BASE_DIR / "macros"
WIFI_DB_PATH = BASE_DIR / "wifi_location.db"
HISTORY_SIZE = 300

COLORS = {
    "bg": "#0d1117",
    "card_bg": "#161b22",
    "card_border": "#30363d",
    "accent": "#2ea043",
    "accent_hover": "#238636",
    "secondary": "#8250df",
    "secondary_hover": "#6b3fc0",
    "gold": "#f0c040",
    "text_primary": "#c9d1d9",
    "text_secondary": "#8b949e",
    "danger": "#da3633",
    "danger_hover": "#b62324"
}

# -------------------------- Logging Setup --------------------------
LOG_DIR.mkdir(exist_ok=True)
logger = logging.getLogger("Rotator7")
logger.setLevel(logging.DEBUG)
fh = RotatingFileHandler(LOG_DIR / "rotator.log", maxBytes=2*1024*1024, backupCount=3)
fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(fh)

# -------------------------- Utility Functions --------------------------
def _safe_float(val, default=0.0):
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

# -------------------------- Serial Port Enumerator --------------------------
class SerialPortEnumerator:
    @staticmethod
    def list_ports():
        if not SERIAL_AVAILABLE:
            return []
        return [p.device for p in serial.tools.list_ports.comports()]

# -------------------------- Configuration Manager --------------------------
class ConfigManager:
    def __init__(self, path=CONFIG_PATH):
        self.path = path
        self.defaults = {
            "port": "",
            "baud": DEFAULT_BAUD,
            "appearance": "Dark",
            "color_theme": "dark-blue",
            "window_geometry": "1200x850",
            "declination": 0.0,
            "last_lat": None,
            "last_lon": None,
            "logging_enabled": False,
            "auto_reconnect": False
        }
        self.data = self.load()

    def load(self):
        if self.path.exists():
            try:
                with open(self.path) as f:
                    cfg = json.load(f)
                merged = self.defaults.copy()
                merged.update(cfg)
                return merged
            except:
                return self.defaults.copy()
        return self.defaults.copy()

    def save(self):
        with open(self.path, 'w') as f:
            json.dump(self.data, f, indent=2)

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        self.save()

# -------------------------- Command History (Ring Buffer) --------------------------
class CommandHistory:
    def __init__(self, maxsize=HISTORY_SIZE):
        self.buffer = []
        self.maxsize = maxsize
        self.index = -1

    def add(self, cmd):
        if cmd and (not self.buffer or self.buffer[-1] != cmd):
            self.buffer.append(cmd)
            if len(self.buffer) > self.maxsize:
                self.buffer.pop(0)
        self.index = len(self.buffer)

    def up(self, current=""):
        if not self.buffer:
            return current
        if self.index > 0:
            self.index -= 1
        return self.buffer[self.index]

    def down(self, current=""):
        if self.index < len(self.buffer):
            self.index += 1
        if self.index >= len(self.buffer):
            return ""
        return self.buffer[self.index]

# -------------------------- Data Logger (CSV) --------------------------
class DataLogger:
    def __init__(self, log_dir=LOG_DIR):
        self.log_dir = log_dir
        self.log_dir.mkdir(exist_ok=True)
        self.filename = None
        self.file = None
        self.writer = None
        self.mode = None

    def start(self, mode, prefix="rotator7"):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filename = self.log_dir / f"{prefix}_{mode}_{timestamp}.csv"
        self.mode = mode
        self.file = open(self.filename, 'w', newline='')
        self.writer = csv.writer(self.file)
        if mode == "debug":
            self.writer.writerow(["timestamp", "mx", "my", "mz", "gx", "gy", "gz"])
        elif mode == "monitor":
            self.writer.writerow(["timestamp", "az", "el", "azSet", "elSet", "azWindup", "azError", "elError"])
        elif mode == "calibration":
            self.writer.writerow([
                "timestamp", "sample_idx", "meanX", "meanY", "meanZ",
                "minX", "maxX", "minY", "maxY", "minZ", "maxZ",
                "offsetX", "offsetY", "offsetZ", "scaleX", "scaleY", "scaleZ"
            ])
        else:
            self.writer.writerow(["timestamp", "raw"])
        logger.info(f"Logging started: {self.filename}")

    def log(self, *values):
        if self.writer:
            self.writer.writerow([datetime.datetime.now().isoformat()] + list(values))

    def stop(self):
        if self.file:
            self.file.close()
            self.file = None
            self.writer = None
            logger.info(f"Logging stopped: {self.filename}")
            self.filename = None

# -------------------------- WiFi Scanner --------------------------
class WiFiScanner:
    def __init__(self, log_func=None):
        self.log = log_func or logger.info
        self.bssids = []
        self.platform = platform.system()
        self.raw_output = ""

    def scan(self) -> List[str]:
        self.bssids = []
        self.raw_output = ""
        try:
            if self.platform == "Windows":
                cmds = [
                    ['netsh', 'wlan', 'show', 'networks', 'mode=bssid'],
                    ['netsh', 'wlan', 'show', 'networks', 'mode=bssid', 'format=list']
                ]
                for cmd in cmds:
                    res = self._try_command(cmd)
                    if res:
                        self.raw_output = res
                        break
                if not self.raw_output:
                    self.log("netsh failed")
                    return []

            elif self.platform == "Linux":
                cmds = [['sudo', 'iwlist', 'scan'], ['iwlist', 'scan']]
                for cmd in cmds:
                    res = self._try_command(cmd)
                    if res:
                        self.raw_output = res
                        break
                if not self.raw_output:
                    self.log("iwlist failed")
                    return []

            elif self.platform == "Darwin":
                cmds = [
                    ['airport', '-s'],
                    ['/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport', '-s']
                ]
                for cmd in cmds:
                    res = self._try_command(cmd)
                    if res:
                        self.raw_output = res
                        break
                if not self.raw_output:
                    self.log("airport failed")
                    return []

        except Exception as e:
            self.log(f"Scan error: {e}")
            return []

        if self.raw_output:
            self.log(f"Raw scan captured ({len(self.raw_output)} chars)")
        return self._extract_bssids()

    def _try_command(self, command: list) -> Optional[str]:
        try:
            proc = subprocess.run(command, capture_output=True, text=True, timeout=10)
            if proc.returncode == 0 and proc.stdout.strip():
                return proc.stdout
        except Exception:
            pass
        return None

    def _extract_bssids(self) -> List[str]:
        patterns = [
            r'BSSID\s+\d+\s+:\s+(([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})',
            r'BSSID\s+:\s+(([0-9A-Fa-f]{2}-){5}[0-9A-Fa-f]{2})',
            r'BSSID\s+:\s+(([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})',
            r'Address: (([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})',
            r'(([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})',
            r'(([0-9A-Fa-f]{2}[: -]){5}[0-9A-Fa-f]{2})'
        ]
        for i, pat in enumerate(patterns, 1):
            matches = re.findall(pat, self.raw_output)
            if matches:
                self.bssids = [m[0].replace('-', ':').upper() for m in matches]
                self.log(f"Pattern #{i} matched, found {len(self.bssids)} BSSIDs")
                return self.bssids
        self.log("No BSSID pattern matched")
        return []

    def get_location_from_db(self, db_path: Path) -> Optional[Tuple[float, float]]:
        if not self.bssids or not db_path.exists():
            return None
        try:
            with sqlite3.connect(str(db_path)) as conn:
                cur = conn.cursor()
                locs = []
                for b in self.bssids:
                    cur.execute('SELECT lat, lon FROM access_points WHERE bssid = ?', (b,))
                    row = cur.fetchone()
                    if row:
                        locs.append((row[0], row[1]))
                if locs:
                    avg_lat = sum(lat for lat, lon in locs) / len(locs)
                    avg_lon = sum(lon for lat, lon in locs) / len(locs)
                    return avg_lat, avg_lon
        except Exception as e:
            self.log(f"DB lookup error: {e}")
        return None

# -------------------------- BeaconDB Client --------------------------
class BeaconDBClient:
    @staticmethod
    def geolocate(bssids: list) -> Tuple[Optional[float], Optional[float], Optional[float], str]:
        if not bssids:
            return None, None, None, "No BSSIDs"
        url = "https://api.beacondb.net/v1/geolocate"
        payload = {
            "wifiAccessPoints": [{"macAddress": b, "signalStrength": -70} for b in bssids[:10]],
            "considerIp": False
        }
        headers = {"User-Agent": "Rotator7ControlCenter/3.0"}
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=5)
            if r.status_code == 200:
                data = r.json()
                loc = data.get("location", {})
                if "lat" in loc and "lng" in loc:
                    return loc["lat"], loc["lng"], data.get("accuracy", 150), "success"
                return None, None, None, "200 but no location"
            elif r.status_code == 404:
                return None, None, None, "404 – no data for these BSSIDs"
            else:
                return None, None, None, f"Error {r.status_code}"
        except Exception:
            return None, None, None, "Network error"

    @staticmethod
    def submit(bssids: list, lat: float, lon: float, callback: Callable[[str], None]):
        url = "https://api.beacondb.net/v2/geosubmit"
        payload = {
            "reports": [{
                "timestamp": int(time.time() * 1000),
                "position": {"latitude": lat, "longitude": lon, "accuracy": 5},
                "wifiAccessPoints": [{"macAddress": b, "signalStrength": -70, "channel": 0, "frequency": 0} for b in bssids]
            }]
        }
        headers = {"User-Agent": "Rotator7ControlCenter/3.0", "Content-Type": "application/json"}
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=10)
            if r.status_code == 200:
                callback("Success – data accepted")
            else:
                callback(f"HTTP {r.status_code}")
        except Exception as e:
            callback(f"Error: {str(e)[:20]}")

# -------------------------- IP Geolocation --------------------------
def get_ip_location():
    try:
        r = requests.get('http://ip-api.com/json/', timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data.get('status') == 'success':
                lat = float(data['lat'])
                lon = float(data['lon'])
                desc = f"{data.get('city','?')}, {data.get('country','?')}"
                return lat, lon, desc
    except:
        pass
    return None, None, None

# -------------------------- Arduino Interface (Rotator7 Protocol) --------------------------
if SERIAL_AVAILABLE:
    class Rotator7Controller:
        def __init__(self, port=None, baudrate=DEFAULT_BAUD, timeout=0.5):
            self.port = port
            self.baudrate = baudrate
            self.timeout = timeout
            self.ser = None
            self.is_connected = False
            self.lock = threading.Lock()
            self.buffer = ""
            # Callbacks
            self.on_raw_line = None
            self.on_debug = None
            self.on_monitor = None
            self.on_calibration = None
            self.on_status = None

        def connect(self, port=None, baudrate=None):
            if port:
                self.port = port
            if baudrate:
                self.baudrate = baudrate
            if not self.port:
                raise ValueError("No port specified")
            self.ser = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            self.is_connected = True
            logger.info(f"Connected to {self.port} @ {self.baudrate}")
            self._notify_status(f"Connected {self.port}")
            self._start_reader()

        def disconnect(self):
            with self.lock:
                if self.ser and self.ser.is_open:
                    self.ser.close()
                self.is_connected = False
            logger.info("Disconnected")
            self._notify_status("Disconnected")

        def send_raw(self, cmd: str):
            if not self.is_connected:
                raise ConnectionError("Not connected")
            with self.lock:
                self.ser.write((cmd + "\r").encode("utf-8"))
                self.ser.flush()
            logger.debug(f"Sent: {cmd}")

        # Predefined commands
        def send_help(self):              self.send_raw("h")
        def set_declination(self, dec):   self.send_raw(f"e{dec:.2f}")
        def start_calibration(self):      self.send_raw("c")
        def save_eeprom(self):            self.send_raw("s")
        def abort(self):                  self.send_raw("a")
        def reset(self):                  self.send_raw("r")
        def start_debug(self):            self.send_raw("b")
        def start_monitor(self):          self.send_raw("m")
        def pause(self):                  self.send_raw("p")
        def start_demo(self):             self.send_raw("d")
        def set_position(self, az, el):   self.send_raw(f"{az:.1f} {el:.1f}")
        def read_eeprom(self):            self.send_raw("R")
        def clear_eeprom(self):           self.send_raw("X")

        def _start_reader(self):
            self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
            self._reader_thread.start()

        def _reader_loop(self):
            while self.is_connected:
                try:
                    if self.ser.in_waiting > 0:
                        data = self.ser.read(self.ser.in_waiting)
                        self.buffer += data.decode("utf-8", errors="replace")
                        while "\n" in self.buffer:
                            line, self.buffer = self.buffer.split("\n", 1)
                            line = line.strip()
                            if line:
                                self._process_line(line)
                    else:
                        time.sleep(0.01)
                except (serial.SerialException, OSError):
                    self.is_connected = False
                    self._notify_status("Connection lost")
                    logger.warning("Serial connection lost")
                    break
                except Exception as e:
                    logger.error(f"Reader error: {e}")
                    break

        def _process_line(self, line: str):
            if self.on_raw_line:
                self.on_raw_line(line)

            parts = line.split(",")
            # Debug mode: 6 floats
            if len(parts) == 6:
                try:
                    vals = [float(p) for p in parts]
                    if self.on_debug:
                        self.on_debug(*vals)
                    return
                except ValueError:
                    pass
            # Monitor mode: 8 fields
            if len(parts) == 8:
                try:
                    d = {
                        "az": float(parts[0]),
                        "el": float(parts[1]),
                        "azSet": float(parts[2]),
                        "elSet": float(parts[3]),
                        "azWindup": float(parts[4]),
                        "azError": float(parts[5]),
                        "elError": float(parts[6]),
                        "windup": parts[7] == "1"
                    }
                    if self.on_monitor:
                        self.on_monitor(d)
                    return
                except ValueError:
                    pass
            # Calibration mode: 13 fields (example)
            if len(parts) == 13:
                try:
                    numbers = [float(p) for p in parts]
                    if self.on_calibration:
                        self.on_calibration(numbers)
                    return
                except ValueError:
                    pass
            if self.on_status:
                self.on_status(line)

        def _notify_status(self, msg):
            if self.on_status:
                self.on_status(f"[SYS] {msg}")
else:
    class Rotator7Controller:
        def __init__(self, *args, **kwargs):
            raise ImportError("pyserial not installed")

# -------------------------- Live Plot Frame --------------------------
if MPL_AVAILABLE:
    class LivePlotFrame(ctk.CTkFrame):
        def __init__(self, master, title="Plot", ylabel="Value", max_points=200):
            super().__init__(master, fg_color=COLORS["card_bg"], corner_radius=8, border_width=1,
                             border_color=COLORS["card_border"])
            self.max_points = max_points
            self.data_buffers = {}
            self.timestamps = []
            self.fig = Figure(figsize=(5, 2.5), dpi=100, facecolor=COLORS["card_bg"])
            self.ax = self.fig.add_subplot(111)
            self.ax.set_title(title, color=COLORS["text_primary"], fontsize=10)
            self.ax.set_ylabel(ylabel, color=COLORS["text_secondary"])
            self.ax.set_xlabel("Time (s)", color=COLORS["text_secondary"])
            self.ax.grid(True, alpha=0.3, color=COLORS["card_border"])
            self.ax.set_facecolor(COLORS["card_bg"])
            self.ax.tick_params(colors=COLORS["text_secondary"])

            self.canvas = FigureCanvasTkAgg(self.fig, master=self)
            self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=5, pady=5)

        def add_data(self, label, value):
            if label not in self.data_buffers:
                self.data_buffers[label] = []
            buf = self.data_buffers[label]
            buf.append(value)
            if len(buf) > self.max_points:
                buf.pop(0)
            if len(self.timestamps) == 0 or len(self.timestamps) < len(buf):
                self.timestamps.append(time.time())
            elif len(self.timestamps) > len(buf):
                self.timestamps.pop()
                self.timestamps.append(time.time())

        def refresh(self):
            self.ax.cla()
            self.ax.set_title(self.ax.get_title(), color=COLORS["text_primary"], fontsize=10)
            self.ax.set_ylabel(self.ax.get_ylabel(), color=COLORS["text_secondary"])
            self.ax.set_xlabel("Time (s)", color=COLORS["text_secondary"])
            self.ax.set_facecolor(COLORS["card_bg"])
            self.ax.grid(True, alpha=0.3, color=COLORS["card_border"])
            self.ax.tick_params(colors=COLORS["text_secondary"])
            colors = ["#ffaa00", "#00ccff", "#ff4444", "#44ff44", "#ff44ff", "#44ffff"]
            if not self.timestamps:
                return
            t0 = self.timestamps[0]
            rel_time = [(t - t0) for t in self.timestamps]
            for i, (label, buf) in enumerate(self.data_buffers.items()):
                if not buf:
                    continue
                plot_len = min(len(rel_time), len(buf))
                self.ax.plot(rel_time[:plot_len], buf[:plot_len], label=label,
                             linewidth=1.2, color=colors[i % len(colors)])
            if self.data_buffers:
                self.ax.legend(loc='upper right', fontsize=7, facecolor=COLORS["bg"], framealpha=0.8)
            self.canvas.draw()

        def clear(self):
            self.data_buffers.clear()
            self.timestamps.clear()
            self.refresh()
else:
    class LivePlotFrame(ctk.CTkFrame):
        def __init__(self, master, title="Plot", **kwargs):
            super().__init__(master, fg_color=COLORS["card_bg"], corner_radius=8)
            ctk.CTkLabel(self, text="Install 'matplotlib' for live plots",
                         text_color=COLORS["text_secondary"]).pack(expand=True)
        def add_data(self, *args): pass
        def refresh(self): pass
        def clear(self): pass

# -------------------------- Macros --------------------------
class MacroManager:
    def __init__(self, macro_dir=MACRO_DIR):
        self.macro_dir = macro_dir
        self.macro_dir.mkdir(exist_ok=True)

    def list_macros(self):
        return sorted([p.stem for p in self.macro_dir.glob("*.json")])

    def load_macro(self, name):
        path = self.macro_dir / f"{name}.json"
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return None

    def save_macro(self, name, commands):
        path = self.macro_dir / f"{name}.json"
        with open(path, 'w') as f:
            json.dump(commands, f, indent=2)

    def delete_macro(self, name):
        path = self.macro_dir / f"{name}.json"
        if path.exists():
            path.unlink()

# -------------------------- Calibration Assistant --------------------------
class CalibrationAssistant:
    def __init__(self, controller: Rotator7Controller, log_func: Callable[[str], None]):
        self.controller = controller
        self.log_func = log_func
        self.active = False
        self.steps = [
            "Place device flat (Z up)", "Rotate to left side", "Rotate to right side",
            "Tilt forward", "Tilt backward", "Rotate 180° (Z down)"
        ]
        self.current_step = 0

    def start(self):
        self.active = True
        self.current_step = 0
        self.log_func("Calibration assistant started.")
        self._next_step()

    def _next_step(self):
        if self.current_step < len(self.steps):
            self.log_func(f"Step {self.current_step+1}/{len(self.steps)}: {self.steps[self.current_step]}")
            self.log_func("Press 'Capture' when ready.")
        else:
            self.log_func("All steps captured. Saving to EEPROM...")
            self.controller.save_eeprom()
            self.active = False
            self.log_func("Calibration completed.")

    def capture_step(self):
        if not self.active:
            return
        self.controller.send_raw(f"T{self.current_step}")
        self.current_step += 1
        self._next_step()

    def abort(self):
        self.active = False
        self.controller.abort()
        self.log_func("Calibration aborted.")

# -------------------------- GUI Application --------------------------
class Rotator7App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.config = ConfigManager()
        self.geometry(self.config.get("window_geometry", "1200x850"))
        self.minsize(1000, 700)
        self.configure(fg_color=COLORS["bg"])
        ctk.set_appearance_mode(self.config.get("appearance", "Dark"))
        ctk.set_default_color_theme(self.config.get("color_theme", "dark-blue"))

        # Core services
        self.log_data = DataLogger()
        self.logging_active = False
        self.macro_manager = MacroManager()
        self.command_history = CommandHistory()

        # WiFi & location state
        self.wifi_scanner = WiFiScanner(log_func=self._console_log)
        self.latitude = self.config.get("last_lat")
        self.longitude = self.config.get("last_lon")

        # Serial controller
        self.controller = None
        if SERIAL_AVAILABLE:
            self.controller = Rotator7Controller()
            self.controller.on_raw_line = self._on_raw_line
            self.controller.on_debug = self._on_debug
            self.controller.on_monitor = self._on_monitor
            self.controller.on_calibration = self._on_calibration
            self.controller.on_status = self._on_status
        self.calib_assistant = CalibrationAssistant(self.controller, self._status_msg) if self.controller else None

        # Build GUI
        self._create_layout()
        self._setup_bindings()
        self._plot_update_loop()

        if self.config.get("auto_reconnect", False):
            self.auto_reconnect()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------- Layout ----------
    def _create_layout(self):
        # Top bar
        top_bar = ctk.CTkFrame(self, fg_color=COLORS["card_bg"], corner_radius=6)
        top_bar.pack(fill="x", padx=10, pady=(10,5))

        ctk.CTkLabel(top_bar, text="Port:", text_color=COLORS["text_secondary"]).pack(side="left", padx=5)
        self.port_var = ctk.StringVar(value=self.config.get("port", ""))
        self.port_combo = ctk.CTkComboBox(top_bar, values=SerialPortEnumerator.list_ports(),
                                          variable=self.port_var, width=120)
        self.port_combo.pack(side="left", padx=5)
        ctk.CTkButton(top_bar, text="↻", width=30, command=self._refresh_ports,
                      fg_color="transparent", border_width=1, border_color=COLORS["secondary"],
                      text_color=COLORS["secondary"]).pack(side="left")

        ctk.CTkLabel(top_bar, text="Baud:", text_color=COLORS["text_secondary"]).pack(side="left", padx=5)
        self.baud_var = ctk.StringVar(value=str(self.config.get("baud", DEFAULT_BAUD)))
        ctk.CTkComboBox(top_bar, values=["9600","19200","38400","57600","115200","230400"],
                        variable=self.baud_var, width=90).pack(side="left", padx=5)

        self.connect_btn = ctk.CTkButton(top_bar, text="Connect", command=self._toggle_connect,
                                         width=90, fg_color=COLORS["accent"])
        self.connect_btn.pack(side="left", padx=10)
        self.connection_status = ctk.CTkLabel(top_bar, text="Disconnected", text_color=COLORS["danger"])
        self.connection_status.pack(side="left", padx=10)

        self.logging_btn = ctk.CTkButton(top_bar, text="Start Log", command=self._toggle_logging,
                                         width=80, fg_color="transparent", border_width=1,
                                         border_color=COLORS["gold"], text_color=COLORS["gold"])
        self.logging_btn.pack(side="left", padx=10)

        ctk.CTkButton(top_bar, text="Reset", command=self._safe_command(self.controller.reset),
                      width=60, fg_color=COLORS["danger"]).pack(side="left", padx=5)
        ctk.CTkButton(top_bar, text="Help", command=self._safe_command(self.controller.send_help),
                      width=60, fg_color="transparent", border_width=1, border_color=COLORS["secondary"],
                      text_color=COLORS["secondary"]).pack(side="left", padx=5)

        # TabView
        self.tab_view = ctk.CTkTabview(self, fg_color="transparent")
        self.tab_view.pack(fill="both", expand=True, padx=10, pady=(0,10))

        self.tab_terminal = self.tab_view.add("Terminal")
        self.tab_debug = self.tab_view.add("Debug Stream")
        self.tab_monitor = self.tab_view.add("Monitor")
        self.tab_calib = self.tab_view.add("Calibration")
        self.tab_macros = self.tab_view.add("Macros")
        self.tab_location = self.tab_view.add("Location")
        self.tab_decl = self.tab_view.add("Declination")

        self._build_terminal_tab()
        self._build_debug_tab()
        self._build_monitor_tab()
        self._build_calib_tab()
        self._build_macros_tab()
        self._build_location_tab()      # Build location before declination
        self._build_declination_tab()   # Build declination last – its entries now exist

        # If we had saved coords, we already updated the location labels in _build_location_tab
        # Now that declination tab exists, sync those saved coords to its entry fields
        if self.latitude is not None:
            self._sync_declination_entries()

        # Status bar
        status_frame = ctk.CTkFrame(self, fg_color=COLORS["card_bg"], corner_radius=6)
        status_frame.pack(fill="x", padx=10, pady=(0,10))
        self.status_label = ctk.CTkLabel(status_frame, text="Ready", text_color=COLORS["text_secondary"])
        self.status_label.pack(side="left", padx=10)

    # ---------- Terminal Tab ----------
    def _build_terminal_tab(self):
        frame = ctk.CTkFrame(self.tab_terminal, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.terminal_output = ctk.CTkTextbox(frame, font=("Consolas", 11), fg_color="#0d1117",
                                              text_color="#c9d1d9", border_width=0, corner_radius=8)
        self.terminal_output.pack(fill="both", expand=True, pady=(0,5))

        input_frame = ctk.CTkFrame(frame, fg_color="transparent")
        input_frame.pack(fill="x")
        self.cmd_entry = ctk.CTkEntry(input_frame, font=("Consolas", 12), placeholder_text="Type command...")
        self.cmd_entry.pack(side="left", fill="x", expand=True, padx=(0,5))
        self.cmd_entry.bind("<Return>", self._send_command)
        self.cmd_entry.bind("<Up>", self._history_up)
        self.cmd_entry.bind("<Down>", self._history_down)

        ctk.CTkButton(input_frame, text="Send", command=self._send_command, width=60,
                      fg_color=COLORS["accent"]).pack(side="left")
        ctk.CTkButton(input_frame, text="Clear", command=lambda: self.terminal_output.delete("1.0","end"),
                      width=60, fg_color="transparent", border_width=1,
                      border_color=COLORS["secondary"], text_color=COLORS["secondary"]).pack(side="left", padx=5)

    # ---------- Debug Tab ----------
    def _build_debug_tab(self):
        frame = ctk.CTkFrame(self.tab_debug, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.debug_plot_mag = LivePlotFrame(frame, title="Magnetometer (mx, my, mz)", ylabel="Raw")
        self.debug_plot_mag.pack(fill="both", expand=True, pady=(0,5))

        self.debug_plot_gyro = LivePlotFrame(frame, title="Gyroscope (gx, gy, gz)", ylabel="Raw")
        self.debug_plot_gyro.pack(fill="both", expand=True, pady=(0,5))

        ctrl = ctk.CTkFrame(frame, fg_color="transparent")
        ctrl.pack(fill="x", pady=5)
        ctk.CTkButton(ctrl, text="Start Debug", command=self._safe_command(self.controller.start_debug),
                      width=100, fg_color=COLORS["accent"]).pack(side="left", padx=5)
        ctk.CTkButton(ctrl, text="Stop", command=self._safe_command(self.controller.pause),
                      width=60, fg_color=COLORS["danger"]).pack(side="left", padx=5)
        ctk.CTkButton(ctrl, text="Clear Plots", command=lambda: [self.debug_plot_mag.clear(), self.debug_plot_gyro.clear()],
                      width=80, fg_color="transparent", border_width=1, border_color=COLORS["secondary"],
                      text_color=COLORS["secondary"]).pack(side="left", padx=5)

    # ---------- Monitor Tab ----------
    def _build_monitor_tab(self):
        frame = ctk.CTkFrame(self.tab_monitor, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.monitor_plot = LivePlotFrame(frame, title="Angles (AZ / EL) vs Setpoint", ylabel="Degrees")
        self.monitor_plot.pack(fill="both", expand=True, pady=(0,5))

        ctrl = ctk.CTkFrame(frame, fg_color="transparent")
        ctrl.pack(fill="x", pady=5)
        ctk.CTkButton(ctrl, text="Start Monitor", command=self._safe_command(self.controller.start_monitor),
                      width=100, fg_color=COLORS["accent"]).pack(side="left", padx=5)
        ctk.CTkButton(ctrl, text="Stop", command=self._safe_command(self.controller.pause),
                      width=60, fg_color=COLORS["danger"]).pack(side="left", padx=5)
        ctk.CTkButton(ctrl, text="Demo", command=self._safe_command(self.controller.start_demo),
                      width=60, fg_color=COLORS["secondary"]).pack(side="left", padx=5)
        ctk.CTkButton(ctrl, text="Clear Plot", command=self.monitor_plot.clear,
                      width=80, fg_color="transparent", border_width=1, border_color=COLORS["secondary"],
                      text_color=COLORS["secondary"]).pack(side="left", padx=5)

        pos_frame = ctk.CTkFrame(frame, fg_color="transparent")
        pos_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(pos_frame, text="AZ:", text_color=COLORS["text_secondary"]).pack(side="left")
        self.az_entry = ctk.CTkEntry(pos_frame, width=60); self.az_entry.pack(side="left", padx=5)
        ctk.CTkLabel(pos_frame, text="EL:", text_color=COLORS["text_secondary"]).pack(side="left")
        self.el_entry = ctk.CTkEntry(pos_frame, width=60); self.el_entry.pack(side="left", padx=5)
        ctk.CTkButton(pos_frame, text="Set Position", command=self._set_position,
                      width=100, fg_color=COLORS["secondary"]).pack(side="left", padx=10)

    # ---------- Calibration Tab ----------
    def _build_calib_tab(self):
        frame = ctk.CTkFrame(self.tab_calib, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.calib_output = ctk.CTkTextbox(frame, height=8, font=("Consolas", 10),
                                           fg_color="#0d1117", text_color="#c9d1d9",
                                           border_width=0, corner_radius=8)
        self.calib_output.pack(fill="both", expand=True)

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=5)
        ctk.CTkButton(btn_frame, text="Start Calibration", command=self._start_calib,
                      width=120, fg_color=COLORS["accent"]).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Capture Step", command=self._capture_calib_step,
                      width=100, fg_color=COLORS["gold"], text_color="black").pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Save EEPROM", command=self._safe_command(self.controller.save_eeprom),
                      width=100, fg_color=COLORS["secondary"]).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Abort", command=self._abort_calib,
                      width=60, fg_color=COLORS["danger"]).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Read EEPROM", command=self._safe_command(self.controller.read_eeprom),
                      width=100, fg_color="transparent", border_width=1,
                      border_color=COLORS["secondary"], text_color=COLORS["secondary"]).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Clear EEPROM", command=self._safe_command(self.controller.clear_eeprom),
                      width=100, fg_color="transparent", border_width=1,
                      border_color=COLORS["danger"], text_color=COLORS["danger"]).pack(side="left", padx=5)

    # ---------- Macros Tab ----------
    def _build_macros_tab(self):
        frame = ctk.CTkFrame(self.tab_macros, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=10, pady=5)

        list_frame = ctk.CTkFrame(frame, fg_color="transparent")
        list_frame.pack(side="left", fill="y", padx=(0,10))
        ctk.CTkLabel(list_frame, text="Saved Macros", font=("Arial",12,"bold"),
                     text_color=COLORS["text_primary"]).pack(anchor="w", pady=(0,5))
        self.macro_listbox = ctk.CTkTextbox(list_frame, width=200, height=300,
                                            font=("Consolas",10), fg_color="#0d1117",
                                            text_color="#c9d1d9", border_width=0, corner_radius=6)
        self.macro_listbox.pack(fill="both", expand=True)
        self._refresh_macro_list()

        editor_frame = ctk.CTkFrame(frame, fg_color="transparent")
        editor_frame.pack(side="left", fill="both", expand=True)
        ctk.CTkLabel(editor_frame, text="Macro Commands (one per line)", text_color=COLORS["text_secondary"]).pack(anchor="w")
        self.macro_editor = ctk.CTkTextbox(editor_frame, font=("Consolas",10),
                                           fg_color="#0d1117", text_color="#c9d1d9",
                                           border_width=0, corner_radius=6)
        self.macro_editor.pack(fill="both", expand=True, pady=(0,5))

        btn_frame = ctk.CTkFrame(editor_frame, fg_color="transparent")
        btn_frame.pack(fill="x")
        self.macro_name_entry = ctk.CTkEntry(btn_frame, placeholder_text="Macro name", width=120)
        self.macro_name_entry.pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Load", command=self._load_macro, width=60,
                      fg_color="transparent", border_width=1, border_color=COLORS["secondary"],
                      text_color=COLORS["secondary"]).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="Save", command=self._save_macro, width=60,
                      fg_color=COLORS["accent"]).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="Delete", command=self._delete_macro, width=60,
                      fg_color=COLORS["danger"]).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="Run", command=self._run_macro, width=60,
                      fg_color=COLORS["gold"], text_color="black").pack(side="left", padx=2)

    # ---------- Location Tab (WiFi, BeaconDB, offline DB, IP, GPS, manual) ----------
    def _build_location_tab(self):
        frame = ctk.CTkFrame(self.tab_location, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Console for location logs
        self.location_console = ctk.CTkTextbox(frame, height=6, font=("Consolas", 10),
                                               fg_color="#0d1117", text_color="#c9d1d9",
                                               border_width=0, corner_radius=8)
        self.location_console.pack(fill="both", expand=True, pady=(0,5))

        # Info card with coordinates
        info_card = ctk.CTkFrame(frame, fg_color=COLORS["card_bg"], corner_radius=8)
        info_card.pack(fill="x", pady=5, ipady=5)
        ctk.CTkLabel(info_card, text="Current Coordinates", font=("Arial",14,"bold"),
                     text_color=COLORS["text_primary"]).pack(anchor="w", padx=10, pady=(5,0))
        self.lbl_coords = ctk.CTkLabel(info_card, text="Not set", text_color=COLORS["text_secondary"])
        self.lbl_coords.pack(anchor="w", padx=10, pady=2)
        self.lbl_precision = ctk.CTkLabel(info_card, text="Source: –", text_color=COLORS["text_secondary"])
        self.lbl_precision.pack(anchor="w", padx=10, pady=(0,5))

        # Buttons row 1
        btn_row1 = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row1.pack(fill="x", pady=5)
        ctk.CTkButton(btn_row1, text="Auto-Locate", command=self._auto_locate,
                      width=120, fg_color=COLORS["accent"]).pack(side="left", padx=5)
        ctk.CTkButton(btn_row1, text="GPS", command=self._toggle_gps,
                      width=80, fg_color=COLORS["secondary"]).pack(side="left", padx=5)
        ctk.CTkButton(btn_row1, text="Manual", command=self._manual_coords,
                      width=80, fg_color="transparent", border_width=1,
                      border_color=COLORS["secondary"], text_color=COLORS["secondary"]).pack(side="left", padx=5)
        ctk.CTkButton(btn_row1, text="Calibrate Wi‑Fi", command=self._calibrate_wifi_popup,
                      width=120, fg_color="transparent", border_width=1,
                      border_color=COLORS["gold"], text_color=COLORS["gold"]).pack(side="left", padx=5)

        # Buttons row 2
        btn_row2 = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row2.pack(fill="x", pady=5)
        ctk.CTkButton(btn_row2, text="Submit to BeaconDB", command=self._submit_beacondb,
                      width=140, fg_color="transparent", border_width=1,
                      border_color=COLORS["accent"], text_color=COLORS["accent"]).pack(side="left", padx=5)
        ctk.CTkButton(btn_row2, text="Show on Map", command=self._show_on_map,
                      width=100, fg_color="transparent", border_width=1,
                      border_color=COLORS["secondary"], text_color=COLORS["secondary"]).pack(side="left", padx=5)
        ctk.CTkButton(btn_row2, text="Send to Rotator", command=self._send_location_decl,
                      width=120, fg_color=COLORS["gold"], text_color="black").pack(side="left", padx=5)

        # Update location labels if saved coords exist – do NOT touch declination entries here
        if self.latitude is not None and self.longitude is not None:
            self.lbl_coords.configure(text=f"Lat: {self.latitude:.6f}  Lon: {self.longitude:.6f}")
            self.lbl_precision.configure(text="Source: Saved")

    # ---------- Declination Tab (manual calculator + GPS) ----------
    def _build_declination_tab(self):
        frame = ctk.CTkFrame(self.tab_decl, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=10, pady=5)

        info_frame = ctk.CTkFrame(frame, fg_color=COLORS["card_bg"], corner_radius=8)
        info_frame.pack(fill="x", pady=5, padx=10, ipady=10)
        ctk.CTkLabel(info_frame, text="Declination Calculator", font=("Arial",14,"bold"),
                     text_color=COLORS["text_primary"]).pack(anchor="w", padx=10, pady=(5,0))
        self.lat_entry = ctk.CTkEntry(info_frame, placeholder_text="Latitude", width=120)
        self.lat_entry.pack(side="left", padx=10, pady=10)
        self.lon_entry = ctk.CTkEntry(info_frame, placeholder_text="Longitude", width=120)
        self.lon_entry.pack(side="left", padx=10, pady=10)
        ctk.CTkButton(info_frame, text="Calculate", command=self._calc_declination,
                      width=80, fg_color=COLORS["accent"]).pack(side="left", padx=10)
        self.decl_result = ctk.CTkLabel(info_frame, text="?", font=("Arial",18,"bold"),
                                        text_color=COLORS["gold"])
        self.decl_result.pack(side="left", padx=10)

        ctk.CTkButton(info_frame, text="Send to Rotator", command=self._send_decl_to_rotator,
                      width=120, fg_color=COLORS["secondary"]).pack(side="left", padx=10)

        # Use .get() for config access
        last_lat = self.config.get("last_lat")
        last_lon = self.config.get("last_lon")
        if last_lat is not None:
            self.lat_entry.insert(0, str(last_lat))
        if last_lon is not None:
            self.lon_entry.insert(0, str(last_lon))

        if SERIAL_AVAILABLE:
            ctk.CTkButton(info_frame, text="GPS", command=self._gps_get_coords,
                          width=60, fg_color="transparent", border_width=1,
                          border_color=COLORS["secondary"], text_color=COLORS["secondary"]).pack(side="left", padx=10)

    # ---------- Helper to sync saved coords into declination entries after both tabs built ----------
    def _sync_declination_entries(self):
        if hasattr(self, 'lat_entry') and hasattr(self, 'lon_entry'):
            self.lat_entry.delete(0, "end")
            self.lon_entry.delete(0, "end")
            if self.latitude is not None:
                self.lat_entry.insert(0, f"{self.latitude:.6f}")
            if self.longitude is not None:
                self.lon_entry.insert(0, f"{self.longitude:.6f}")
            self._calc_declination()

    # ---------- Bindings ----------
    def _setup_bindings(self):
        self.bind("<F5>", lambda e: self._refresh_ports())
        self.bind("<Control-l>", lambda e: self._toggle_logging())
        self.bind("<Control-r>", lambda e: self._safe_command(self.controller.reset)())

    # ---------- Plot update timer ----------
    def _plot_update_loop(self):
        if hasattr(self, 'debug_plot_mag'):
            self.debug_plot_mag.refresh()
            self.debug_plot_gyro.refresh()
            self.monitor_plot.refresh()
        self.after(100, self._plot_update_loop)

    # ---------- Console log helper for location tab ----------
    def _console_log(self, msg):
        self.after(0, lambda: self.location_console.insert("end", msg + "\n"))
        self.after(0, lambda: self.location_console.see("end"))

    # ---------- Serial callbacks ----------
    def _on_raw_line(self, line):
        self.after(0, lambda: self.terminal_output.insert("end", line + "\n"))
        self.after(0, lambda: self.terminal_output.see("end"))
        if self.logging_active:
            self.log_data.log(line)

    def _on_debug(self, mx, my, mz, gx, gy, gz):
        self.after(0, lambda: self._update_debug_plots(mx, my, mz, gx, gy, gz))
        if self.logging_active and self.log_data.mode == "debug":
            self.log_data.log(mx, my, mz, gx, gy, gz)

    def _update_debug_plots(self, mx, my, mz, gx, gy, gz):
        self.debug_plot_mag.add_data("mx", mx)
        self.debug_plot_mag.add_data("my", my)
        self.debug_plot_mag.add_data("mz", mz)
        self.debug_plot_gyro.add_data("gx", gx)
        self.debug_plot_gyro.add_data("gy", gy)
        self.debug_plot_gyro.add_data("gz", gz)

    def _on_monitor(self, d):
        self.after(0, lambda: self._update_monitor_plot(d))
        if self.logging_active and self.log_data.mode == "monitor":
            self.log_data.log(d["az"], d["el"], d["azSet"], d["elSet"],
                              d["azWindup"], d["azError"], d["elError"])

    def _update_monitor_plot(self, d):
        self.monitor_plot.add_data("AZ", d["az"])
        self.monitor_plot.add_data("EL", d["el"])
        self.monitor_plot.add_data("AZ_set", d["azSet"])
        self.monitor_plot.add_data("EL_set", d["elSet"])

    def _on_calibration(self, data):
        self.after(0, lambda: self.calib_output.insert("end", f"Calib data: {data}\n"))
        if self.logging_active and self.log_data.mode == "calibration":
            self.log_data.log(*data)

    def _on_status(self, msg):
        self.after(0, lambda: self._status_msg(msg))

    def _status_msg(self, msg):
        self.status_label.configure(text=msg)

    # ---------- Connection toggle ----------
    def _toggle_connect(self):
        if self.controller and self.controller.is_connected:
            self.controller.disconnect()
            self.connect_btn.configure(text="Connect", fg_color=COLORS["accent"])
            self.connection_status.configure(text="Disconnected", text_color=COLORS["danger"])
        else:
            port = self.port_var.get()
            baud = int(self.baud_var.get())
            if not port:
                self._status_msg("Select a port")
                return
            try:
                self.controller.connect(port, baud)
                self.connect_btn.configure(text="Disconnect", fg_color=COLORS["danger"])
                self.connection_status.configure(text=f"Connected @ {baud}", text_color=COLORS["accent"])
                self.config.set("port", port)
                self.config.set("baud", baud)
            except Exception as e:
                self._status_msg(f"Connection error: {e}")

    def _refresh_ports(self):
        ports = SerialPortEnumerator.list_ports()
        self.port_combo.configure(values=ports)

    def _toggle_logging(self):
        if self.logging_active:
            self.log_data.stop()
            self.logging_btn.configure(text="Start Log", text_color=COLORS["gold"])
            self.logging_active = False
            self._status_msg("Logging stopped")
        else:
            mode = "raw"
            self.log_data.start(mode)
            self.logging_btn.configure(text="Stop Log", text_color=COLORS["danger"])
            self.logging_active = True
            self._status_msg(f"Logging started ({mode})")

    def _send_command(self, event=None):
        cmd = self.cmd_entry.get().strip()
        if not cmd:
            return
        self.command_history.add(cmd)
        self._safe_command(lambda: self.controller.send_raw(cmd))()
        self.cmd_entry.delete(0, "end")

    def _history_up(self, event):
        self.cmd_entry.delete(0, "end")
        self.cmd_entry.insert(0, self.command_history.up())
    def _history_down(self, event):
        self.cmd_entry.delete(0, "end")
        self.cmd_entry.insert(0, self.command_history.down())

    def _safe_command(self, func):
        def wrapper():
            if not self.controller or not self.controller.is_connected:
                self._status_msg("Not connected")
                return
            try:
                func()
            except Exception as e:
                self._status_msg(f"Error: {e}")
        return wrapper

    def _set_position(self):
        try:
            az = float(self.az_entry.get())
            el = float(self.el_entry.get())
            self._safe_command(lambda: self.controller.set_position(az, el))()
        except ValueError:
            self._status_msg("Invalid AZ/EL")

    def _start_calib(self):
        if self.calib_assistant:
            self.calib_assistant.start()

    def _capture_calib_step(self):
        if self.calib_assistant:
            self.calib_assistant.capture_step()

    def _abort_calib(self):
        if self.calib_assistant:
            self.calib_assistant.abort()

    # ---------- Macro management ----------
    def _refresh_macro_list(self):
        self.macro_listbox.delete("1.0", "end")
        for name in self.macro_manager.list_macros():
            self.macro_listbox.insert("end", name + "\n")

    def _load_macro(self):
        name = self.macro_name_entry.get().strip()
        if not name:
            return
        macro = self.macro_manager.load_macro(name)
        if macro:
            self.macro_editor.delete("1.0", "end")
            self.macro_editor.insert("1.0", "\n".join(macro))
            self._status_msg(f"Loaded macro '{name}'")
        else:
            self._status_msg("Macro not found")

    def _save_macro(self):
        name = self.macro_name_entry.get().strip()
        if not name:
            return
        commands = self.macro_editor.get("1.0", "end").strip().split("\n")
        commands = [c.strip() for c in commands if c.strip()]
        self.macro_manager.save_macro(name, commands)
        self._refresh_macro_list()
        self._status_msg(f"Saved macro '{name}'")

    def _delete_macro(self):
        name = self.macro_name_entry.get().strip()
        if not name:
            return
        self.macro_manager.delete_macro(name)
        self._refresh_macro_list()
        self._status_msg(f"Deleted macro '{name}'")

    def _run_macro(self):
        name = self.macro_name_entry.get().strip()
        macro = self.macro_manager.load_macro(name) if name else None
        if not macro:
            self._status_msg("No macro loaded")
            return
        def execute():
            for cmd in macro:
                if not self.controller or not self.controller.is_connected:
                    break
                self.controller.send_raw(cmd)
                time.sleep(0.2)
            self.after(0, lambda: self._status_msg("Macro finished"))
        threading.Thread(target=execute, daemon=True).start()

    # ---------- Location helpers ----------
    def _update_coord_display(self, lat, lon, source, detail=""):
        """Update all coordinate displays (location tab labels + declination tab entries if they exist)."""
        self.latitude = lat
        self.longitude = lon
        self.config.set("last_lat", lat)
        self.config.set("last_lon", lon)
        # Update location tab labels
        self.lbl_coords.configure(text=f"Lat: {lat:.6f}  Lon: {lon:.6f}")
        self.lbl_precision.configure(text=f"Source: {source}{' (' + detail + ')' if detail else ''}")
        # Update declination tab entries if they exist (may not be built yet)
        if hasattr(self, 'lat_entry') and hasattr(self, 'lon_entry'):
            self.lat_entry.delete(0, "end")
            self.lon_entry.delete(0, "end")
            self.lat_entry.insert(0, f"{lat:.6f}")
            self.lon_entry.insert(0, f"{lon:.6f}")
        # Calculate declination if possible
        if hasattr(self, 'decl_result'):
            self._calc_declination()

    def _auto_locate(self):
        self._console_log("Starting auto-locate...")
        threading.Thread(target=self._auto_locate_thread, daemon=True).start()

    def _auto_locate_thread(self):
        # 1. WiFi scan
        bssids = self.wifi_scanner.scan()
        if bssids:
            self._console_log(f"Found {len(bssids)} BSSIDs")
            # 2. BeaconDB
            lat, lon, acc, status = BeaconDBClient.geolocate(bssids)
            if lat is not None:
                self.after(0, lambda: self._update_coord_display(lat, lon, "BeaconDB", f"±{acc:.0f}m"))
                self._console_log(f"BeaconDB success: {lat:.6f}, {lon:.6f}")
                return
            else:
                self._console_log(f"BeaconDB failed: {status}")
            # 3. Offline DB
            loc = self.wifi_scanner.get_location_from_db(WIFI_DB_PATH)
            if loc:
                self.after(0, lambda: self._update_coord_display(loc[0], loc[1], "Offline DB"))
                self._console_log("Offline DB success")
                return
        # 4. IP geolocation
        ip_lat, ip_lon, desc = get_ip_location()
        if ip_lat is not None:
            self.after(0, lambda: self._update_coord_display(ip_lat, ip_lon, "IP Geolocation", desc))
            self._console_log(f"IP geolocation: {desc}")
        else:
            self._console_log("All methods failed")
            self.after(0, lambda: self._status_msg("Unable to locate"))

    def _toggle_gps(self):
        if not SERIAL_AVAILABLE:
            self._status_msg("pyserial not installed")
            return
        def gps_thread():
            gps = GPSReader()
            port = gps.find_gps_port()
            if not port:
                self.after(0, lambda: self._status_msg("No GPS device"))
                return
            self._console_log(f"GPS found on {port}")
            def update(lat, lon, q):
                self.after(0, lambda: self._update_coord_display(lat, lon, "GPS", f"fix={q}"))
                gps.stop_reading()
            gps.start_reading(update, baud=9600)
        threading.Thread(target=gps_thread, daemon=True).start()

    def _manual_coords(self):
        popup = ctk.CTkToplevel(self)
        popup.title("Manual Coordinates")
        popup.geometry("300x200")
        popup.configure(fg_color=COLORS["bg"])
        popup.transient(self)
        popup.grab_set()
        ctk.CTkLabel(popup, text="Enter coordinates:", text_color=COLORS["text_primary"]).pack(pady=10)
        e1 = ctk.CTkEntry(popup, placeholder_text="Latitude"); e1.pack(pady=5)
        e2 = ctk.CTkEntry(popup, placeholder_text="Longitude"); e2.pack(pady=5)
        def set_manual():
            try:
                lat = float(e1.get())
                lon = float(e2.get())
                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    raise ValueError
                self._update_coord_display(lat, lon, "Manual")
                popup.destroy()
            except:
                self._status_msg("Invalid coordinates")
        ctk.CTkButton(popup, text="Set", command=set_manual, fg_color=COLORS["accent"]).pack(pady=10)

    def _calibrate_wifi_popup(self):
        popup = ctk.CTkToplevel(self)
        popup.title("Calibrate Wi‑Fi")
        popup.geometry("350x220")
        popup.configure(fg_color=COLORS["bg"])
        popup.transient(self)
        popup.grab_set()
        ctk.CTkLabel(popup, text="Enter exact coordinates:", text_color=COLORS["text_primary"]).pack(pady=5)
        e1 = ctk.CTkEntry(popup, placeholder_text="Latitude"); e1.pack(pady=5)
        e1.insert(0, f"{self.latitude:.6f}" if self.latitude else "")
        e2 = ctk.CTkEntry(popup, placeholder_text="Longitude"); e2.pack(pady=5)
        e2.insert(0, f"{self.longitude:.6f}" if self.longitude else "")
        def do_calibrate():
            try:
                lat = float(e1.get())
                lon = float(e2.get())
                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    raise ValueError
                popup.destroy()
                threading.Thread(target=self._calibrate_wifi_thread, args=(lat, lon), daemon=True).start()
            except:
                self._status_msg("Invalid coordinates")
        ctk.CTkButton(popup, text="Calibrate", command=do_calibrate, fg_color=COLORS["gold"]).pack(pady=10)

    def _calibrate_wifi_thread(self, lat, lon):
        if WIFI_DB_PATH.exists():
            WIFI_DB_PATH.unlink()
        scanner = WiFiScanner(log_func=self._console_log)
        bssids = scanner.scan()
        if not bssids:
            self._console_log("No WiFi networks found for calibration")
            return
        with sqlite3.connect(str(WIFI_DB_PATH)) as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS access_points (bssid TEXT PRIMARY KEY, lat REAL, lon REAL, timestamp INTEGER)')
            conn.executemany('INSERT OR REPLACE INTO access_points VALUES (?,?,?,?)',
                             [(b, lat, lon, int(time.time())) for b in bssids])
        self._console_log(f"Wi‑Fi database rebuilt with {len(bssids)} APs")
        self.after(0, lambda: self._status_msg("Wi‑Fi calibrated"))

    def _submit_beacondb(self):
        if self.latitude is None:
            self._status_msg("No coordinates")
            return
        bssids = self.wifi_scanner.scan()
        if not bssids:
            self._status_msg("No WiFi networks")
            return
        def cb(msg):
            self._console_log(f"BeaconDB submit: {msg}")
        threading.Thread(target=lambda: BeaconDBClient.submit(bssids, self.latitude, self.longitude, cb), daemon=True).start()

    def _show_on_map(self):
        if self.latitude is not None:
            url = f"https://www.openstreetmap.org/?mlat={self.latitude}&mlon={self.longitude}#map=15/{self.latitude}/{self.longitude}"
            webbrowser.open(url)

    def _send_location_decl(self):
        if self.latitude is None:
            self._status_msg("Locate first")
            return
        try:
            dec = declination(self.latitude, self.longitude, 0)
            self._safe_command(lambda: self.controller.set_declination(dec))()
            self._status_msg(f"Sent declination {dec:.2f}° to rotator")
        except Exception as e:
            self._status_msg(f"Error: {e}")

    # ---------- Declination tab manual calc ----------
    def _calc_declination(self):
        try:
            lat = float(self.lat_entry.get())
            lon = float(self.lon_entry.get())
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError
            dec = declination(lat, lon, 0)
            self.decl_result.configure(text=f"{dec:.2f}°")
        except:
            pass

    def _send_decl_to_rotator(self):
        dec_str = self.decl_result.cget("text").replace("°", "")
        try:
            dec = float(dec_str)
            self._safe_command(lambda: self.controller.set_declination(dec))()
        except:
            self._status_msg("Calculate declination first")

    def _gps_get_coords(self):
        if not SERIAL_AVAILABLE:
            self._status_msg("pyserial not installed")
            return
        def gps_thread():
            gps = GPSReader()
            port = gps.find_gps_port()
            if not port:
                self.after(0, lambda: self._status_msg("No GPS device"))
                return
            def update(lat, lon, q):
                self.after(0, lambda: self.lat_entry.delete(0, "end") or self.lat_entry.insert(0, f"{lat:.6f}"))
                self.after(0, lambda: self.lon_entry.delete(0, "end") or self.lon_entry.insert(0, f"{lon:.6f}"))
                gps.stop_reading()
            gps.start_reading(update, baud=9600)
        threading.Thread(target=gps_thread, daemon=True).start()

    # ---------- Auto-reconnect ----------
    def auto_reconnect(self):
        port = self.config.get("port")
        baud = self.config.get("baud", DEFAULT_BAUD)
        if port and port in SerialPortEnumerator.list_ports():
            try:
                self.controller.connect(port, baud)
                self.connect_btn.configure(text="Disconnect", fg_color=COLORS["danger"])
                self.connection_status.configure(text=f"Connected @ {baud}", text_color=COLORS["accent"])
            except:
                pass

    # ---------- Cleanup ----------
    def _on_close(self):
        if self.controller and self.controller.is_connected:
            self.controller.disconnect()
        if self.logging_active:
            self.log_data.stop()
        self.config.set("window_geometry", self.geometry())
        self.config.save()
        self.destroy()

# -------------------------- GPS Reader (simple) --------------------------
if SERIAL_AVAILABLE:
    class GPSReader:
        def __init__(self):
            self.serial_port = None
            self.reading = False

        def find_gps_port(self, baud=9600):
            for port in serial.tools.list_ports.comports():
                try:
                    ser = serial.Serial(port.device, baud, timeout=1)
                    for _ in range(10):
                        line = ser.readline().decode('ascii', errors='replace').strip()
                        if line.startswith('$GPGGA') or line.startswith('$GNGGA'):
                            ser.close()
                            return port.device
                    ser.close()
                except:
                    continue
            return None

        def start_reading(self, callback, baud=9600):
            port = self.find_gps_port(baud)
            if not port:
                return False
            self.serial_port = serial.Serial(port, baud, timeout=2)
            self.reading = True
            threading.Thread(target=self._read_loop, args=(callback,), daemon=True).start()
            return True

        def _read_loop(self, callback):
            while self.reading:
                try:
                    line = self.serial_port.readline().decode('ascii', errors='replace').strip()
                    if line.startswith('$GPGGA') or line.startswith('$GNGGA'):
                        msg = pynmea2.parse(line)
                        if msg.latitude and msg.longitude:
                            callback(float(msg.latitude), float(msg.longitude), msg.gps_qual)
                            break
                except:
                    continue

        def stop_reading(self):
            self.reading = False
            if self.serial_port:
                try:
                    self.serial_port.close()
                except:
                    pass

# -------------------------- Main Entry --------------------------
if __name__ == "__main__":
    app = Rotator7App()
    app.mainloop()