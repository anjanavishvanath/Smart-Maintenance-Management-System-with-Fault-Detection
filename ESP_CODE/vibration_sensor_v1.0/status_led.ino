// ================= Status LED =================
// One GPIO, six visual states. The factory_reset task takes over the pin
// while a button is held (so the user sees "you're doing the right thing");
// otherwise this task drives the LED based on `ledPattern`.
//
// Patterns:
//   PROVISIONING  — slow blink (1 Hz)
//   CONNECTING    — fast blink (5 Hz)
//   ACTIVATING    — double-blink (two quick on, then off)
//   RUNNING       — solid on
//   ERROR         — triple-blink
//   OFF           — off

void ledTask(void* pv) {
  while (true) {
    LedPattern p = ledPattern;
    switch (p) {
      case LED_PROVISIONING:
        digitalWrite(PIN_LED, HIGH); vTaskDelay(pdMS_TO_TICKS(500));
        digitalWrite(PIN_LED, LOW);  vTaskDelay(pdMS_TO_TICKS(500));
        break;
      case LED_CONNECTING:
        digitalWrite(PIN_LED, HIGH); vTaskDelay(pdMS_TO_TICKS(100));
        digitalWrite(PIN_LED, LOW);  vTaskDelay(pdMS_TO_TICKS(100));
        break;
      case LED_ACTIVATING:
        for (int i = 0; i < 2; i++) {
          digitalWrite(PIN_LED, HIGH); vTaskDelay(pdMS_TO_TICKS(80));
          digitalWrite(PIN_LED, LOW);  vTaskDelay(pdMS_TO_TICKS(80));
        }
        vTaskDelay(pdMS_TO_TICKS(700));
        break;
      case LED_RUNNING:
        digitalWrite(PIN_LED, HIGH);
        vTaskDelay(pdMS_TO_TICKS(500));
        break;
      case LED_ERROR:
        for (int i = 0; i < 3; i++) {
          digitalWrite(PIN_LED, HIGH); vTaskDelay(pdMS_TO_TICKS(120));
          digitalWrite(PIN_LED, LOW);  vTaskDelay(pdMS_TO_TICKS(120));
        }
        vTaskDelay(pdMS_TO_TICKS(700));
        break;
      case LED_OFF:
      default:
        digitalWrite(PIN_LED, LOW);
        vTaskDelay(pdMS_TO_TICKS(200));
        break;
    }
  }
}
