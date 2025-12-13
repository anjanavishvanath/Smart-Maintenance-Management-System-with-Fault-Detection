#include <WiFi.h>

void setup(){
  Serial.begin(115200);

  WiFi.mode(WIFI_STA);
  WiFi.STA.begin();

  Serial.print("[DEFAULT] ESP32 Board MAC Address: ");
  Serial.println(String(WiFi.macAddress()));
}
 
void loop(){

}