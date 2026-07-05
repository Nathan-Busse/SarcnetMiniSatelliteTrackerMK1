# Sarcnet Mini Satellite Tracker Mk 1

## Table of contents
- [IMPORTANT](#important)
- [Resources](#resources)
- [Introduction](#introduction)
- [Who is Sarcnet](#who-is-sarcnet)
- [What is a Satellite Tracker?](#what-is-a-satellite-tracker)
- [Why build Sarcnet's Mini Satellite Tracker Mk 1?](#why-build-sarcnets-mini-satellite-tracker-mk-1)
- [Bill Of Materials](#bill-of-materials)
- [SARCTRAC 3D Sensor Calibration Guide](#sarctrac-3d-sensor-calibration-guide)

## IMPORTANT
> ⚠️ Placeholder – add any safety warnings, compliance notes, or critical build instructions here.

## Resources
- Official website: [www.norcalhypno.com](http://www.norcalhypno.com)
- [Sarcnet's video (Sensor calibration): timestamps referenced below.](https://www.youtube.com/watch?v=oJnpO5Nj7Gc&t=7)


## Introduction
The Sarcnet Mini Satellite Tracker Mk 1 is an open‑source antenna rotator controller and tracker. It uses a 3‑axis magnetometer and accelerometer (the SARCTRAC sensor) to determine its orientation relative to Earth’s magnetic and gravitational fields. Proper calibration of this sensor is essential for accurate satellite tracking.

This document provides a complete build and setup guide for the Mk 1, with a detailed step‑by‑step calibration procedure for the SARCTRAC 3D sensor.

## Who is Sarcnet
Sarcnet is the School Amateur Radio Club Network. The project is maintained at [www.norcalhypno.com](http://www.norcalhypno.com). The tracker software and hardware are designed by the club to make satellite tracking accessible for educational and amateur radio use.

## What is a Satellite Tracker?
A satellite tracker is a device that automatically points an antenna toward an orbiting satellite. By knowing the satellite’s trajectory and the tracker’s own position and orientation, the rotator can follow the satellite across the sky, maintaining a strong signal.

## Why build Sarcnet's Mini Satellite Tracker Mk 1?
(Placeholder – briefly describe the advantages: low cost, educational value, open‑source, community support, etc.)

## Bill Of Materials
(Placeholder – list all components, hardware, and 3D‑printed parts with quantities and possible sourcing links.)

---



# SARCTRAC 3D Sensor Calibration Guide

Calibrating the SARCNET Mini Satellite Tracker Mk 1 (and its associated 3D sensor) requires orienting the sensor board in specific directions while the system captures the Earth's magnetic and gravitational fields.

## For the step-by-step instructions:
**1. Connect & Access:** Disconnect the 12V motor supply. Connect the Mk 1 controller to your PC via USB. Open the Arduino IDE, open the rotator sketch, and launch the Serial Monitor.

**2. Debug Mode:** Type b followed by Enter in the Serial Monitor to enter debug mode and verify your raw sensor data (Mx, My, Mz, Gx, Gy, Gz). Type a to abort.

**3. Calibration Data:** Type m and press Enter to enter monitor mode, then follow the on-screen prompts.

**4. Physical Orientation:** You will be prompted to orient the 3D sensor. The calibration algorithm will guide you to point the sensor at various angles (e.g., North, horizontal, and vertical). The built-in beeper (or piezo buzzer) will beep during data collection and stop when the point is successfully recorded.

**5. Save Configuration:** Once all required points are searched and collected, type s in the Serial Monitor to save the calibration data to the EEPROM.

Ensure your unit is rigidly mounted and free from nearby metallic/magnetic structures, as external magnets or metals can invalidate the calibration.



### Quick Checklist

- [ ] Sensor secured to ruler
- [ ] No magnetic interference nearby
- [ ] Facing magnetic north at start
- [ ] Rough calibration completed
- [ ] 12 points recorded in correct order
- [ ] No bumps or drops during sequence
- [ ] Calibration saved

---


## 1. Understanding Magnetic Inclination & Declination

The Earth’s magnetic field points **upwards** in the southern hemisphere, **downwards** in the northern hemisphere, and is **horizontal** at the equator. The angle it makes with the horizontal is called the **magnetic inclination** (or dip angle). The difference between magnetic north and true north is the **magnetic declination**.

- **SARCTRAC** has a built‑in world magnetic database. When you open the SARCTRAC selection page, it automatically displays the **inclination** and **declination** for your location.
- These angles are critical – the calibration routine requires you to point each sensor face **north at your local magnetic inclination**.

> **Example:** In Melbourne, Australia, the magnetic field points up at an inclination of 69°, with a declination 12° east of true north.

---

## 2. Preparation & Setup

- **Mount the sensor**  
  Tape the SARCTRAC sensor firmly to the centre of a rigid plastic ruler. This gives a stable handle and minimises the chance of accidental bumps or drops during calibration.  
  *The sensor has six faces: Front, Rear, Left, Right, Top, Bottom.* `[1:27]`

- **Choose your environment**  
  Stay away from magnetic interference. Avoid steel structures, reinforced concrete, vehicles, or large metal objects. `[8:23]`

- **Initial orientation**  
  Stand facing **magnetic north**. The sensor’s front face should initially be oriented roughly north. `[2:21]`

---

## 3. Initialisation & Rough Calibration

1. On the SARCTRAC selection page, press the **Begin** button. `[2:04]`
2. Perform a **rough calibration** by slowly rotating the sensor in two horizontal axes:
   - **Yaw (Z‑axis):** rotate the sensor like a compass needle on a flat surface.
   - **Pitch & Roll:** tilt the sensor side‑to‑side and front‑to‑back, keeping it generally horizontal.  
   *This gives the system a baseline; you do not need extreme angles.* `[2:27]`

---

## 4. The 12‑Point Calibration Routine

The calibration consists of 12 distinct orientations – two for each of the sensor’s six faces. For each face you must point:

- **Vertical** – the face points straight up or down relative to gravity.
- **North at local magnetic inclination** – the face points towards magnetic north, tilted at the dip angle displayed on the software.

### How the beeping works
- SARCTRAC **beeps continuously** while it collects data at a point.
- **Move the sensor gently around the target orientation** until the beeping **stops**. Because of heavy filtering, it can take a few seconds for the data to settle after you stop moving. `[1:53]`
- If the rough calibration was sufficient, you may hear **no beeps at all** at some points – just move on to the next orientation. `[4:05]`

### Step‑by‑step sequence

| Point | Face     | Orientation                              | Video time |
|-------|----------|------------------------------------------|------------|
| 1     | **Front**  | Vertical (front points up/down)          | `[3:32]`   |
| 2     | **Front**  | North at local magnetic inclination      | `[3:55]`   |
| 3     | **Top**    | Vertical (top points up/down)            | `[4:22]`   |
| 4     | **Top**    | North at local magnetic inclination      | `[4:44]`   |
| 5     | **Rear**   | Vertical (rear points up/down)           | `[5:02]`   |
| 6     | **Rear**   | North at local magnetic inclination      | `[5:22]`   |
| 7     | **Left**   | Vertical (left points up/down)           | `[5:39]`   |
| 8     | **Left**   | North at local magnetic inclination      | `[6:05]`   |
| 9     | **Right**  | Vertical (right points up/down)          | `[6:22]`   |
| 10    | **Right**  | North at local magnetic inclination      | `[6:47]`   |
| 11    | **Bottom** | Vertical (bottom points up/down)         | `[7:13]`   |
| 12    | **Bottom** | North at local magnetic inclination      | `[7:42]`   |

> **Tip:** You can check around each point again after finishing the last one – additional data will only improve the calibration. `[8:06]`

---

## 5. Troubleshooting & Saving

- **Bumped or dropped the sensor?**  
  Press the **Abort** button immediately and restart the entire sequence from the beginning. Even a small knock can corrupt the data. `[2:09]`

- **Calibration complete**  
  Once all 12 points are successfully captured, press the **Save** button. SARCTRAC stores the calibration and uses it automatically every time it powers up. `[8:11]`

- **When to recalibrate**  
  It is not normally necessary to repeat the calibration unless the local magnetic conditions near the sensor change – for example, if you move the tracker close to a steel structure. `[8:23]`

---
