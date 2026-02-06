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

Preferences preferences;
WiFiClient espClient;
PubSubClient mqttClient(espClient);
MPU9250_asukiaaa mpu9250;
// [TODO] hardcoding for now. Should pull from a from through AP mode
const char* WIFI_SSID = "SLT_FIBRE";
const char* WIFI_PASS = "Anji@123";

// --- NVS Keys ---
const char* NVS_NAMESPACE = "device_config";
const char* ACTIVATED = "is_activated";
// [TODO] pull broker url, mqtt username, password, activaton url from backend and save in NVS as well
String mqttBroker = "192.168.1.3";
String ACTIVATION_URL = "http://" + mqttBroker + ":5000/api/devices/activate";
String slpt = "46e3fe90-6e3b-4c19-9f4a-18587f1cbb54";

// --- Global Variables ---
String deviceTopic = "";
unsigned long lastSampleTime = 0;
const unsigned long interval = 5; // to control sample frequency (200Hz)
long lastMsg = 0;
const float VIBRATION_THRESHOLD = 0.05;
const int BATCH_SIZE = 20;
StaticJsonDocument<4096> jsonDoc;
char mqttBuffer[4096];
int sampleIndex = 0;

void setup() {
  Serial.begin(115200);
  delay(1000);

  // [TODO] Start as an AP and get wifi cred
  setupWiFi();

  // --- LOAD NVS Values ---
  if (preferences.begin(NVS_NAMESPACE, false)) {  // open in read/write mode. Will create namespace if not available
    bool isActivated = preferences.getBool(ACTIVATED, false);
    preferences.end();

    Serial.println("Device Status: " + String(isActivated));

    if (!isActivated) {
      Serial.println("Not Activated. Trying to activate with SLPT");
      activateDevice();
      ESP.restart();
    } else {
      Serial.println("Activated. Ready to send data");
      // --- Sensor init ---
      Wire.begin(21, 22);
      mpu9250.setWire(&Wire);
      mpu9250.beginAccel();
      // --- MQTT init ---
      mqttClient.setServer(mqttBroker.c_str(), 1883);
      mqttClient.setBufferSize(2048);
      deviceTopic = "presense/Divor/1/" + WiFi.macAddress() + "/telemetry";
    }
  } else {
    Serial.println("Critical Error: NVS Namespace failed to open.");
  }
}

void loop() {
  if (!mqttClient.connected()) reconnect();
  mqttClient.loop();
  batchAndSendData();
}
