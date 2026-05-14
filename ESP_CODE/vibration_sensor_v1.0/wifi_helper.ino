// ================= WiFi station-mode helpers =================
// The on-board WiFi stack does its own auto-reconnect once we configure it,
// but we register an event handler so the serial log clearly shows what's
// happening — useful for thesis demos and diagnosing field deployments.

static void wifiEventHandler(WiFiEvent_t event, WiFiEventInfo_t info) {
  switch (event) {
    case ARDUINO_EVENT_WIFI_STA_GOT_IP:
      Serial.printf("[wifi] got IP: %s (RSSI %d dBm)\n",
                    WiFi.localIP().toString().c_str(),
                    WiFi.RSSI());
      break;
    case ARDUINO_EVENT_WIFI_STA_DISCONNECTED:
      Serial.printf("[wifi] disconnected (reason %u). Stack will auto-reconnect.\n",
                    info.wifi_sta_disconnected.reason);
      break;
    default:
      break;
  }
}

bool connectWifiStation(const Config& cfg, uint32_t timeoutMs) {
  WiFi.mode(WIFI_STA);
  // Wake-on-radio modes interact badly with always-on telemetry; pin to highest
  // throughput so we don't drop packets when sleep would have kicked in.
  WiFi.setSleep(false);
  WiFi.setAutoReconnect(true);
  WiFi.persistent(false);
  WiFi.onEvent(wifiEventHandler);

  Serial.printf("[wifi] connecting to %s ...\n", cfg.wifi_ssid.c_str());
  WiFi.begin(cfg.wifi_ssid.c_str(), cfg.wifi_pass.c_str());

  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED) {
    if (millis() - start > timeoutMs) {
      Serial.println("\n[wifi] timeout");
      return false;
    }
    Serial.print('.');
    delay(250);
  }
  Serial.println();
  Serial.printf("[wifi] connected. MAC: %s  IP: %s\n",
                WiFi.macAddress().c_str(),
                WiFi.localIP().toString().c_str());
  return true;
}
