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

# Energy is NOT a live MQTT sensor (a batch NILM sum is non-monotonic and would
# trip total_increasing's reset logic). Instead it's a long-term EXTERNAL
# statistic pushed via recorder/import_statistics, placed at real consumption
# time. statistic_id uses the "linkya:" external source prefix (colon form).

EXTERNAL_SOURCE = "linkya"


def external_stat_id(ha_entity_id: str) -> str:
    """External statistic id, e.g. linkya:nilm_ballon_d_eau_chaude_energy."""
    return f"{EXTERNAL_SOURCE}:{slug(ha_entity_id)}_energy"


# ── Lab diagnostics (one shared JSON state topic, value_template per sensor) ──

STATS_STATE_TOPIC = f"{STATE_PREFIX}/_stats/state"

# (json_key, friendly name, extra discovery opts)
STATS_SENSORS = [
    ("model_version", "NILM Modèle", {"icon": "mdi:tag"}),
    ("model_type", "NILM Architecture", {"icon": "mdi:chip"}),
    ("trained_at", "NILM Entraîné le", {"device_class": "timestamp"}),
    ("train_duration_s", "NILM Durée entraînement", {"unit_of_measurement": "s", "device_class": "duration", "icon": "mdi:timer"}),
    ("num_signatures", "NILM Signatures", {"icon": "mdi:draw"}),
    ("num_appliances", "NILM Appareils", {"icon": "mdi:home-lightning-bolt"}),
    ("epochs", "NILM Epochs", {"icon": "mdi:counter"}),
    ("train_loss", "NILM Train loss", {"icon": "mdi:chart-line"}),
    ("val_loss", "NILM Val loss", {"icon": "mdi:chart-line"}),
    ("detections_total", "NILM Détections total", {"icon": "mdi:magnify"}),
    ("last_detection", "NILM Dernière détection", {"device_class": "timestamp"}),
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
