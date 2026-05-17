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

## Quick Checklist

- [ ] Sensor secured to ruler
- [ ] No magnetic interference nearby
- [ ] Facing magnetic north at start
- [ ] Rough calibration completed
- [ ] 12 points recorded in correct order
- [ ] No bumps or drops during sequence
- [ ] Calibration saved



0:07 this is Sark track the satellite antenna
0:10 rotator controller and tracker by the
0:13 school amateur radio club network at
0:17 www.norcalhypno.com of course in the
0:40 southern hemisphere the Earth's magnetic
0:42 field points upwards it points down in
0:45 the northern hemisphere and is
0:48 horizontal at the equator here in
0:51 Melbourne Australia the magnetic field
0:53 points up at an angle of 69 degrees this
0:57 is called the magnetic inclination and
0:59 it is 12 degrees east of True North this
1:03 is called the magnetic declination Sark
1:06 track has a built-in world magnetic
1:08 database and displays this information
1:11 at your location on the Sark track
1:13 selection page these angles are
1:16 important because Sark track uses the
1:18 Earth's magnetic and gravitational
1:19 fields themselves to calibrate the
1:22 scaling and offset of each axis of the
1:24 sensor I have taped the Sark track
1:27 sensor to the centre of a plastic ruler
1:29 to reduce any bumps during the
1:32 calibration process I note that the
1:35 sensor has six sides front rear left
1:39 right top and bottom I need to point
1:43 site in the direction of each field
1:45 there are 12 points in all and I need to
1:48 carefully search around each point while
1:50 Sark track collects calibration data
1:53 Sark track beeps while it is collecting
1:56 data I have to move it around each point
1:59 until Sark track stops beeping I start
2:02 the calibration process by pressing the
2:04 begin button on the Sark track selection
2:06 page if I bump or drop the sensor during
2:09 calibration I press the abort button and
2:12 have to start over when I have finished
2:15 the calibration process I press the Save
2:17 button let's get started I am facing
2:21 magnetic north to simplify the process I
2:24 press the begin button and do a rough
2:27 calibration by slowly rotating the
2:29 sensor around in two horizontal axes
3:29 now I focus on the front side of the
3:32 sensor I point the front side of the
3:35 sensor vertically I search around that
3:37 point until sark track stops beeping due
3:41 to heavy filtering while calibration is
3:43 in process the data takes a few seconds
3:45 to settle at each point this is point
3:51 number one complete next I point the
3:55 front side north at my local magnetic
3:58 inclination and search around again
4:00 until Sark track stops beeping sometimes
4:05 if the rough calibration was sufficient
4:07 there are no beeps at all at some
4:10 calibration points so I just move on to
4:13 the next one this is point number two
4:19 complete now I focus on the top side of
4:22 the sensor I point the top side of the
4:25 sensor vertically and search around
4:27 until sark track stops beeping whenever
4:31 I hear another beep I stop and
4:33 concentrate around that point this is
4:41 point number three complete next I point
4:44 the top side north at my local magnetic
4:47 inclination and search around again
4:49 until sark track stops beeping this is
4:59 point number four complete now I focus
5:02 on the rear side of the sensor I point
5:05 the rear side of the sensor vertically
5:07 and search around until sark track stops
5:10 beeping
5:18 this is point number five complete next
5:22 I point the rear side north at my local
5:25 magnetic inclination and search around
5:27 again until Sark track stops beeping
5:35 this is point number six complete now I
5:39 focus on the left side of the sensor I
5:42 point the left side of the sensor
5:44 vertically and search around until Sark
5:47 track stops beeping this is point number
6:02 seven complete next I point the left
6:05 side north at my local magnetic
6:08 inclination and search around again
6:10 until Sark track stops beeping this is
6:19 point number eight complete now I focus
6:22 on the right side of the sensor I point
6:25 the right side of the sensor vertically
6:26 and search around until Sark track stops
6:29 beeping
6:43 this is point number nine complete next
6:47 I point the right side north at my local
6:50 magnetic inclination and search around
6:53 again until Sark track stops beeping
7:09 this is point number 10 complete now I
7:13 focus on the bottom side of the sensor I
7:15 point the bottom side of the sensor
7:18 vertically and search around until sark
7:20 track stops beeping
7:38 this is point number 11 complete next I
7:42 point the bottom side north at my local
7:45 magnetic inclination and search around
7:47 again until Sark tract stops beeping
8:00 this is point number 12 in the last
8:03 calibration point complete if I want I
8:06 can check around each of the points
8:08 again for more calibration data when the
8:11 calibration process is finished I press
8:14 the Save button
8:15 sark track will use this calibration
8:18 data every time it powers up it is not
8:21 necessary to repeat this calibration
8:23 process unless the local magnetic
8:25 conditions near the sensor change for
8:28 example if I move Sark track near to a
8:30 steel structure this completes this
8:38 instructional video on calibrating the
8:40 Sark track 3d sensor




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
- Instructional video (SARCTRAC calibration): timestamps referenced below.

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

> Complete procedure for calibrating the SARCTRAC 3D sensor to Earth’s magnetic and gravitational fields. Based directly on the official instructional video.

## Quick Checklist

- [ ] Sensor secured to ruler
- [ ] No magnetic interference nearby
- [ ] Facing magnetic north at start
- [ ] Rough calibration completed
- [ ] 12 points recorded in correct order
- [ ] No bumps or drops during sequence
- [ ] Calibration saved

---



The "12 vector points" on the GY-511 (LSM303DLHC e-Compass module) refer to a standard 3D calibration method used for magnetometers. By rotating the sensor into 12 specific orientations, you collect maximum/minimum field strength data to correct for "hard-iron" and "soft-iron" magnetic distortions in your hardware.To do this calibration, the module (and the attached microcontroller) must be held completely still for a few seconds at each of the following 12 cardinal and inclined points:1. Horizontal Plane (Tilt = 0°)Vector 1: Sensor flat, facing magnetic North (\(0^{\circ }\))Vector 2: Sensor flat, facing East (\(90^{\circ }\))Vector 3: Sensor flat, facing South (\(180^{\circ }\))Vector 4: Sensor flat, facing West (\(270^{\circ }\))2. Tilted Upward (e.g., Pitch \(+45^{\circ }\), Roll \(0^{\circ }\))Vector 5: Compass bearing at \(30^{\circ }\)Vector 6: Compass bearing at \(120^{\circ }\)Vector 7: Compass bearing at \(210^{\circ }\)Vector 8: Compass bearing at \(300^{\circ }\)3. Tilted Downward (e.g., Pitch \(-45^{\circ }\), Roll \(0^{\circ }\))Vector 9: Compass bearing at \(60^{\circ }\)Vector 10: Compass bearing at \(150^{\circ }\)Vector 11: Compass bearing at \(210^{\circ }\)Vector 12: Compass bearing at \(300^{\circ }\)Why This MattersFor absolute compass accuracy, your readings will form an ellipsoid that needs to be mathematically mapped back to a perfect sphere (offsetting the center to 0,0,0). Recording these 12 vector points provides the min/max table necessary to calculate the exact \(X\), \(Y\), and \(Z\) biases.Note: For the best results, you must perform this calibration procedure outdoors, away from ferrous metals (like steel desks or building frames) and magnetic components (like unshielded speakers or motors).















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
