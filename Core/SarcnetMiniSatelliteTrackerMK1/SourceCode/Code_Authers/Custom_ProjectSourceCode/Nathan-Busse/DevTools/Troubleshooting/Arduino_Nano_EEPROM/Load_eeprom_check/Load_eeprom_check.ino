#include <EEPROM.h>
#include <LSM303.h>

// Calculated from previous step
int16_t minX = -500, maxX = 300; // Replace with actual values
int16_t minY = -400, maxY = 400;
int16_t minZ = -300, maxZ = 500;

void setup() {
  // Store Min/Max in EEPROM (use EEPROM.put for struct/int)
  EEPROM.put(0, minX); EEPROM.put(2, maxX);
  EEPROM.put(4, minY); EEPROM.put(6, maxY);
  EEPROM.put(8, minZ); EEPROM.put(10, maxZ);
  Serial.println("Calibrated data saved!");
}
void loop() {}
