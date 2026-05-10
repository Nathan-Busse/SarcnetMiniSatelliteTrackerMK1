#!/usr/bin/env python3
"""
Magnetic Declination Calculator – Popup Edition (Borderless, Centered)
Uses GeoDude (ADM3 reverse geocoding), built‑in WMM2025, and BeaconDB.
Wi‑Fi MACs are normalized to uppercase for BeaconDB submission validity.
"""

import os, sys, locale, threading, time, datetime, sqlite3, subprocess, re, json, platform
from pathlib import Path

os.environ["CHARSET_NORMALIZER_SKIP_CACHE"] = "1"
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"
try:
    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
except:
    pass

import customtkinter as ctk
import requests

try:
    import serial, serial.tools.list_ports, pynmea2
    GPS_AVAILABLE = True
except ImportError:
    GPS_AVAILABLE = False

# --------------------------- GeoDude setup ---------------------------
BASE_DIR = Path(__file__).resolve().parent
GEODUDE_LIB_DIR = (BASE_DIR / ".." / ".." / ".." / "CustomLibraries" / "GeoDudeLibrary").resolve()
sys.path.insert(0, str(GEODUDE_LIB_DIR))

from geodude import fetch_db
from geodude.geomag_calc import declination

try:
    g_instance = fetch_db()
    GEODUDE_AVAILABLE = True
except Exception as e:
    print(f"GeoDude could not be loaded: {e}")
    GEODUDE_AVAILABLE = False
    g_instance = None

# --------------------------- Constants ---------------------------
APP_TITLE = "Magnetic Declination Calculator"
DEFAULT_APPEARANCE = "Dark"
DEFAULT_THEME = "dark-blue"
WIFI_DB_PATH = BASE_DIR / "wifi_location.db"

COLORS = {
    "bg": "#1a1a1a", "card_bg": "#242424", "card_border": "#3a3a3a",
    "accent": "#2a7a3a", "accent_hover": "#1e5e2e", "secondary": "#8a2be2",
    "secondary_hover": "#6a1fa0", "gold": "#f0c040", "text_primary": "#ffffff",
    "text_secondary": "#b0b0b0", "danger": "#d32f2f", "danger_hover": "#b71c1c"
}

# --------------------------- Tooltip ---------------------------
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget; self.text = text; self.tip_window = None
        widget.bind("<Enter>", self.show_tip); widget.bind("<Leave>", self.hide_tip)
    def show_tip(self, event=None):
        if self.tip_window: return
        x = self.widget.winfo_rootx() + 25; y = self.widget.winfo_rooty() + 25
        self.tip_window = tw = ctk.CTkToplevel(self.widget)
        tw.wm_overrideredirect(True); tw.wm_geometry(f"+{x}+{y}")
        ctk.CTkLabel(tw, text=self.text, justify="left", padx=10, pady=8,
                     fg_color="#333333", text_color="white", corner_radius=8).pack()
    def hide_tip(self, event=None):
        if self.tip_window: self.tip_window.destroy(); self.tip_window = None

