"""FastAPI application factory and configuration."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import appliances_router, consumption_router, detections_router, nilm_router, signatures_router, system_router
from .config import settings
from .websockets.routes import websocket_consumption_updates, websocket_detection_updates, websocket_import_progress, websocket_training_logs

# Logging configuration
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance
    """
    app = FastAPI(title=settings.api_title, version=settings.api_version, description=settings.api_description, docs_url="/docs", redoc_url="/redoc", openapi_url="/openapi.json")

    # CORS configuration to allow requests from the frontend
    # Note: WebSocket connections bypass CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins (safe for WebSocket + public API)
        allow_credentials=False,  # Must be False when allow_origins=["*"]
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API routers
    app.include_router(system_router)
    app.include_router(consumption_router)
    app.include_router(appliances_router)
    app.include_router(signatures_router)
    app.include_router(detections_router)
    app.include_router(nilm_router)

    # Register WebSocket routes
    app.websocket("/ws/training")(websocket_training_logs)
    app.websocket("/ws/consumption")(websocket_consumption_updates)
    app.websocket("/ws/detections")(websocket_detection_updates)
    app.websocket("/ws/import")(websocket_import_progress)

    logger.info("FastAPI application configured successfully")

    return app
