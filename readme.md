# PreSense Project — Feature Checklist and Roadmap

## Project Summary
A full-stack IoT vibration monitoring system for predictive maintenance: <br>
* ESP32 + MPU-6500 edge devices (200 Hz, SPI)
* Flask backend with PostgreSQL / TimescaleDB
* React frontend (Vite) with JWT authentication
* Self-hosted Mosquitto MQTT broker (TCP + WebSocket)
* Containerised stack via Docker Compose

Data pipeline: **ESP32 → MQTT (Mosquitto) → Python ingestor → TimescaleDB → Flask API → React UI**

---

## Implemented Features

### 1.1 Backend (Flask + PostgreSQL / TimescaleDB)

#### Authentication & Security
* ✅ JWT-based authentication (access + refresh tokens)
* ✅ Secure password hashing with bcrypt (Passlib)
* ✅ User roles: manager / engineer / technician
* ✅ Signup, login, refresh, logout, change-password endpoints
* ✅ Refresh-token issuance tracking + per-JTI revocation table
* ✅ JWT blocklist (`token_in_blocklist_loader`) for both access and refresh tokens
* ✅ Configurable CORS via `CORS_ORIGINS` env var
* ✅ Per-IP rate limiting on auth + provisioning routes (Flask-Limiter)
* ✅ Fail-fast on missing `JWT_SECRET_KEY` — no hard-coded fallback
* ✅ Audit log table (`audit_logs`) with user/action/entity/metadata

#### Database (TimescaleDB)
* ✅ Core tables: `users`, `devices`, `assets`, `provisioning_tokens`, `refresh_tokens`, `revoked_tokens`
* ✅ Hypertables: `sensor_data`, `asset_health_metrics`
* ✅ Anomaly tracking: `asset_baselines`, `asset_events`
* ✅ Maintenance: `maintenance_tickets`, `ticket_logs`
* ✅ Audit: `audit_logs`
* ✅ Soft-delete on assets (`deleted_at`) preserves history for audit/reporting
* ✅ `last_seen` stamped on devices by ingestor for online/offline UI status
* ✅ Migrations under `sql/migrations/` (asset soft-delete, token blocklist, device last_seen, audit log)
* ✅ Docker-based TimescaleDB with persistent `pgdata` volume

#### Device Provisioning API
* ✅ `POST /api/auth/signup` / `login` / `refresh` / `logout` / `change-password`
* ✅ `POST /api/devices/provision` — manager issues a Short-Lived Provisioning Token (SLPT)
* ✅ `POST /api/devices/activate` — ESP32 exchanges SLPT + MAC for MQTT credentials
* ✅ `GET /api/devices/by_user`, `PUT /api/devices/<id>/name`, `DELETE /api/devices/<id>`
* ✅ `POST /api/assets/link_sensor` — bind a device to an asset

#### Asset Management API
* ✅ `POST /api/assets/add`, `GET /api/assets/by_organization`
* ✅ `PUT /api/assets/<id>`, `DELETE /api/assets/<id>` (soft delete)
* ✅ `GET/POST/DELETE /api/assets/baseline/<asset_id>` — set / fetch / reset baseline

#### Analytics & Alerts API
* ✅ `GET /api/analytics/spectrum/<asset_id>` — FFT spectrum, with optional `until` / `limit`
* ✅ `GET /api/analytics/health/<asset_id>` — RMS, dominant freq, condition score over time
* ✅ `GET /api/alerts/recent` — org-scoped event history with pagination

#### Maintenance / Tickets API
* ✅ `POST /api/tickets/create`, `GET /api/tickets/by_org`
* ✅ `PATCH /api/tickets/<id>/status`, `DELETE /api/tickets/<id>`
* ✅ `GET /api/users/assignable` — list users available for assignment
* ✅ Ticket statuses: open → in_progress → resolved → closed
* ✅ Optional link from ticket to triggering `asset_event`

#### Reports API
* ✅ `GET /api/reports/reliability` — uptime / MTBF style summary
* ✅ `GET /api/reports/alert_resolution` — alert volume + resolution times
* ✅ `GET /api/reports/fft_export/<asset_id>` — CSV/Excel export of spectrum
* ✅ `GET /api/reports/reliability/export`, `GET /api/reports/alert_resolution/export`

#### MQTT Ingestor (separate container)
* ✅ Subscribes to `presense/#` on Mosquitto
* ✅ Parses batched accelerometer frames (x/y/z @ 200 Hz)
* ✅ Bulk insert into `sensor_data` hypertable
* ✅ Computes RMS, peak-to-peak, FFT, dominant frequency per axis
* ✅ Writes `asset_health_metrics` rows per tumbling window
* ✅ Z-score anomaly detection against `asset_baselines` (warning ≥ 3σ, critical ≥ 5σ)
* ✅ Fallback magnitude triage when no baseline exists
* ✅ Opens / closes `asset_events` with severity + initial diagnosis
* ✅ FFT-driven fault hints: 1× → unbalance, 2× → misalignment, sub-harmonics → bearing wear
* ✅ Bounded LRU caches for accumulators / scores / baselines (memory-safe)
* ✅ `cmd/clear_cache` broker hint to force baseline refresh, with 5-min TTL fallback
* ✅ Updates `devices.last_seen` on every metrics batch

