#!/usr/bin/env python3
"""
MagneticDeclinationCalculator.py
Modern, elegant, dark-themed GUI application that calculates the exact magnetic declination
for the user's current location.

- Forward geocoding: online via Nominatim
- Reverse geocoding: offline via Gazetteer (with online fallback if database missing)
- IP location: ip-api.com (online) + reverse geocoding via Gazetteer or fallback
- Manual coordinates: validated via reverse geocoding
- Fullscreen (F11), copy-on-double-click, tooltips, help dialog
"""

# ----------------------------------------------------------------------
# UTF‑8 enforcement (must be at the very top)
# ----------------------------------------------------------------------
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
from pathlib import Path

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
GAZETTEER_DATA_URL = "https://github.com/SOORAJTS2001/gazetteer/raw/main/gazetteer/data/data.db"

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

        self.gazetteer_manager = GazetteerManager(self)
        self.gazetteer = None
        self.use_gazetteer = False

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
        self.btn_gps = ctk.CTkButton(method_frame, text="🌍 Use GPS (IP)",
                                     command=self._on_get_from_gps,
                                     width=150, fg_color=COLORS["secondary"],
                                     hover_color=COLORS["secondary_hover"],
                                     font=("Arial", 12))
        self.btn_gps.pack(side="left", padx=(0,20))
        ToolTip(self.btn_gps, "Get approximate location via IP (reverse geocoded offline)")

        ctk.CTkLabel(method_frame, text="Manual:", font=("Arial", 12),
                     text_color=COLORS["text_secondary"]).pack(side="left", padx=(0,5))
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

        # Card: Actions
        action_card = ctk.CTkFrame(main_frame, fg_color=COLORS["card_bg"], corner_radius=12,
                                   border_width=1, border_color=COLORS["card_border"])
        action_card.pack(fill="x", pady=(0,15))
        action_frame = ctk.CTkFrame(action_card, fg_color="transparent")
        action_frame.pack(pady=12)
        self.btn_calculate = ctk.CTkButton(action_frame, text="🧭 Calculate Declination",
                                           command=self._on_calculate,
                                           width=220, fg_color=COLORS["accent"],
                                           hover_color=COLORS["accent_hover"],
                                           font=("Arial", 14, "bold"))
        self.btn_calculate.pack(side="left", padx=10)
        ToolTip(self.btn_calculate, "Compute magnetic declination using current coordinates")
        self.btn_clear = ctk.CTkButton(action_frame, text="🗑️ Clear All",
                                       command=self._on_clear,
                                       width=120, fg_color=COLORS["danger"],
                                       hover_color=COLORS["danger_hover"],
                                       font=("Arial", 12))
        self.btn_clear.pack(side="left", padx=10)
        ToolTip(self.btn_clear, "Clear all location data and inputs")

        # Card: Result
        result_card = ctk.CTkFrame(main_frame, fg_color=COLORS["card_bg"], corner_radius=12,
                                   border_width=1, border_color=COLORS["card_border"])
        result_card.pack(fill="x", pady=(0,15))
        ctk.CTkLabel(result_card, text="🧮 Declination Result", font=("Arial", 14, "bold"),
                     text_color=COLORS["text_primary"]).pack(anchor="w", padx=20, pady=(15,5))
        self.lbl_result = ctk.CTkEntry(result_card, font=("Arial", 18, "bold"),
                                       text_color=COLORS["gold"], border_width=0,
                                       fg_color="transparent", justify="center",
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
        dialog.geometry("600x450")
        dialog.attributes("-topmost", True)
        dialog.grab_set()
        dialog.configure(fg_color=COLORS["bg"])
        title = ctk.CTkLabel(dialog, text="🧭 Help – Magnetic Declination Calculator",
                             font=("Arial", 18, "bold"), text_color=COLORS["text_primary"])
        title.pack(pady=(20,10))
        text = """
        Three ways to get coordinates:
        1.  Enter a street address → Click "Get from Address" (online Nominatim)
        2.  Click "Use GPS (IP)" → Your approximate location via IP (reverse geocoded offline via Gazetteer)
        3.  Enter latitude/longitude manually → Click "Set Manual" (validated offline via Gazetteer)

        Offline reverse geocoding is strongly recommended, but you can skip it and use online fallback.

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
                for place in self.gazetteer.search([(lon, lat)], limit=1):
                    if place:
                        return f"{place.result.name}, {place.result.admin2}, {place.result.admin1}"
            except Exception as e:
                print(f"Gazetteer reverse error: {e}")
        # Fallback to online
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

    def _on_get_from_gps(self):
        self._set_status("Fetching location via IP...", "info")
        try:
            r = requests.get('http://ip-api.com/json/', timeout=5)
            if r.status_code == 200:
                d = r.json()
                if d.get('status') == 'success':
                    lat, lon = float(d['lat']), float(d['lon'])
                    city, country = d.get('city', 'Unknown'), d.get('country', 'Unknown')
                    self._set_coordinates(lat, lon, "City level (IP approximate)", f"{city}, {country}")
                    self._set_status(f"IP location: {city}, {country}. Looking up nearest address...", "info")
                    addr = self._reverse_geocode(lat, lon)
                    if addr:
                        self._set_precision("City level (IP approximate)", f"Nearest: {addr[:100]}")
                        self._set_status(f"IP location: {city}, {country}. Nearest: {addr}", "success")
                    else:
                        self._set_status(f"IP location: {city}, {country}. No address found.", "info")
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