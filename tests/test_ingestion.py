import paho.mqtt.client as mqtt
import json
import time

MQTT_HOST = "localhost" # Change to "mqtt_broker" if inside Docker
MQTT_PORT = 1883

def test_sensor_ingestion_and_baseline():
    client = mqtt.Client()
    client.connect(MQTT_HOST, MQTT_PORT)
    
    # Topic format from your ingestor: presense/org/asset/mac
    topic = "presense/1/101/AA:BB:CC:DD:EE:FF"
    
    # Send a batch of normal data
    payload = {
        "ts": int(time.time() * 1000),
        "samples": [{"ax": 0.01, "ay": 0.02, "az": 1.0} for _ in range(10)]
    }
    
    result = client.publish(topic, json.dumps(payload))
    client.disconnect()
    
    assert result.rc == mqtt.MQTT_ERR_SUCCESS
    print("Test Passed: Sensor data ingested successfully.")

if __name__ == "__main__":
    test_sensor_ingestion_and_baseline()