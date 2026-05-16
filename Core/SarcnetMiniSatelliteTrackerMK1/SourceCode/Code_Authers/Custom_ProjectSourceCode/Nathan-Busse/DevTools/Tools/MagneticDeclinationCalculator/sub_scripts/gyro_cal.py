#!/usr/bin/env python3
"""
GyroCal - GY‑511 (LSM303D) Calibration Controller
Part of the Sarcnet Rotator7 toolchain.
"""

import threading
import time
import serial
import serial.tools.list_ports


class GyroCalController:
    """Handles serial communication with the Rotator7 Arduino."""

    def __init__(self, port: str = None, baudrate: int = 9600, timeout: float = 2.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None
        self.is_connected = False
        self.lock = threading.Lock()

        # Live data
        self.declination = 0.0          # stored from the main app
        self.raw_debug = ""             # latest debug line (mx,my,mz,gx,gy,gz)
        self.monitor_data = ""          # latest monitor line (az,el,azSet,elSet,windup,...)
        self.calibration_data = ""      # latest calibration data line (save format)

        # Callbacks (set by the GUI)
        self.on_debug_line = None       # called with (mx,my,mz,gx,gy,gz)
        self.on_monitor_line = None     # called with parsed monitor data dict
        self.on_calibration_line = None # called with raw calibration line
        self.on_status = None           # called with status string

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------
    @staticmethod
    def list_ports():
        """Return a list of available COM ports (Windows) or serial devices."""
        ports = serial.tools.list_ports.comports()
        return [p.device for p in ports]

    def connect(self, port: str = None):
        """Open the serial connection. If no port given, uses the one set in self.port."""
        if port:
            self.port = port
        if not self.port:
            raise ValueError("No serial port specified.")
        self.ser = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
        self.is_connected = True
        self._notify("Connected to " + self.port)
        # Start a background reader thread
        threading.Thread(target=self._reader, daemon=True).start()

    def disconnect(self):
        """Close the serial connection."""
        with self.lock:
            if self.ser and self.ser.is_open:
                self.ser.close()
            self.is_connected = False
        self._notify("Disconnected")

    # ------------------------------------------------------------------
    # Command helpers
    # ------------------------------------------------------------------
    def _send_command(self, cmd: str):
        """Send a command string followed by a carriage return."""
        if not self.is_connected:
            raise ConnectionError("Not connected to rotator.")
        with self.lock:
            self.ser.write((cmd + "\r").encode("utf-8"))

    def send_declination(self, dec: float):
        """Send the magnetic declination to the rotator (e command)."""
        self.declination = dec
        self._send_command(f"e{dec:.2f}")
        self._notify(f"Declination set to {dec:.2f}°")

    def start_calibration(self):
        """Start the calibration routine (c command)."""
        self._send_command("c")
        self._notify("Calibration started. Move the antenna through various orientations.")

    def save_to_eeprom(self):
        """Save calibration data to EEPROM (s command)."""
        self._send_command("s")
        self._notify("Calibration saved to EEPROM.")

    def start_debug(self):
        """Start debug mode – streams raw sensor data."""
        self._send_command("b")

    def start_monitor(self):
        """Start monitor mode – streams processed position data."""
        self._send_command("m")

    def abort(self):
        """Abort current operation and return to tracking mode."""
        self._send_command("a")

    def reset(self):
        """Reset the rotator and reload EEPROM calibration."""
        self._send_command("r")

    def pause(self):
        """Toggle pause mode."""
        self._send_command("p")

    def set_position(self, az: float, el: float):
        """Set target azimuth (0‑360) and elevation (0‑90)."""
        self._send_command(f"{az:.1f} {el:.1f}")

    # ------------------------------------------------------------------
    # Background reader
    # ------------------------------------------------------------------
    def _reader(self):
        """Continuously read lines from the serial port and dispatch them."""
        buffer = ""
        while self.is_connected:
            try:
                chunk = self.ser.read(128)
                if not chunk:
                    continue
                buffer += chunk.decode("utf-8", errors="replace")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if line:
                        self._process_line(line)
            except (serial.SerialException, OSError):
                self.is_connected = False
                self._notify("Serial connection lost.")
                break

    def _process_line(self, line: str):
        """Identify the type of incoming data line and parse it."""
        # Debug line: comma‑separated floats "mx,my,mz,gx,gy,gz"
        parts = line.split(",")
        if len(parts) == 6:
            try:
                values = [float(p) for p in parts]
                self.raw_debug = line
                if self.on_debug_line:
                    self.on_debug_line(*values)
                return
            except ValueError:
                pass

        # Monitor line: "az,el,azSet,elSet,azWindup,windup,azError,elError"
        if len(parts) == 8:
            try:
                data = {
                    "az": float(parts[0]),
                    "el": float(parts[1]),
                    "azSet": float(parts[2]),
                    "elSet": float(parts[3]),
                    "azWindup": float(parts[4]),
                    "windup": parts[5] == "1",
                    "azError": float(parts[6]),
                    "elError": float(parts[7]),
                }
                self.monitor_data = line
                if self.on_monitor_line:
                    self.on_monitor_line(data)
                return
            except ValueError:
                pass

        # Calibration data line: 13 comma‑separated floats (the cal struct)
        if len(parts) == 13:
            try:
                _ = [float(p) for p in parts]
                self.calibration_data = line
                if self.on_calibration_line:
                    self.on_calibration_line(line)
                return
            except ValueError:
                pass

        # Other status messages
        if self.on_status:
            self.on_status(line)

    def _notify(self, msg):
        """Send a status notification to the GUI callback."""
        if self.on_status:
            self.on_status(msg)