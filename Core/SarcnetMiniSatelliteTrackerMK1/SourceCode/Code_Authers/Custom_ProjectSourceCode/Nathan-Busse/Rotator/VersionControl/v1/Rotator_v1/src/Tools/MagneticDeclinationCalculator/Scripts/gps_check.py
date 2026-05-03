import serial
import serial.tools.list_ports
import pynmea2

print("✅ Success! GPS libraries are installed and available.")
print("📡 Available COM ports:")
for port in serial.tools.list_ports.comports():
    print(f" - {port.device}: {port.description}")