// Paste over your current sketch (only minor changes)
#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <time.h>

// --- CONFIG ---
// NOTE: Fill these in
const char* WIFI_SSID = "SLT_FIBRE";
const char* WIFI_PASSWORD = "Anji@123";

const char* DEVICE_ID = "dev000";

const char* MQTT_HOST = "8931093ac74c4ab0ac3f0cb16e92d38b.s1.eu.hivemq.cloud";
const int MQTT_PORT = 8883;  // TLS port

const char* MQTT_USERNAME = "dev000-Hq8JsuNz";
const char* MQTT_PASSWORD = "pVD6cVJoOipWW_WzwlJ2mEg2m7seiCVv";

WiFiClientSecure secureClient;
PubSubClient mqttClient(secureClient);

// telemetry topics
String telemetryTopic;
String statusTopic;
String configTopic;

// CA PEM (same as you used)
const char CA_PEM[] PROGMEM =  R"EOF(
-----BEGIN CERTIFICATE-----
MIIFazCCA1OgAwIBAgIRAIIQz7DSQONZRGPgu2OCiwAwDQYJKoZIhvcNAQELBQAw
TzELMAkGA1UEBhMCVVMxKTAnBgNVBAoTIEludGVybmV0IFNlY3VyaXR5IFJlc2Vh
cmNoIEdyb3VwMRUwEwYDVQQDEwxJU1JHIFJvb3QgWDEwHhcNMTUwNjA0MTEwNDM4
WhcNMzUwNjA0MTEwNDM4WjBPMQswCQYDVQQGEwJVUzEpMCcGA1UEChMgSW50ZXJu
ZXQgU2VjdXJpdHkgUmVzZWFyY2ggR3JvdXAxFTATBgNVBAMTDElTUkcgUm9vdCBY
MTCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBAK3oJHP0FDfzm54rVygc
h77ct984kIxuPOZXoHj3dcKi/vVqbvYATyjb3miGbESTtrFj/RQSa78f0uoxmyF+
0TM8ukj13Xnfs7j/EvEhmkvBioZxaUpmZmyPfjxwv60pIgbz5MDmgK7iS4+3mX6U
A5/TR5d8mUgjU+g4rk8Kb4Mu0UlXjIB0ttov0DiNewNwIRt18jA8+o+u3dpjq+sW
T8KOEUt+zwvo/7V3LvSye0rgTBIlDHCNAymg4VMk7BPZ7hm/ELNKjD+Jo2FR3qyH
B5T0Y3HsLuJvW5iB4YlcNHlsdu87kGJ55tukmi8mxdAQ4Q7e2RCOFvu396j3x+UC
B5iPNgiV5+I3lg02dZ77DnKxHZu8A/lJBdiB3QW0KtZB6awBdpUKD9jf1b0SHzUv
KBds0pjBqAlkd25HN7rOrFleaJ1/ctaJxQZBKT5ZPt0m9STJEadao0xAH0ahmbWn
OlFuhjuefXKnEgV4We0+UXgVCwOPjdAvBbI+e0ocS3MFEvzG6uBQE3xDk3SzynTn
jh8BCNAw1FtxNrQHusEwMFxIt4I7mKZ9YIqioymCzLq9gwQbooMDQaHWBfEbwrbw
qHyGO0aoSCqI3Haadr8faqU9GY/rOPNk3sgrDQoo//fb4hVC1CLQJ13hef4Y53CI
rU7m2Ys6xt0nUW7/vGT1M0NPAgMBAAGjQjBAMA4GA1UdDwEB/wQEAwIBBjAPBgNV
HRMBAf8EBTADAQH/MB0GA1UdDgQWBBR5tFnme7bl5AFzgAiIyBpY9umbbjANBgkq
hkiG9w0BAQsFAAOCAgEAVR9YqbyyqFDQDLHYGmkgJykIrGF1XIpu+ILlaS/V9lZL
ubhzEFnTIZd+50xx+7LSYK05qAvqFyFWhfFQDlnrzuBZ6brJFe+GnY+EgPbk6ZGQ
3BebYhtF8GaV0nxvwuo77x/Py9auJ/GpsMiu/X1+mvoiBOv/2X/qkSsisRcOj/KK
NFtY2PwByVS5uCbMiogziUwthDyC3+6WVwW6LLv3xLfHTjuCvjHIInNzktHCgKQ5
ORAzI4JMPJ+GslWYHb4phowim57iaztXOoJwTdwJx4nLCgdNbOhdjsnvzqvHu7Ur
TkXWStAmzOVyyghqpZXjFaH3pO3JLF+l+/+sKAIuvtd7u+Nxe5AW0wdeRlN8NwdC
jNPElpzVmbUq4JUagEiuTDkHzsxHpFKVK7q4+63SM1N95R1NbdWhscdCb+ZAJzVc
oyi3B43njTOQ5yOf+1CceWxG1bQVs5ZufpsMljq4Ui0/1lvh+wjChP4kqKOJ2qxq
4RgqsahDYVvTH9w7jXbyLeiNdd8XM2w9U/t7y0Ff/9yi0GE44Za4rF2LN9d11TPA
mRGunUHBcnWEvgJBQl9nJEiU0Zsnvgc/ubhPgXRR4Xq37Z0j4r7g1SgEEzwxA57d
emyPxgcYxn/eR44/KJ4EBs+lVDR3veyJm+kXQ99b21/+jh5Xos1AnX5iItreGCc=
-----END CERTIFICATE-----
)EOF";

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  Serial.printf("MQTT msg on: %s\n", topic);
  String s;
  for (unsigned int i = 0; i < length; i++) s += (char)payload[i];
  Serial.println("Payload: " + s);
}

