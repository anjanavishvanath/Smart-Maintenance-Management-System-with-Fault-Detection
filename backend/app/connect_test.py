import os, time, traceback
import paho.mqtt.client as mqtt

HOST = "8931093ac74c4ab0ac3f0cb16e92d38b.s1.eu.hivemq.cloud"
PORT = 8883
CA_FILE = "/usr/src/app/app/ca-chain.pem"
USER = os.getenv("MQTT_USER", os.getenv("MQTT_USERNAME", "preSense_vibrations"))
PASS = os.getenv("MQTT_PASSWORD", os.getenv("MQTT_PASS", "Test@123"))
TOPIC = os.getenv("MQTT_TOPIC_SUB", "test/topic")
CLIENT_ID = "debug-client-001"

def on_connect(client, userdata, flags, rc):
    print("[CB] on_connect rc=", rc)
    if rc == 0:
        print("[CB] Connected OK -> subscribing", TOPIC)
        client.subscribe(TOPIC)
    else:
        print("[CB] Bad connect rc:", rc)

def on_disconnect(client, userdata, rc):
    print("[CB] on_disconnect rc=", rc)

def on_subscribe(client, userdata, mid, granted_qos):
    print("[CB] on_subscribe mid=", mid, "qos=", granted_qos)

def on_message(client, userdata, msg):
    print("[CB] on_message:", msg.topic, msg.payload.decode(errors='replace'))

def on_log(client, userdata, level, buf):
    print("[CB-LOG]", level, buf)

client = mqtt.Client(client_id=CLIENT_ID, protocol=mqtt.MQTTv311)
client.username_pw_set(USER, PASS)
client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.on_subscribe = on_subscribe
client.on_message = on_message
client.on_log = on_log

print("Debug client starting. Host:", HOST, "Port:", PORT, "User:", USER, "Topic:", TOPIC)
print("Using CA file:", CA_FILE)
try:
    client.tls_set(ca_certs=CA_FILE)
except Exception as e:
    print("tls_set() error:", e)
    traceback.print_exc()

try:
    client.connect(HOST, PORT, keepalive=60)
except Exception as e:
    print("Connect threw:", e)
    traceback.print_exc()
    raise

client.loop_start()
# wait for callbacks (publish from HiveMQ Web Client while this runs)
print("Loop started; waiting 30s for callbacks. Publish a message now from HiveMQ web client.")
time.sleep(30)
client.loop_stop()
client.disconnect()
print("Debug client finished")
