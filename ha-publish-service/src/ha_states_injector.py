"""Inject NILM detection cycles into HA SQLite states as per-minute energy ramps
and exact ON/OFF binary transitions.

Entity_ids are resolved from HA's entity registry JSON by unique_id (which we
control via MQTT discovery payloads) — never computed from a slug pattern, since
HA may assign arbitrary entity_ids depending on name collisions, areas, etc.

Requires HA_SQLITE_PATH pointing to home-assistant_v2.db (mounted volume).
Feature is silently disabled when the variable is empty or the file is absent.
"""

import json
import sqlite3
from datetime import timezone
from pathlib import Path

from loguru import logger

from .database import repo
from .discovery import slug as make_slug


class HAStatesInjector:
    def __init__(self, sqlite_path: str):
        self.path = sqlite_path
        self.synced = False
        self._uid_to_eid: dict[str, str] = {}         # unique_id → real HA entity_id
        self._meta: dict[str, int] = {}               # entity_id → metadata_id (positive only)
        self._attrs: dict[str, int | None] = {}       # entity_id → attributes_id
        self._has_last_reported: bool | None = None

    # ── SQLite helpers ────────────────────────────────────────────────────

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _detect_schema(self, conn: sqlite3.Connection):
        if self._has_last_reported is not None:
            return
        cols = {r[1] for r in conn.execute("PRAGMA table_info(states)")}
        self._has_last_reported = "last_reported_ts" in cols

    # ── Entity registry (unique_id → real entity_id) ──────────────────────

    def _load_entity_registry(self):
        """Read HA entity registry JSON and build unique_id → entity_id map."""
        reg_path = Path(self.path).parent / ".storage" / "core.entity_registry"
        try:
            with open(reg_path) as f:
                reg = json.load(f)
            self._uid_to_eid = {
                e["unique_id"]: e["entity_id"]
                for e in reg["data"]["entities"]
                if "unique_id" in e and "entity_id" in e
            }
            logger.debug(f"Entity registry loaded: {len(self._uid_to_eid)} entries")
        except Exception as e:
            logger.warning(f"Could not read HA entity registry: {e}")

    def _eid(self, unique_id: str) -> str | None:
        return self._uid_to_eid.get(unique_id)

    # ── states_meta lookup ────────────────────────────────────────────────

    def _metadata_id(self, entity_id: str) -> int | None:
        """Only cache positive hits — None forces a re-query next call."""
        if entity_id in self._meta:
            return self._meta[entity_id]
        with self._conn() as conn:
            row = conn.execute(
                "SELECT metadata_id FROM states_meta WHERE entity_id = ?",
                (entity_id,),
            ).fetchone()
        if row:
            self._meta[entity_id] = row[0]
            return row[0]
        return None

    def _attributes_id(self, entity_id: str, metadata_id: int) -> int | None:
        if entity_id in self._attrs:
            return self._attrs[entity_id]
        with self._conn() as conn:
            row = conn.execute(
                "SELECT attributes_id FROM states "
                "WHERE metadata_id = ? AND attributes_id IS NOT NULL "
                "ORDER BY last_updated_ts DESC LIMIT 1",
                (metadata_id,),
            ).fetchone()
        result = row[0] if row else None
        self._attrs[entity_id] = result
        return result

    # ── Core state insertion ──────────────────────────────────────────────

    def _insert_state(self, conn, metadata_id, state, ts, attrs_id=None):
        if self._has_last_reported:
            conn.execute(
                "INSERT INTO states (metadata_id, state, last_changed_ts, "
                "last_updated_ts, last_reported_ts, attributes_id) VALUES (?,?,?,?,?,?)",
                (metadata_id, state, ts, ts, ts, attrs_id),
            )
        else:
            conn.execute(
                "INSERT INTO states (metadata_id, state, last_changed_ts, "
                "last_updated_ts, attributes_id) VALUES (?,?,?,?,?)",
                (metadata_id, state, ts, ts, attrs_id),
            )

    # ── Energy injection (per-minute ramp) ───────────────────────────────

    def _inject_energy_cycle(self, conn, meta_id, attrs_id, start_ts, end_ts, kwh_before, kwh_after):
        conn.execute(
            "DELETE FROM states WHERE metadata_id = ? "
            "AND last_changed_ts >= ? AND last_changed_ts <= ?",
            (meta_id, start_ts, end_ts),
        )
        duration = max(end_ts - start_ts, 1.0)
        t = start_ts
        rows = []
        while t <= end_ts + 0.5:
            frac = min(1.0, (t - start_ts) / duration)
            val = str(round(kwh_before + frac * (kwh_after - kwh_before), 4))
            if self._has_last_reported:
                rows.append((meta_id, val, t, t, t, attrs_id))
            else:
                rows.append((meta_id, val, t, t, attrs_id))
            t += 60.0
        if self._has_last_reported:
            conn.executemany(
                "INSERT INTO states (metadata_id, state, last_changed_ts, "
                "last_updated_ts, last_reported_ts, attributes_id) VALUES (?,?,?,?,?,?)",
                rows,
            )
        else:
            conn.executemany(
                "INSERT INTO states (metadata_id, state, last_changed_ts, "
                "last_updated_ts, attributes_id) VALUES (?,?,?,?,?)",
                rows,
            )

    # ── Binary injection (on/off) ─────────────────────────────────────────

    def _inject_binary_full(self, conn, meta_id, detections):
        if not detections:
            return
        first_ts = _to_ts(detections[0]["start_time"])
        conn.execute(
            "DELETE FROM states WHERE metadata_id = ? AND last_changed_ts >= ?",
            (meta_id, first_ts - 120),
        )
        self._insert_state(conn, meta_id, "off", first_ts - 60)
        for det in detections:
            self._insert_state(conn, meta_id, "on", _to_ts(det["start_time"]))
            self._insert_state(conn, meta_id, "off", _to_ts(det["end_time"]))

    def _inject_binary_cycle(self, conn, meta_id, start_ts, end_ts):
        conn.execute(
            "DELETE FROM states WHERE metadata_id = ? "
            "AND last_changed_ts >= ? AND last_changed_ts <= ?",
            (meta_id, start_ts - 60, end_ts + 1),
        )
        self._insert_state(conn, meta_id, "on", start_ts)
        self._insert_state(conn, meta_id, "off", end_ts)

    # ── Per-appliance processing ──────────────────────────────────────────

    def _process(
        self,
        label: str,
        detections: list[dict],
        baseline_kwh: float,
        cum_start: float,
        energy_meta: int | None,
        attrs_id: int | None,
        binary_meta: int | None,
        full_binary: bool,
    ) -> int:
        cum = cum_start
        injected = 0
        try:
            with self._conn() as conn:
                self._detect_schema(conn)
                if binary_meta and full_binary:
                    self._inject_binary_full(conn, binary_meta, detections)
                for det in detections:
                    kwh = det["energy_wh"] / 1000.0
                    start_ts = _to_ts(det["start_time"])
                    end_ts = _to_ts(det["end_time"])
                    if energy_meta is not None:
                        self._inject_energy_cycle(
                            conn, energy_meta, attrs_id, start_ts, end_ts,
                            max(0.0, cum - baseline_kwh),
                            max(0.0, cum + kwh - baseline_kwh),
                        )
                    if binary_meta is not None and not full_binary:
                        self._inject_binary_cycle(conn, binary_meta, start_ts, end_ts)
                    cum += kwh
                    injected += 1
        except sqlite3.OperationalError as e:
            logger.warning(f"HA SQLite locked ({label}): {e} — will retry next poll")
            return 0

        if injected:
            parts = []
            if energy_meta:
                parts.append(f"{round(max(0.0, cum - baseline_kwh), 3)} kWh")
            if binary_meta:
                parts.append("ON/OFF")
            logger.info(f"{label}: injected {injected} cycles — {', '.join(parts)}")
        return injected

    # ── Public API ────────────────────────────────────────────────────────

    def full_resync(self):
        """Inject all detections for all active appliances.
        Retried every poll until HA's entity registry has all expected entries."""
        self._load_entity_registry()

        all_ready = True
        for appliance in repo.get_active_appliances():
            aid = appliance["id"]
            sl = make_slug(appliance["ha_entity_id"])
            label = sl

            energy_uid = f"linkya_{sl}_energy"
            binary_uid = f"linkya_{sl}_state"
            energy_eid = self._eid(energy_uid)
            binary_eid = self._eid(binary_uid)

            if not energy_eid or not binary_eid:
                logger.debug(
                    f"{label}: entity registry not ready "
                    f"(energy={'ok' if energy_eid else 'missing'}, "
                    f"binary={'ok' if binary_eid else 'missing'}) — retry next poll"
                )
                all_ready = False
                continue

            energy_meta = self._metadata_id(energy_eid)
            binary_meta = self._metadata_id(binary_eid)

            if not energy_meta or not binary_meta:
                logger.debug(
                    f"{label}: states_meta not ready "
                    f"(energy={'ok' if energy_meta else 'missing'}, "
                    f"binary={'ok' if binary_meta else 'missing'}) — retry next poll"
                )
                all_ready = False
                continue

            baseline = repo.get_energy_baseline_kwh(aid)
            if baseline is None:
                logger.debug(f"{label}: HWM baseline not set — retry next poll")
                all_ready = False
                continue

            attrs_id = self._attributes_id(energy_eid, energy_meta)
            detections = repo.get_all_detections_ordered(aid)
            self._process(label, detections, baseline, 0.0, energy_meta, attrs_id, binary_meta, True)
            if detections:
                self._last_id[aid] = max(d["id"] for d in detections)

        if all_ready:
            self.synced = True
            logger.info("HA states injector: full resync complete")

    def incremental(self, appliance: dict):
        """Inject new detections since last seen — called every poll."""
        aid = appliance["id"]
        sl = make_slug(appliance["ha_entity_id"])

        energy_eid = self._eid(f"linkya_{sl}_energy")
        binary_eid = self._eid(f"linkya_{sl}_state")
        energy_meta = self._metadata_id(energy_eid) if energy_eid else None
        binary_meta = self._metadata_id(binary_eid) if binary_eid else None

        if not energy_meta and not binary_meta:
            return

        baseline = repo.get_energy_baseline_kwh(aid)
        if baseline is None:
            return

        last_seen = self._last_id.get(aid, 0)
        new_dets = repo.get_detections_since_id(aid, last_seen)
        if not new_dets:
            return

        cum_before = repo.get_cumulative_energy_before_id(aid, new_dets[0]["id"])
        attrs_id = self._attributes_id(energy_eid, energy_meta) if energy_meta and energy_eid else None
        self._process(sl, new_dets, baseline, cum_before, energy_meta, attrs_id, binary_meta, False)
        self._last_id[aid] = max(d["id"] for d in new_dets)

def _to_ts(dt) -> float:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()
