#include <WiFi.h>
#include <WebServer.h>
#include <Preferences.h>
#include <HTTPClient.h>

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

  preferences.begin(NVS_NAMESPACE, true); // Open in read-only mode
  String savedSSID = preferences.getString(KEY_SSID, "");
  String savedPass = preferences.getString(KEY_PASS, "");
  String savedSLPT = preferences.getString(KEY_SLPT, "");
  preferences.end();

  if (savedSSID != "" && savedPass != "") {
    Serial.println("Credentials found. Attempting to connect to WiFi...");
    WiFi.mode(WIFI_STA);
    WiFi.begin(savedSSID.c_str(), savedPass.c_str());
    // waiting for connection with a timeout
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 20) {
      delay(300);
      Serial.print(".");
      attempts++;
    }

    if (WiFi.status() == WL_CONNECTED){
      Serial.println("\nConnected to WiFi!");
      activateDevice(savedSLPT);//If we have a SLPT but no permanent ID, activate!
    }else {
      Serial.println("\nFailed to connect. Falling back to SoftAP.");
      startSoftAP();
    }
  }else {
    startSoftAP();
  }
}

void loop() {
  if (WiFi.getMode() == WIFI_AP || WiFi.getMode() == WIFI_AP_STA) {
        server.handleClient();
  }
}

void activateDevice (String slpt) {
  if (slpt == "") return;

  HTTPClient http;
  String serverPath = "http://192.168.1.2:5000/api/devices/activate"; //IP from IPConfig.
  Serial.println("Sending activation request...");
  http.begin(serverPath);
  http.addHeader("Content-Type", "application/json");
  String macAddr = WiFi.macAddress(); //STR mac address for final ID
  String payload = "{\"slpt\":\"" + slpt + "\", \"mac\":\"" + macAddr + "\"}";
  int httpResponseCode = http.POST(payload);
  if (httpResponseCode == 200 || httpResponseCode == 201) {
    String response = http.getString();
    Serial.println("Activation Successful!");
    Serial.println("Response: " + response);
    // todo: parse req to get mqtt cred, permanent id, delete slpt from NVS 
    preferences.begin(NVS_NAMESPACE, false);
    preferences.remove(KEY_SLPT);
    preferences.end();
  } else{
    Serial.print("Activation Failed. Error code: ");
    Serial.println(httpResponseCode);
    // todo: check for 401/403 for expiration of slpt. (For now backend is just sending 500)
    Serial.println("Falling back to softAP");
    startSoftAP();
  }
  http.end();
}

void startSoftAP() {
  WiFi.mode(WIFI_AP);
  WiFi.softAP("preSense_provision");
  server.on("/", HTTP_GET, handleRoot);
  server.on("/save", HTTP_POST, handleSave);
  server.begin();
  Serial.print("SoftAP started at: ");
  Serial.println(WiFi.softAPIP());
  Serial.print("ESP MAC address: ");
  Serial.println(String(WiFi.softAPmacAddress()));
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

  slpt.trim();
  mac_entered.trim();

  Serial.println("SSID: " + ssid);
  Serial.println("Pass: " + password);

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
