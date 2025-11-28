#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <time.h>
#include "esp_timer.h"

// ---------- CONFIG ----------
const char* WIFI_SSID = "SLT_FIBRE";
const char* WIFI_PASSWORD = "Anji@123";

const char* DEVICE_ID = "dev000";

const char* MQTT_HOST = "8931093ac74c4ab0ac3f0cb16e92d38b.s1.eu.hivemq.cloud";
const int MQTT_PORT = 8883;
const char* MQTT_USERNAME = "dev000-VtSxrXh6";
const char* MQTT_PASSWORD = "mJrUSIgHFt-CdGA3VVvNylhE-syD6EA2";

// Sampling config
const uint32_t SAMPLE_RATE_HZ = 1000;       // 1000 Hz
const uint16_t BUFFER_SAMPLES = 256;        // power of two (256, 512...)
const uint16_t PUBLISH_INTERVAL_MS = 1000;  // publish time-domain metrics every 1s

// Occasional raw data send
const bool SEND_RAW_BLOCK = true;
const uint16_t RAW_SEND_INTERVAL_S = 30;

// MPU9250 / I2C
const uint8_t MPU_ADDR = 0x68;
const uint8_t PWR_MGMT_1 = 0x6B;
const uint8_t ACCEL_CONFIG = 0x1C;
const uint8_t ACCEL_XOUT_H = 0x3B;
const float ACCEL_SENS = 16384.0;  // LSB/g for +/-2g

// CA PEM (shortened here — keep the full PEM in your sketch)
const char CA_PEM[] PROGMEM = R"EOF(
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

// ---------- Globals ----------
WiFiClientSecure secureClient;
PubSubClient mqttClient(secureClient);
String telemetryTopic, statusTopic, configTopic;

// buffers and sampling
volatile uint16_t buf_idx = 0;           // next write index
volatile bool buffer_full_flag = false;  // set when buffer wrapped
int16_t ax_buf[BUFFER_SAMPLES];
int16_t ay_buf[BUFFER_SAMPLES];
int16_t az_buf[BUFFER_SAMPLES];

// esp timer handle and flag
esp_timer_handle_t sampling_timer = nullptr;
volatile bool sample_flag = false;  // set by timer callback; consumed in loop()

// critical section mutex
portMUX_TYPE timerMux = portMUX_INITIALIZER_UNLOCKED;

// base64 helper
static const char b64_table[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

String base64_encode(const uint8_t* data, size_t input_length) {
  if (input_length == 0) return String();

  size_t output_length = ((input_length + 2) / 3) * 4;
  char* out = (char*)malloc(output_length + 1);
  if (!out) return String();

  size_t i = 0, o = 0;
  while (i + 2 < input_length) {
    uint32_t triple = ((uint32_t)data[i] << 16) | ((uint32_t)data[i + 1] << 8) | ((uint32_t)data[i + 2]);
    out[o++] = b64_table[(triple >> 18) & 0x3F];
    out[o++] = b64_table[(triple >> 12) & 0x3F];
    out[o++] = b64_table[(triple >> 6) & 0x3F];
    out[o++] = b64_table[triple & 0x3F];
    i += 3;
  }

  if (i < input_length) {
    uint32_t triple = 0;
    int pad = 0;
    triple |= (uint32_t)data[i] << 16;
    if (i + 1 < input_length) triple |= (uint32_t)data[i + 1] << 8;
    else pad++;
    if (i + 1 >= input_length) pad++;

    out[o++] = b64_table[(triple >> 18) & 0x3F];
    out[o++] = b64_table[(triple >> 12) & 0x3F];
    if (pad == 2) {
      out[o++] = '=';
      out[o++] = '=';
    } else if (pad == 1) {
      out[o++] = b64_table[(triple >> 6) & 0x3F];
      out[o++] = '=';
    } else {
      out[o++] = b64_table[(triple >> 6) & 0x3F];
      out[o++] = b64_table[triple & 0x3F];
    }
  }

  out[o] = '\0';
  String s(out);
  free(out);
  return s;
}

// ---------- I2C helper ----------
int16_t read16(uint8_t reg) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  Wire.endTransmission(false);
  Wire.requestFrom(MPU_ADDR, (uint8_t)2);
  unsigned long start = micros();
  while (Wire.available() < 2) {
    // small timeout protection (avoid blocking forever)
    if (micros() - start > 2000) break;  // 2ms timeout
  }
  int16_t hi = Wire.available() ? Wire.read() : 0;
  int16_t lo = Wire.available() ? Wire.read() : 0;
  return (int16_t)((hi << 8) | (lo & 0xFF));
}