bool testTlsConnectOnce() {
  Serial.printf("Testing raw TLS connect to %s:%d ...\n", MQTT_HOST, MQTT_PORT);
  // Try a direct TLS connect (this exercises DNS + TLS handshake, without MQTT)
  bool ok = false;
  // make a fresh temporary client so we don't disturb mqttClient internals
  WiFiClientSecure tmp;
  tmp.setCACert(CA_PEM);
  // attempt connect (short timeout)
  if (tmp.connect(MQTT_HOST, MQTT_PORT)) {
    Serial.println("Raw TLS TCP connect succeeded (TLS handshake OK).");
    tmp.stop();
    ok = true;
  } else {
    Serial.println("Raw TLS TCP connect FAILED.");
    // optional: attempt to get more info
  }
  return ok;
}

bool handleMqttConnection() {
  if (mqttClient.connected()) {
    return true;
  }

  Serial.printf("Attempting MQTT connection to HiveMQ Cloud (%s:%d)...\n", MQTT_HOST, MQTT_PORT);

  mqttClient.setServer(MQTT_HOST, MQTT_PORT);
  mqttClient.setCallback(mqttCallback);

  // Ensure CA is set for TLS certificate validation
  secureClient.setCACert(CA_PEM);

  // Attempt connection
  if (mqttClient.connect(DEVICE_ID, MQTT_USERNAME, MQTT_PASSWORD)) {
    Serial.println("Connected to HiveMQ Cloud (MQTT).");
    mqttClient.subscribe(configTopic.c_str(), 1);
    StaticJsonDocument<128> st;
    st["status"] = "online";
    st["ts"] = (uint64_t)millis();
    String stp;
    serializeJson(st, stp);
    mqttClient.publish(statusTopic.c_str(), stp.c_str(), true);
    return true;
  } else {
    Serial.printf("MQTT connect failed, state=%d. (See notes below)\n", mqttClient.state());
    return false;
  }
}

