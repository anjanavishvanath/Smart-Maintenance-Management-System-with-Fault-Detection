// ================= Factory-reset button =================
// Long-press of PIN_RESET_BTN (GPIO 0 / BOOT) for ≥ 5 s wipes the NVS namespace
// and reboots into provisioning AP mode. Polled in a low-priority task so it
// works in every boot mode (provisioning, activating, running).

const uint32_t RESET_HOLD_MS  = 5000;
const uint32_t POLL_PERIOD_MS = 50;

void resetButtonTask(void* pv) {
  uint32_t pressedFor = 0;
  bool wasPressed = false;

  while (true) {
    bool pressed = (digitalRead(PIN_RESET_BTN) == LOW);  // active-low w/ pullup
    if (pressed) {
      if (!wasPressed) {
        wasPressed = true;
        pressedFor = 0;
      } else {
        pressedFor += POLL_PERIOD_MS;
        // While held, blink fast as a visual progress indicator. We don't
        // override ledPattern permanently — the LED task ignores us until reset
        // fires. Instead we toggle the pin directly for the duration of the hold.
        digitalWrite(PIN_LED, (pressedFor / 100) % 2);
        if (pressedFor >= RESET_HOLD_MS) {
          Serial.println("[reset] long-press detected → wiping NVS and rebooting");
          clearAllConfig();
          // Solid LED for a beat to confirm before reboot.
          digitalWrite(PIN_LED, HIGH);
          delay(500);
          ESP.restart();
        }
      }
    } else {
      if (wasPressed && pressedFor >= 200) {
        Serial.printf("[reset] release after %ums (need %ums for factory reset)\n",
                      pressedFor, RESET_HOLD_MS);
      }
      wasPressed = false;
      pressedFor = 0;
    }
    vTaskDelay(pdMS_TO_TICKS(POLL_PERIOD_MS));
  }
}
