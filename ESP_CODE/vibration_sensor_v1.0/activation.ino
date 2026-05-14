// ================= /api/devices/activate exchange =================
// Uses the SLPT in NVS to obtain MQTT credentials. On HTTP success the response
// JSON is parsed, broker/mqtt_user/mqtt_pass are written to NVS, and the SLPT
// is cleared (single-use). On HTTP failure the SLPT is preserved so the user
// can retry — either automatically on next boot or manually via factory reset.

static const int   ACTIVATION_TIMEOUT_MS = 8000;
static const int   ACTIVATION_MAX_TRIES  = 3;
static const int   ACTIVATION_BACKOFF_MS = 3000;

// Build the activation URL from the broker host. The backend exposes /activate
// on port 5000 in the dev compose layout. If you run the API behind a reverse
// proxy on 80/443, change the URL pattern here accordingly.
static String activationUrlFromBroker(const String& broker) {
  if (broker.isEmpty()) return "";
  return "http://" + broker + ":5000/api/devices/activate";
}

bool attemptActivation(Config& cfg) {
  // The "server host" the user entered during provisioning is stored as
  // cfg.broker. We assume the API and the MQTT broker share a host, which is
  // true for the dev compose stack and most single-VPS deployments. The
  // activation response can return a different broker_url to override.
  if (cfg.broker.isEmpty()) {
    Serial.println("[activate] no server host stored — re-provisioning required");
    return false;
  }
  String url = activationUrlFromBroker(cfg.broker);
  if (url.isEmpty()) {
    Serial.println("[activate] no activation URL");
    return false;
  }

  if (cfg.slpt.isEmpty()) {
    Serial.println("[activate] no SLPT stored — nothing to do");
    return false;
  }

  String macAddr = WiFi.macAddress();

  StaticJsonDocument<512> req;
  req["slpt"]       = cfg.slpt;
  req["mac"]        = macAddr;
  req["fw_version"] = FW_VERSION;
  String payload;
  serializeJson(req, payload);

  for (int attempt = 1; attempt <= ACTIVATION_MAX_TRIES; ++attempt) {
    Serial.printf("[activate] attempt %d/%d → %s\n", attempt, ACTIVATION_MAX_TRIES, url.c_str());

    HTTPClient http;
    http.setTimeout(ACTIVATION_TIMEOUT_MS);
    if (!http.begin(url)) {
      Serial.println("[activate] http.begin failed");
      delay(ACTIVATION_BACKOFF_MS);
      continue;
    }
    http.addHeader("Content-Type", "application/json");
    int code = http.POST(payload);
    String body = (code > 0) ? http.getString() : String();
    http.end();

    Serial.printf("[activate] HTTP %d body: %s\n", code, body.c_str());

    if (code != 200) {
      // Server-side rejection (token expired, bad MAC, etc.) is non-recoverable
      // by retrying the same SLPT. Bubble up so the boot loop falls back to AP mode.
      if (code == 403 || code == 404 || code == 400) {
        Serial.println("[activate] server rejected SLPT — keeping it so the user can re-enter, "
                       "but this attempt is over.");
        return false;
      }
      // Transient (timeout, 5xx, etc.) → backoff + retry.
      delay(ACTIVATION_BACKOFF_MS);
      continue;
    }

    StaticJsonDocument<1024> resp;
    DeserializationError err = deserializeJson(resp, body);
    if (err) {
      Serial.printf("[activate] JSON parse error: %s\n", err.c_str());
      delay(ACTIVATION_BACKOFF_MS);
      continue;
    }

    const char* msg       = resp["message"] | resp["msg"] | "";
    const char* mqttUser  = resp["mqtt_user"] | "";
    const char* mqttPass  = resp["mqtt_pass"] | "";
    const char* brokerUrl = resp["broker_url"] | "";

    if (String(msg) != "Device activated" || strlen(mqttUser) == 0 || strlen(mqttPass) == 0) {
      Serial.println("[activate] response missing required fields");
      return false;
    }

    String brokerToStore = (strlen(brokerUrl) > 0) ? String(brokerUrl) : cfg.broker;
    saveActivationResult(brokerToStore, String(mqttUser), String(mqttPass));
    Serial.println("[activate] activation succeeded.");
    return true;
  }

  Serial.println("[activate] all retries exhausted; SLPT preserved for next attempt.");
  return false;
}
