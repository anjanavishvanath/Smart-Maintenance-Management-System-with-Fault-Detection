import os
import json
import math
import paho.mqtt.client as mqtt
from collections import Counter
from datetime import datetime, timezone
from db import insert_sensor_data, insert_sensor_metrics, get_asset_baseline
from processing import calculate_vibration_metrics

# --- CONFIG ---
MQTT_BROKER = os.getenv("MQTT_BROKER", "mqtt_broker")
MQTT_PORT = 1883
MQTT_TOPIC_SUB = "presense/#"

# to prevent false warnings
score_history = {} 

def on_connect(client, userdata, flags, rc):
    """Standard Paho v1 callback signature"""
    if rc == 0:
        print(f"Connected to Broker! Subscribing to {MQTT_TOPIC_SUB}...", flush=True)
        client.subscribe(MQTT_TOPIC_SUB)
    else:
        print(f"Connection failed with code {rc}", flush=True)

def on_message(client, userdata, msg):
    # print(f"\nMESSAGE RECEIVED: {msg.topic}", flush=True)
    try:
        event_time = datetime.now(timezone.utc)
        payload_str = msg.payload.decode()
        payload = json.loads(payload_str)
        parts = msg.topic.split('/')

        # Ensure we have enough parts: presense/org/asset/mac/...
        if len(parts) < 4:
            return

        device_mac = parts[3]
        asset_id = int(parts[2]) if parts[2].isdigit() else 0

        baseline = get_asset_baseline(asset_id)
        
        if "samples" in payload:
            raw_samples = payload["samples"]
            for sample in raw_samples:
                time = event_time
                insert_sensor_data(
                    time, device_mac, asset_id,
                    float(sample.get("ax", 0)),
                    float(sample.get("ay", 0)),
                    float(sample.get("az", 0))
                )
            print(f"Successfully stored batch from {device_mac}", flush=True)
            # Extract arrays
            x_vals = [float(s.get("ax", 0)) for s in raw_samples]
            y_vals = [float(s.get("ay", 0)) for s in raw_samples]
            z_vals = [float(s.get("az", 0)) for s in raw_samples]
            # Calculate Metrics
            mx = calculate_vibration_metrics(x_vals, sampling_rate=200)
            my = calculate_vibration_metrics(y_vals, sampling_rate=200)
            mz = calculate_vibration_metrics(z_vals, sampling_rate=200)
            total_rms = math.sqrt(mx['rms']**2 + my['rms']**2 + mz['rms']**2)
            
            if mx is None or my is None or mz is None:
                print(f"No valid samples to process for device {device_mac}", flush=True)
                return
            # Determine condition score 
            score = 0
            z_score = 0 # Optional: store the raw Z-score in the DB

            if baseline and baseline.get('std_rms_total') and baseline['std_rms_total'] > 0:
                # 2. Calculate Z-Score
                mu = baseline['mean_rms_total']
                sigma = baseline['std_rms_total']
    
                # Using a 'noise floor' for sigma to prevent division by zero and over-sensitivity on very still machines
                sigma = max(sigma, 0.01) 
    
                z_score = (total_rms - mu) / sigma if sigma > 0 else 0

                # 3. Dynamic Scoring based on statistical deviation
                if z_score > 3:   # 99.7% deviation - Something is definitely wrong
                    score = 2     # Critical
                elif z_score > 2: # 95% deviation - Outside normal operating range
                    score = 1     # Warning
                else:
                    score = 0     # Healthy
            else:
                # FALLBACK: If no baseline exists yet, using hardcoded logic
                if total_rms > 1.2:
                    score = 2
                elif total_rms > 0.6:
                    score = 1
                print(f"No baseline for asset {asset_id}, using fallback scoring.")
            
            if asset_id not in score_history:
                score_history[asset_id] = []
            score_history[asset_id].append(score)
            if len(score_history[asset_id]) > 5: # Keep last 5 batches
                score_history[asset_id].pop(0)
            # promote the most common score in history to avoid false alarms
            reported_score = Counter(score_history[asset_id]).most_common(1)[0][0]
            # Save Metrics. One row per batch.
            insert_sensor_metrics(
                time=event_time,
                asset_id=asset_id,
                rms_x=mx['rms'],
                rms_y=my['rms'],
                rms_z=mz['rms'],
                rms_total=round(total_rms, 4),
                peak_to_peak_z=mz['peak_to_peak'],
                dominant_freq_x=mx['dominant_freq'],
                condition_score=reported_score
            )
            print(f"Inserted metrics for asset {asset_id} (Condition Score: {score})", flush=True)

    except Exception as e:
        print(f"Error processing message: {e}", flush=True)

# --- INITIALIZE (Paho v1.x Style) ---
client = mqtt.Client() # No arguments needed for v1.x
client.on_connect = on_connect
client.on_message = on_message

print(f"Attempting connection to {MQTT_BROKER}...", flush=True)
client.connect(MQTT_BROKER, MQTT_PORT, 60)

client.loop_forever()