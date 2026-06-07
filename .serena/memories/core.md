# Linkya — Core

NILM platform (Non-Intrusive Load Monitoring). Detects appliances (water heater, dryer, oven…) from the aggregate Linky meter curve. Published as native HA sensors via MQTT discovery. Production on Raspberry Pi.

## Source map

```
linkya/
├── backend-service/src/        FastAPI REST + SSE bus + React SPA serving
│   ├── app.py                  create_app()
│   ├── main.py                 entrypoint
│   ├── events.py               in-memory SSE bus
│   ├── config.py
│   ├── api/                    routers: appliances, consumption, detections, events, nilm, signatures, system
│   ├── db/                     SQLAlchemy layer: appliances, consumption, detections, signatures, models, manager
│   └── models.py               Pydantic schemas
├── nilm-service/src/           TF/Keras Seq2Point engine + FastAPI
│   ├── main.py
│   ├── jobs.py                 run_training, run_detection, add_signature, delete_models, promote_model
│   │                           request_training/request_detection → coalescing (1 pending max)
│   ├── seq2point_nilm.py       Seq2PointNILMManager: train_all_appliances, disaggregate
│   └── nilm/                   detectors/change_point_detector.py, models/multioutput_model.py,
│                               callbacks, layers, losses, morphology, preprocessing, utils
├── ha-ingest-service/src/      asyncio + aiomqtt + httpx
│   ├── main.py                 mqtt_loop, main
│   ├── ha_client.py            HA History API backfill
│   └── database.py
├── ha-publish-service/src/     asyncio + aiomqtt
│   ├── main.py                 publish_loop, run
│   ├── discovery.py            MQTT discovery payloads
│   ├── ha_states_injector.py   SQLite direct injection for HA history slopes
│   └── database.py
├── frontend-service/src/       React SPA (French locale)
│   ├── App.js
│   ├── components/             AppliancesList, DetectionsList, SignaturesList, Charts, ModelCard…
│   ├── context/                DataContext, ApplianceColorsContext, NotificationContext
│   └── services/               api.js, sse.js
├── docker-compose.yml          PROD (no override)
├── docker-compose.override.yml DEV (auto-loaded locally)
├── Makefile
├── pyproject.toml              isort + black config (root, covers all services)
└── .env / .env.example         single source of truth for config
```

## Project-wide invariants

- No broker, no TimescaleDB, no nginx in the stack.
- Backend serves React build AND the single `GET /api/events` SSE endpoint (no WebSocket).
- nilm-service is internal-only; backend proxies to it via HTTP (`NILM_URL=http://nilm:8001`).
- nilm-service fires HTTP callbacks → backend `POST /internal/event` for live UI updates.
- PostgreSQL is the only DB (pure SQL DDL, no ORM migrations — `make clean && make up` resets schema).
- ha-publish mounts HA SQLite at `/ha_db` for direct state injection (enables history slopes in HA panel).
- Backend binds to LAN IP (`BACKEND_BIND`), never `0.0.0.0`.
- TF variant per arch: `tensorflow-cpu` on x86_64, `tensorflow` on aarch64.
- Coalescing in jobs.py: max 1 training + 1 detection pending — bursts collapse into one.

See `mem:tech_stack` for versions/deps, `mem:conventions` for code rules, `mem:suggested_commands` for dev/prod commands, `mem:task_completion` for pre-commit checklist.
