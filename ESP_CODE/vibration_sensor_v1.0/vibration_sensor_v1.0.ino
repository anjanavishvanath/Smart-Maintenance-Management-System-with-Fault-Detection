/*
 * PreSense ESP32 firmware — v1.0
 * ----------------------------------
 * Properly-provisioned vibration sensor:
 *   1. On first boot (no WiFi creds in NVS) → start a captive-portal AP so the
 *      user can enter SSID / password / org / asset_id / SLPT.
 *   2. With creds present but not yet activated → connect WiFi, exchange the
 *      SLPT for MQTT credentials at /api/devices/activate, persist those.
 *   3. Fully provisioned → connect WiFi + MQTT, stream telemetry.
 *
 * A long-press of GPIO 0 (BOOT button, ≥5 s) wipes the NVS namespace and reboots
 * into provisioning mode. The on-board LED on GPIO 2 signals state.
 *
 * Files in this sketch (Arduino IDE concatenates them in alphabetical order):
 *   - vibration_sensor_v1.0.ino  (this file: setup/loop, globals, prototypes)
 *   - activation.ino             (POST /activate, persist response)
 *   - factory_reset.ino          (long-press button task)
 *   - mqtt_n_imu.ino             (sampling + MQTT tasks)
 *   - nvs_config.ino             (Config load/save/clear)
 *   - provisioning.ino           (AP mode + captive portal + form)
 *   - status_led.ino             (LED patterns)
 *   - wifi_helper.ino            (station-mode connect + event handlers)
 *
 * See README.md in this folder for wiring, libraries, and the full setup walkthrough.
 */

#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>
#include <ESPmDNS.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <PubSubClient.h>
#include <SPI.h>
#include "mpu6500.h"

// ================= FIRMWARE VERSION =================
#define FW_VERSION "1.0.0"

// ================= HARDWARE PINS =================
// Override these to match your wiring if you've changed it from the v0.4 layout.
const int PIN_LED        = 2;   // Built-in LED on most ESP32 dev boards
const int PIN_RESET_BTN  = 0;   // BOOT button — internal pullup; held LOW = pressed
const int PIN_IMU_CS     = 5;   // MPU-6500 SPI chip-select
const int PIN_IMU_SCK    = 18;
const int PIN_IMU_MISO   = 19;
const int PIN_IMU_MOSI   = 23;

// ================= NVS LAYOUT =================
// Namespace bumped from v0.x ("device_config") so older flag values are ignored.
const char* NVS_NAMESPACE   = "presense_v1";
const uint8_t NVS_SCHEMA    = 1;

// NVS keys (≤15 chars per Espressif Preferences limit)
const char* K_SCHEMA      = "schema_v";
const char* K_WIFI_SSID   = "wifi_ssid";
const char* K_WIFI_PASS   = "wifi_pass";
const char* K_SLPT        = "slpt";
const char* K_ORG         = "org";
const char* K_ASSET_ID    = "asset_id";
const char* K_DEV_NAME    = "dev_name";
const char* K_BROKER      = "broker";
const char* K_MQTT_USER   = "mqtt_user";
const char* K_MQTT_PASS   = "mqtt_pass";
const char* K_ACTIVATED   = "activated";

// ================= CONFIG STRUCT =================
struct Config {
  String   wifi_ssid;
  String   wifi_pass;
  String   slpt;          // cleared once activation succeeds
  String   organization;  // e.g. "Divor"
  uint16_t asset_id;      // numeric, used in topic
  String   device_name;   // optional, free text
  String   broker;        // host or IP, no scheme
  String   mqtt_user;
  String   mqtt_pass;
  bool     activated;
};

// ================= BOOT MODE =================
enum BootMode {
  MODE_PROVISIONING,  // No WiFi creds yet → AP + captive portal
  MODE_ACTIVATING,    // Have WiFi but no MQTT creds → connect + /activate
  MODE_RUNNING        // Fully provisioned → telemetry
};

