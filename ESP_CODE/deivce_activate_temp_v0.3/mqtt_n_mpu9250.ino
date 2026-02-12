void reconnect() {
  while (!mqttClient.connected()) {
    Serial.println("Attempting MQTT Connection...");
    if (mqttClient.connect("ESP32_Vibe_Sensor")) {
      Serial.println("Connected");
    } else {
      delay(5000);
    }
  }
}

void batchAndSendData() {
  if (!mqttClient.connected()) reconnect();
  mqttClient.loop();

  // --- NON-BLOCKING SAMPLING ---
  if (millis() - lastSampleTime >= interval) {
    lastSampleTime = millis(); // Reset timer

    if (mpu9250.accelUpdate() == 0) {
       if (sampleIndex == 0) {
           jsonDoc.clear();
       }       
       JsonArray samples = jsonDoc["samples"];
       if (samples.isNull()) {
          samples = jsonDoc.createNestedArray("samples");
       }

       JsonObject obj = samples.createNestedObject();
       obj["ax"] = mpu9250.accelX();
       obj["ay"] = mpu9250.accelY();
       obj["az"] = mpu9250.accelZ();
       
       sampleIndex++;
    }

    if (sampleIndex >= BATCH_SIZE) {
        serializeJson(jsonDoc, mqttBuffer);
        if (mqttClient.publish(deviceTopic.c_str(), mqttBuffer)) {
            Serial.print("Batch Sent! Size: ");
            Serial.println(sampleIndex);
        } else {
            Serial.println("Publish Failed");
        }
        sampleIndex = 0;
        lastMsg = millis(); 
    }
  }
}