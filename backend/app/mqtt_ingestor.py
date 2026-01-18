import os
import json
import paho.mqtt.client as mqtt
from datetime import datetime, timezone
from db import insert_sensor_data

# --- CONFIG ---
MQTT_BROKER = os.getenv("MQTT_BROKER", "mqtt_broker")
MQTT_PORT = 1883
MQTT_TOPIC_SUB = "presense/#"

def on_connect(client, userdata, flags, rc):
    """Standard Paho v1 callback signature"""
    if rc == 0:
        print(f"Connected to Broker! Subscribing to {MQTT_TOPIC_SUB}...", flush=True)
        client.subscribe(MQTT_TOPIC_SUB)
    else:
        print(f"Connection failed with code {rc}", flush=True)

def on_message(client, userdata, msg):
    print(f"\nMESSAGE RECEIVED: {msg.topic}", flush=True)
    try:
        payload_str = msg.payload.decode()
        payload = json.loads(payload_str)
        parts = msg.topic.split('/')

        # Ensure we have enough parts: presense/org/asset/mac/...
        if len(parts) < 4:
            return

        device_mac = parts[3]
        asset_id = int(parts[2]) if parts[2].isdigit() else 0
        
        if "samples" in payload:
            for sample in payload["samples"]:
                time = datetime.now(timezone.utc)
                insert_sensor_data(
                    time, device_mac, asset_id,
                    float(sample.get("ax", 0)),
                    float(sample.get("ay", 0)),
                    float(sample.get("az", 0))
                )
            print(f"Successfully stored batch from {device_mac}", flush=True)

    except Exception as e:
        print(f"Error processing message: {e}", flush=True)

# --- INITIALIZE (Paho v1.x Style) ---
client = mqtt.Client() # No arguments needed for v1.x
client.on_connect = on_connect
client.on_message = on_message

print(f"Attempting connection to {MQTT_BROKER}...", flush=True)
client.connect(MQTT_BROKER, MQTT_PORT, 60)

client.loop_forever()