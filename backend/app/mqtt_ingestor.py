import os
import json
import math
import paho.mqtt.client as mqtt
from collections import Counter
from datetime import datetime, timezone, timedelta
from db import insert_sensor_data, insert_sensor_metrics, get_asset_baseline, insert_sensor_data_bulk, get_asset_details
from processing import calculate_vibration_metrics

# --- CONFIG ---
MQTT_BROKER = os.getenv("MQTT_BROKER", "mqtt_broker")
MQTT_PORT = 1883
MQTT_TOPIC_SUB = "presense/#"

# Global buffers to accumulate samples for higher resolution FFT
# Format: { asset_id: {'x': [], 'y': [], 'z': []} }
data_accumulators = {}
score_history = {} 

SAMPLING_RATE = 200 # 200Hz
DT_MS = 1000 / SAMPLING_RATE # 5ms


def on_connect(client, userdata, flags, rc):
    """Standard Paho v1 callback signature"""
    if rc == 0:
        print(f"Connected to Broker! Subscribing to {MQTT_TOPIC_SUB}...", flush=True)
        client.subscribe(MQTT_TOPIC_SUB)
    else:
        print(f"Connection failed with code {rc}", flush=True)

def diagnose_fault(rpm, mx, my, mz, score):
    if score == 0:
        return "Healthy"
    # Calculating anchor frequencies 
    fundamental_hz = rpm / 60 # eg: 1500RPM/60 = 25Hz
    two_x = fundamental_hz * 2
    # defining a tolerance cz FFT bins are not exact
    tol = 3

    # RULE: Unbalance
    if(math.isclose(mx['dominant_freq'], fundamental_hz, abs_tol=tol) or math.isclose(my['dominant_freq'], fundamental_hz, abs_tol=tol)):
        if mx['rms'] > 0.5 or my['rms'] > 0.5:
            return "Potential Unbalance"
    # RULE: Misalignment
    if (math.isclose(mz['dominant_freq'], fundamental_hz, abs_tol=tol) or 
        math.isclose(mz['dominant_freq'], two_x, abs_tol=tol)):
        if mz['rms'] > 0.4:
            return "Potential Misalignment"
    # RULE: Electrical Fault
    if math.isclose(mx['dominant_freq'], 50, abs_tol=1) or math.isclose(mx['dominant_freq'], 100, abs_tol=1):
        return "Electrical/Grid Noise"
    # FALLBACK: Mechanical Looseness
    return "General Mechanical Looseness"

