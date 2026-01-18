/*
  Standalone sensor test
*/

#include <MPU9250_asukiaaa.h>

MPU9250_asukiaaa mpu9250;

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("Initializing I2C...");
  Wire.begin(21,22);
  mpu9250.setWire(&Wire);

  Serial.println("Initializing sensor...");
  uint8_t sensorId;
  if (mpu9250.readId(&sensorId) == 0) {
    Serial.print("Device ID: ");
    Serial.println(sensorId);
  } else {
    Serial.println("Cannot find MPU9250. Check wiring!");
    while (1); 
  }
  mpu9250.beginAccel();
}

void loop() {
  // Read Accelerometer values
  if(mpu9250.accelUpdate() == 0) {
    float aX = mpu9250.accelX();
    float aY = mpu9250.accelY();
    float aZ = mpu9250.accelZ();
    // Calculaiting resultant acceleration (magnitude)
    float totalAcc = sqrt(pow(aX, 2) + pow(aY, 2) + pow(aZ, 2));

    Serial.print("X: "); Serial.print(aX);
    Serial.print(" | Y: "); Serial.print(aY);
    Serial.print(" | Z: "); Serial.print(aZ);
    Serial.print(" | Mag: "); Serial.println(totalAcc);
  } else {
    Serial.println("Failed to read accel data");
  }

  delay(100);

}
