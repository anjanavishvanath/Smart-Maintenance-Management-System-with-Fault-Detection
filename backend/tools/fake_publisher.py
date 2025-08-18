#!/usr/bin/env python3
import time, json, random
import paho.mqtt.client as mqtt

BROKER = "localhost"  # or "mosquitto" if running inside container network
PORT = 1883
topic = "machines/test_asset/esp32-0001/telemetry"

client = mqtt.Client()
client.connect(BROKER, PORT, 60)

def gen_window(n=200):
    # synthetic 3-axis vibration samples (simulate sine + noise)
    import math
    sr = 2000
    t = [i/sr for i in range(n)]
    x = [0.02*math.sin(2*math.pi*50*ti) + 0.005*random.random() for ti in t]
    y = [0.02*math.sin(2*math.pi*70*ti) + 0.005*random.random() for ti in t]
    z = [0.015*random.random() for _ in t]
    return {"sample_rate": sr, "window_ms": int(n/sr*1000), "acc": {"x": x, "y": y, "z": z}}

while True:
    payload = {"device_id":"esp32-0001", "ts": time.time(), **gen_window(200)}
    client.publish(topic, json.dumps(payload))
    print("published")
    time.sleep(3)
