from flask import Flask, jsonify
import os
import threading
import time
import json
import paho.mqtt.client as mqtt

app = Flask(__name__)

MQTT_BROKER = os.getenv('MQTT_BROKER', 'mosquitto')
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
TOPIC = "machines/+/+/telemetry" # add to env later

last_message = {}

def on_connect(client, userdata, flags, rc):
    print("Connected to MQTT broker")
    client.subscribe(TOPIC)

def on_message(client, userdata, msg):
    global last_message
    try:
        payload = msg.payload.decode()
        last_message = {
            "topic": msg.topic,
            "payload": payload,
            "ts": time.time()
        }
        print("MQTT msg", msg.topic, payload[:200])
    except Exception as e:
        print("Error processing MQTT message:", e)

def start_mqtt():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()

@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "mqtt_broker": MQTT_BROKER})

@app.route("/api/last")
def last():
    return jsonify(last_message)

if __name__ == "__main__":
    #Start MQTT in a thread
    t = threading.Thread(target=start_mqtt, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=5000)