// ---------- MPU init ----------
void mpu_init() {
  Wire.begin();  // ensure Wire initialized
  // wake up
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(PWR_MGMT_1);
  Wire.write(0x00);
  Wire.endTransmission();
  delay(50);
  // set accel range to +/-2g
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(ACCEL_CONFIG);
  Wire.write(0x00);
  Wire.endTransmission();
  delay(10);
}

// Sampling timer callback (runs in esp_timer task)
void sampling_timer_cb(void* arg) {
  // set flag only
  sample_flag = true;
}

// start periodic esp_timer for sampling
bool startSamplingTimer() {
  if (sampling_timer) {
    esp_timer_stop(sampling_timer);
    esp_timer_delete(sampling_timer);
    sampling_timer = nullptr;
  }

  esp_timer_create_args_t timer_args = {
    .callback = &sampling_timer_cb,
    .arg = nullptr,
    .name = "sampling_timer"
  };

  esp_err_t err = esp_timer_create(&timer_args, &sampling_timer);
  if (err != ESP_OK) {
    Serial.printf("esp_timer_create failed: %d\n", err);
    return false;
  }

  const int64_t period_us = (int64_t)(1000000LL / (int64_t)SAMPLE_RATE_HZ);
  err = esp_timer_start_periodic(sampling_timer, (uint64_t)period_us);
  if (err != ESP_OK) {
    Serial.printf("esp_timer_start_periodic failed: %d\n", err);
    esp_timer_delete(sampling_timer);
    sampling_timer = nullptr;
    return false;
  }

  Serial.printf("Sampling timer started @ %lld us period\n", (long long)period_us);
  return true;
}

void stopSamplingTimer() {
  if (sampling_timer) {
    esp_timer_stop(sampling_timer);
    esp_timer_delete(sampling_timer);
    sampling_timer = nullptr;
  }
}

// ---------- MQTT ----------
void mqttCallback(char* topic, byte* payload, unsigned int length) {
  // placeholder for config updates
}

bool mqttConnect() {
  mqttClient.setServer(MQTT_HOST, MQTT_PORT);
  mqttClient.setCallback(mqttCallback);
  secureClient.setCACert(CA_PEM);
  if (mqttClient.connect(DEVICE_ID, MQTT_USERNAME, MQTT_PASSWORD)) {
    mqttClient.subscribe(configTopic.c_str(), 1);
    StaticJsonDocument<128> st;
    st["status"] = "online";
    st["ts"] = (uint64_t)time(nullptr) * 1000ULL;
    String out;
    serializeJson(st, out);
    mqttClient.publish(statusTopic.c_str(), out.c_str(), true);
    return true;
  }
  return false;
}

bool waitForNTP(int timeoutSec = 12) {
  configTime(0, 0, "pool.ntp.org", "time.google.com");
  time_t now = time(nullptr);
  int waited = 0;
  while (now < 1000000000UL && waited < timeoutSec) {
    delay(500);
    now = time(nullptr);
    waited++;
  }
  return now >= 1000000000UL;
}

