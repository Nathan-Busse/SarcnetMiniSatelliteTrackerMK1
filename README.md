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
> ⚠️ When shopping for your parts always make sure to have spare hardware in your cart just  in case a component you have installed fails or is defective out of the box, especially for your 3D digital compass module... 

## Resources
- Official Sarcnet website: [www.sercnet.org](http://www.sarcnet.org)
- Official NOAA website: [www.ngdc.noaa.gov](https://www.ngdc.noaa.gov/geomag/calculators/magcalc.shtml)
- Official Sarcnet calibration video: [Sensor calibration timestamps referenced below.](https://www.youtube.com/watch?v=oJnpO5Nj7Gc&t=7)


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


## Understanding Magnetic Inclination & Declination

The Earth’s magnetic field points **upwards** in the southern hemisphere, **downwards** in the northern hemisphere, and is **horizontal** at the equator. The angle it makes with the horizontal is called the **magnetic inclination** (or dip angle). The difference between magnetic north and true north is the **magnetic declination**.

 **When to recalibrate**  
  It is not normally necessary to repeat the calibration unless the local magnetic conditions near the sensor change – for example, if you move the tracker close to a steel structure. `[8:23]`

---
