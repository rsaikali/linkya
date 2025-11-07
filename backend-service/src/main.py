"""Main FastAPI backend for Linkya."""

from .app import create_app

# Create the FastAPI application instance
app = create_app()
