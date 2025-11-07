"""WebSocket route handlers."""

import logging

from fastapi import WebSocket, WebSocketDisconnect

from .consumption import consumption_updates_manager
from .detections import detection_updates_manager
from .import_progress import import_progress_manager
from .training import training_logs_manager


logger = logging.getLogger(__name__)


async def websocket_training_logs(websocket: WebSocket):
    """
    WebSocket endpoint for real-time training logs.

    Clients connect to this endpoint to receive live updates during model training.
    Events include: training_start, epoch_start, epoch_end, batch_update, training_complete.
    """
    await training_logs_manager.connect(websocket)
    try:
        while True:
            try:
                data = await websocket.receive_text()
                logger.debug(f"Received from client: {data}")
            except Exception as recv_error:
                logger.debug(f"Receive error (client may have closed): {recv_error}")
                break
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
        training_logs_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        training_logs_manager.disconnect(websocket)


async def websocket_consumption_updates(websocket: WebSocket):
    """
    WebSocket endpoint for real-time consumption data updates.

    Clients connect to receive live consumption data as it arrives from sync-service.
    Events include: new_consumption with latest PAPP, temperature, counters.
    """
    await consumption_updates_manager.connect(websocket)
    try:
        while True:
            try:
                data = await websocket.receive_text()
                logger.debug(f"Received from consumption client: {data}")
            except Exception as recv_error:
                logger.debug(f"Consumption receive error: {recv_error}")
                break
    except WebSocketDisconnect:
        logger.info("Consumption WebSocket client disconnected")
        consumption_updates_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Consumption WebSocket error: {e}")
        consumption_updates_manager.disconnect(websocket)


async def websocket_detection_updates(websocket: WebSocket):
    """
    WebSocket endpoint for real-time detection updates.

    Clients connect to receive live NILM detection results as they are created.
    Events include: new_detection with appliance, timing, power, confidence.
    """
    await detection_updates_manager.connect(websocket)
    try:
        while True:
            try:
                data = await websocket.receive_text()
                logger.debug(f"Received from detection client: {data}")
            except Exception as recv_error:
                logger.debug(f"Detection receive error: {recv_error}")
                break
    except WebSocketDisconnect:
        logger.info("Detection WebSocket client disconnected")
        detection_updates_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Detection WebSocket error: {e}")
        detection_updates_manager.disconnect(websocket)


async def websocket_import_progress(websocket: WebSocket):
    """
    WebSocket endpoint for real-time import progress updates.

    Clients connect to receive live progress during CSV signature import.
    Events include: import_start, import_progress, import_complete.
    """
    await import_progress_manager.connect(websocket)
    try:
        while True:
            try:
                data = await websocket.receive_text()
                logger.debug(f"Received from import client: {data}")
            except Exception as recv_error:
                logger.debug(f"Import receive error: {recv_error}")
                break
    except WebSocketDisconnect:
        logger.info("Import WebSocket client disconnected")
        import_progress_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Import WebSocket error: {e}")
        import_progress_manager.disconnect(websocket)
