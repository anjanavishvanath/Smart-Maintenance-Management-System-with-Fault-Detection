// ================= IMU sampling + MQTT publish =================
// Two FreeRTOS tasks pinned to opposite cores:
//   * Core 1 (samplingTask): tight 200 Hz read of the MPU-6500, batched, only
//     enqueued when the batch's peak vibration exceeds VIBRATION_THRESHOLD.
//     This keeps "machine asleep" from spamming the broker.
//   * Core 0 (mqttTask): pulls from the queue, builds JSON batches, publishes.
//
// MQTT auth + topic come from NVS (set during activation/provisioning).

struct SamplePacket {
  uint32_t ts;
  float ax, ay, az;
};

// ---- MQTT reconnect with backoff ----------------------------------------
static void mqttReconnect() {
  uint32_t backoffMs = 1000;
  const uint32_t backoffCapMs = 30 * 1000;

  while (!mqttClient.connected()) {
    Serial.printf("[mqtt] connecting to %s as %s ...\n",
                  config.broker.c_str(), config.mqtt_user.c_str());
    String clientId = "presense-" + WiFi.macAddress();
    bool ok = mqttClient.connect(
      clientId.c_str(),
      config.mqtt_user.c_str(),
      config.mqtt_pass.c_str(),
      "status/topic", 0, true, "offline"
    );
    if (ok) {
      Serial.println("[mqtt] connected.");
      mqttClient.publish("status/topic", "online", true);
      return;
    }
    Serial.printf("[mqtt] failed rc=%d; retrying in %ums\n", mqttClient.state(), backoffMs);
    vTaskDelay(pdMS_TO_TICKS(backoffMs));
    backoffMs = min(backoffMs * 2, backoffCapMs);   // exponential backoff capped at 30s
  }
}

// ---- Sampling task (Core 1) ---------------------------------------------
// Idle-suppression note: we measure vibration as the AC-coupled peak deviation
// from the *window's own mean* — NOT as |a| - 1g. The latter is contaminated
// by the IMU's per-chip calibration offset (typically 3-7%), so a perfectly
// stationary sensor reads ~0.07 g and never gates idle data correctly.
// Subtracting the window mean cancels gravity, calibration bias, and any
// mounting tilt in one shot, giving a sensor-agnostic threshold.
static void samplingTask(void* pv) {
  const TickType_t periodTicks = pdMS_TO_TICKS(5);  // 200 Hz
  TickType_t lastWake = xTaskGetTickCount();

  SamplePacket window[BATCH_SIZE];
  int count = 0;
  uint32_t windowTs = 0;

  Serial.println("[sampling] started on core 1");
  while (true) {
    if (imu.Read()) {
      float ax = imu.accel_x_mps2() / G_TO_MPS2;
      float ay = imu.accel_y_mps2() / G_TO_MPS2;
      float az = imu.accel_z_mps2() / G_TO_MPS2;

      if (count == 0) windowTs = micros();
      window[count] = { windowTs, ax, ay, az };
      count++;

      if (count >= BATCH_SIZE) {
        // Window mean (the DC / gravity component, including any sensor bias).
        float mx = 0.0f, my = 0.0f, mz = 0.0f;
        for (int i = 0; i < BATCH_SIZE; i++) {
          mx += window[i].ax;
          my += window[i].ay;
          mz += window[i].az;
        }
        mx /= BATCH_SIZE;
        my /= BATCH_SIZE;
        mz /= BATCH_SIZE;

        // Peak AC residual across the window. This is the actual vibration
        // magnitude — robust to any constant offset on any axis.
        float maxResidual = 0.0f;
        for (int i = 0; i < BATCH_SIZE; i++) {
          float dx = window[i].ax - mx;
          float dy = window[i].ay - my;
          float dz = window[i].az - mz;
          float r  = sqrtf(dx*dx + dy*dy + dz*dz);
          if (r > maxResidual) maxResidual = r;
        }

        if (maxResidual > VIBRATION_THRESHOLD) {
          for (int i = 0; i < BATCH_SIZE; i++) {
            xQueueSend(sampleQueue, &window[i], 0);
          }
        }
        count = 0;
      }
    }
    vTaskDelayUntil(&lastWake, periodTicks);
  }
}

// ---- MQTT task (Core 0) -------------------------------------------------
static void mqttTask(void* pv) {
  SamplePacket s;
  int sampleIndex = 0;
  uint32_t batchTs = 0;

  while (true) {
    if (!mqttClient.connected()) mqttReconnect();
    mqttClient.loop();

    if (xQueueReceive(sampleQueue, &s, pdMS_TO_TICKS(10))) {
      if (sampleIndex == 0) {
        jsonDoc.clear();
        batchTs = s.ts;
        jsonDoc["ts"] = batchTs;
      }
      JsonArray samples = jsonDoc["samples"];
      if (samples.isNull()) samples = jsonDoc.createNestedArray("samples");

      JsonObject obj = samples.createNestedObject();
      obj["ax"] = s.ax;
      obj["ay"] = s.ay;
      obj["az"] = s.az;

      sampleIndex++;
      if (sampleIndex >= BATCH_SIZE) {
        serializeJson(jsonDoc, mqttBuffer);
        if (!mqttClient.publish(deviceTopic.c_str(), mqttBuffer)) {
          Serial.println("[mqtt] publish failed");
        }
        sampleIndex = 0;
      }
    }
  }
}

// ---- Public entry point -------------------------------------------------
void startTelemetryTasks(const Config& cfg) {
  // Bring up the IMU.
  SPI.begin(PIN_IMU_SCK, PIN_IMU_MISO, PIN_IMU_MOSI, PIN_IMU_CS);
  pinMode(PIN_IMU_CS, OUTPUT);
  digitalWrite(PIN_IMU_CS, HIGH);

  Serial.println("[imu] initialising MPU-6500 over SPI ...");
  if (!imu.Begin()) {
    Serial.println("[imu] init failed (check wiring on MISO/MOSI/SCK/CS)");
    ledPattern = LED_ERROR;
    while (true) delay(1000);
  }
  if (!imu.ConfigSrd(4)) {
    Serial.println("[imu] sample-rate divider config failed");
  }

  // Topic format expected by the backend ingestor:
  // presense/{org}/{asset_id}/{mac}/telemetry
  deviceTopic = "presense/" + cfg.organization + "/" + String(cfg.asset_id) +
                "/" + WiFi.macAddress() + "/telemetry";
  Serial.println("[mqtt] topic: " + deviceTopic);

  mqttClient.setServer(cfg.broker.c_str(), 1883);
  mqttClient.setBufferSize(8192);
  mqttClient.setKeepAlive(30);

  sampleQueue = xQueueCreate(400, sizeof(SamplePacket));
  if (sampleQueue == nullptr) {
    Serial.println("[mqtt] queue alloc failed");
    ledPattern = LED_ERROR;
    return;
  }

  xTaskCreatePinnedToCore(samplingTask, "sampling", 4096, nullptr, 2, nullptr, 1);
  xTaskCreatePinnedToCore(mqttTask,     "mqtt",     8192, nullptr, 1, nullptr, 0);
  Serial.println("[mqtt] telemetry tasks running.");
}