enum LedPattern {
  LED_OFF,
  LED_PROVISIONING,   // slow blink
  LED_CONNECTING,     // fast blink
  LED_ACTIVATING,     // double-blink
  LED_RUNNING,        // solid on
  LED_ERROR           // triple-blink
};

// ================= GLOBAL OBJECTS =================
Preferences preferences;
Config       config;
BootMode     currentMode = MODE_PROVISIONING;
volatile LedPattern ledPattern = LED_OFF;

WebServer    apServer(80);
DNSServer    dnsServer;

WiFiClient   espClient;
PubSubClient mqttClient(espClient);
bfs::Mpu6500 imu(&SPI, PIN_IMU_CS);

QueueHandle_t sampleQueue = nullptr;

// JSON / MQTT buffers
StaticJsonDocument<8192> jsonDoc;
char mqttBuffer[8192];

const float G_TO_MPS2          = 9.80665f;
const float VIBRATION_THRESHOLD = 0.05f;
const int   BATCH_SIZE         = 80;

String deviceTopic = "";

// ================= FORWARD DECLARATIONS =================
// Implementations live in the companion .ino files.
bool   loadConfig(Config& out);
void   saveWifiAndProvisioning(const Config& in);
void   saveActivationResult(const String& broker, const String& user, const String& pass);
void   clearAllConfig();

void   startProvisioningPortal();
bool   connectWifiStation(const Config& cfg, uint32_t timeoutMs);
bool   attemptActivation(Config& cfg);

void   startTelemetryTasks(const Config& cfg);
void   resetButtonTask(void* pv);
void   ledTask(void* pv);

// ================= SETUP =================
void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println();
  Serial.printf("PreSense firmware v%s booting...\n", FW_VERSION);

  pinMode(PIN_LED, OUTPUT);
  digitalWrite(PIN_LED, LOW);
  pinMode(PIN_RESET_BTN, INPUT_PULLUP);

  // The reset-button + LED tasks run in the background regardless of mode so
  // the user can always force-reprovision and so they get visual feedback.
  xTaskCreatePinnedToCore(resetButtonTask, "reset_btn", 2048, nullptr, 1, nullptr, 0);
  xTaskCreatePinnedToCore(ledTask,         "led",       2048, nullptr, 1, nullptr, 0);

  if (!loadConfig(config)) {
    Serial.println("[main] No / invalid config in NVS → starting provisioning AP.");
    currentMode = MODE_PROVISIONING;
    ledPattern = LED_PROVISIONING;
    startProvisioningPortal();   // returns when user submits the form (then we reboot)
    return;
  }

  ledPattern = LED_CONNECTING;
  if (!connectWifiStation(config, /*timeoutMs=*/30000)) {
    Serial.println("[main] WiFi connection failed → falling back to AP mode (creds preserved).");
    ledPattern = LED_ERROR;
    delay(1500);
    ledPattern = LED_PROVISIONING;
    startProvisioningPortal();
    return;
  }

  if (!config.activated || config.mqtt_user.isEmpty()) {
    Serial.println("[main] WiFi up; attempting device activation...");
    currentMode = MODE_ACTIVATING;
    ledPattern = LED_ACTIVATING;
    if (!attemptActivation(config)) {
      Serial.println("[main] Activation failed; rebooting to retry / fall back to AP.");
      ledPattern = LED_ERROR;
      delay(2000);
      ESP.restart();
    }
    // attemptActivation persists creds; reload to pick them up before we proceed.
    loadConfig(config);
  }

  currentMode = MODE_RUNNING;
  ledPattern = LED_RUNNING;
  startTelemetryTasks(config);
  Serial.println("[main] System running.");
}

void loop() {
  // Telemetry runs in FreeRTOS tasks; AP mode runs its own server.handleClient loop
  // inside startProvisioningPortal. Nothing needs to happen here.
  delay(1000);
}
