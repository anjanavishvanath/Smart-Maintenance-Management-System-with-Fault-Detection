# PreSense ESP32 firmware — v1.0

Properly-provisioned vibration sensor firmware for the PreSense system. Replaces the
hardcoded-credential v0.4 sketch with a captive-portal provisioning flow, NVS storage,
and a factory-reset gesture.

## What changed vs v0.4

- **No more hardcoded WiFi / SLPT / broker.** Everything is entered once in a captive portal and persisted to NVS.
- **Captive portal** (`PreSense-Setup-XXXX` SoftAP) with DNS hijacking and an inline HTML form.
- **Multi-attempt activation** with backoff. The SLPT is **only** cleared after the server confirms activation, so a transient WiFi blip won't burn the token.
- **Factory-reset gesture**: long-press BOOT for 5 s → NVS wiped, device reboots into provisioning mode.
- **Status LED** with six visual states (see legend below).
- **NVS schema versioning** (`NVS_SCHEMA = 1`) so future firmware can migrate cleanly.
- **Firmware version** (`FW_VERSION = "1.0.0"`) is sent in the activation payload so the dashboard can show what each device is running.
- **mDNS** (`presense-setup.local`) for setup-page discovery.

## Hardware

| Pin   | Purpose                                |
|-------|----------------------------------------|
| GPIO 0  | Factory-reset button (BOOT button — internal pullup, active-low) |
| GPIO 2  | Status LED (built-in on most dev boards)              |
| GPIO 5  | MPU-6500 SPI chip-select                              |
| GPIO 18 | MPU-6500 SPI SCK                                      |
| GPIO 19 | MPU-6500 SPI MISO                                     |
| GPIO 23 | MPU-6500 SPI MOSI                                     |

If your board uses different pins, edit the `PIN_*` constants near the top of
`vibration_sensor_v1.0.ino`.

## Required Arduino libraries

Install these via the Arduino Library Manager (or PlatformIO equivalents):

- **WiFi** — bundled with ESP32 board package
- **WebServer** — bundled with ESP32 board package
- **DNSServer** — bundled with ESP32 board package
- **ESPmDNS** — bundled with ESP32 board package
- **Preferences** — bundled with ESP32 board package
- **HTTPClient** — bundled with ESP32 board package
- **SPI** — bundled
- **PubSubClient** — Nick O'Leary
- **ArduinoJson** — Benoît Blanchon (≥6.x)
- **Bolder Flight Systems MPU9250** — provides `bfs::Mpu6500`

Tested with ESP32 Arduino core 2.0.14 and PubSubClient 2.8.

## Build & flash

1. Open `vibration_sensor_v1.0.ino` in the Arduino IDE.
2. Tools → Board → "ESP32 Dev Module" (or your specific variant).
3. Tools → Partition Scheme → "Default 4MB with spiffs" or any partition that includes NVS.
4. Tools → Upload Speed → 921600.
5. Click **Upload**.

## First-boot setup walkthrough

1. **Power the device.** The status LED slow-blinks → it's in provisioning mode.
2. On your phone or laptop, **join WiFi `PreSense-Setup-XXXX`** (default password: `presense-setup`). Most platforms will pop a captive-portal browser automatically. If not, browse to `http://192.168.4.1` or `http://presense-setup.local`.
3. Fill in the form:
   - **WiFi SSID / password** — your normal network.
   - **Organization** — must match the value managers use on the dashboard (e.g. `Divor`).
   - **Asset ID** — numeric id of the asset this device is monitoring.
   - **Server host** — IP or hostname of the machine running the PreSense backend (e.g. `192.168.1.3`). Used both as the activation endpoint (`http://<server>:5000/api/devices/activate`) and as the initial MQTT broker host.
   - **Device name** (optional) — friendly label that the dashboard will show.
   - **Activation token (SLPT)** — copy/paste from the "Provision New Device" flow on the dashboard. It's single-use and expires.
4. Click **Save & Restart**. The device reboots, joins your WiFi (LED fast-blinks), exchanges the SLPT for MQTT credentials (LED double-blinks), and starts streaming telemetry (LED solid).

## LED legend

| Pattern        | Meaning                                              |
|----------------|------------------------------------------------------|
| Slow blink (1 Hz)   | Provisioning AP up — waiting for the setup form |
| Fast blink (5 Hz)   | Connecting to WiFi                              |
| Double-blink        | Activating — talking to `/api/devices/activate` |
| Solid on            | Running — streaming telemetry                   |
| Triple-blink        | Error — check serial log                        |
| Dimming during BOOT-button hold | Factory reset in progress (release before 5 s to abort) |

## Factory reset

Hold the **BOOT** button for **5 seconds**. The LED blinks fast while you hold;
when the timer fires, NVS is wiped and the device reboots straight into
provisioning AP mode. Release before 5 s to abort.

## Topic format

The device publishes to:

```
presense/{organization}/{asset_id}/{MAC}/telemetry
```

The values come from the AP form, so re-pairing a sensor with a different asset
requires a factory reset + re-provisioning. The dashboard's "Pair with Asset"
feature updates the database record (used for display) but doesn't push a new
topic config to the device — that's a known limitation tracked under "Stronger
device auth + remote config" in the project's IMPROVEMENTS.md.

## Troubleshooting

- **Captive portal doesn't pop on join.** Browse manually to `http://192.168.4.1`. On some Android variants, disable mobile data while the AP is connected.
- **WiFi join times out.** Watch the serial log at 115200 baud. Most often it's a typo in the password (the AP form does no live verification). Long-press BOOT to factory-reset and retry.
- **Activation keeps failing.** Confirm the SLPT hasn't expired (15 minutes by default), confirm the dashboard issued it for *this* MAC, and confirm the laptop / server hosting the API is reachable from the device's WiFi network. The serial log prints the URL it's calling.
- **Telemetry shows up under the wrong asset.** Verify the org / asset_id you typed in the form match the dashboard. Factory-reset + re-provision to fix.
- **MQTT keeps reconnecting.** Check that `MQTT_BROKER` host (returned by `/activate` as `broker_url`) is reachable on port 1883 from the device's WiFi network. Default dev compose listens on the host machine's IP.

## Extending

Pin-out tweaks, baud rate, batch size, and the vibration threshold are all near
the top of `vibration_sensor_v1.0.ino` and `mqtt_n_imu.ino`. NVS keys and the
schema version are defined in the main `.ino` so new fields are easy to add —
remember to bump `NVS_SCHEMA` when the layout changes so older devices
re-provision on the next firmware push.
