# PreSense Project Manifesto
> The Source of Truth for the PreSense IoT Vibration Monitoring System

## 1. The Architecture
PreSense is a Full Stack IoT Vibration monitoring system designed for asset monitoring and fault detection. It is divided into three main components: edge devices, backend infrastructure, and frontend UI.
- **Backend**: Python (Flask) API serving endpoints for authentication and business logic.
- **Database**: PostgreSQL with TimescaleDB extension for high-performance time-series sensor data storage.
- **Message Broker**: Eclipse Mosquitto (MQTT) handling telemetry ingestion. A Python script (`mqtt_ingestor.py`) subscribes to MQTT topics and persists chunks into the database.
- **Frontend**: React (Vite) application with JWT authentication, context API state management, and React Router.
- **Edge Devices**: ESP32 microcontrollers written in C++ (Arduino Framework). The architecture uses **polling** (at 200Hz) rather than an RTOS for simplicity. Data is batched in chunks of 20 samples and sent to the broker.

## 2. The Hardware Stack
- **Microcontroller**: ESP32 module with WiFi connectivity.
- **Sensors**: MPU9250 (9-axis MotionTracking device containing an accelerometer, gyroscope, and magnetometer).
- **Communication Protocols**:
  - **SPI**: Handled via `SPI.begin()`, linking the ESP32 and MPU9250 sensor.
  - **WiFi**: Used by the ESP32 as a Station to connect to the local network.
  - **MQTT**: The primary protocol for sending telemetry payloads to the `v1/device/<DEVICE_ID>/telemetry` topics.
  - **HTTP/REST**: For REST APIs between frontend/backend and initial device provisioning flow.

## 3. The "Current State"
### What is Currently Working
- **Full Auth Flow**: JWT-based authentication with bcrypt hashing, refresh token revocation, and user roles (manager/engineer/technician).
- **Database Layer**: Initial schema setup with migrations (`init_schema.sql`) and TimescaleDB running smoothly in Docker Compose.
- **Device Provisioning API**: Endpoints for device provisioning, claiming, and temporary MQTT credential assignment mapping configurable fields in JSON.
- **Frontend App Structure**: Authentication UI (Signup/Login), protected routing, and basic dashboard layout.
- **MQTT Telemetry Pipeline**: ESP32 accurately senses motion via the MPU9250 and transmits batched payloads; Python ingestor reliably inserts data to TimescaleDB.

### Specific Bugs & Works in Progress We Are Chasing
- **Establishing Device Baselines**: Integrating mean & standard deviation calculation for X, Y, Z dominant frequencies to the `asset_baselines` table and running raw data through FFT.
- **Fault Tolerance/Conditioning**: Defining fault conditions using these newly established FFT parameters to trigger actionable "Alerts".
- **Dynamic Device Provisioning**: Current firmware hardcodes WiFi/MQTT credentials. Transition to an ESP-native AP mode that serves an HTML page to dynamically provision WiFi credentials, saving directly into non-volatile storage (NVS).
- **Frontend Dashboards**: Ensuring complete behavior for the asset hierarchy (Company -> Users -> Assets -> Sensors). Display debugging and refining the alerts dashboard. 
- **MQTT Automation**: Managing and automating device provisioning and credentials seamlessly directly on a containerized Mosquitto broker rather than the manual HiveMQ tier.

## 4. The Codebase - Critical Parts

### A. Infrastructure (docker-compose.yml)
The application is entirely containerized.
```yaml
services:
  backend:
    build: ./backend
    # ... Flask API
  timescaledb:
    image: timescale/timescaledb:latest-pg14
    # ... Persistent data storage & migrations
  mqtt_broker:
    image: eclipse-mosquitto:latest
    # ... Receives telemetry
  mqtt_ingestor:
    build: ./backend
    command: python mqtt_ingestor.py
    # ... Bridges Mosquitto and TimescaleDB
```

### B. Device Telemetry Polling & Batching (ESP32 `deivce_activate_temp_v0.3.ino`)
The core reading and publishing loop for the ESP32.
```cpp
// --- Global Variables ---
unsigned long lastSampleTime = 0;
const unsigned long interval = 5; // to control sample frequency (200Hz)
const float VIBRATION_THRESHOLD = 0.05;
const int BATCH_SIZE = 20;

void setup() {
    // Basic startup & NVS loads
    Wire.begin(21, 22);
    mpu9250.setWire(&Wire);
    mpu9250.beginAccel();
    
    // MQTT setup
    mqttClient.setServer(mqttBroker.c_str(), 1883);
}

void loop() {
  if (!mqttClient.connected()) reconnect();
  mqttClient.loop();
  batchAndSendData();
}

// Data is pushed via JSON over PubSubClient mqttClient as a topic:
// e.g. "presense/Divor/1/<MAC_ADDRESS>/telemetry"
```

### C. Backend Telemetry Ingestion API (Example route)
Python routes defining the API contracts:
```python
# [POST] /api/devices/provision
# [MQTT] v1/device/<DEVICE_ID>/telemetry/
# [MQTT] v1/device/<DEVICE_ID>/telemetry/raw/meta
# [MQTT] v1/device/<id>/telemetry/raw/chunk/<block_id>/<idx>
```
