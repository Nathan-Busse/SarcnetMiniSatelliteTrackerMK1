# GY-511 (LSM303DLHC) 12-Point Magnetometer Calibration Guide

## THE PHYSICAL MARKINGS ON YOUR SENSOR ARE IMPORTANT:

The GY-511 module (housing an LSM303DLHC chip) contains a 3-axis accelerometer and magnetometer, plus an auxiliary gyroscope. Its axes use the right-hand rule: when flat, X points forward (nose), Y points left, and Z points up. Calibration fixes magnetic biases before heading calculations.

**Axis Orientations**
To ensure accurate spatial awareness, orient your board correctly in your project:

- X-Axis: Positive is forward (the direction your robot or aircraft is traveling).

- Y-Axis: Positive is to the left.

- Z-Axis: Positive points straight up towards the sky.

**Magnetometer Calibration (Hard and Soft Iron)**
Magnetic materials and nearby electronics warp your sensor's readings, often producing elliptical data rather than a clean sphere. Calibration shifts and scales this data to a centered origin.

1. **Collect Raw Data:** Run an I2C data-logging sketch to stream raw \((X, Y, Z)\)  magnetometer values to your serial monitor.

2. **Move in a Sphere:** Slowly rotate the sensor through all 3-dimensional orientations (pitch, roll, and yaw) until you have captured a full 360-degree range of points in every direction.

3. **Calculate Offsets:** Note the minimum and maximum values for each axis. Your offset is calculated as:\(\text{Offset} = \frac{\text{Max} + \text{Min}}{2}\)

4. **Apply to Code:** Subtract these offsets from your raw readings and multiply them by your scale to get true compass headings in your Arduino sketch.

## How it works:

For absolute compass accuracy, your readings will form an ellipsoid that needs to be mathematically mapped back to a perfect sphere (offsetting the center to 0,0,0). Recording these 12 vector points provides the min/max table necessary to calculate the exact **X**, **Y**, and **Z** biases.

### What is an **ellipsoid**?

An ellipsoid is a three-dimensional geometric shape that looks like a squashed or stretched sphere. 

It is the 3D equivalent of an ellipse (like a rugby ball or a flattened egg), where every cross-section sliced through the shape is either an ellipse or a circle.

### why is an ellipsoid used for gyro magnetometer calibration?
An ellipsoid is used to calibrate gyro magnetometers because Earth's magnetic field is constant. In an ideal environment, rotating a 3-axis sensor forms a perfect sphere. However, sensor errors and local magnetic disturbances distort these readings into an offset and skewed 3D shape, mathematically known as an ellipsoid. Ellipsoid fitting is the mathematical method used to correct these distortions and restore accurate directional data.

The calibration process treats raw, distorted data as an ellipsoid to correct for specific hardware and environmental issues:

- **Earth's Magnetic Field:** The total magnitude of Earth's magnetic field is constant at any given location. Therefore, plotting perfect, error-free 3-axis magnetometer data in all orientations forms a perfect sphere.

- **Hard Iron Distortion:** Caused by permanent magnets or magnetized metal on the device itself (e.g., speakers, batteries, or metal chassis). This effect adds a constant offset to the sensor readings, shifting the theoretical sphere off-center.

- **Soft Iron Distortion:** Caused by the interaction of Earth's magnetic field with nearby ferromagnetic materials (e.g., iron or steel). This distorts and warps the surrounding magnetic field, stretching the ideal sphere into an asymmetrical ellipsoid.

- **Sensor Imperfections:** Manufacturing defects like scale factor errors (uneven sensitivity on each axis) and non-orthogonality (the three axes are not perfectly 90 degrees apart) further compress and tilt the shape.

With that said by rotating the magnetometer and gyroscope in multiple orientations, 
you collect a set of data points. 

Algorithms—such as **MATLAB Magnetometer Calibration** calculate the mathematical parameters of the resulting ellipsoid. 

The calibration process then generates a correction matrix that essentially shrinks, stretches, and centers the distorted ellipsoid back into a perfect, centered sphere, yielding true magnetic north and reliable attitude tracking.
