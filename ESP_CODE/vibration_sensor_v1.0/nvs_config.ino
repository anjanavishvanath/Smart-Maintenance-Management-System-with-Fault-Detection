// ================= NVS persistence =================
// All config lives in a single namespace (NVS_NAMESPACE) so factory-reset is
// just a clear() of that namespace.
//
// Schema versioning: K_SCHEMA stores an incrementing integer. If a future
// firmware introduces a layout change, bump NVS_SCHEMA and add a migration
// path here; older data is treated as "no config" and forces re-provisioning.

bool loadConfig(Config& out) {
  if (!preferences.begin(NVS_NAMESPACE, true)) {  // read-only
    Serial.println("[nvs] open(read) failed");
    return false;
  }

  uint8_t schema = preferences.getUChar(K_SCHEMA, 0);
  out.wifi_ssid    = preferences.getString(K_WIFI_SSID, "");
  out.wifi_pass    = preferences.getString(K_WIFI_PASS, "");
  out.slpt         = preferences.getString(K_SLPT, "");
  out.organization = preferences.getString(K_ORG, "");
  out.asset_id     = preferences.getUShort(K_ASSET_ID, 0);
  out.device_name  = preferences.getString(K_DEV_NAME, "");
  out.broker       = preferences.getString(K_BROKER, "");
  out.mqtt_user    = preferences.getString(K_MQTT_USER, "");
  out.mqtt_pass    = preferences.getString(K_MQTT_PASS, "");
  out.activated    = preferences.getBool(K_ACTIVATED, false);
  preferences.end();

  if (schema != NVS_SCHEMA) {
    Serial.printf("[nvs] schema mismatch (got %u, want %u) → forcing re-provision\n",
                  schema, NVS_SCHEMA);
    return false;
  }

  // Minimum viable config to even attempt a station-mode connect.
  if (out.wifi_ssid.isEmpty()) {
    Serial.println("[nvs] no WiFi SSID stored");
    return false;
  }

  return true;
}

void saveWifiAndProvisioning(const Config& in) {
  if (!preferences.begin(NVS_NAMESPACE, false)) {  // read-write
    Serial.println("[nvs] open(write) failed");
    return;
  }
  preferences.putUChar(K_SCHEMA, NVS_SCHEMA);
  preferences.putString(K_WIFI_SSID, in.wifi_ssid);
  preferences.putString(K_WIFI_PASS, in.wifi_pass);
  preferences.putString(K_SLPT, in.slpt);
  preferences.putString(K_ORG, in.organization);
  preferences.putUShort(K_ASSET_ID, in.asset_id);
  preferences.putString(K_DEV_NAME, in.device_name);
  // Server / broker host doubles as the activation endpoint host on first boot.
  // /api/devices/activate may return a broker_url that overrides this after success.
  preferences.putString(K_BROKER, in.broker);
  // Activation-derived fields (mqtt_user/pass) are NOT written here — those
  // land later, after /activate succeeds.
  preferences.putBool(K_ACTIVATED, false);
  preferences.end();
  Serial.println("[nvs] provisioning fields persisted.");
}

void saveActivationResult(const String& broker, const String& user, const String& pass) {
  if (!preferences.begin(NVS_NAMESPACE, false)) {
    Serial.println("[nvs] open(write) failed in saveActivationResult");
    return;
  }
  preferences.putString(K_BROKER, broker);
  preferences.putString(K_MQTT_USER, user);
  preferences.putString(K_MQTT_PASS, pass);
  preferences.putBool(K_ACTIVATED, true);
  // Burn the SLPT — it's single-use per spec, and keeping it around invites replay.
  preferences.remove(K_SLPT);
  preferences.end();
  Serial.println("[nvs] activation result persisted; SLPT cleared.");
}

void clearAllConfig() {
  if (preferences.begin(NVS_NAMESPACE, false)) {
    preferences.clear();
    preferences.end();
    Serial.println("[nvs] namespace cleared (factory reset).");
  } else {
    Serial.println("[nvs] clear failed — could not open namespace.");
  }
}