// ---------- Compute & publish ----------
void compute_and_publish_metrics() {
  // local copy to avoid races with ISR/timer flag
  int16_t ax_local[BUFFER_SAMPLES];
  int16_t ay_local[BUFFER_SAMPLES];
  int16_t az_local[BUFFER_SAMPLES];

  portENTER_CRITICAL(&timerMux);
  for (uint16_t i = 0; i < BUFFER_SAMPLES; ++i) {
    ax_local[i] = ax_buf[i];
    ay_local[i] = ay_buf[i];
    az_local[i] = az_buf[i];
  }
  bool block_ready = buffer_full_flag;
  buffer_full_flag = false;
  portEXIT_CRITICAL(&timerMux);

  // compute features
  double ax_sum = 0.0, ay_sum = 0.0, az_sum = 0.0;
  double ax_sq = 0.0, ay_sq = 0.0, az_sq = 0.0;
  double ax_peak = 0.0, ay_peak = 0.0, az_peak = 0.0;
  double mag_sq = 0.0, mag_peak = 0.0;

  for (uint16_t i = 0; i < BUFFER_SAMPLES; ++i) {
    double ax = ((double)ax_local[i]) / ACCEL_SENS;
    double ay = ((double)ay_local[i]) / ACCEL_SENS;
    double az = ((double)az_local[i]) / ACCEL_SENS;
    ax_sum += ax;
    ay_sum += ay;
    az_sum += az;
    ax_sq += ax * ax;
    ay_sq += ay * ay;
    az_sq += az * az;
    if (fabs(ax) > ax_peak) ax_peak = fabs(ax);
    if (fabs(ay) > ay_peak) ay_peak = fabs(ay);
    if (fabs(az) > az_peak) az_peak = fabs(az);
    double mag = sqrt(ax * ax + ay * ay + az * az);
    mag_sq += mag * mag;
    if (mag > mag_peak) mag_peak = mag;
  }

  double n = (double)BUFFER_SAMPLES;
  double ax_mean = ax_sum / n;
  double ay_mean = ay_sum / n;
  double az_mean = az_sum / n;
  double ax_rms = sqrt(ax_sq / n);
  double ay_rms = sqrt(ay_sq / n);
  double az_rms = sqrt(az_sq / n);
  double mag_rms = sqrt(mag_sq / n);

  StaticJsonDocument<512> doc;
  doc["device_id"] = DEVICE_ID;
  doc["ts_ms"] = (uint64_t)time(nullptr) * 1000ULL;
  doc["sample_rate_hz"] = SAMPLE_RATE_HZ;
  doc["samples"] = BUFFER_SAMPLES;
  JsonObject metrics = doc.createNestedObject("metrics");
  metrics["ax_mean_g"] = ax_mean;
  metrics["ay_mean_g"] = ay_mean;
  metrics["az_mean_g"] = az_mean;
  metrics["ax_rms_g"] = ax_rms;
  metrics["ay_rms_g"] = ay_rms;
  metrics["az_rms_g"] = az_rms;
  metrics["ax_peak_g"] = ax_peak;
  metrics["ay_peak_g"] = ay_peak;
  metrics["az_peak_g"] = az_peak;
  metrics["magnitude_rms_g"] = mag_rms;
  metrics["magnitude_peak_g"] = mag_peak;

  String out;
  serializeJson(doc, out);
  if (mqttClient.connected()) {
    mqttClient.publish(telemetryTopic.c_str(), out.c_str());
  }
}

// pack and send raw block (base64 int16_le ax,ay,az)
bool publish_binary_chunks(const String& baseTopic, const uint8_t* bin, size_t bytes, size_t maxChunk = 256) {
  // create a simple id (timestamp + rand)
  String id = String((uint32_t)time(nullptr)) + "-" + String(random(0xFFFF), HEX);
  uint16_t chunks = (bytes + maxChunk - 1) / maxChunk;

  // send small meta JSON
  StaticJsonDocument<256> meta;
  meta["device_id"] = DEVICE_ID;
  meta["id"] = id;
  meta["chunks"] = chunks;
  meta["bytes"] = bytes;
  String metaOut;
  serializeJson(meta, metaOut);
  if (!mqttClient.publish((baseTopic + "/meta").c_str(), metaOut.c_str())) {
    Serial.println("publish meta failed");
    return false;
  }

  // publish each chunk as binary to baseTopic + "/chunk/<id>/<seq>"
  for (uint16_t i = 0; i < chunks; ++i) {
    size_t offset = i * maxChunk;
    size_t thisLen = min(maxChunk, bytes - offset);

    String chunkTopic = baseTopic + "/chunk/" + id + "/" + String(i);

    bool ok = mqttClient.publish(
      chunkTopic.c_str(),
      bin + offset,
      thisLen,
      false  // <--- CRITICAL
    );
    if (!ok) {
      Serial.printf("publish chunk %d failed (len=%u)\n", i, thisLen);
      return false;
    }
    delay(10);
  }
  return true;
}

