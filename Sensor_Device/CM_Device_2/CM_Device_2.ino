#include <Wire.h>
#include <MPU9250.h>

#define SDA_PIN 21
#define SCL_PIN 22

MPU9250 mpu;

void setup() {
  Serial.begin(115200);
  delay(1000);


  Wire.begin(SDA_PIN, SCL_PIN);

  if (!mpu.setup(0x68)) {  
    Serial.println("MPU9250 connection failed!");
    while (1);
  }
  
  Serial.println("MPU9250 initialized successfully");
}

void loop() {
  if (mpu.update()) {
    Serial.print("Accel (g): ");
    Serial.print(mpu.getAccX()); Serial.print(", ");
    Serial.print(mpu.getAccY()); Serial.print(", ");
    Serial.print(mpu.getAccZ());

    // Serial.print(" | Gyro (deg/s): ");
    // Serial.print(mpu.getGyroX()); Serial.print(", ");
    // Serial.print(mpu.getGyroY()); Serial.print(", ");
    // Serial.print(mpu.getGyroZ());

    // Serial.print(" | Mag (uT): ");
    // Serial.print(mpu.getMagX()); Serial.print(", ");
    // Serial.print(mpu.getMagY()); Serial.print(", ");
    // Serial.print(mpu.getMagZ());

    Serial.print(" | Temp (°C): ");
    Serial.println(mpu.getTemperature());
  }

  delay(100);
}