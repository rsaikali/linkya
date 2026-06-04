"""ha-publish: NILM detections → HA binary_sensor + energy sensor + lab stats."""

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
    energy_discovery_payload,
    energy_discovery_topic,
    energy_state_topic,
    stats_discovery_payload,
    stats_discovery_topic,
)
from .ha_backfill import backfill_appliance


RECONNECT_DELAY = 10


async def publish_loop(client: aiomqtt.Client):
    """
    Every poll_interval seconds:
    1. Publish MQTT discovery for newly enabled appliances (both entities).
    2. Remove discovery for disabled appliances.
    3. Publish current binary state (ON/OFF) and cumulative energy (kWh).

    On first discovery of an appliance, trigger HA historical backfill.
    """
    known: set[str] = set()   # ha_entity_ids with discovery already published
    stats_announced = False   # lab-diagnostic sensors discovery published once

    while True:
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
                # Binary sensor
                await client.publish(
                    binary_discovery_topic(eid),
                    payload=binary_discovery_payload(name, eid),
                    retain=True,
                )
                # Energy sensor
                await client.publish(
                    energy_discovery_topic(eid),
                    payload=energy_discovery_payload(name, eid),
                    retain=True,
                )
                logger.info(f"Discovery published: {eid} (binary + energy)")
                known.add(eid)

                # Backfill historical detections into HA statistics
                # Small delay to let HA register the entity first
                await asyncio.sleep(2)
                await backfill_appliance(appliance)

        # ── Remove discovery for disabled appliances ──────────────────────
        for eid in known - active_ids:
            await client.publish(binary_discovery_topic(eid), payload="", retain=True)
            await client.publish(energy_discovery_topic(eid), payload="", retain=True)
            logger.info(f"Discovery removed: {eid}")
        known &= active_ids

        # ── Publish current state for all active appliances ───────────────
        for appliance in active:
            eid = appliance["ha_entity_id"]

            # Binary: ON only if a cycle is currently in progress
            is_active = repo.is_currently_active(appliance["id"])
            await client.publish(
                binary_state_topic(eid),
                payload="ON" if is_active else "OFF",
            )

            # Energy: cumulative kWh (total_increasing)
            energy_kwh = repo.get_cumulative_energy_kwh(appliance["id"])
            await client.publish(
                energy_state_topic(eid),
                payload=str(energy_kwh),
            )

            logger.debug(
                f"{eid} → {'ON' if is_active else 'OFF'} | {energy_kwh} kWh"
            )

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