// wait for NTP time sync (needed for TLS certificate validation)
bool waitForNtpSync(int secondsTimeout = 10) {
  Serial.println("Starting NTP time sync...");
  configTime(0, 0, "pool.ntp.org", "time.google.com");
  time_t now = time(nullptr);
  int waited = 0;
  while (now < 1000000000UL && waited < secondsTimeout) { // time < ~2001-09-09 indicates not synced
    delay(1000);
    Serial.print(".");
    now = time(nullptr);
    waited++;
  }
  Serial.println();
  if (now < 1000000000UL) {
    Serial.println("NTP sync FAILED (time not set). TLS certificate validation may fail.");
    return false;
  } else {
    struct tm timeinfo;
    gmtime_r(&now, &timeinfo);
    char buf[64];
    strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M:%S UTC", &timeinfo);
    Serial.printf("NTP sync OK: %s\n", buf);
    return true;
  }
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\n\nESP32 MQTT Telemetry Publisher (debug build)");

  // Topic initialization
  telemetryTopic = String("v1/device/") + DEVICE_ID + "/telemetry";
  statusTopic = String("v1/device/") + DEVICE_ID + "/status";
  configTopic = String("v1/device/") + DEVICE_ID + "/config";

  // Connect to WiFi
  Serial.printf("Connecting to WiFi '%s' ...\n", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries < 60) {
    Serial.print(".");
    delay(500);
    tries++;
  }
  Serial.println();
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi connect failed - rebooting in 10s");
    delay(10000);
    ESP.restart();
  }
  Serial.printf("WiFi connected, IP=%s\n", WiFi.localIP().toString().c_str());

  // Sync time for TLS
  bool ntp_ok = waitForNtpSync(12);

  // Test raw TLS connect (useful diagnostics)
  bool tls_ok = testTlsConnectOnce();
  if (!tls_ok) {
    Serial.println("Raw TLS connect failed. Possible causes:");
    Serial.println("- No network/DNS to broker, port/corresponding firewall blocking");
    Serial.println("- CA PEM does not match broker TLS chain");
    Serial.println("- Device time not set (NTP failed).");
    Serial.println("- SNI / TLS compatibility issue (rare)");
    Serial.println();

    // Temporary debugging shortcut:
    Serial.println("You can try running with certificate validation disabled for debugging.");
    Serial.println(">>> To do that uncomment secureClient.setInsecure() below (NOT recommended in production).");
    // For safety we DO NOT setInsecure automatically here.
    // If you need to test quickly, uncomment the following (only for debugging):
    // secureClient.setInsecure();
  } else {
    Serial.println("TLS handshake verified by raw test.");
  }

  // Attempt MQTT connect (will use secureClient with CA)
  if (!handleMqttConnection()) {
    Serial.println("Initial MQTT connect failed. Try the following:");
    Serial.println(" - Confirm username/password in HiveMQ console matches");
    Serial.println(" - Confirm the credential is active and allowed to publish to v1/device/... topics");
    Serial.println(" - If TLS test failed, address CA/time issue first");
    Serial.println(" - You can try secureClient.setInsecure() temporarily to isolate CA/time vs auth problems");
  }
}

unsigned long lastPubMs = 0;
const unsigned long PUB_INTERVAL_MS = 1000;

void loop() {
  if (!mqttClient.connected()) {
    Serial.println("MQTT disconnected — trying to reconnect in 5s...");
    delay(5000);
    handleMqttConnection();
  }
  mqttClient.loop();

  unsigned long now = millis();
  if (now - lastPubMs >= PUB_INTERVAL_MS) {
    StaticJsonDocument<256> doc;
    doc["device_id"] = DEVICE_ID;
    doc["ts_ms"] = (uint64_t)millis();
    doc["ax"] = 0.01;
    doc["ay"] = -0.01;
    doc["az"] = 0.99;
    doc["sample_rate"] = 10;
    String out; serializeJson(doc, out);

    if (mqttClient.connected()) {
      if (!mqttClient.publish(telemetryTopic.c_str(), out.c_str())) {
        Serial.println("Publish failed");
      } else {
        Serial.println("Telemetry published:");
        Serial.println(out);
      }
    } else {
      Serial.println("Not connected to MQTT — skipping publish");
    }
    lastPubMs = now;
  }

  delay(10);
}
