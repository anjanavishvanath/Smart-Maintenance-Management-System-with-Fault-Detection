# PreSense Projet - Feature Checklist and Roadmap

## Project Summary
A full stack IoT Vibration monitoring system using: <br>
* ESP32 + MPU9250 edge devices
* Flask backend with PostgresSQL/TimescaleDB
* React Frontend (Vite) with JWT authentication
* MQTT telemetry + Device management

## Implemented Features
### 1.1 Backend (Flask + PostgreSQL/TimescaleDB)
#### Authentication
- ✅ JWT-based authentication (access + refresh tokens)
* ✅ Secure hashing with bcrypt (Passlib)
* ✅ User roles: manager / engineer / technician
* ✅ Signup & login endpoints
* ✅ Username added to user table + tokens
* ✅ Refresh token revocation table
* ✅ CORS correctly configured for frontend
#### Database
* ✅ __users__, __devices__, 
* ✅ Migrations via init_schema.sql
* ✅ Working TimescaleDB + Docker Compose setup
#### Device Provisioning Backend API
* ✅ [POST] __/api/auth/signup__ 
* ✅ [POST] __/api/auth/login__ 
* ✅ [POST] __/api/auth/refresh__ 
* ✅ [POST] __/api/auth/logout__
* ✅ [POST] __/api/devices/provision__ endpoint structure defined
* ✅ Device creates claim request → backend validates → returns MQTT credentials (temporary)
* ✅ Device entry auto-created in DB on first provisioning
* ✅ Placeholder MQTT credentials generation (Manually entered to HiveMQ for now)
* ✅ Device config JSON field added to DB
* ✅ [MQTT] v1/device/<DEVICE_ID>/telemetry/
* ✅ [MQTT] v1/device/<DEVICE_ID>/telemetry/raw/meta
* ✅ [MQTT] v1/device/<id>/telemetry/raw/chunk/<block_id>/<idx>
* ✅ [MQTT] on_message parse between metrics and raw data 

### 1.2 Frontend (React)
#### Authentication UI
* ✅ Signup page working
* ✅ Login page working
* ✅ Username validation
* ✅ Email + password validation
* ✅ AuthProvider with JWT token decoding
* ✅ Tokens stored in localStorage
* ✅ Protected routes
* ✅ Logout working
* ✅ Device provisioning (temp) to user
#### Basic App Structure
* ✅ React Router implemented
* ✅ Dashboard page loads user info
* ✅ Global auth state via Context API

### 1.3 ESP32 Firmware
#### Local WiFi AP Provisioning Flow
* ✅ ESP32 runs as a station (cridentials hardcoded)
* ✅ Hardcoded MQTT cridentials
* ✅ Sends metrics to __v1/device/<DEVICE_ID>/telemetry/ topic__
* ✅ Sends raw data meta to __v1/device/<DEVICE_ID>/telemetry/raw/meta__ (# of chunks, etc...)
* ✅ Sends raw data as chunks __v1/device/<id>/telemetry/raw/chunk/<block_id>/<idx>__

## Features to Add
### 2.1 Backend
* 🟥 Establish baseline for device
* 🟥 Run FFT for raw data
* 🟥 Define faulty conditions with FFT parametes
* 🟥 Collect/Find dataset for DL model?

### 2.2 Frontend
* 🟥 Being able to create a company entity - for managers
* 🟥 Add users to company entity
* 🟥 Add assets - managers and engineers
* 🟥 Share assets across comapany
* 🟥 link a sensor module to asset

### 2.3 ESP32 Firmware
* 🟥 Start as an AP
* 🟥 Serve HTML form for WiFi credentials + User id?
* 🟥 Switch to station and try to connect, if not possible, switch to AP again
* 🟥 Find a way to provision devices automatically 
* 🟥 Save config data in persistent memory

# 2.4 MQTT Broker
* ⚠️ free tier of HiveMQ does not allow to API intergration.
* 🟥 Either spin up a docker mosquitto broker or find one that lets us automate device provisioning
