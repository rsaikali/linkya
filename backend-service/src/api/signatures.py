"""Signature endpoints — list/delete/export direct DB; create/import via nilm."""

import csv
import logging
from datetime import datetime
from io import StringIO

import httpx
from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import Response

from ..config import settings
from ..db import db_manager
from ..events import bus
from ..models import SignatureCreate


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/signatures", tags=["Signatures"])

_TIMEOUT = 30.0


async def _nilm_add_signature(appliance_name, start_time, end_time, is_negative, auto_train=True):
    """Ask the nilm service to compute + store a signature."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(
            f"{settings.nilm_url}/signatures",
            json={
                "appliance_name": appliance_name,
                "start_time": start_time,
                "end_time": end_time,
                "is_negative": is_negative,
                "auto_train": auto_train,
            },
        )
        r.raise_for_status()
        return r.json()


@router.get("")
async def get_all_signatures():
    signatures = db_manager.get_all_signatures_with_appliance()
    return {"total": len(signatures), "signatures": signatures}


@router.post("")
async def create_signature(signature: SignatureCreate):
    try:
        result = await _nilm_add_signature(
            signature.appliance_name, signature.start_time, signature.end_time, False
        )
    except httpx.HTTPError as e:
        logger.error("nilm add signature failed: %s", e)
        raise HTTPException(status_code=502, detail="Service NILM injoignable")

    bus.publish("signature_added", {"appliance_name": signature.appliance_name})
    return {"status": "success", "appliance_name": signature.appliance_name, **result}


@router.delete("")
async def delete_all_signatures():
    result = db_manager.delete_all_signatures()
    bus.publish("signatures_cleared", {"count": result["signatures_deleted"]})
    return {"status": "success", "signatures_deleted": result["signatures_deleted"]}


@router.delete("/{signature_id}")
async def delete_signature(signature_id: int):
    result = db_manager.delete_signature(signature_id)
    if not result:
        raise HTTPException(status_code=404, detail="Signature non trouvée")
    bus.publish("signature_deleted", {"id": signature_id})
    return {"status": "success", "signature": result}


@router.get("/export")
async def export_signatures():
    signatures = db_manager.get_all_signatures_with_appliance()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["appliance_name", "start_time", "end_time", "is_negative"])
    for sig in signatures:
        writer.writerow([sig["appliance_name"], sig["start_time"], sig["end_time"], sig.get("is_negative", False)])
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="linkya_signatures_{timestamp}.csv"'},
    )


@router.post("/import")
async def import_signatures(file: UploadFile):
    """Replace all signatures with the CSV content. Each row is sent to nilm."""
    content = (await file.read()).decode("utf-8")
    reader = csv.DictReader(StringIO(content))
    required = {"appliance_name", "start_time", "end_time"}
    if not required.issubset(reader.fieldnames or []):
        raise HTTPException(status_code=422, detail=f"Colonnes requises: {', '.join(required)}")

    # Capture existing IDs before any mutation. Old signatures are deleted only
    # after a successful import so nilm-service failure mid-import doesn't wipe them.
    existing = db_manager.get_all_signatures_with_appliance()
    old_ids = [s["id"] for s in existing]

    bus.publish("import_start", {"filename": file.filename})

    success, errors = 0, []
    rows = list(reader)
    for line_num, row in enumerate(rows, start=2):
        try:
            name = row["appliance_name"].strip()
            start = row["start_time"].strip()
            end = row["end_time"].strip()
            is_neg = row.get("is_negative", "False").strip().lower() in ("true", "1", "yes", "oui")
            if not name:
                raise ValueError("nom vide")
            if datetime.fromisoformat(start) > datetime.fromisoformat(end):
                raise ValueError("start_time >= end_time")
            # auto_train=False: avoid one training per row; train once at the end.
            await _nilm_add_signature(name, start, end, is_neg, auto_train=False)
            success += 1
            if success % 5 == 0:
                total = len(rows)
                bus.publish("import_progress", {
                    "done": success,
                    "total": total,
                    "total_lines": total,
                    "success_count": success,
                    "error_count": len(errors),
                    "progress_percent": round(success / total * 100),
                })
        except Exception as e:
            errors.append({"line": line_num, "error": str(e)})

    # Only replace old signatures if at least one new one was stored successfully.
    deleted = {"signatures_deleted": 0}
    if success > 0:
        deleted = db_manager.delete_signatures_by_ids(old_ids)
        # Single training after the whole import (coalesced on the nilm side too).
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                await client.post(f"{settings.nilm_url}/train")
        except httpx.HTTPError as e:
            logger.warning("post-import train trigger failed: %s", e)

    total_rows = len(rows)
    bus.publish("import_complete", {
        "success": success,
        "errors": len(errors),
        "total_lines": total_rows,
        "success_count": success,
        "error_count": len(errors),
    })
    return {
        "status": "completed",
        "signatures_deleted": deleted["signatures_deleted"],
        "success_count": success,
        "error_count": len(errors),
        "errors": errors,
    }