# --------------------------- Console Panel ---------------------------
class ConsolePanel(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(fg_color=COLORS["card_bg"], corner_radius=12, border_width=1, border_color=COLORS["card_border"])
        ctk.CTkLabel(self, text="Console Output", font=("Arial",12,"bold"), text_color=COLORS["text_primary"]).pack(anchor="w", padx=10, pady=(5,2))
        self.console_text = ctk.CTkTextbox(self, height=120, font=("Consolas",10), fg_color="#1e1e1e", text_color="#d4d4d4", border_width=0, corner_radius=8)
        self.console_text.pack(fill="both", expand=True, padx=10, pady=5)
        self.copy_btn = ctk.CTkButton(self, text="Copy Console", command=self._copy_console, width=100, fg_color="#555555", hover_color="#666666", font=("Arial",10))
        self.copy_btn.pack(anchor="e", padx=10, pady=(0,5))
        self.messages = []
    def append(self, message):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.messages.append(f"[{ts}] {message}\n")
        self.console_text.insert("end", f"[{ts}] {message}\n")
        self.console_text.see("end")
    def clear(self):
        self.messages.clear(); self.console_text.delete("1.0", "end")
    def _copy_console(self):
        self.clipboard_clear(); self.clipboard_append(self.console_text.get("1.0","end"))
        self.copy_btn.configure(text="Copied!", text_color="#4caf50")
        self.after(2000, lambda: self.copy_btn.configure(text="Copy Console", text_color="white"))

# --------------------------- WiFi Scanner (uppercased BSSIDs) ---------------------------
class WiFiScanner:
    def __init__(self, parent_app): self.parent_app = parent_app; self.bssids = []; self.platform = platform.system(); self.raw_output = ""
    def scan(self):
        self.bssids = []; self.raw_output = ""
        try:
            if self.platform == "Windows":
                cmds = [['netsh','wlan','show','networks','mode=bssid'], ['netsh','wlan','show','networks','mode=bssid','format=list']]
                for cmd in cmds:
                    try:
                        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                        if res.returncode == 0: self.raw_output = res.stdout; break
                    except: continue
                if not self.raw_output: self.parent_app.console.append("Failed to run netsh commands."); return []
            elif self.platform == "Linux":
                cmds = [['sudo','iwlist','scan'],['iwlist','scan']]
                for cmd in cmds:
                    try:
                        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                        if res.returncode == 0: self.raw_output = res.stdout; break
                    except: continue
                if not self.raw_output: self.parent_app.console.append("Failed to run iwlist commands."); return []
            elif self.platform == "Darwin":
                cmds = [['airport','-s'],['/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport','-s']]
                for cmd in cmds:
                    try:
                        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                        if res.returncode == 0: self.raw_output = res.stdout; break
                    except: continue
                if not self.raw_output: self.parent_app.console.append("Failed to run airport command."); return []
        except Exception as e: self.parent_app.console.append(f"Wi‑Fi scan error: {e}"); return []
        self.parent_app.console.append(f"Raw Wi‑Fi scan (first 500 chars):\n{self.raw_output[:500]}...")
        patterns = [r'BSSID\s+\d+\s+:\s+(([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})', r'BSSID\s+:\s+(([0-9A-Fa-f]{2}-){5}[0-9A-Fa-f]{2})', r'BSSID\s+:\s+(([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})', r'Address: (([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})', r'(([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})', r'(([0-9A-Fa-f]{2}[: -]){5}[0-9A-Fa-f]{2})']
        for i, p in enumerate(patterns, 1):
            matches = re.findall(p, self.raw_output)
            if matches:
                self.bssids = [m[0].replace('-',':').upper() for m in matches]   # ← uppercased
                self.parent_app.console.append(f"Pattern #{i} matched, found {len(self.bssids)} BSSIDs.")
                return self.bssids
        self.parent_app.console.append("No regex pattern matched."); return []
    def get_location(self, db_path):
        if not self.bssids: return None
        if not db_path.exists(): return None
        try:
            conn = sqlite3.connect(str(db_path)); cur = conn.cursor(); locs = []
            for b in self.bssids:
                cur.execute('SELECT lat, lon FROM access_points WHERE bssid = ?', (b,))
                row = cur.fetchone()
                if row: locs.append((row[0], row[1]))
            conn.close()
            if not locs: return None
            return sum(lat for lat, lon in locs)/len(locs), sum(lon for lat, lon in locs)/len(locs)
        except Exception as e: self.parent_app.console.append(f"Wi‑Fi DB error: {e}"); return None

# --------------------------- GPS Reader ---------------------------
class GPSReader:
    def __init__(self, parent_app): self.parent_app = parent_app; self.serial_port = None; self.reading = False
    def find_gps_port(self):
        if not GPS_AVAILABLE: return None
        try:
            for port in serial.tools.list_ports.comports():
                try:
                    ser = serial.Serial(port.device, 9600, timeout=1)
                    for _ in range(10):
                        line = ser.readline().decode('ascii', errors='replace').strip()
                        if line.startswith('$GPGGA') or line.startswith('$GNGGA'): ser.close(); return port.device
                    ser.close()
                except: continue
        except: pass
        return None
    def start_reading(self, callback):
        if not GPS_AVAILABLE: self.parent_app._set_status("GPS libs missing. pip install pyserial pynmea2","error"); return False
        port = self.find_gps_port()
        if not port: self.parent_app._set_status("No GPS device found.","error"); return False
        try:
            self.serial_port = serial.Serial(port, 9600, timeout=2); self.reading = True
            threading.Thread(target=self._read_loop, args=(callback,), daemon=True).start()
            self.parent_app._set_status(f"GPS connected on {port}","success")
            return True
        except Exception as e: self.parent_app._set_status(f"GPS error: {str(e)}","error"); return False
    def _read_loop(self, callback):
        while self.reading:
            try:
                line = self.serial_port.readline().decode('ascii', errors='replace').strip()
                if line.startswith('$GPGGA') or line.startswith('$GNGGA'):
                    msg = pynmea2.parse(line)
                    if msg.latitude and msg.longitude:
                        self.parent_app.after(0, lambda: callback(float(msg.latitude), float(msg.longitude), msg.gps_qual))
            except (pynmea2.ParseError, UnicodeDecodeError, ValueError, TypeError): continue
            except serial.SerialException: break
    def stop_reading(self):
        self.reading = False
        if self.serial_port:
            try: self.serial_port.close()
            except: pass

# --------------------------- BeaconDB helpers ---------------------------
def _locate_via_beacondb(bssids):
    url = "https://api.beacondb.net/v1/geolocate"
    payload = {"wifiAccessPoints": [{"macAddress":b,"signalStrength":-70} for b in bssids[:10]], "considerIp": False}
    headers = {"User-Agent":"MagneticDeclinationCalculator/1.0"}
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json(); loc = data.get("location",{})
            if "lat" in loc and "lng" in loc: return loc["lat"], loc["lng"], data.get("accuracy",150.0), "success"
            else: return None,None,None,"200 OK but missing location"
        elif resp.status_code == 404: return None,None,None,"404 – no data for these BSSIDs"
        else: return None,None,None,f"Error {resp.status_code}"
    except requests.exceptions.Timeout: return None,None,None,"Timeout"
    except requests.exceptions.ConnectionError: return None,None,None,"Connection error"
    except Exception as e: return None,None,None,f"Unexpected: {str(e)}"

def _submit_beacondb(bssids, lat, lon, status_callback):
    url = "https://api.beacondb.net/v1/geosubmit"
    payload = {
        "items": [{
            "timestamp": int(time.time() * 1000),
            "position": {"latitude": lat, "longitude": lon, "accuracy": 5.0},
            "wifiAccessPoints": [{"macAddress": b, "signalStrength": -70} for b in bssids]
        }]
    }
    headers = {"User-Agent": "MagneticDeclinationCalculator/1.0", "Content-Type": "application/json"}
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        if resp.status_code == 200:
            status_callback("Success – data accepted by BeaconDB")
        else:
            status_callback(f"HTTP {resp.status_code} – check console")
    except Exception as e:
        status_callback(f"Error: {str(e)[:20]}")

# --------------------------- Helper to center a borderless popup ---------------------------
def _center_popup(popup, w, h):
    popup.update_idletasks()
    sw = popup.winfo_screenwidth(); sh = popup.winfo_screenheight()
    x = (sw - w) // 2; y = (sh - h) // 2
    popup.geometry(f"{w}x{h}+{x}+{y}")

# --------------------------- App with Popups ---------------------------
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE); self.geometry("800x700"); self.minsize(700,500)
        self.configure(fg_color=COLORS["bg"])
        ctk.set_appearance_mode(DEFAULT_APPEARANCE); ctk.set_default_color_theme(DEFAULT_THEME)
        self._maximize_window()
        self.bind("<F11>", self._toggle_fullscreen)
        self.is_fullscreen = False; self.prev_geometry = ""

        self.latitude = None; self.longitude = None
        self.geodude = g_instance; self.use_geodude = GEODUDE_AVAILABLE
        self.gps_reader = GPSReader(self); self.gps_active = False
        self.ip_location = None; self.processing = False

        self._create_main_ui()
        self.after(100, self._update_geodude_label)

    # ---- Window management ----
    def _maximize_window(self):
        s = platform.system()
        if s == "Windows": self.state('zoomed')
        elif s == "Darwin": self.attributes('-zoomed', True)
        else: self.state('zoomed')
    def _toggle_fullscreen(self, event=None):
        if self.is_fullscreen:
            self.attributes('-fullscreen', False); self.is_fullscreen = False
            if self.prev_geometry: self.geometry(self.prev_geometry)
        else:
            self.prev_geometry = self.geometry(); self.attributes('-fullscreen', True); self.is_fullscreen = True

    # ---- Main UI ----
    def _create_main_ui(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Header
        hdr = ctk.CTkFrame(frame, fg_color="transparent")
        hdr.pack(fill="x", pady=(0,15))
        ctk.CTkLabel(hdr, text="Magnetic Declination Calculator", font=("Arial",24,"bold"),
                     text_color=COLORS["text_primary"]).pack(side="left")
        self.btn_help = ctk.CTkButton(hdr, text="Help", command=self._show_help,
                                      width=60, fg_color="transparent", hover_color=COLORS["card_bg"],
                                      text_color=COLORS["text_secondary"], font=("Arial",12))
        self.btn_help.pack(side="right")

        # Console
        self.console = ConsolePanel(frame)
        self.console.pack(fill="x", pady=(0,10))

        # Info card: Coordinates + Precision + GeoDude status
        info_card = ctk.CTkFrame(frame, fg_color=COLORS["card_bg"], corner_radius=12,
                                 border_width=1, border_color=COLORS["card_border"])
        info_card.pack(fill="x", pady=(0,10))
        ctk.CTkLabel(info_card, text="Current Coordinates", font=("Arial",14,"bold"),
                     text_color=COLORS["text_primary"]).pack(anchor="w", padx=15, pady=(10,5))
        self.lbl_coords = ctk.CTkLabel(info_card, text="Not set", font=("Arial",13),
                                       text_color=COLORS["text_secondary"])
        self.lbl_coords.pack(anchor="w", padx=15, pady=2)
        self.lbl_precision = ctk.CTkLabel(info_card, text="Precision: Not set", font=("Arial",12),
                                          text_color="#888888")
        self.lbl_precision.pack(anchor="w", padx=15, pady=2)
        self.lbl_geodude = ctk.CTkLabel(info_card, text="Offline GeoDude ADM3: Initializing...",
                                        font=("Arial",11), text_color="#888888")
        self.lbl_geodude.pack(anchor="w", padx=15, pady=(0,5))

        # Result card
        result_card = ctk.CTkFrame(frame, fg_color=COLORS["card_bg"], corner_radius=12,
                                   border_width=1, border_color=COLORS["card_border"])
        result_card.pack(fill="x", pady=(0,10))
        ctk.CTkLabel(result_card, text="Declination Result", font=("Arial",14,"bold"),
                     text_color=COLORS["text_primary"]).pack(anchor="w", padx=15, pady=(10,5))
        self.lbl_result = ctk.CTkEntry(result_card, font=("Arial",18,"bold"), text_color=COLORS["gold"],
                                       border_width=0, fg_color=COLORS["card_bg"], justify="center",
                                       state="readonly", width=300)
        self.lbl_result.insert(0, "Declination: 0.00°"); self.lbl_result.pack(pady=10)
        ToolTip(self.lbl_result, "Double-click to copy")

        # Action buttons
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=10)

        self.btn_locate = ctk.CTkButton(btn_frame, text="Locate & Calculate", command=self._open_locate_popup,
                                        width=160, fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"])
        self.btn_locate.pack(side="left", padx=5)

        self.btn_gps = ctk.CTkButton(btn_frame, text="GPS", command=self._open_gps_popup,
                                     width=80, fg_color=COLORS["secondary"], hover_color=COLORS["secondary_hover"])
        self.btn_gps.pack(side="left", padx=5)

        self.btn_manual = ctk.CTkButton(btn_frame, text="Set Manual", command=self._open_manual_popup,
                                        width=100, fg_color="transparent", border_width=1,
                                        border_color=COLORS["secondary"], text_color=COLORS["secondary"],
                                        hover_color=COLORS["secondary_hover"])
        self.btn_manual.pack(side="left", padx=5)

        self.btn_calibrate = ctk.CTkButton(btn_frame, text="Calibrate Wi‑Fi", command=self._open_calibrate_popup,
                                           width=120, fg_color="transparent", border_width=1,
                                           border_color=COLORS["gold"], text_color=COLORS["gold"],
                                           hover_color=COLORS["gold"])
        self.btn_calibrate.pack(side="left", padx=5)

        # Submit button + status indicator
        submit_frame = ctk.CTkFrame(btn_frame, fg_color="transparent")
        submit_frame.pack(side="left", padx=5)
        self.btn_submit = ctk.CTkButton(submit_frame, text="Submit to BeaconDB", command=self._open_submit_popup,
                                        width=140, fg_color="transparent", border_width=1,
                                        border_color=COLORS["accent"], text_color=COLORS["accent"],
                                        hover_color=COLORS["accent_hover"])
        self.btn_submit.pack(side="left")
        self.lbl_submit_status = ctk.CTkLabel(submit_frame, text="Ready", font=("Arial",10),
                                              text_color=COLORS["text_secondary"])
        self.lbl_submit_status.pack(side="left", padx=5)

        # Status bar
        self.lbl_status = ctk.CTkLabel(frame, text="Ready", font=("Arial",11), text_color="#888888")
        self.lbl_status.pack(side="left", padx=(10,0), pady=(5,0))

    def _update_geodude_label(self):
        if self.use_geodude:
            self._set_status("Offline GeoDude ADM3: Loaded", "success")
            self.lbl_geodude.configure(text="Offline GeoDude ADM3: Loaded", text_color=COLORS["accent"])
        else:
            self._set_status("GeoDude not loaded. Reverse geocoding unavailable.", "error")
            self.lbl_geodude.configure(text="Offline GeoDude ADM3: Not loaded", text_color=COLORS["danger"])

    def _set_status(self, msg, mtype="info"):
        colors = {"info":"#888888","success":COLORS["accent"],"error":COLORS["danger"],"warning":COLORS["gold"]}
        self.lbl_status.configure(text=msg, text_color=colors.get(mtype,"#888888"))

    def _set_precision(self, level, detail=""):
        self.lbl_precision.configure(text=f"Precision: {level}" + (f" ({detail})" if detail else ""))

    def _set_coordinates(self, lat, lon, level, detail=""):
        self.latitude = lat; self.longitude = lon
        self.lbl_coords.configure(text=f"Lat: {lat:.6f}  Lon: {lon:.6f}", text_color=COLORS["text_primary"])
        self._set_precision(level, detail)

    # ---------- Borderless, centered popup factory ----------
    def _create_borderless_popup(self, title, w, h):
        popup = ctk.CTkToplevel(self)
        popup.overrideredirect(True)
        popup.resizable(False, False)
        popup.configure(fg_color=COLORS["bg"])
        popup.attributes('-topmost', True)
        _center_popup(popup, w, h)
        title_lbl = ctk.CTkLabel(popup, text=title, font=("Arial",16,"bold"), text_color=COLORS["text_primary"])
        title_lbl.pack(pady=15)
        return popup, title_lbl

    # ---- Popup handlers ----
    def _open_locate_popup(self):
        popup, _ = self._create_borderless_popup("Auto-Locate", 450, 300)
        ctk.CTkLabel(popup, text="Scans Wi‑Fi networks, tries BeaconDB, then offline DB,\nfalls back to IP. After locating, declination is calculated.",
                     font=("Arial",12), text_color=COLORS["text_secondary"]).pack(pady=5)
        def start():
            popup.destroy()
            self._on_locate_and_calculate()
        btn_frame = ctk.CTkFrame(popup, fg_color="transparent")
        btn_frame.pack(pady=20)
        ctk.CTkButton(btn_frame, text="Start Locate & Calculate", command=start, fg_color=COLORS["accent"]).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="Cancel", command=popup.destroy, fg_color="#555555").pack(side="left", padx=10)

    def _open_gps_popup(self):
        popup, _ = self._create_borderless_popup("GPS Tracking", 350, 250)
        lbl = ctk.CTkLabel(popup, text="Not active", font=("Arial",12), text_color=COLORS["text_secondary"])
        lbl.pack(pady=10)
        def toggle():
            if self.gps_active:
                self.gps_reader.stop_reading(); self.gps_active = False
                lbl.configure(text="Stopped"); self.btn_gps.configure(text="GPS", fg_color=COLORS["secondary"])
            else:
                if self.gps_reader.start_reading(self._on_gps_update):
                    self.gps_active = True; lbl.configure(text="Active – coordinates update live")
                    self.btn_gps.configure(text="Stop GPS", fg_color=COLORS["danger"])
                else:
                    lbl.configure(text="Failed to start GPS")
        btn_frame = ctk.CTkFrame(popup, fg_color="transparent")
        btn_frame.pack(pady=10)
        ctk.CTkButton(btn_frame, text="Start / Stop", command=toggle, fg_color=COLORS["secondary"]).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="Close", command=popup.destroy, fg_color="#555555").pack(side="left", padx=10)

    def _open_manual_popup(self):
        popup, _ = self._create_borderless_popup("Enter Coordinates", 400, 280)
        entry_frame = ctk.CTkFrame(popup, fg_color="transparent"); entry_frame.pack(pady=10)
        e_lat = ctk.CTkEntry(entry_frame, placeholder_text="Latitude", width=100, font=("Arial",12)); e_lat.pack(side="left", padx=5)
        e_lon = ctk.CTkEntry(entry_frame, placeholder_text="Longitude", width=100, font=("Arial",12)); e_lon.pack(side="left", padx=5)
        def set_manual():
            try:
                lat = float(e_lat.get().strip()); lon = float(e_lon.get().strip())
                if not (-90<=lat<=90 and -180<=lon<=180): raise ValueError
            except:
                self._set_status("Invalid coordinates. Use numbers only.", "error"); return
            self._set_coordinates(lat, lon, "Exact (manual input)")
            self._set_status("Coordinates set.", "success")
            popup.destroy()
        btn_frame = ctk.CTkFrame(popup, fg_color="transparent")
        btn_frame.pack(pady=10)
        ctk.CTkButton(btn_frame, text="Set Coordinates", command=set_manual, fg_color=COLORS["secondary"]).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="Cancel", command=popup.destroy, fg_color="#555555").pack(side="left", padx=10)

    def _open_calibrate_popup(self):
        popup, _ = self._create_borderless_popup("Wi‑Fi Calibration", 450, 300)
        ctk.CTkLabel(popup, text="Use the manual coordinates currently\nset in the main window (or enter new ones here)\nto seed the offline Wi‑Fi database.\nOld database will be deleted.",
                     font=("Arial",12), text_color=COLORS["text_secondary"]).pack(pady=5)
        entry_frame = ctk.CTkFrame(popup, fg_color="transparent"); entry_frame.pack(pady=10)
        e_lat = ctk.CTkEntry(entry_frame, placeholder_text="Latitude", width=100, font=("Arial",12)); e_lat.pack(side="left", padx=5)
        e_lon = ctk.CTkEntry(entry_frame, placeholder_text="Longitude", width=100, font=("Arial",12)); e_lon.pack(side="left", padx=5)
        if self.latitude is not None:
            e_lat.insert(0, f"{self.latitude:.6f}")
            e_lon.insert(0, f"{self.longitude:.6f}")
        def calibrate():
            try:
                lat = float(e_lat.get().strip()); lon = float(e_lon.get().strip())
                if not (-90<=lat<=90 and -180<=lon<=180): raise ValueError
            except:
                self._set_status("Invalid coordinates.", "error"); return
            popup.destroy()
            self._on_calibrate_wifi(lat, lon)
        btn_frame = ctk.CTkFrame(popup, fg_color="transparent")
        btn_frame.pack(pady=10)
        ctk.CTkButton(btn_frame, text="Start Calibration", command=calibrate, fg_color=COLORS["gold"]).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="Cancel", command=popup.destroy, fg_color="#555555").pack(side="left", padx=10)

    def _open_submit_popup(self):
        popup, _ = self._create_borderless_popup("Submit to BeaconDB", 450, 300)
        ctk.CTkLabel(popup, text="Your current coordinates will be\nuploaded along with visible Wi‑Fi networks.\nData becomes available in ~5 minutes.",
                     font=("Arial",12), text_color=COLORS["text_secondary"]).pack(pady=5)
        def submit():
            if self.latitude is None:
                self._set_status("Set coordinates first (Manual or GPS).", "error"); return
            popup.destroy()
            self._on_submit_beacondb()
        btn_frame = ctk.CTkFrame(popup, fg_color="transparent")
        btn_frame.pack(pady=10)
        ctk.CTkButton(btn_frame, text="Submit Now", command=submit, fg_color=COLORS["accent"]).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="Cancel", command=popup.destroy, fg_color="#555555").pack(side="left", padx=10)

    # ---- Workflow ----
    def _on_locate_and_calculate(self):
        if self.processing: return
        self.processing = True
        self.btn_locate.configure(state="disabled", text="Working...")
        self.console.clear()
        self._set_status("Locating...", "info")
        threading.Thread(target=self._locate_workflow, daemon=True).start()

    def _locate_workflow(self):
        try:
            wifi_ok, status = self._check_wifi_adapter_status()
            if not wifi_ok: self.console.append(f"[WIFI_ADAPTER] Status: {status} – disabling Wi‑Fi.")
            else: self.console.append(f"[WIFI_ADAPTER] Status: {status}")

            scanner = WiFiScanner(self); bssids = scanner.scan()
            if bssids:
                self.console.append(f"Scanned {len(bssids)} BSSIDs.")
                lat_b, lon_b, acc_b, reason = _locate_via_beacondb(bssids)
                if lat_b is not None:
                    self.console.append(f"BeaconDB returned: {lat_b:.6f}, {lon_b:.6f} (accuracy {acc_b:.0f} m)")
                    self.after(0, lambda: self._set_coordinates(lat_b, lon_b, f"BeaconDB ({acc_b:.0f} m)", "Wi‑Fi geolocation – BeaconDB"))
                    self.after(0, lambda: self._set_status(f"Location via BeaconDB: {lat_b:.6f}, {lon_b:.6f} (±{acc_b:.0f} m)", "success"))
                    self.after(0, self._on_calculate); self.after(0, self._finish_processing); return
                else: self.console.append(f"BeaconDB lookup failed: {reason}")

                if WIFI_DB_PATH.exists():
                    loc = scanner.get_location(WIFI_DB_PATH)
                    if loc:
                        lat, lon = loc
                        self.after(0, lambda: self._set_coordinates(lat, lon, "Wi‑Fi Location (100‑500 m)", "Offline database"))
                        self.after(0, lambda: self._set_status(f"Location via offline Wi‑Fi DB: {lat:.6f}, {lon:.6f}", "success"))
                        self.console.append(f"Offline Wi‑Fi DB returned: {lat:.6f}, {lon:.6f}")
                        self.after(0, self._on_calculate); self.after(0, self._finish_processing); return

            ip = self._get_ip_location()
            if ip:
                lat, lon, desc = ip
                self.after(0, lambda: self._set_coordinates(lat, lon, "IP (5‑50 km)", desc))
                self.after(0, lambda: self._set_status(f"Using IP location: {lat:.6f}, {lon:.6f}", "warning"))
                self.console.append(f"IP geolocation returned: {lat:.6f}, {lon:.6f}")
                self.after(0, self._on_calculate)
            else:
                self.console.append("All location methods failed.")
                self.after(0, lambda: self._set_status("Unable to determine location.", "error"))
            self.after(0, self._finish_processing)
        except Exception as e:
            self.console.append(f"Fatal error: {e}")
            self.after(0, lambda: self._set_status("An error occurred.", "error"))
            self.after(0, self._finish_processing)

    def _on_calibrate_wifi(self, lat, lon):
        if WIFI_DB_PATH.exists():
            try: WIFI_DB_PATH.unlink(); self.console.append("Old wifi_location.db deleted.")
            except Exception as e: self.console.append(f"Warning: {e}")
        self._set_coordinates(lat, lon, "Calibrating Wi‑Fi", "Manual seed – rebuilding…")
        self._set_status("Rebuilding Wi‑Fi database…", "info")
        def rebuild():
            scanner = WiFiScanner(self); bssids = scanner.scan()
            if bssids:
                self._build_update_wifi_db(bssids, lat, lon)
                self.console.append("Wi‑Fi database rebuilt.")
                self.after(0, lambda: self._set_status("Wi‑Fi database calibrated.", "success"))
            else:
                self.after(0, lambda: self.console.append("No BSSIDs found."))
                self.after(0, lambda: self._set_status("Calibration failed – no networks.", "error"))
        threading.Thread(target=rebuild, daemon=True).start()

    def _on_submit_beacondb(self):
        if self.latitude is None: self._set_status("Set coordinates first.", "error"); return
        scanner = WiFiScanner(self); bssids = scanner.scan()
        if not bssids: self._set_status("No Wi‑Fi networks to submit.", "error"); return
        self.lbl_submit_status.configure(text="Submitting…", text_color=COLORS["gold"])
        self._set_status("Submitting to BeaconDB…", "info")
        def task():
            def update_status(msg):
                self.after(0, lambda: self.lbl_submit_status.configure(
                    text=msg, text_color=COLORS["accent"] if msg.startswith("Success") else COLORS["danger"]))
                if msg.startswith("Success"):
                    self.after(5000, lambda: self.lbl_submit_status.configure(text="Ready", text_color=COLORS["text_secondary"]))
                else:
                    self.after(8000, lambda: self.lbl_submit_status.configure(text="Ready", text_color=COLORS["text_secondary"]))
                self.after(0, lambda: self.console.append(f"BeaconDB submission: {msg}"))
            _submit_beacondb(bssids, self.latitude, self.longitude, update_status)
        threading.Thread(target=task, daemon=True).start()

    # ---- Helpers ----
    def _build_update_wifi_db(self, bssids, lat, lon):
        try:
            conn = sqlite3.connect(str(WIFI_DB_PATH)); cur = conn.cursor()
            cur.execute('CREATE TABLE IF NOT EXISTS access_points (bssid TEXT PRIMARY KEY, lat REAL, lon REAL, timestamp INTEGER)')
            cur.executemany('INSERT OR REPLACE INTO access_points VALUES (?,?,?,?)', [(b, lat, lon, int(time.time())) for b in bssids])
            conn.commit(); conn.close()
        except Exception as e: self.console.append(f"DB error: {e}")

    def _get_ip_location(self):
        if self.ip_location: return self.ip_location
        try:
            resp = requests.get('http://ip-api.com/json/', timeout=10)
            if resp.status_code==200:
                data = resp.json()
                if data.get('status')=='success':
                    self.ip_location = (float(data['lat']), float(data['lon']), f"{data.get('city','?')}, {data.get('country','?')}")
                    return self.ip_location
        except: pass
        return None

    def _check_wifi_adapter_status(self):
        cur_os = platform.system()
        try:
            if cur_os == "Windows":
                out = subprocess.check_output(['netsh','wlan','show','interfaces'], text=True)
                for line in out.splitlines():
                    if "State" in line:
                        s = line.split(':')[-1].strip()
                        if s=="connected": return True, "connected"
                        elif s=="disconnected": return True, "disconnected"
                return False, "disabled"
            elif cur_os == "Linux":
                out = subprocess.check_output(['ip','link'], text=True)
                for line in out.splitlines():
                    if 'wlan' in line and 'UP' in line: return True, "enabled"
                return False, "down"
        except: return False, "unknown"

    def _on_gps_update(self, lat, lon, quality):
        self._set_coordinates(lat, lon, "GPS", f"Fix quality: {quality}")
        self._set_status(f"GPS live: {lat:.6f}, {lon:.6f} (q{quality})", "success")

    def _on_calculate(self):
        if self.latitude is None: return
        try:
            d = declination(self.latitude, self.longitude, 0)
            self.lbl_result.configure(state="normal"); self.lbl_result.delete(0,"end")
            self.lbl_result.insert(0, f"Declination: {d:.2f}°"); self.lbl_result.configure(state="readonly")
            self._set_status("Calculated successfully.", "success")
            self._highlight_result()
        except Exception as e: self._set_status(f"Calculation error: {str(e)}", "error")

    def _highlight_result(self):
        orig_fg = self.lbl_result.cget("fg_color"); self.lbl_result.configure(fg_color=COLORS["accent"], text_color="white")
        self.after(800, lambda: self.lbl_result.configure(fg_color=orig_fg, text_color=COLORS["gold"]))

    def _finish_processing(self):
        self.btn_locate.configure(state="normal", text="Locate & Calculate")
        self.processing = False

    def _show_help(self):
        popup = ctk.CTkToplevel(self); popup.title("Help"); popup.geometry("500x400")
        popup.attributes("-topmost", True); popup.grab_set()
        popup.configure(fg_color=COLORS["bg"])
        ctk.CTkLabel(popup, text="Help – Magnetic Declination Calculator", font=("Arial",16,"bold"),
                     text_color=COLORS["text_primary"]).pack(pady=15)
        msg = ("This calculator uses BeaconDB (free online Wi‑Fi geolocation),\n"
               "an offline Wi‑Fi database, or manual coordinates to obtain your\n"
               "location, then calculates magnetic declination using GeoDude's\n"
               "built‑in WMM2025 model.\n\n"
               "Buttons:\n"
               "  Locate & Calculate – auto‑scan Wi‑Fi and compute declination\n"
               "  GPS – start/stop live serial GPS tracking\n"
               "  Set Manual – enter exact coordinates\n"
               "  Calibrate Wi‑Fi – rebuild offline database with manual seed\n"
               "  Submit to BeaconDB – contribute your Wi‑Fi scan to the global DB\n\n"
               "Double-click any result field to copy its content.\n"
               "F11 toggles fullscreen.")
        ctk.CTkLabel(popup, text=msg, font=("Arial",11), justify="left",
                     text_color=COLORS["text_secondary"]).pack(padx=20, pady=10)
        ctk.CTkButton(popup, text="OK", command=popup.destroy, fg_color=COLORS["accent"]).pack(pady=10)

if __name__ == "__main__":
    app = App(); app.mainloop()