# Linkya — NILM for Home Assistant

**Linkya** detects appliances that don't have a smart plug — water heater, dryer, oven — from your Linky smart meter's aggregate power curve, and pushes them to Home Assistant as native sensors.

**Story**: you already have HA with smart plugs for most devices. But some big consumers (water heater, 2000-3500 W) have no plug. Linkya fills the gap: draw a few signatures on the power curve, train a model, detect cycles, see them in HA like any other device.

---

## What you need

- **Home Assistant** with the Linky integration exposing `sensor.linky_sinsts` (or equivalent VA sensor)
- **Mosquitto add-on** in HA with `mqtt_statestream` enabled
- **Docker + Docker Compose** on a machine that can reach HA (same LAN)
- A Linky smart meter (France)

---

## Quick start

### 1 — Prerequisites in HA

**Enable `mqtt_statestream`** in `configuration.yaml`:

```yaml
mqtt_statestream:
  base_topic: statestream
  publish_attributes: false
```

**Create a long-lived access token**: HA → Profile → Security → Long-lived access tokens.

**Get your Mosquitto credentials**: HA Settings → Add-ons → Mosquitto → Configuration → note a user/password.

### 2 — Configure

```bash
git clone https://github.com/YOUR_USER/linkya
cd linkya
cp .env.example .env
```

Edit `.env` with your values:

```env
HA_URL=http://homeassistant.local:8123
HA_TOKEN=<your long-lived token>
HA_ENTITY_PAPP=sensor.linky_sinsts   # adjust to your entity name
HA_MQTT_HOST=homeassistant.local
HA_MQTT_PORT=1883
HA_MQTT_USER=homeassistant
HA_MQTT_PASSWORD=<your mqtt password>
```

### 3 — Start

```bash
make build
make up
make status   # all 10 services should be Up
```

Open **http://localhost** (or your machine's IP).

---

## How to use

### Annotate signatures

1. Open Linkya UI → **Consommation** tab
2. The power curve of the last 30 days loads automatically (backfilled from HA history)
3. Select a time range when you know the appliance was running (e.g. water heater ON)
4. Give it a name → **Créer signature**
5. Repeat for 5-10 cycles per appliance — the more varied, the better

### Train

After adding signatures, training triggers automatically (every 5th positive signature). You can also click **Entraîner** manually.

### Detect

Detection runs automatically every 5 minutes on the last 2 hours. Click **Détecter** to run on the full history.

### Publish to HA

In the **Appareils** tab, toggle **Home Assistant** for any appliance you trust. Linkya will:
1. Create two entities in HA via MQTT discovery:
   - `binary_sensor.nilm_{appliance}` — ON when a cycle is in progress
   - `sensor.nilm_{appliance}_energy` — cumulative kWh (shows in Energy Dashboard)
2. Import historical detections into HA's statistics (Energy Dashboard history)

### Validate detections

In the **Détections** tab, mark detections as correct (✓) or incorrect (✗).
- ✓ adds a positive signature → strengthens the model
- ✗ adds a negative signature → prevents similar false positives in future

---

## Architecture

```
HA (sensor.linky_sinsts)
  ├── mqtt_statestream → ha-ingest → TimescaleDB (real-time)
  └── History API → ha-ingest → TimescaleDB (30d backfill at startup)

TimescaleDB → nilm-worker (Seq2Point GRU) → nilm_detections

nilm_detections → ha-publish → HA MQTT
  ├── binary_sensor.nilm_* (ON/OFF)
  └── sensor.nilm_*_energy (kWh, Energy Dashboard)

React UI → FastAPI → TimescaleDB
```

Services: `timescaledb`, `redis`, `ha-ingest`, `nilm-worker`, `nilm-beat`, `backend`, `react-dev`, `frontend`, `ha-publish`, `pgweb`

---

## Services ports

| Service | URL | Purpose |
|---------|-----|---------|
| Frontend | http://localhost | Main UI |
| API docs | http://localhost/docs | Swagger |
| pgweb | http://localhost:8081 | DB explorer |
| Backend | http://localhost:8001 | API (internal) |

---

## Common commands

```bash
make build          # Build all images
make up             # Start all services
make down           # Stop
make clean          # Stop + delete volumes (resets all data)
make status         # Container status
make logs           # All logs
make train          # Trigger training manually
make detect         # Trigger detection on full history
```

---

## NILM model

Seq2Point multi-output GRU with attention (TensorFlow/Keras). Trained on user-annotated signatures from the aggregate Linky curve. Detection via change-point detection + pattern matching (energy, duration, power shape). Negative signature feedback loop to reduce false positives over time.

Works well for: water heater, dryer, EV charger, oven (high-power, clear on/off pattern).
Harder to detect: fridge (low power, concurrent), heat pump (variable).

---

## Environment variables

See `.env.example` for the full list with comments. Required:

| Variable | Description |
|---|---|
| `HA_URL` | Home Assistant base URL |
| `HA_TOKEN` | Long-lived access token |
| `HA_ENTITY_PAPP` | Linky power sensor entity_id |
| `HA_MQTT_HOST` | Mosquitto broker hostname |
| `HA_MQTT_USER/PASSWORD` | Mosquitto credentials |

---

## License

MIT
