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
  // Serial.print("IP address: ");
  // Serial.println(WiFi.localIP());
}

void activateDevice() {
  HTTPClient http;
  String macAddr = WiFi.macAddress();
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