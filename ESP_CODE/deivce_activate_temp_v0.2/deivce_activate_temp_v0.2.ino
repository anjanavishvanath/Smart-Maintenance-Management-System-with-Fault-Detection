/*
ESP32 MQTT sensor data transmission test
 - ESP as a station
 - WiFi & SLPT cred hardcoded for now
 - Read acc. from MPU9250 get magnitude sqrt(x^2+y^2+z^2)
 - Add to a buffer and transmit when buffer is full
 - Note: only add to buffer when the machine is working
*/

#include <WiFi.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <ArduinoJson.h>
#include <MPU9250_asukiaaa.h>
#include <PubSubClient.h>

// --- Global Objects ---
const char* WIFI_SSID = "SLT_FIBRE";
const char* WIFI_PASS = "Anji@123";
String mqttBroker = "192.168.1.2";
String ACTIVATION_URL = "http://" + mqttBroker + ":5000/api/devices/activate";
String slpt = "bf14436a-4369-4bc5-b94b-65543a736581";
String deviceTopic = "";
long lastMsg = 0;

Preferences preferences;
WiFiClient espClient;
PubSubClient mqttClient(espClient);
MPU9250_asukiaaa mpu9250;

// --- NVS Keys ---
const char* NVS_NAMESPACE = "device_config";
const char* KEY_SSID = "ssid";
const char* KEY_PASS = "pass";
const char* ACTIVATED = "is_activated";
const char* DEVICE_ID = "dev_id";
const char* BROKER_URL = "broker_url";
const char* MQTT_USER = "mqtt_u";
const char* MQTT_PASS = "mqtt_p";

// -- MPU9250 config --
const float VIBRATION_THRESHOLD = 0.05;
const int BATCH_SIZE = 20;

void setup() {
  Serial.begin(115200);
  Wire.begin(21, 22);
  delay(1000);

  // --- LOAD NVS VALUES ---
  if (preferences.begin(NVS_NAMESPACE, true)) {  // Open in read-only mode
    // bool isActivated = preferences.getBool(ACTIVATED, false);
    bool isActivated = true;
    String savedDeviceID = preferences.getString(DEVICE_ID, "");
    String savedBrokerURL = preferences.getString(BROKER_URL, "");
    String savedMqttUser = preferences.getString(MQTT_USER, "");
    String savedMqttPass = preferences.getString(MQTT_PASS, "");
    preferences.end();
    Serial.println("Device Status: " + String(isActivated));
    //hardcoding WIFI Cridentials for now. Later will start in softAP with a form for that
    setupWiFi();

    if (!isActivated) {
      Serial.println("Not Activated. Trying to activate with SLPT");
      activateDevice();
      ESP.restart();
    } else {
      Serial.print("Activated. Ready to send data");
      mqttClient.setServer(mqttBroker.c_str(), 1883);
      mqttClient.setBufferSize(2048);
      deviceTopic = "presense/Divor/1/" + WiFi.macAddress() + "/telemetry";
    }
  } else {
    Serial.println("Critical Error: NVS Namespace failed to open.");
  }

  // --- Initializing sensor ---
  mpu9250.setWire(&Wire);
  mpu9250.beginAccel();
}

void loop() {
  if (!mqttClient.connected()) reconnect();
  mqttClient.loop();

  // --- Batching Logic ---
  StaticJsonDocument<2048> doc;
  JsonArray samples = doc.createNestedArray("samples");
  bool isMoving = false;

  for (int i = 0; i < BATCH_SIZE; i++) {
    if (mpu9250.accelUpdate() == 0) {
      float ax = mpu9250.accelX();
      float ay = mpu9250.accelY();
      float az = mpu9250.accelZ();

      // Checking if the motor is operating. -1 on z axis assumes vertical mounting. might have to make this more dynamic.
      // make inital measurement and then if > 1, -1 from that axis or all 3 if an angular mount
      if (fabsf(ax) > VIBRATION_THRESHOLD || fabsf(ay) > VIBRATION_THRESHOLD || fabsf(az - 1) > VIBRATION_THRESHOLD) {
        isMoving = true;
      }

      JsonObject obj = samples.createNestedObject();
      obj["ax"] = ax;
      obj["ay"] = ay;
      obj["az"] = az;
      Serial.println("Readings:- x:"+String(ax)+" | y:"+String(ay)+" | z:"+String(az));
    }
    delay(20);  // 50Hz sampling rate
  }

  // send data if moving or every 5 minutes (heartbeat)
  if (isMoving || (millis() - lastMsg > 300000)) {
    char buffer[2048];
    serializeJson(doc, buffer);

    if(mqttClient.publish(deviceTopic.c_str(), buffer)) {
      Serial.println("Batch successfully sent to broker");
    } else {
      Serial.println("MQTT Publish failed! (Check buffer size or connection)");
    }
    lastMsg = millis();
  }
}

void setupWiFi() {
  Serial.println("Connecting to WiFi...");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  Serial.print("MAC Address: ");
  Serial.println(WiFi.macAddress());
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("\n WiFi connection failed");
    return;
  }

  Serial.println("\n WiFi connected");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
}

void reconnect() {
  while (!mqttClient.connected()) {
    Serial.println("Attempting MQTT Connection...");
    if (mqttClient.connect("ESP32_Vibe_Sensor")) {
      Serial.println("Connected");
    } else {
      delay(5000);
    }
  }
}

void activateDevice() {
  HTTPClient http;
  String macAddr = WiFi.macAddress();
  String payload = "{\"slpt\":\"" + slpt + "\", \"mac\":\"" + macAddr + "\"}";

  Serial.println("Checkpoint 1: Sending POST...");
  http.begin(ACTIVATION_URL);
  http.addHeader("Content-Type", "application/json");

  int httpResponseCode = http.POST(payload);

  if (httpResponseCode > 0) {
    Serial.print("HTTP Code: ");
    Serial.println(httpResponseCode);

    Serial.println("Checkpoint 2: Getting String...");
    String response = http.getString();

    Serial.println("Response received: " + response);

    // Increase buffer to 1024 for safety
    StaticJsonDocument<1024> activationResponse;
    DeserializationError error = deserializeJson(activationResponse, response);

    if (error) {
      Serial.print("JSON Error: ");
      Serial.println(error.f_str());
      return;
    }

    Serial.println("Checkpoint 3: Writing to NVS...");

    // Open NVS once in Read/Write mode (false)
    if (preferences.begin(NVS_NAMESPACE, false)) {

      // Use .as<const char*>() for direct NVS storage
      preferences.putString(DEVICE_ID, activationResponse["device_id"].as<const char*>());
      preferences.putString(BROKER_URL, activationResponse["broker_url"].as<const char*>());
      preferences.putString(MQTT_USER, activationResponse["mqtt_user"].as<const char*>());
      preferences.putString(MQTT_PASS, activationResponse["mqtt_pass"].as<const char*>());

      // Use as<String> to ensure comparison works
      String msg = activationResponse["msg"].as<String>();
      if (msg == "Device activated") {
        preferences.putBool(ACTIVATED, true);
        Serial.println("Status set to ACTIVATED");
      } else {
        preferences.putBool(ACTIVATED, false);
        Serial.println("Status set to FAILED");
      }

      preferences.end();
      Serial.println("Checkpoint 4: NVS Closed. Restarting in 2 seconds...");
      delay(2000);
    } else {
      Serial.println("NVS Error: Could not open namespace for writing");
    }

  } else {
    Serial.print("HTTP Failed: ");
    Serial.println(http.errorToString(httpResponseCode));
  }
  http.end();
}
