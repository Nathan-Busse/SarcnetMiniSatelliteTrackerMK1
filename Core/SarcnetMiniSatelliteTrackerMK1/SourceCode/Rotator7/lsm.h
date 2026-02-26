#ifndef LSM_H
#define LSM_H

#include <Arduino.h>
#include <Wire.h>
#include "cal.h"
#include "fil.h"
#include "vec.h"

//Sensor type definitions
#define LSM303D 0       //For LSM303D sensor
#define LSM303DLHC 1    //For LSM303DLHC sensor

//LSM303D Registers
#define LSM303D_ADDRESS 0b0011101
#define LSM303D_OUT_X_L_A 0x28
#define LSM303D_OUT_X_L_M 0x08
#define LSM303D_CTRL1 0x20
#define LSM303D_CTRL2 0x21
#define LSM303D_CTRL3 0x22
#define LSM303D_CTRL4 0x23
#define LSM303D_CTRL5 0x24
#define LSM303D_CTRL6 0x25
#define LSM303D_CTRL7 0x26

//LSM303DLHC Registers
#define LSM303DLHC_ADDRESS_A 0x1D   // Accelerometer address (corrected)
#define LSM303DLHC_ADDRESS_M 0x1E   // Magnetometer address
#define LSM303DLHC_OUT_X_L_A 0x28
#define LSM303DLHC_OUT_X_H_M 0x03
#define LSM303DLHC_CTRL_REG1_A 0x20
#define LSM303DLHC_CTRL_REG4_A 0x23
#define LSM303DLHC_CRA_REG_M 0x00
#define LSM303DLHC_CRB_REG_M 0x01
#define LSM303DLHC_MR_REG_M 0x02

class Lsm {
  public:
    Lsm(int type, float alpha);
    void begin();
    bool calibrate();
    void readGM();
    void getAzEl();
    //Uncalibrated magnetometer and accelerometer values
    int  mx, my, mz, gx, gy, gz;
    //Calibration data structure
    struct {
      float md;               //The magnetic declination
      Vec me, ge, ms, gs;     //Calibration vectors
    } cal;
    const float rad2deg = 57.295779513;   //Degrees per radian
    void reset();
    void calStart();
    float az, el;
  private:
    int _type;
    void readG();
    void readM();
    void writeReg(byte address, byte reg, byte value);
    byte readReg(byte address, byte reg);
    //Create calibration objects for each axis
    Cal calMX, calMY, calMZ, calGX, calGY, calGZ;
    //Create filter objects for each axis
    Fil filMX, filMY, filMZ, filGX, filGY, filGZ;
};

#endif
