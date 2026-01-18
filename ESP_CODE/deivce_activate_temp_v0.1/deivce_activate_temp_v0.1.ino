/*
ESP32 activation through SLPT test
 - ESP as a station
 - WiFi cred hardcoded
 - SLPT hardcoded for activation
 - Data saved to NVS but not used 
*/

#include <WiFi.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <ArduinoJson.h>

const char* WIFI_SSID = "SLT_FIBRE";
const char* WIFI_PASS = "Anji@123";
const char* ACTIVATION_URL = "http://192.168.1.2:5000/api/devices/activate";
String slpt = "e215ed81-77b4-4475-87f8-3435dd779fb1";

// --- Global Objects ---
Preferences preferences;

// --- NVS Keys ---
const char* NVS_NAMESPACE = "device_config";
const char* KEY_SSID = "ssid";
const char* KEY_PASS = "pass";
const char* ACTIVATED = "activation_status";
const char* DEVICE_ID = "device_id";
const char* BROKER_URL = "broker_url";
const char* MQTT_USER = "mqtt_user";
const char* MQTT_PASS = "mqtt_pass";

void setup() {
  Serial.begin(115200);
  delay(1000);

  // --- LOAD NVS VALUES ---
  preferences.begin(NVS_NAMESPACE, true);  // Open in read-only mode
  //hardcoding WIFI Cridentials for now. Later will start in softAP with a form for that
  bool isActivated = preferences.getBool(ACTIVATED, false);
  String savedDeviceID = preferences.getString(DEVICE_ID, "");
  String savedBrokerURL = preferences.getString(BROKER_URL, "");
  String savedMqttUser = preferences.getString(MQTT_USER, "");
  String savedMqttPass = preferences.getString(MQTT_PASS, "");
  preferences.end();

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
    Serial.println("\n❌ WiFi connection failed");
    return;
  }

  Serial.println("\n✅ WiFi connected");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());

  if (!isActivated) {
    activateDevice();
  } else {
    Serial.print("Activated. Ready to send data");
  }
}

void loop() {
  // put your main code here, to run repeatedly:
}

void activateDevice() {
  HTTPClient http;
  String macAddr = WiFi.macAddress();
  String payload = "{\"slpt\":\"" + slpt + "\", \"mac\":\"" + macAddr + "\"}";
  http.begin(ACTIVATION_URL);
  http.addHeader("Content-Type", "application/json");

  int httpResponseCode = http.POST(payload);

  if (httpResponseCode > 0) {
    Serial.print("HTTP Response code: ");
    Serial.println(httpResponseCode);

    String response = http.getString();
    Serial.println("Response body:");
    Serial.println(response);
    // --- DESERIALIZE WITH ARDUINO JSON ---
    StaticJsonDocument<512> activationResponse;
    DeserializationError error= deserializeJson(activationResponse, response);
    if (error) {
      Serial.print("deserializeJson() failed: ");
      Serial.println(error.f_str());
      return;
    }
    preferences.begin(NVS_NAMESPACE, false);  // Open in read-write mode
    preferences.putString(DEVICE_ID, activationResponse["device_id"].as<String>());
    preferences.putString(BROKER_URL, activationResponse["broker_url"].as<String>());
    preferences.putString(MQTT_USER, activationResponse["mqtt_user"].as<String>());
    preferences.putString(MQTT_PASS, activationResponse["mqtt_pass"].as<String>());
    if (activationResponse["msg"] == "Device activated") {
      preferences.putBool(ACTIVATED, true);
    } else {
      preferences.putBool(ACTIVATED, false);
    }
    preferences.end();
  } else {
    Serial.print("HTTP request failed, error: ");
    Serial.println(http.errorToString(httpResponseCode));
  }

  http.end();
}
