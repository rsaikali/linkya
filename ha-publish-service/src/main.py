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
    stats_discovery_payload,
    stats_discovery_topic,
)
from .ha_backfill import backfill_appliance


# Re-import energy statistics every N cycles so fresh detections land in HA at
# real consumption time (idempotent upsert). 10 × poll_interval (30s) = 5 min.
_STATS_REIMPORT_EVERY = 10


RECONNECT_DELAY = 10


async def publish_loop(client: aiomqtt.Client):
    """
    Every poll_interval seconds:
    1. Publish lab-diagnostic stats sensors.
    2. Discovery for newly enabled appliances (binary_sensor only).
    3. Live binary ON/OFF per active appliance.
    4. Periodically re-import energy statistics (external stat, real conso time).

    Energy is an external long-term statistic (import_statistics), not a live
    MQTT sensor — a batch NILM sum is non-monotonic and would break
    total_increasing. Initial import on first toggle, then every ~5 min.
    """
    known: set[str] = set()   # ha_entity_ids with discovery already published
    stats_announced = False   # lab-diagnostic sensors discovery published once
    cycle = 0

    while True:
        cycle += 1
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
                # Binary sensor (live ON/OFF). Energy is an external statistic,
                # not an MQTT sensor — see ha_backfill.
                await client.publish(
                    binary_discovery_topic(eid),
                    payload=binary_discovery_payload(name, eid),
                    retain=True,
                )
                logger.info(f"Discovery published: {eid} (binary)")
                known.add(eid)
                await asyncio.sleep(2)
                await backfill_appliance(appliance)   # initial energy import

        # ── Remove discovery for disabled appliances ──────────────────────
        for eid in known - active_ids:
            await client.publish(binary_discovery_topic(eid), payload="", retain=True)
            logger.info(f"Discovery removed: {eid}")
        known &= active_ids

        # ── Live binary state for all active appliances ───────────────────
        for appliance in active:
            eid = appliance["ha_entity_id"]
            is_active = repo.is_currently_active(appliance["id"])
            await client.publish(binary_state_topic(eid), payload="ON" if is_active else "OFF")
            logger.debug(f"{eid} → {'ON' if is_active else 'OFF'}")

        # ── Periodic energy stats re-import (real consumption time) ────────
        if active and cycle % _STATS_REIMPORT_EVERY == 0:
            for appliance in active:
                await backfill_appliance(appliance)

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
