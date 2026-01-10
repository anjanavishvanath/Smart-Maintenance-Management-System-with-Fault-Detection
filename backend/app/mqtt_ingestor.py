import os
import json
import paho.mqtt.client as mqtt
from datetime import datetime, timezone
from sqlalchemy import text
from db import insert_sensor_data

# Configure MQTT broker settings
MQTT_BROKER = os.getenv("MQTT_BROKER", "mqtt_broker")
MQTT_PORT = 1883
MQTT_TOPIC = "presense/+/+/+/telemetry" # wildcard for org/asset/mac

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT Broker!")
        client.subscribe("#")
    else:
        print(f"Failed to connect, return code {rc}")

def on_message(client, userdata, msg):
    print(f"Received message on topic {msg.topic}")
    try:
        # Parse Topic: presense/{org}/{asset_id}/{mac}/telemetry
        parts = msg.topic.split('/')
        org_name = parts[1]
        asset_id = int(parts[2]) if parts[2].isdigit() else None
        device_mac = parts[3]
        # Parse Payload
        payload = json.loads(msg.payload.decode())
        # Extract Data. Using server side time for consistency
        time = datetime.now(timezone.utc)
        x = float(payload.get("x", 0))
        y = float(payload.get("y", 0))
        z = float(payload.get("z", 0))
        # Insert into DB
        insert_sensor_data(time, device_mac, asset_id, x, y, z)
        print(f"Inserted data for device {device_mac} at {time.isoformat()}")
    except Exception as e:
        print(f"Error parsing message: {e}")

# Initialize MQTT Client
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

# Connect and Loop
print(f"Attempting to connect to MQTT Broker at {MQTT_BROKER}:{MQTT_PORT}")
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_forever()