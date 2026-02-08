/*
ESP32 MQTT sensor data transmission test
 - ESP as a station
 - WiFi & SLPT cred hardcoded for now
 - Read acc. from MPU9250 get magnitude sqrt(x^2+y^2+z^2) ?
 - Note: only add to buffer when the machine is working
*/

#include <WiFi.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <ArduinoJson.h>
#include <MPU9250_asukiaaa.h>
#include <PubSubClient.h>

// ================= GLOBAL OBJECTS =================
Preferences preferences;
WiFiClient espClient;
PubSubClient mqttClient(espClient);
MPU9250_asukiaaa mpu9250;

QueueHandle_t sampleQueue;

// ================= CONFIG =================
const char* WIFI_SSID = "SLT_FIBRE";
const char* WIFI_PASS = "Anji@123";
String mqttBroker = "192.168.1.3";
String deviceTopic = "";

const float VIBRATION_THRESHOLD = 0.05;
const int BATCH_SIZE = 80;

// JSON buffers
StaticJsonDocument<8192> jsonDoc;
char mqttBuffer[8192];

// ================= SAMPLE STRUCT =================
struct SamplePacket {
  uint32_t ts;  // window timestamp (micros)
  float ax;
  float ay;
  float az;
};


// ================= WIFI =================
void setupWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) delay(500);
}

// ================= MQTT =================
void reconnect() {
  while (!mqttClient.connected()) {
    mqttClient.connect("ESP32_Vibe_Sensor");
    delay(1000);
  }
}

// ================= SAMPLING TASK (CORE 1) =================

void samplingTask(void* pv) {
  const TickType_t freq = pdMS_TO_TICKS(5);
  TickType_t lastWake = xTaskGetTickCount();

  SamplePacket window[BATCH_SIZE];
  int count = 0;
  float maxMagInWindow = 0;
  uint32_t windowTs = 0;

  while (true) {
    int status = mpu9250.accelUpdate();
    // 1. Check if update was successful
    if (status == 0) {
      float ax = mpu9250.accelX();
      float ay = mpu9250.accelY();
      float az = mpu9250.accelZ();

      // 2. Fix the magnitude logic
      float rawMag = sqrt(ax * ax + ay * ay + az * az);

      // If the sensor returns exactly 0, it's a hardware failure
      if (rawMag > 0.001) {
        float mag = fabs(rawMag - 1.0);
        if (mag > maxMagInWindow) maxMagInWindow = mag;

        if (count == 0) windowTs = micros();
        window[count] = { windowTs, ax, ay, az };
        count++;
      }
    } else {
      Serial.println("I2C Error!");
      // Try to recover the bus
      Wire.end();
      vTaskDelay(pdMS_TO_TICKS(10));  // Give it a moment to breathe 
      Wire.begin(21, 22);
      Wire.setClock(100000);
      vTaskDelay(pdMS_TO_TICKS(10));  // Give it a moment to breathe
      mpu9250.beginAccel();
      continue;                       // Skip this sample
    }

    if (count >= BATCH_SIZE) {
      // Lower the threshold slightly? 0.02 is usually safe for "Healthy"
      if (maxMagInWindow > 0.02) {
        for (int i = 0; i < BATCH_SIZE; i++) {
          xQueueSend(sampleQueue, &window[i], 0);
        }
      }
      count = 0;
      maxMagInWindow = 0;
    }
    vTaskDelayUntil(&lastWake, freq);
  }
}

// ================= MQTT TASK (CORE 0) =================
void mqttTask(void* pv) {
  SamplePacket s;
  int sampleIndex = 0;
  uint32_t batchTs = 0;

  while (true) {

    if (!mqttClient.connected()) reconnect();
    mqttClient.loop();

    if (xQueueReceive(sampleQueue, &s, pdMS_TO_TICKS(10))) {

      if (sampleIndex == 0) {
        jsonDoc.clear();
        batchTs = s.ts;  //Get window timestamp
        jsonDoc["ts"] = batchTs;
      }

      JsonArray samples = jsonDoc["samples"];
      if (samples.isNull()) samples = jsonDoc.createNestedArray("samples");

      JsonObject obj = samples.createNestedObject();
      obj["ax"] = s.ax;
      obj["ay"] = s.ay;
      obj["az"] = s.az;

      sampleIndex++;

      if (sampleIndex >= BATCH_SIZE) {
        serializeJson(jsonDoc, mqttBuffer);
        if (!mqttClient.publish(deviceTopic.c_str(), mqttBuffer)) {
          Serial.println("MQTT publish failed");
        }
        sampleIndex = 0;
      }
    }
  }
}

// ================= SETUP =================
void setup() {
  Serial.begin(115200);
  setupWiFi();

  Wire.begin(21, 22);
  Wire.setClock(100000);
  mpu9250.setWire(&Wire);
  mpu9250.beginAccel();

  mqttClient.setServer(mqttBroker.c_str(), 1883);
  mqttClient.setKeepAlive(120);
  mqttClient.setBufferSize(8192);

  deviceTopic = "presense/Divor/1/" + WiFi.macAddress() + "/telemetry";

  sampleQueue = xQueueCreate(400, sizeof(SamplePacket));

  xTaskCreatePinnedToCore(
    samplingTask, "Sampling Task",
    4096, NULL, 2, NULL, 1);  // Core 1

  xTaskCreatePinnedToCore(
    mqttTask, "MQTT Task",
    8192, NULL, 1, NULL, 0);  // Core 0
}

void loop() {
  // RTOS handles everything
}
