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

In the **Appareils** tab, toggle **Home Assistant** for any appliance you trust. Linkya then exposes, on a `Linkya NILM` device:

- **`binary_sensor.nilm_{appliance}`** — ON while a cycle is running (live, via MQTT discovery). State history starts at toggle time (HA can't backfill past states).
- **Energy** — a HA **external statistic** `linkya:nilm_{appliance}_energy` (kWh), placed at the real consumption hour and idempotently re-imported. Add it under **Settings → Energy → add consumption** to compare it with a real smart plug. (It is not a live sensor: a batch NILM sum is non-monotonic and would break `total_increasing`.)
- **Diagnostic sensors** — model version, type, trained-at, train duration, signatures, epochs, train/val loss, detections total, last detection. No F1 (Linkya has no ground-truth labels).

### Validate detections

In the **Détections** tab, mark detections as correct (✓) or incorrect (✗).
- ✓ adds a positive signature → strengthens the model
- ✗ adds a negative signature → prevents similar false positives in future

---

## Architecture

Five services. No broker, no TimescaleDB, no nginx — the FastAPI backend serves
the React build and a single SSE stream for live UI updates.

```
HA (sensor.linky_sinsts)
  ├── MQTT statestream ─┐
  └── History API ──────┴─→ ha-ingest ─→ PostgreSQL (linky_realtime, 30d)

PostgreSQL ─→ nilm (Seq2Point GRU, FastAPI + APScheduler) ─→ nilm_detections

nilm_detections ─→ ha-publish ─→ HA MQTT discovery
                     ├── binary_sensor.nilm_*            (ON/OFF, live)
                     └── linkya:nilm_*_energy (kWh)   (external statistic, Energy Dashboard)

Browser ─→ backend (FastAPI: REST + SSE + React build) ─→ PostgreSQL
                     └── proxies train/detect/signatures → nilm
```

| Service | Stack | Role |
|---------|-------|------|
| `postgres` | PostgreSQL 16 | `linky_realtime` + NILM tables |
| `backend` | FastAPI | REST API, SSE bus, serves the React SPA |
| `nilm` | FastAPI + TensorFlow (CPU) | train / detect / signature processing + detect cron |
| `ha-ingest` | asyncio | HA MQTT statestream + History API backfill |
| `ha-publish` | asyncio | detections → HA MQTT discovery + statistics |

Live UI updates use one SSE endpoint (`GET /api/events`) — no WebSocket.

---

## Access

Production: the backend serves everything on one port. Behind a reverse proxy
(e.g. Nginx Proxy Manager) point a host at `backend:8000`. Dev: http://localhost:8000.

---

## Common commands

```bash
make up       # dev: start all services (docker-compose.override.yml)
make down     # stop
make clean    # stop + delete volumes (resets all data)
make status   # container status
make logs     # tail all logs
make train    # trigger training
make detect   # trigger detection on full history
make deploy   # prod build + restart (Pi / CD), skips the dev override
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
