# Sarcnet Mini Satellite Tracker Mk 1

## Table of contents
- [IMPORTANT]()
- [Resources]()
- [Introduction]()
- [Who is Sarcnet]()
- [What is a Satellite Tracker?]()
- [Why build Sarcnet's Mini Satellite Tracker Mk 1?]()
- [Bill Of Materials]()

# SARCTRAC 3D Sensor Calibration Guide

Complete procedure for calibrating the SARCTRAC sensor to Earth’s magnetic and gravitational fields, based on the official instructional video. Follow every step in order to ensure an accurate, repeatable calibration.

---

## 1. Preparation & Setup

- **Tools**  
  Firmly tape the sensor to the centre of a rigid plastic ruler. This provides a stable handling platform and helps prevent accidental bumps or drops `[1:27]`.

- **Environment**  
  Perform the calibration away from magnetic interference — avoid steel furniture, reinforced concrete, vehicles, and large metal structures `[8:23]`.

- **Initial orientation**  
  Open the SARCTRAC selection page in the software. Stand facing **magnetic north** before you begin `[2:21]`.

---

## 2. Initialisation & Rough Calibration

1. Press the **Begin** button in the software `[2:04]`.
2. Perform the rough calibration by slowly rotating the sensor in two horizontal axes:
   - **Yaw (Z‑axis):** Rotate the sensor like a compass needle on a flat surface.
   - **Pitch & Roll (horizontal axes):** Tilt the sensor side‑to‑side and front‑to‑back, keeping it generally horizontal `[2:27]`.

> 💡 This step gives the system a baseline; it does not require extreme angles.

---

## 3. The 12‑Point Calibration Routine

The sensor has six faces: **Front, Top, Rear, Left, Right, Bottom**.  
For **each face**, orient the sensor in two distinct positions:

- **Vertical** — face points straight up/down relative to gravity
- **North at local magnetic inclination** — face points towards magnetic north, tilted to match your location’s dip angle

While collecting data the device beeps. **Move the sensor gently around the target orientation** until the beeping stops, confirming the point is captured `[1:53]`.

| Face | Point | Orientation | Timestamp |
|------|-------|-------------|-----------|
| **Front** | 1 | Vertical | `[3:32]` |
| | 2 | North at local magnetic inclination | `[3:55]` |
| **Top** | 3 | Vertical | `[4:22]` |
| | 4 | North at local magnetic inclination | `[4:44]` |
| **Rear** | 5 | Vertical | `[5:02]` |
| | 6 | North at local magnetic inclination | `[5:22]` |
| **Left** | 7 | Vertical | `[5:39]` |
| | 8 | North at local magnetic inclination | `[6:05]` |
| **Right** | 9 | Vertical | `[6:22]` |
| | 10 | North at local magnetic inclination | `[6:47]` |
| **Bottom** | 11 | Vertical | `[7:13]` |
| | 12 | North at local magnetic inclination | `[7:42]` |

> ⚠️ **Local magnetic inclination (dip angle)** is the angle the Earth’s magnetic field makes with the horizontal at your location. Look it up beforehand (e.g., using NOAA’s magnetic field calculator) and use an inclinometer or reference chart to set the correct tilt.

---

## 4. Troubleshooting & Saving

- **If the sensor is bumped or dropped** at any point during the 12‑point routine:  
  Press the **Abort** button immediately and restart the entire sequence from the beginning `[2:09]`. Partial data will compromise accuracy.

- **After all 12 points are collected successfully:**  
  Press the **Save** button `[8:11]`. The calibration is stored permanently and will be used automatically every time the sensor powers up `[8:15]`.

---

## Quick Checklist

- [ ] Sensor secured to ruler
- [ ] No magnetic interference nearby
- [ ] Facing magnetic north at start
- [ ] Rough calibration completed
- [ ] 12 points recorded in correct order
- [ ] No bumps or drops during sequence
- [ ] Calibration saved
