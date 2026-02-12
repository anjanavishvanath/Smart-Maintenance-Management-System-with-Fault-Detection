/*
ESP32 MQTT sensor data transmission test
 - ESP as a station
 - WiFi & SLPT cred hardcoded for now
 - Read acc. from MPU9250 (6500) use Bolder lib -> convert m/s2 to g-force
*/

#include <WiFi.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <PubSubClient.h>
#include <SPI.h>
#include "mpu6500.h"

// ================= GLOBAL OBJECTS =================
Preferences preferences;
WiFiClient espClient;
PubSubClient mqttClient(espClient);
bfs::Mpu6500 imu(&SPI, 5);  // CS pin on GPIO 5

QueueHandle_t sampleQueue;

// ================= CONFIG =================
const char* WIFI_SSID = "SLT_FIBRE";
const char* WIFI_PASS = "Anji@123";
String mqttBroker = "192.168.1.3";
String ACTIVATION_URL = "http://" + mqttBroker + ":5000/api/devices/activate";
String slpt = "b005702e-56ab-4427-b34f-8438d95e7d14";
// [TODO] pull broker url, mqtt username, password, activaton url from backend and save in NVS as well
const char* NVS_NAMESPACE = "device_config";
const char* ACTIVATED = "is_activated";
String deviceTopic = "";

const float VIBRATION_THRESHOLD = 0.02;
const int BATCH_SIZE = 80;
const float G_TO_MPS2 = 9.80665;

// JSON buffers
StaticJsonDocument<8192> jsonDoc;
char mqttBuffer[8192];

// ================= SAMPLE STRUCT =================
struct SamplePacket {
  uint32_t ts;
  float ax, ay, az;
};


// ================= WIFI =================
void setupWiFi() {
  Serial.print("Connecting to WiFi");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) {
    Serial.print(".");
    delay(200);
  }
  Serial.print("Connected to WiFi");
}

void activateDevice() {
  HTTPClient http;
  String macAddr = WiFi.macAddress();
  Serial.println("mac: "+ macAddr);
  String payload = "{\"slpt\":\"" + slpt + "\", \"mac\":\"" + macAddr + "\"}";

  http.begin(ACTIVATION_URL);
  http.addHeader("Content-Type", "application/json");
  int res = http.POST(payload);
  if (res > 0) {
    String response = http.getString();
    Serial.println("Response received: " + response);

    StaticJsonDocument<1024> activationResponse;
    DeserializationError error = deserializeJson(activationResponse, response);

    if (error) {
      Serial.print("JSON Error: ");
      Serial.println(error.f_str());
      return;
    }
    //  should get device_id, broker_url, mqtt_user, mqtt_pass, msg in json
    if (preferences.begin(NVS_NAMESPACE, false)) { // Open in read/write mode
      String msg = activationResponse["msg"].as<String>();
      if (msg == "Device activated") {
        preferences.putBool(ACTIVATED, true);
        Serial.println("Status set to ACTIVATED. Restarting...");
      } else {
        preferences.putBool(ACTIVATED, false);
        Serial.println("Status set to FAILED");
      }
      preferences.end();
      delay(2000);
    } else {
      Serial.println("NVS Error: Could not open namespace for writing");
    }
  } else {
    Serial.print("HTTP Failed: ");
    Serial.println(http.errorToString(res));
  }
  http.end();
  delay(2000);
}

// ================= MQTT =================
void reconnect() {
  while (!mqttClient.connected()) {
    if (mqttClient.connect("ESP32_Vibe_Sensor_SPI", NULL, NULL, "status/topic", 0, true, "offline")) {
      mqttClient.publish("status/topic", "online", true);
    } else {
      delay(2000);
    }
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

  Serial.println("Sampling Task Started on Core 1");

  while (true) {
    if (imu.Read()) {
      float ax = imu.accel_x_mps2() / G_TO_MPS2;
      float ay = imu.accel_y_mps2() / G_TO_MPS2;
      float az = imu.accel_z_mps2() / G_TO_MPS2;

      float mag = fabs(sqrt(ax * ax + ay * ay + az * az) - 1.0);
      if (mag > maxMagInWindow) maxMagInWindow = mag;

      if (count == 0) windowTs = micros();
      window[count] = { windowTs, ax, ay, az };
      count++;

      if (count >= BATCH_SIZE) {
        // If it's too quiet, print a dot just to know the sensor is alive
        if (maxMagInWindow <= VIBRATION_THRESHOLD) {
          Serial.print(".");
        } else {
          Serial.printf("\nSending batch! Max Mag: %.4f\n", maxMagInWindow);
          for (int i = 0; i < BATCH_SIZE; i++) {
            xQueueSend(sampleQueue, &window[i], 0);
          }
        }
        count = 0;
        maxMagInWindow = 0;
      }
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
  delay(1000);
  // [TODO] Start as an AP and get wifi cred
  setupWiFi();

  // LOAD NVS Values
  if (preferences.begin(NVS_NAMESPACE, false)) {
    bool isActivated = preferences.getBool(ACTIVATED, false);
    preferences.end();

    Serial.println("Device Status: " + String(isActivated));

    if (!isActivated) {
      Serial.println("Not Activated. Trying to activate with SLPT");
      activateDevice();
      ESP.restart();
    } else {
      // Init SPI
      SPI.begin(18, 19, 23, 5);
      pinMode(5, OUTPUT);
      digitalWrite(5, HIGH);

      Serial.println("\nInitializing IMU...");
      if (!imu.Begin()) {
        Serial.println("IMU SPI init failed! Check wiring (MISO/MOSI/SCK/CS).");
        while (1) delay(10);
      }

      Serial.println("IMU Initialized. Configuring Sample Rate...");
      if (!imu.ConfigSrd(4)) {
        Serial.println("SRD Config Failed");
      }

      // Construction of topic and MQTT setup
      deviceTopic = "presense/Divor/1/" + WiFi.macAddress() + "/telemetry";
      Serial.println("Topic: " + deviceTopic);

      mqttClient.setServer(mqttBroker.c_str(), 1883);
      mqttClient.setBufferSize(8192);

      sampleQueue = xQueueCreate(400, sizeof(SamplePacket));

      xTaskCreatePinnedToCore(samplingTask, "SamplingTask", 4096, NULL, 2, NULL, 1);
      xTaskCreatePinnedToCore(mqttTask, "MQTTTask", 8192, NULL, 1, NULL, 0);

      Serial.println("System Ready.");
    }
  } else {
    Serial.println("Critical Error: NVS Namespace failed to open.");
  }
}

void loop() {
  // RTOS handles everything
}
