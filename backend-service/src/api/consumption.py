"""Consumption data endpoints."""

import logging

from fastapi import APIRouter, HTTPException, Query

from ..db import db_manager


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/consumption", tags=["Consumption"])


@router.get("/latest")
async def get_latest_consumption():
    """
    Retrieves the latest energy consumption value.

    Returns:
        Latest measurement with timestamp, power, index, temperature
    """
    try:
        data = db_manager.get_latest_consumption()
        if not data:
            raise HTTPException(status_code=404, detail="Aucune donnée disponible")
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")


@router.get("/history")
async def get_consumption_history(
    interval=Query(
        default="auto",
        description="Aggregation interval (auto, raw, 1 minute, 5 minutes, 15 minutes, 1 hour)",
    )
):
    """
    Retrieves all consumption history data.

    Args:
        interval: Data aggregation interval (auto adapts to data range)

    Returns:
        List of consumption points aggregated by interval
    """
    try:
        # Get min/max timestamps from database
        all_data_range = db_manager.get_consumption_time_range()
        if not all_data_range:
            raise HTTPException(status_code=404, detail="Aucune donnée disponible")
        start_time_dt = all_data_range["min_time"]
        end_time_dt = all_data_range["max_time"]

        # Auto-determine optimal interval based on data range
        if interval == "auto":
            duration_hours = (end_time_dt - start_time_dt).total_seconds() / 3600
            if duration_hours <= 6:
                interval = "raw"
            elif duration_hours <= 24:
                interval = "1 minute"
            elif duration_hours <= 72:
                interval = "5 minutes"
            elif duration_hours <= 168:
                interval = "10 minutes"
            else:
                interval = "1 hour"

        data = db_manager.get_consumption_history(start_time_dt, end_time_dt, interval)
        if not data:
            raise HTTPException(status_code=404, detail="Aucune donnée disponible pour cette période")

        return {
            "start_time": start_time_dt.isoformat(),
            "end_time": end_time_dt.isoformat(),
            "interval": interval,
            "data_points": len(data),
            "data": data,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")