#### Observability
* ✅ `GET /api/health` — liveness probe
* ✅ `GET /api/ready` — readiness probe with DB connectivity check
* ✅ Structured logging configuration shared across Flask + ingestor

---

### 1.2 Frontend (React + Vite)

#### Authentication UI
* ✅ Signup, Login, Logout pages
* ✅ Username, email, and password validation (with policy)
* ✅ `AuthProvider` with JWT token decoding (user / role / org from claims)
* ✅ Tokens stored in `localStorage`
* ✅ Protected routes via `ProtectedRoute` wrapper
* ✅ Axios interceptor: automatic refresh on 401, queues concurrent requests during refresh
* ✅ Change-password flow in Settings

#### App Structure & Pages
* ✅ React Router with `AppLayout` shell
* ✅ Dashboard — user info + at-a-glance health
* ✅ Assets page — CRUD + baseline management
* ✅ Sensors page — device list, rename, delete, link to asset
* ✅ Maintenance page — ticket board, create / assign / transition
* ✅ Reports page — reliability + alert-resolution views, CSV/Excel export
* ✅ Settings page

#### Components
* ✅ Device provisioning UI (SLPT issuance flow)
* ✅ Asset provisioning UI
* ✅ Vibration spectrum chart (FFT)
* ✅ Health trend chart (RMS / condition score over time)
* ✅ Alerts dashboard
* ✅ Create-ticket modal (with optional event linkage)

---

### 1.3 ESP32 Firmware (`ESP_CODE/vibration_sensor_v1.0/`)

#### Provisioning & Lifecycle
* ✅ Starts as **AP** with captive portal on first boot (no creds in NVS)
* ✅ Serves HTML form for WiFi SSID/password + org + asset_id + SLPT
* ✅ Switches to **station** mode and connects to WiFi
* ✅ Exchanges SLPT for MQTT credentials via `POST /api/devices/activate`
* ✅ Persists WiFi creds, MQTT creds, asset/org in NVS (`presense_v1` namespace)
* ✅ Long-press of BOOT button (≥5 s) wipes NVS and reboots into provisioning mode
* ✅ Status LED patterns for AP / connecting / streaming states
* ✅ Versioned firmware (`FW_VERSION 1.0.0`)

#### Telemetry
* ✅ MPU-6500 via SPI at 200 Hz
* ✅ Publishes batched accelerometer frames over MQTT (TLS-ready Mosquitto)
* ✅ Topic pattern: `presense/{org}/{asset_id}/{device_mac}/data`

---

### 1.4 MQTT Broker
* ✅ Self-hosted **Eclipse Mosquitto** (Docker Compose service)
* ✅ TCP on 1883, WebSocket on 9001
* ✅ Replaces HiveMQ free tier (which blocked API-driven device provisioning)
* ✅ Volume-mounted config + persistent data/log directories

---

### 1.5 Testing
* ✅ Pytest suite under `backend/tests/` — `test_auth_api.py`, `test_db.py`, `test_logic.py`, `conftest.py`
* ✅ Integration / verification scripts under `tests/` — `verify_baselines.py`, `test_ingestion.py`, `test_scope.py`, `test_auth.py`

---

## Features to Add

### 2.1 Backend / ML
* 🟥 Collect or curate labelled vibration dataset for DL model training
* 🟥 Train and integrate a fault-classification model (beyond rule-based FFT diagnosis)
* 🟥 Online/incremental baseline updates (currently calibrated on demand)
* 🟥 Per-asset threshold tuning + manager-facing tuning UI
* 🟥 Webhook / email notifications on critical events

### 2.2 Frontend
* 🟥 Company / organization entity management (managers create + invite users)
* 🟥 Asset sharing across an organization with per-asset permissions
* 🟥 Mobile-friendly responsive layout pass
* 🟥 Real-time push (WebSocket) for live spectrum + alerts instead of polling

### 2.3 ESP32 Firmware
* 🟥 OTA firmware updates
* 🟥 TLS to broker with per-device certificates
* 🟥 Local buffering when broker is unreachable (replay on reconnect)
* 🟥 Self-test / IMU health diagnostic on boot

### 2.4 MQTT / Infrastructure
* 🟥 Mosquitto ACLs per `org` so a device can only publish to its own subtree
* 🟥 Dynamic broker user provisioning (currently password is stored in `devices.mqtt_password`; needs broker-side sync)
* 🟥 Production deployment manifests (Compose → k8s or systemd)
* 🟥 Redis-backed rate-limit storage (`RATE_LIMIT_STORAGE_URI`) for multi-worker deployments
