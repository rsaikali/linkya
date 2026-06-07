"""ha-publish: NILM detections → HA energy + numeric history + confidence sensors + lab stats."""

import asyncio
import json

import aiomqtt
from loguru import logger

from .config import settings
from .database import repo
from .discovery import (
    STATS_SENSORS,
    STATS_STATE_TOPIC,
    binary_discovery_topic,
    confidence_discovery_payload,
    confidence_discovery_topic,
    confidence_state_topic,
    energy_discovery_payload,
    energy_discovery_topic,
    energy_state_topic,
    numeric_state_discovery_payload,
    numeric_state_discovery_topic,
    numeric_state_topic,
    stats_discovery_payload,
    stats_discovery_topic,
)


RECONNECT_DELAY = 10


async def publish_loop(client: aiomqtt.Client):
    """
    Every poll_interval seconds, per appliance with ha_publish=True:
    - discovery (energy + numeric history + confidence) once,
    - energy kWh (total_increasing, monotonic via high-water-mark),
    - confidence of last detection,
    - numeric state fixed at 0 (history via recorder.import_statistics only).
    Plus lab-diagnostic stats sensors on the Linkya NILM device.
    """
    known: set[str] = set()   # ha_entity_ids with discovery already published
    stats_announced = False   # lab-diagnostic sensors discovery published once
    binary_cleared = False    # legacy binary_sensor retained topics cleared once

    while True:
        # ── One-time cleanup: remove legacy binary_sensor retained topics ─────
        if not binary_cleared:
            for appliance in repo.get_active_appliances():
                await client.publish(
                    binary_discovery_topic(appliance["ha_entity_id"]),
                    payload="",
                    retain=True,
                )
            binary_cleared = True
            logger.info("Legacy binary_sensor discovery topics cleared")
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
            # Drop null keys so HA shows 'unknown' instead of the string "None".
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
                    energy_discovery_topic(eid),
                    payload=energy_discovery_payload(name, eid),
                    retain=True,
                )
                await client.publish(
                    confidence_discovery_topic(eid),
                    payload=confidence_discovery_payload(name, eid),
                    retain=True,
                )
                await client.publish(
                    numeric_state_discovery_topic(eid),
                    payload=numeric_state_discovery_payload(name, eid),
                    retain=True,
                )
                logger.info(f"Discovery published: {eid} (energy + confidence + numeric)")
                known.add(eid)

        # ── Remove discovery for disabled appliances ──────────────────────
        for eid in known - active_ids:
            await client.publish(energy_discovery_topic(eid), payload="", retain=True)
            await client.publish(confidence_discovery_topic(eid), payload="", retain=True)
            await client.publish(numeric_state_discovery_topic(eid), payload="", retain=True)
            logger.info(f"Discovery removed: {eid}")
        known &= active_ids

        # ── Live state per active appliance ───────────────────────────────
        paused = repo.is_publish_paused()
        if paused:
            logger.info("ha-publish: experiment mode ON — energy frozen")

        for appliance in active:
            eid = appliance["ha_entity_id"]
            if paused:
                # Freeze energy at the current HWM — do NOT update it while the user
                # is experimenting with signatures/detect cycles.  This prevents
                # artificial detections from inflating the HA Energy Dashboard.
                energy_kwh = repo.get_frozen_energy_kwh(appliance["id"])
            else:
                energy_kwh = repo.get_monotonic_energy_kwh(appliance["id"])
            await client.publish(energy_state_topic(eid), payload=str(energy_kwh))
            await client.publish(numeric_state_topic(eid), payload="0")
            conf = repo.get_last_confidence(appliance["id"])
            if conf is not None:
                await client.publish(confidence_state_topic(eid), payload=str(conf))
            logger.debug(f"{eid} | {energy_kwh} kWh | conf={conf}%{' (frozen)' if paused else ''}")

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
