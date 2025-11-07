"""Pydantic models for API request/response validation."""

from pydantic import BaseModel


class SignatureCreate(BaseModel):
    """Model for creating a new appliance signature."""

    appliance_name: str | None = None
    start_time: str | None = None  # ISO format
    end_time: str | None = None  # ISO format
