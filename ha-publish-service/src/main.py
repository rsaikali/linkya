"""ha-publish: NILM detections → HA energy + confidence sensors + lab stats."""

import asyncio
import json
import os

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
    energy_discovery_payload,
    energy_discovery_topic,
    energy_state_topic,
    numeric_state_discovery_topic,
    stats_discovery_payload,
    stats_discovery_topic,
)


RECONNECT_DELAY = 10

_states_injector = None

if settings.ha_sqlite_path:
    if os.path.exists(settings.ha_sqlite_path):
        try:
            from .ha_states_injector import HAStatesInjector
            _states_injector = HAStatesInjector(settings.ha_sqlite_path)
            logger.info(f"HA states injector enabled: {settings.ha_sqlite_path}")
        except Exception as e:
            logger.error(f"Failed to init HA states injector: {e}")
    else:
        logger.warning(f"HA_SQLITE_PATH set but file not found: {settings.ha_sqlite_path}")


async def publish_loop(client: aiomqtt.Client):
    """
    Every poll_interval seconds, per appliance with ha_publish=True:
    - discovery (energy + confidence) once,
    - energy kWh (total_increasing, monotonic via high-water-mark),
    - confidence of last detection.
    Plus lab-diagnostic stats sensors on the Linkya NILM device.

    Historical energy backfill is handled by the backend service via WebSocket
    (recorder/import_statistics) after each full detection run.
    """
    known: set[str] = set()   # ha_entity_ids with discovery already published
    stats_announced = False   # lab-diagnostic sensors discovery published once
    legacy_cleared = False    # legacy retained topics cleared once

    while True:
        # ── One-time cleanup: remove legacy numeric_state retained topic ──
        if not legacy_cleared:
            for appliance in repo.get_active_appliances():
                eid = appliance["ha_entity_id"]
                await client.publish(numeric_state_discovery_topic(eid), payload="", retain=True)
            legacy_cleared = True
            logger.info("Legacy numeric_state discovery topics cleared")

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
                    energy_discovery_topic(eid),
                    payload=energy_discovery_payload(name, eid),
                    retain=True,
                )
                await client.publish(
                    confidence_discovery_topic(eid),
                    payload=confidence_discovery_payload(name, eid),
                    retain=True,
                )
                logger.info(f"Discovery published: {eid} (binary + energy + confidence)")
                known.add(eid)

        # ── Remove discovery for disabled appliances ──────────────────────
        for eid in known - active_ids:
            await client.publish(binary_discovery_topic(eid), payload="", retain=True)
            await client.publish(energy_discovery_topic(eid), payload="", retain=True)
            await client.publish(confidence_discovery_topic(eid), payload="", retain=True)
            logger.info(f"Discovery removed: {eid}")
        known &= active_ids

        # ── Live state per active appliance ───────────────────────────────
        for appliance in active:
            eid = appliance["ha_entity_id"]
            energy_kwh = repo.get_cumulative_energy_kwh(appliance["id"])
            is_on = repo.is_currently_active(appliance["id"])
            await client.publish(binary_state_topic(eid), payload="on" if is_on else "off")
            await client.publish(energy_state_topic(eid), payload=str(energy_kwh))
            conf = repo.get_last_confidence(appliance["id"])
            if conf is not None:
                await client.publish(confidence_state_topic(eid), payload=str(conf))
            logger.debug(f"{eid} | {'ON' if is_on else 'off'} | {energy_kwh} kWh total | conf={conf}%")

        # ── HA SQLite states injection (minute-level history) ─────────────
        if _states_injector is not None:
            loop = asyncio.get_running_loop()
            if not _states_injector.synced:
                await loop.run_in_executor(None, _states_injector.full_resync)
            else:
                for appliance in active:
                    await loop.run_in_executor(
                        None, _states_injector.incremental, appliance
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
