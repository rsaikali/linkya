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


def energy_entity_id(ha_entity_id: str) -> str:
    """Full HA entity_id for the energy sensor — used in statistics API."""
    return f"sensor.{slug(ha_entity_id)}_energy"


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
