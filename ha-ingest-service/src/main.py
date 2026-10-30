"""ha-ingest: HA MQTT listener + History API backfill → linky_realtime."""

import asyncio
from datetime import datetime, timezone

import aiomqtt
from loguru import logger

from .config import settings
from .database import db_manager
from .ha_client import backfill, sync_energy

RECONNECT_DELAY = 5  # seconds between MQTT reconnect attempts
ENERGY_SYNC_INTERVAL = 600  # seconds between pulls of the Linky energy index from HA


async def mqtt_loop():
    """Subscribe to statestream MQTT and insert papp values."""
    topic = settings.mqtt_topic_papp
    logger.info(f"MQTT: connecting to {settings.ha_mqtt_host}:{settings.ha_mqtt_port}")
    logger.info(f"MQTT: subscribing to {topic}")

    while True:
        try:
            async with aiomqtt.Client(
                hostname=settings.ha_mqtt_host,
                port=settings.ha_mqtt_port,
                username=settings.ha_mqtt_user,
                password=settings.ha_mqtt_password,
            ) as client:
                await client.subscribe(topic)
                logger.info("MQTT: connected and subscribed")

                async for message in client.messages:
                    payload = message.payload.decode().strip()
                    if payload in ("unavailable", "unknown", ""):
                        continue
                    try:
                        papp = int(float(payload))
                        ts = datetime.now(timezone.utc)
                        db_manager.insert_point(ts, papp)
                        logger.debug(f"papp={papp} VA")
                    except ValueError:
                        logger.warning(f"Non-numeric payload: {payload!r}")

        except aiomqtt.MqttError as e:
            logger.warning(f"MQTT disconnected: {e} — reconnecting in {RECONNECT_DELAY}s")
            await asyncio.sleep(RECONNECT_DELAY)
        except Exception as e:
            logger.error(f"MQTT unexpected error: {e} — reconnecting in {RECONNECT_DELAY}s")
            await asyncio.sleep(RECONNECT_DELAY)


async def energy_loop():
    """Keep linky_energy (Linky energy index) up to date; the index changes slowly, a periodic pull is enough."""
    while True:
        try:
            await sync_energy()
        except Exception as e:
            logger.warning(f"Energy sync failed: {e}")
        await asyncio.sleep(ENERGY_SYNC_INTERVAL)


async def main():
    logger.info("ha-ingest starting")

    db_manager.init_db()
    logger.info("DB initialized")

    await backfill()

    await asyncio.gather(mqtt_loop(), energy_loop())


if __name__ == "__main__":
    asyncio.run(main())
