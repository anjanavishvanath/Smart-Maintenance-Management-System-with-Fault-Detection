// ================= AP mode + captive portal =================
// Soft-AP SSID = "PreSense-Setup-XXXX" where XXXX is the last 4 hex chars of the
// MAC, so multiple unflashed devices in the same room don't collide.
// DNSServer hijacks all DNS lookups → captive portal pops up automatically on
// most platforms (Android, iOS, recent Windows).

const byte DNS_PORT = 53;
const char* AP_PASSWORD = "presense-setup";   // Default WPA2 password printed on the device label
const IPAddress AP_IP(192, 168, 4, 1);
const IPAddress AP_NETMASK(255, 255, 255, 0);

// HTML form. Inline so the firmware is a single binary; ~3 KB so it fits comfortably.
static const char FORM_HTML[] PROGMEM = R"HTML(
<!doctype html>
<html><head>
<meta name=viewport content="width=device-width,initial-scale=1">
<meta charset=utf-8>
<title>PreSense Setup</title>
<style>
  body{font-family:system-ui,sans-serif;background:#0f1115;color:#e6e6e6;margin:0;padding:1.2rem;max-width:520px}
  h1{font-size:1.3rem;margin:0 0 0.4rem}
  p.muted{color:#888;font-size:0.85rem;margin:0 0 1rem}
  label{display:block;margin:0.7rem 0 0.2rem;font-size:0.9rem;color:#ccc}
  input{width:100%;padding:0.55rem;border-radius:6px;border:1px solid #333;background:#1a1d23;color:#fff;box-sizing:border-box}
  button{margin-top:1.2rem;width:100%;padding:0.7rem;border-radius:6px;border:0;background:#3b82f6;color:#fff;font-size:1rem;font-weight:600;cursor:pointer}
  .row{display:flex;gap:0.5rem}
  .row>div{flex:1}
  small{color:#777}
</style></head><body>
<h1>PreSense Device Setup</h1>
<p class=muted>Enter your WiFi credentials and the activation token issued by the dashboard.</p>
<form method=POST action="/save">
  <label>WiFi SSID</label>
  <input name=ssid required maxlength=32 autocomplete=off>
  <label>WiFi password</label>
  <input name=pass type=password maxlength=63 autocomplete=off>
  <div class=row>
    <div>
      <label>Organization</label>
      <input name=org required maxlength=32 autocomplete=off>
    </div>
    <div>
      <label>Asset ID</label>
      <input name=asset_id required type=number min=1 max=65535>
    </div>
  </div>
  <label>Server host (IP or hostname of the PreSense backend, e.g. 192.168.1.3)</label>
  <input name=server required maxlength=64 autocomplete=off>
  <label>Device name (optional)</label>
  <input name=dev_name maxlength=64 autocomplete=off>
  <label>Activation token (SLPT)</label>
  <input name=slpt required type=password maxlength=128 autocomplete=off>
  <button type=submit>Save & Restart</button>
</form>
<small>The device will reboot and try to join your network.</small>
</body></html>
)HTML";

// Lightweight HTML escape for echoing user input back into a confirmation page.
static String htmlEscape(const String& s) {
  String out;
  out.reserve(s.length());
  for (size_t i = 0; i < s.length(); ++i) {
    char c = s[i];
    switch (c) {
      case '&': out += "&amp;"; break;
      case '<': out += "&lt;";  break;
      case '>': out += "&gt;";  break;
      case '"': out += "&quot;"; break;
      case '\'': out += "&#39;"; break;
      default: out += c;
    }
  }
  return out;
}

// Validate inputs on the server side (don't trust the form-side `required`).
// Returns empty string on success, or a human-readable reason for failure.
static String validateProvisioningInput(const String& ssid, const String& pass,
                                        const String& org,  const String& assetIdRaw,
                                        const String& server, const String& slpt) {
  if (ssid.length() < 1 || ssid.length() > 32)            return "SSID must be 1–32 characters.";
  if (pass.length() > 63)                                  return "WiFi password too long (max 63).";
  if (org.length()  < 1 || org.length()  > 32)             return "Organization must be 1–32 characters.";
  if (assetIdRaw.length() == 0)                            return "Asset ID is required.";
  long asset_id = assetIdRaw.toInt();
  if (asset_id < 1 || asset_id > 65535)                    return "Asset ID must be between 1 and 65535.";
  if (server.length() < 3 || server.length() > 64)         return "Server host must be 3–64 characters (IP or hostname).";
  if (slpt.length() < 8 || slpt.length() > 128)            return "SLPT looks malformed.";
  return "";
}

static String apSsidFromMac() {
  String mac = WiFi.macAddress();
  mac.replace(":", "");
  // Last 4 chars of the MAC for a stable per-device suffix.
  return "PreSense-Setup-" + mac.substring(mac.length() - 4);
}

static void handleRoot() {
  apServer.sendHeader("Cache-Control", "no-store");
  apServer.send_P(200, "text/html", FORM_HTML);
}

static void handleSave() {
  if (apServer.method() != HTTP_POST) {
    apServer.send(405, "text/plain", "POST only");
    return;
  }

  String ssid     = apServer.arg("ssid");
  String pass     = apServer.arg("pass");
  String org      = apServer.arg("org");
  String assetRaw = apServer.arg("asset_id");
  String server   = apServer.arg("server");
  String devName  = apServer.arg("dev_name");
  String slpt     = apServer.arg("slpt");

  String validationError = validateProvisioningInput(ssid, pass, org, assetRaw, server, slpt);
  if (!validationError.isEmpty()) {
    String body = "<!doctype html><body style='font-family:sans-serif;padding:1rem'>"
                  "<h2>Setup error</h2><p>" + htmlEscape(validationError) +
                  "</p><p><a href='/'>Go back</a></p></body>";
    apServer.send(400, "text/html", body);
    return;
  }

  Config in;
  in.wifi_ssid    = ssid;
  in.wifi_pass    = pass;
  in.organization = org;
  in.asset_id     = (uint16_t) assetRaw.toInt();
  in.device_name  = devName;
  in.slpt         = slpt;
  // The server-host field doubles as the initial broker host. /api/devices/activate
  // can return broker_url to override it post-activation.
  in.broker       = server;
  saveWifiAndProvisioning(in);

  String body =
    "<!doctype html><body style='font-family:sans-serif;padding:1rem'>"
    "<h2>Saved.</h2><p>Device is rebooting to join <b>" + htmlEscape(ssid) + "</b>.</p>"
    "<p>If it doesn't connect within a minute, hold the BOOT button for 5 seconds to retry setup.</p>"
    "</body>";
  apServer.send(200, "text/html", body);
  delay(800);
  ESP.restart();
}

// Captive-portal probe URLs — return 302 to / so the OS pops the in-system browser.
static void handleCaptiveProbe() {
  apServer.sendHeader("Location", "/", true);
  apServer.send(302, "text/plain", "");
}

void startProvisioningPortal() {
  Serial.println("[ap] starting provisioning portal...");
  WiFi.mode(WIFI_AP);
  WiFi.softAPConfig(AP_IP, AP_IP, AP_NETMASK);

  String ssid = apSsidFromMac();
  WiFi.softAP(ssid.c_str(), AP_PASSWORD);
  Serial.printf("[ap] SSID: %s   pw: %s   IP: %s\n",
                ssid.c_str(), AP_PASSWORD, WiFi.softAPIP().toString().c_str());

  // mDNS so users on a friendly host can browse to http://presense-setup.local/
  if (MDNS.begin("presense-setup")) {
    MDNS.addService("http", "tcp", 80);
    Serial.println("[ap] mDNS up: presense-setup.local");
  } else {
    Serial.println("[ap] mDNS init failed (continuing without)");
  }

  // Hijack DNS so any hostname → AP IP → captive portal.
  dnsServer.start(DNS_PORT, "*", AP_IP);

  apServer.on("/",        handleRoot);
  apServer.on("/save",    HTTP_POST, handleSave);
  // Common captive-portal probe targets used by major OSes.
  apServer.on("/generate_204", handleCaptiveProbe);          // Android
  apServer.on("/hotspot-detect.html", handleCaptiveProbe);   // iOS / macOS
  apServer.on("/connecttest.txt", handleCaptiveProbe);       // Windows
  apServer.on("/redirect", handleCaptiveProbe);
  apServer.onNotFound(handleCaptiveProbe);

  apServer.begin();
  Serial.println("[ap] HTTP server listening; awaiting setup form...");

  // Stay here, servicing DNS + HTTP, until the user submits and we ESP.restart().
  while (true) {
    dnsServer.processNextRequest();
    apServer.handleClient();
    delay(1);
  }
}
