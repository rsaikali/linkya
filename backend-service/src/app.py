"""FastAPI application factory."""

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import appliances_router, consumption_router, detections_router, events_router, nilm_router, signatures_router, system_router
from .config import settings


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.api_title,
        version=settings.api_version,
        description=settings.api_description,
    )

    # Same-origin in prod (nginx-less: backend serves the SPA). CORS open for dev.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(system_router)
    app.include_router(consumption_router)
    app.include_router(appliances_router)
    app.include_router(signatures_router)
    app.include_router(detections_router)
    app.include_router(nilm_router)
    app.include_router(events_router)

    # Serve the React production build if present (prod image). The SPA fallback
    # sends index.html for any non-API path so client-side routing works.
    static_dir = settings.static_dir
    if os.path.isdir(static_dir):
        app.mount("/static", StaticFiles(directory=os.path.join(static_dir, "static")), name="assets")

        @app.get("/{full_path:path}")
        async def spa(full_path: str):
            candidate = os.path.join(static_dir, full_path)
            if full_path and os.path.isfile(candidate):
                return FileResponse(candidate)
            return FileResponse(os.path.join(static_dir, "index.html"))

        logger.info("Serving React build from %s", static_dir)
    else:
        logger.info("No static dir (%s) — API-only mode (dev)", static_dir)

    logger.info("FastAPI application configured")
    return app
