"""ha-publish: NILM live state (binary + confidence) + lab stats via MQTT.

Energy is NOT published here. It goes through the backend as HA external
statistics (recorder/import_statistics, statistic_id "linkya:<slug>_energy")
after each detection run — the official way to write energy into the past.
"""

import asyncio
import json

import aiomqtt
from loguru import logger

from .config import settings
from .database import repo
from .discovery import (
    STATS_SENSORS,
    STATS_STATE_TOPIC,
    binary_discovery_payload,
    binary_discovery_topic,
    binary_state_topic,
    confidence_discovery_payload,
    confidence_discovery_topic,
    confidence_state_topic,
    energy_discovery_topic,
    numeric_state_discovery_topic,
    stats_discovery_payload,
    stats_discovery_topic,
)


RECONNECT_DELAY = 10


async def publish_loop(client: aiomqtt.Client):
    """
    Every poll_interval seconds, per appliance with ha_publish=True:
    - discovery (binary + confidence) once,
    - binary ON/OFF (cycle in progress),
    - confidence of last detection.
    Plus lab-diagnostic stats sensors on the Linkya NILM device.
    """
    known: set[str] = set()   # ha_entity_ids with discovery already published
    stats_announced = False   # lab-diagnostic sensors discovery published once
    legacy_cleared = False    # legacy retained topics cleared once

    while True:
        # ── One-time cleanup: remove legacy retained discovery topics ─────
        # (numeric_state sensor + MQTT energy sensor, both replaced).
        if not legacy_cleared:
            for appliance in repo.get_active_appliances():
                eid = appliance["ha_entity_id"]
                await client.publish(numeric_state_discovery_topic(eid), payload="", retain=True)
                await client.publish(energy_discovery_topic(eid), payload="", retain=True)
            legacy_cleared = True
            logger.info("Legacy retained discovery topics cleared (numeric_state + energy)")

        # ── Lab diagnostics (model + detection stats) ─────────────────────
        stats = repo.get_nilm_stats()
        if stats:
            if not stats_announced:
                for key, name, opts in STATS_SENSORS:
                    await client.publish(
                        stats_discovery_topic(key),
                        payload=stats_discovery_payload(key, name, opts),
                        retain=True,
                    )
                stats_announced = True
                logger.info("NILM stats sensors announced")
            clean = {k: v for k, v in stats.items() if v is not None}
            await client.publish(STATS_STATE_TOPIC, payload=json.dumps(clean), retain=True)

        active = repo.get_active_appliances()
        active_ids = {a["ha_entity_id"] for a in active}

        # ── Publish discovery for new appliances ──────────────────────────
        for appliance in active:
            eid = appliance["ha_entity_id"]
            name = appliance["name"]

            if eid not in known:
                await client.publish(
                    binary_discovery_topic(eid),
                    payload=binary_discovery_payload(name, eid),
                    retain=True,
                )
                await client.publish(
                    confidence_discovery_topic(eid),
                    payload=confidence_discovery_payload(name, eid),
                    retain=True,
                )
                logger.info(f"Discovery published: {eid} (binary + confidence)")
                known.add(eid)

        # ── Remove discovery for disabled appliances ──────────────────────
        for eid in known - active_ids:
            await client.publish(binary_discovery_topic(eid), payload="", retain=True)
            await client.publish(confidence_discovery_topic(eid), payload="", retain=True)
            logger.info(f"Discovery removed: {eid}")
        known &= active_ids

        # ── Live state per active appliance ───────────────────────────────
        for appliance in active:
            eid = appliance["ha_entity_id"]
            is_on = repo.is_currently_active(appliance["id"])
            await client.publish(binary_state_topic(eid), payload="on" if is_on else "off")
            conf = repo.get_last_confidence(appliance["id"])
            if conf is not None:
                await client.publish(confidence_state_topic(eid), payload=str(conf))
            logger.debug(f"{eid} | {'ON' if is_on else 'off'} | conf={conf}%")

        await asyncio.sleep(settings.poll_interval)


async def run():
    logger.info(
        f"ha-publish: connecting to {settings.ha_mqtt_host}:{settings.ha_mqtt_port}"
    )
    while True:
        try:
            async with aiomqtt.Client(
                hostname=settings.ha_mqtt_host,
                port=settings.ha_mqtt_port,
                username=settings.ha_mqtt_user,
                password=settings.ha_mqtt_password,
            ) as client:
                logger.info("ha-publish: MQTT connected")
                await publish_loop(client)
        except aiomqtt.MqttError as e:
            logger.warning(f"MQTT disconnected: {e} — retry in {RECONNECT_DELAY}s")
            await asyncio.sleep(RECONNECT_DELAY)
        except Exception as e:
            logger.error(f"Unexpected error: {e} — retry in {RECONNECT_DELAY}s")
            await asyncio.sleep(RECONNECT_DELAY)


if __name__ == "__main__":
    asyncio.run(run())