void send_raw_block_binary_chunked() {
  // copy buffer under critical section
  int16_t ax_local[BUFFER_SAMPLES];
  int16_t ay_local[BUFFER_SAMPLES];
  int16_t az_local[BUFFER_SAMPLES];

  portENTER_CRITICAL(&timerMux);
  for (uint16_t i = 0; i < BUFFER_SAMPLES; ++i) {
    ax_local[i] = ax_buf[i];
    ay_local[i] = ay_buf[i];
    az_local[i] = az_buf[i];
  }
  portEXIT_CRITICAL(&timerMux);

  // pack into binary buffer (ax,ay,az int16 little-endian interleaved)
  const size_t bytes = (size_t)BUFFER_SAMPLES * 3 * 2;
  uint8_t* bin = (uint8_t*)malloc(bytes);
  if (!bin) {
    Serial.println("send_raw_block_binary_chunked: malloc failed");
    return;
  }
  size_t p = 0;
  for (uint16_t i = 0; i < BUFFER_SAMPLES; ++i) {
    int16_t v;
    v = ax_local[i];
    bin[p++] = (uint8_t)(v & 0xFF);
    bin[p++] = (uint8_t)((v >> 8) & 0xFF);
    v = ay_local[i];
    bin[p++] = (uint8_t)(v & 0xFF);
    bin[p++] = (uint8_t)((v >> 8) & 0xFF);
    v = az_local[i];
    bin[p++] = (uint8_t)(v & 0xFF);
    bin[p++] = (uint8_t)((v >> 8) & 0xFF);
  }

  // Publish a small metadata message on the regular telemetry topic (optional)
  {
    StaticJsonDocument<256> meta;
    meta["device_id"] = DEVICE_ID;
    meta["ts_ms"] = (uint64_t)time(nullptr) * 1000ULL;
    meta["sample_rate_hz"] = SAMPLE_RATE_HZ;
    meta["samples"] = BUFFER_SAMPLES;
    meta["encoding"] = "int16_le_axayaz_bin_chunks";
    String out;
    serializeJson(meta, out);
    mqttClient.publish(telemetryTopic.c_str(), out.c_str());
  }

  // Publish binary chunks to telemetryTopic + "/raw"
  String rawBase = telemetryTopic + String("/raw");
  bool ok = publish_binary_chunks(rawBase, bin, bytes, 256 /* chunk size */);
  if (!ok) {
    Serial.println("send_raw_block_binary_chunked: publish_binary_chunks failed");
  } else {
    Serial.printf("send_raw_block_binary_chunked: published %u bytes in chunks\n", (unsigned)bytes);
  }

  free(bin);
}



// ---------- main ----------
unsigned long lastPublish = 0;
unsigned long lastRawSend = 0;

void setup() {
  Serial.begin(115200);
  delay(200);

  telemetryTopic = String("v1/device/") + DEVICE_ID + "/telemetry";
  statusTopic = String("v1/device/") + DEVICE_ID + "/status";
  configTopic = String("v1/device/") + DEVICE_ID + "/config";

  Wire.begin();
  mpu_init();

  // WiFi
  Serial.printf("Connecting to WiFi '%s'... ", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries < 60) {
    Serial.print(".");
    delay(500);
    tries++;
  }
  Serial.println();
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi connect failed - rebooting");
    delay(5000);
    ESP.restart();
  }
  Serial.println("WiFi connected: " + WiFi.localIP().toString());

  // NTP
  if (!waitForNTP(12)) {
    Serial.println("Warning: NTP failed; TLS may fail");
  }

  // Start sampling timer
  if (!startSamplingTimer()) {
    Serial.println("Failed to start sampling timer");
  }

  mqttClient.setBufferSize(4096);
  secureClient.setCACert(CA_PEM);
  if (!mqttConnect()) {
    Serial.println("Initial MQTT connect failed - retrying");
  }
}

void loop() {
  // reconnect MQTT if needed
  if (!mqttClient.connected()) {
    if (mqttConnect()) {
      Serial.println("MQTT reconnected");
    } else {
      delay(2000);
    }
  }
  mqttClient.loop();

  // handle sampling flag (set by esp_timer callback)
  if (sample_flag) {
    sample_flag = false;

    // do the actual sensor read and buffering
    int16_t ax_raw = read16(ACCEL_XOUT_H + 0);
    int16_t ay_raw = read16(ACCEL_XOUT_H + 2);
    int16_t az_raw = read16(ACCEL_XOUT_H + 4);

    portENTER_CRITICAL(&timerMux);
    ax_buf[buf_idx] = ax_raw;
    ay_buf[buf_idx] = ay_raw;
    az_buf[buf_idx] = az_raw;
    buf_idx++;
    if (buf_idx >= BUFFER_SAMPLES) {
      buf_idx = 0;
      buffer_full_flag = true;
    }
    portEXIT_CRITICAL(&timerMux);
  }

  unsigned long now = millis();
  if (now - lastPublish >= PUBLISH_INTERVAL_MS) {
    compute_and_publish_metrics();
    lastPublish = now;
  }

  if (SEND_RAW_BLOCK && now - lastRawSend >= RAW_SEND_INTERVAL_S * 1000UL) {
    if (buffer_full_flag) {
      send_raw_block_binary_chunked();
      lastRawSend = now;
    }
  }

  // keep loop responsive
  delay(5);
}