def on_message(client, userdata, msg):
    # print(f"\nMESSAGE RECEIVED: {msg.topic}", flush=True)
    try:
        # Use arrival time as the wall-clock anchor
        arrival_time = datetime.now(timezone.utc)
        payload = json.loads(msg.payload.decode())
        parts = msg.topic.split('/')

        # Ensure we have enough parts: presense/org/asset/mac/...
        if len(parts) < 4: return

        asset_id = int(parts[2]) if parts[2].isdigit() else 0
        device_mac = parts[3]

        # Initialize buffer for this asset if not exists
        if asset_id not in data_accumulators:
            data_accumulators[asset_id] = {'x': [], 'y': [], 'z': []}

        baseline = get_asset_baseline(asset_id)
        
        if "samples" in payload:
            raw_samples = payload["samples"]
            esp_micros_start = payload.get("ts", 0) # Optional: if ESP32's internal 'ts' is needed for jitter analysis
            bulk_data = []

            for i, s in enumerate(raw_samples):
                ax = float(s.get("ax", 0))
                ay = float(s.get("ay", 0))
                az = float(s.get("az", 0))

                # Reconstruct timeline: Each sample is i*5ms after the arrival of the batch
                sample_time = arrival_time + timedelta(milliseconds=i * DT_MS)
                bulk_data.append((sample_time, device_mac, asset_id, ax, ay, az))
                # Buffer for FFT/Metrics
                if asset_id not in data_accumulators:
                    data_accumulators[asset_id] = {'x': [], 'y': [], 'z': []}
                data_accumulators[asset_id]['x'].append(ax)
                data_accumulators[asset_id]['y'].append(ay)
                data_accumulators[asset_id]['z'].append(az)
            
            # Insert into DB in bulk
            insert_sensor_data_bulk(bulk_data)

            # Check Buffer Size (Tumbling Window)
            current_buffer_size = len(data_accumulators[asset_id]['x'])
            
            if current_buffer_size >= SAMPLING_RATE:
                print(f"Buffer full ({current_buffer_size} samples). Processing metrics for Asset {asset_id}...", flush=True)
                # Get asset info
                asset_info = get_asset_details(asset_id)
                asset_rpm = asset_info.get('max_rpm', 1500)

                # Extract accumulated data
                x_vals = data_accumulators[asset_id]['x']
                y_vals = data_accumulators[asset_id]['y']
                z_vals = data_accumulators[asset_id]['z']

                # Calculate Metrics on large batch
                mx = calculate_vibration_metrics(x_vals, sampling_rate=200)
                my = calculate_vibration_metrics(y_vals, sampling_rate=200)
                mz = calculate_vibration_metrics(z_vals, sampling_rate=200)
                
                if mx is None or my is None or mz is None:
                    print(f"Error calculating metrics for device {device_mac}", flush=True)
                    # Reset buffer to avoid getting stuck? Or keep accumulating? 
                    # Better to reset to avoid bad state.
                    data_accumulators[asset_id] = {'x': [], 'y': [], 'z': []}
                    return

                total_rms = math.sqrt(mx['rms']**2 + my['rms']**2 + mz['rms']**2)
                
                # Clear Buffer immediately after processing
                data_accumulators[asset_id] = {'x': [], 'y': [], 'z': []}

                # Determine condition score 
                score = 0
                z_score = 0 

                if baseline and baseline.get('std_rms_total') and baseline['std_rms_total'] > 0:
                    # Z-Score Calculation
                    mu = baseline['mean_rms_total']
                    sigma = max(baseline['std_rms_total'], 0.01)
        
                    z_score = (total_rms - mu) / sigma

                    if z_score > 3:   # 99.7% deviation
                        score = 2     # Critical
                    elif z_score > 2: # 95% deviation
                        score = 1     # Warning
                    else:
                        score = 0     # Healthy
                else:
                    # FALLBACK
                    if total_rms > 1.2:
                        score = 2
                    elif total_rms > 0.6:
                        score = 1
                
                # Update Score History
                if asset_id not in score_history:
                    score_history[asset_id] = []
                score_history[asset_id].append(score)
                if len(score_history[asset_id]) > 5: # Keep last 5 PROCESSED batches
                    score_history[asset_id].pop(0)
                
                reported_score = Counter(score_history[asset_id]).most_common(1)[0][0]

                # Run diagnosis
                diagnosis = diagnose_fault(asset_rpm, mx, my, mz, reported_score)

                # Save Metrics
                insert_sensor_metrics(
                    time=arrival_time,
                    asset_id=asset_id,
                    rms_x=mx['rms'],
                    rms_y=my['rms'],
                    rms_z=mz['rms'],
                    rms_total=round(total_rms, 4),
                    peak_to_peak_z=mz['peak_to_peak'],
                    dominant_freq_x=mx['dominant_freq'],
                    dominant_freq_y=my['dominant_freq'],
                    dominant_freq_z=mz['dominant_freq'],
                    condition_score=reported_score,
                    diagnosis=diagnosis
                )
                print(f"Inserted metrics for asset {asset_id} (Score: {reported_score}, Freq Res: ~1Hz)", flush=True)

    except Exception as e:
        print(f"Error processing message: {e}", flush=True)

# --- INITIALIZE (Paho v1.x Style) ---
client = mqtt.Client() # No arguments needed for v1.x
client.on_connect = on_connect
client.on_message = on_message

print(f"Attempting connection to {MQTT_BROKER}...", flush=True)
client.connect(MQTT_BROKER, MQTT_PORT, 60)

client.loop_forever()