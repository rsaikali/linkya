"""MQTT discovery payloads for HA — two entities per NILM appliance."""

import json
import re


DISCOVERY_PREFIX = "homeassistant"
STATE_PREFIX = "linkya/nilm"

_DEVICE = {
    "identifiers": ["linkya_nilm"],
    "name": "Linkya NILM",
    "model": "Seq2Point",
    "manufacturer": "Linkya",
}


def slug(ha_entity_id: str) -> str:
    """
    Extract object_id, sanitize to valid HA slug (a-z, 0-9, _ only).
    sensor.nilm_ballon_d'eau_chaude → nilm_ballon_d_eau_chaude
    """
    s = ha_entity_id.replace("sensor.", "").replace("binary_sensor.", "")
    s = re.sub(r"[^a-z0-9_]", "_", s.lower())
    s = re.sub(r"_+", "_", s)
    return s.strip("_")


# ── Binary sensor (ON/OFF cycle en cours) ────────────────────────────────────

def binary_discovery_topic(ha_entity_id: str) -> str:
    return f"{DISCOVERY_PREFIX}/binary_sensor/{slug(ha_entity_id)}/config"


def binary_state_topic(ha_entity_id: str) -> str:
    return f"{STATE_PREFIX}/{slug(ha_entity_id)}/binary_state"


def binary_discovery_payload(name: str, ha_entity_id: str) -> str:
    return json.dumps({
        "name": f"NILM {name}",
        "unique_id": f"linkya_{slug(ha_entity_id)}_binary",
        "state_topic": binary_state_topic(ha_entity_id),
        "payload_on": "ON",
        "payload_off": "OFF",
        "device_class": "running",
        "icon": "mdi:home-lightning-bolt",
        "device": _DEVICE,
    })


# ── Energy sensor (kWh cumulatif, total_increasing) ──────────────────────────

def energy_discovery_topic(ha_entity_id: str) -> str:
    return f"{DISCOVERY_PREFIX}/sensor/{slug(ha_entity_id)}_energy/config"


def energy_state_topic(ha_entity_id: str) -> str:
    return f"{STATE_PREFIX}/{slug(ha_entity_id)}/energy_state"


def energy_discovery_payload(name: str, ha_entity_id: str) -> str:
    return json.dumps({
        "name": f"NILM {name} Énergie",
        "unique_id": f"linkya_{slug(ha_entity_id)}_energy",
        "state_topic": energy_state_topic(ha_entity_id),
        "unit_of_measurement": "kWh",
        "device_class": "energy",
        "state_class": "total_increasing",
        "icon": "mdi:lightning-bolt",
        "device": _DEVICE,
    })


# ── Confidence sensor per appliance (last detection) ─────────────────────────

def confidence_discovery_topic(ha_entity_id: str) -> str:
    return f"{DISCOVERY_PREFIX}/sensor/{slug(ha_entity_id)}_confidence/config"


def confidence_state_topic(ha_entity_id: str) -> str:
    return f"{STATE_PREFIX}/{slug(ha_entity_id)}/confidence_state"


def confidence_discovery_payload(name: str, ha_entity_id: str) -> str:
    return json.dumps({
        "name": f"NILM {name} Confiance",
        "unique_id": f"linkya_{slug(ha_entity_id)}_confidence",
        "state_topic": confidence_state_topic(ha_entity_id),
        "unit_of_measurement": "%",
        "state_class": "measurement",
        "icon": "mdi:percent",
        "device": _DEVICE,
    })


# ── Lab diagnostics (one shared JSON state topic, value_template per sensor) ──

STATS_STATE_TOPIC = f"{STATE_PREFIX}/_stats/state"

# (json_key, friendly name, extra discovery opts)
# numeric sensors must have state_class so HA plots them as numbers, not text.
STATS_SENSORS = [
    ("model_version", "NILM Modèle", {"icon": "mdi:tag"}),
    ("model_type", "NILM Architecture", {"icon": "mdi:chip"}),
    ("trained_at", "NILM Entraîné le", {"device_class": "timestamp"}),
    ("train_duration_s", "NILM Durée entraînement", {
        "unit_of_measurement": "s", "device_class": "duration",
        "state_class": "measurement", "icon": "mdi:timer",
    }),
    ("num_signatures", "NILM Signatures", {
        "unit_of_measurement": "", "state_class": "measurement", "icon": "mdi:draw",
    }),
    ("num_appliances", "NILM Appareils", {
        "unit_of_measurement": "", "state_class": "measurement", "icon": "mdi:home-lightning-bolt",
    }),
    ("epochs", "NILM Epochs", {
        "unit_of_measurement": "", "state_class": "measurement", "icon": "mdi:counter",
    }),
    ("train_loss", "NILM Train loss", {
        "unit_of_measurement": "", "state_class": "measurement", "icon": "mdi:chart-line",
    }),
    ("val_loss", "NILM Val loss", {
        "unit_of_measurement": "", "state_class": "measurement", "icon": "mdi:chart-line",
    }),
    ("avg_confidence_pct", "NILM Confiance détection (30j)", {
        "unit_of_measurement": "%", "state_class": "measurement", "icon": "mdi:percent",
    }),
    ("detections_total", "NILM Détections total", {
        "unit_of_measurement": "", "state_class": "total_increasing", "icon": "mdi:magnify",
    }),
    ("last_detection", "NILM Dernier cycle détecté", {"device_class": "timestamp"}),
    ("last_detect_run", "NILM Dernière exécution détection", {"device_class": "timestamp"}),
]


def stats_discovery_topic(key: str) -> str:
    return f"{DISCOVERY_PREFIX}/sensor/linkya_nilm_{key}/config"


def stats_discovery_payload(key: str, name: str, opts: dict) -> str:
    payload = {
        "name": name,
        "unique_id": f"linkya_nilm_{key}",
        "state_topic": STATS_STATE_TOPIC,
        "value_template": f"{{{{ value_json.{key} }}}}",
        "entity_category": "diagnostic",
        "device": _DEVICE,
        **opts,
    }
    return json.dumps(payload)
