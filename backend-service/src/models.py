"""Pydantic models for API request/response validation."""

from pydantic import BaseModel


class SignatureCreate(BaseModel):
    """Model for creating a new appliance signature."""

    appliance_name: str | None = None
    start_time: str | None = None  # ISO format
    end_time: str | None = None  # ISO format


class HaPublishUpdate(BaseModel):
    """Toggle HA publishing for an appliance."""

    enabled: bool


class ApplianceUpdate(BaseModel):
    """Update appliance name."""

    name: str
