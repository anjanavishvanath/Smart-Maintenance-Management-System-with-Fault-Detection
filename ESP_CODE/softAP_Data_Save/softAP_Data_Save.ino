#include <WiFi.h>
#include <WebServer.h>
#include <Preferences.h>

// --- Global Objects ---
WebServer server(80);
Preferences preferences;

//  --- NVS keys ---
const char* NVS_NAMESPACE = "cm_config";
const char* KEY_SSID = "ssid";
const char* KEY_PASS = "pass";
const char* KEY_SLPT = "slpt"; // Short-Lived Provisioning Token

void setup() {
  Serial.begin(115200);

  // Check if config exist and jump to STA mode if not
  WiFi.mode(WIFI_AP_STA);
  
  //1. Start SoftAP
  const char* softAP_ssid = "preSense_provision";
  WiFi.softAP(softAP_ssid);

  Serial.print("SoftAP IP address: ");
  Serial.println(WiFi.softAPIP());
  Serial.print("ESP MAC address: ");
  Serial.println(String(WiFi.softAPmacAddress()));

  //2. Setup WebServer Routes
  server.on("/", HTTP_GET, handleRoot);
  server.on("/save", HTTP_POST, handleSave);
  server.begin();

  Serial.println("SoftAP server started");
}

void loop() {
  server.handleClient();
}

void handleRoot() {
  String html = "<h1>Sensor Provisioning</h1>";
    html += "<form method='POST' action='/save'>";
    html += "WiFi SSID: <input type='text' name='ssid'><br>";
    html += "WiFi Pass: <input type='password' name='pass'><br>";
    // This is the Enrollment ID the user manually enters
    html += "Enrollment ID (MAC): <input type='text' name='mac'><br>"; 
    html += "Provisioning Token (SLPT): <input type='text' name='slpt'><br>"; 
    html += "<input type='submit' value='Provision'>";
    html += "</form>";
    server.send(200, "text/html", html);
}

void handleSave() {
  String ssid = server.arg("ssid");
  String password = server.arg("pass");
  String slpt = server.arg("slpt");
  String mac_entered = server.arg("mac");

  //2. Validate MAC Address
  if(mac_entered != String(WiFi.softAPmacAddress())) {
    server.send(400, "text/plain", "Error: Enrollment ID mismatch");
    return;
  }

  //3. Save data to NVS
  preferences.begin(NVS_NAMESPACE, false); //false = read/write
  preferences.putString(KEY_SSID, ssid);
  preferences.putString(KEY_PASS, password);
  preferences.putString(KEY_SLPT, slpt);
  preferences.end();

  //4. Server send success and restart;
  server.send(200, "text/plain", "Configuration saved. Restarting to connect to WiFi...");
  delay(500);
  ESP.restart();

}
