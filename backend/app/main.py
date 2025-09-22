from flask import Flask, jsonify
import paho.mqtt.client as mqtt
import os
import threading
import time
import traceback

app = Flask(__name__)

# MQTT Configuration
MQTT_HOST = "8931093ac74c4ab0ac3f0cb16e92d38b.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USERNAME = "preSense_vibrations"
MQTT_PASSWORD = "Test@123"
MQTT_TOPIC_SUB = "test/topic"
CLIENT_ID = "cm-backend"

# using absolute path for the certificate
BASEDIR = os.path.abspath(os.path.dirname(__file__))
CA_FILE = os.path.join(BASEDIR, "ca-chain.pem")

# Global storage
latest_message = {}
mqtt_connected = False
mqtt_client = None

def on_connect(client, userdata, flags, rc):
    global mqtt_connected
    if rc == 0:
        mqtt_connected = True
        client.subscribe(MQTT_TOPIC_SUB, qos=0)
        print(f"[MQTT] Connected (rc=0). Subscribed to {MQTT_TOPIC_SUB}")
    else:
        print(f"[MQTT] Connection failed with code {rc}")
        mqtt_connected = False

def on_message(client, userdata, msg):
    global latest_message
    try:
        payload = msg.payload.decode("utf-8", errors="replace")
        entry = {"topic": msg.topic, "payload": payload, "qos": msg.qos, "timestamp": time.time()}
        latest_message = entry
        print(f"[MQTT] Message received: {entry}")
    except Exception as e:
        print(f"[MQTT] Error processing message: {e}")
        traceback.print_exc()

def on_log(client, userdata, level, buf):
    print(f"[MQTT-log] {level}: {buf}")

def start_mqtt_thread():
    global mqtt_client, mqtt_connected
    print("[MQTT] Starting MQTT thread...")
    try:
        mqtt_client = mqtt.Client(client_id=CLIENT_ID, protocol=mqtt.MQTTv311) #see what clean_session does
        mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        # set TLS/CA file; raise if file not found
        if not os.path.isfile(CA_FILE):
            raise FileNotFoundError(f"CA file not found: {CA_FILE}")
        mqtt_client.tls_set(ca_certs=CA_FILE)
        mqtt_client.on_connect = on_connect
        mqtt_client.on_message = on_message
        mqtt_client.on_log = on_log

        print(f"[MQTT] Connecting to HiveMQ:{MQTT_PORT} with CA file {CA_FILE}...")
        mqtt_client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
        mqtt_client.loop_start()

        # Wait for connection
        timeout = 10  # seconds
        for i in range(timeout):
            if mqtt_connected:
                break
            print(f"[MQTT] Waiting for connection... {i+1}/{timeout}")
            time.sleep(1)
        if not mqtt_connected:
            print("[MQTT] Connection timeout. Check logs, CA file and network.")
    
    except Exception as e:
        print(f"[MQTT] Error setting up MQTT client: {e}")
        traceback.print_exc()
    
#Flask routes
@app.route("/")
def index():
    return jsonify({"message": "Welcome to the Flask API!", "mqtt_connected": mqtt_connected})

@app.route("/latest")
def get_latest_message():
    if latest_message:
        return jsonify({"mqtt_connected": mqtt_connected, "data": latest_message})
    else:
        return jsonify({"message": "No data received yet", "mqtt_connected": mqtt_connected}), 404

if __name__ == "__main__":
    # Start MQTT thread (guarded by __main__ so it does not run on import)
    mqtt_thread = threading.Thread(target=start_mqtt_thread, daemon=True)
    mqtt_thread.start()
    # Start Flask (dev). In production, use WSGI server and run mqtt client separately.
    app.run(host="0.0.0.0", port=5000)


'''
 Only for development: use threaded=True so the app and the mqtt thread can coexist.
 For production, run via gunicorn / uwsgi. When using multiple worker processes,
 run this MQTT client as a separate service (or use one worker (in docker?)).
'''