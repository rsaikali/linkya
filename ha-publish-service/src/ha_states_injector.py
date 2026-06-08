"""Inject NILM detection cycles into HA SQLite states.

Energy sensors: per-minute cumulative ramps (total_increasing, no daily reset).
Binary sensors: exact ON/OFF transitions.

Requires HA_SQLITE_PATH pointing to home-assistant_v2.db (mounted volume).
Silently disabled when variable is empty or file absent.
"""

import json
import sqlite3
from datetime import timezone
from pathlib import Path

from loguru import logger

from .database import repo
from .discovery import slug as make_slug


def _to_ts(dt) -> float:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


class HAStatesInjector:
    def __init__(self, sqlite_path: str):
        self.path = sqlite_path
        self.synced = False
        self._uid_to_eid: dict[str, str] = {}
        self._meta: dict[str, int] = {}
        self._has_last_reported: bool | None = None
        self._last_id: dict[int, int] = {}

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

    # ── Entity registry ───────────────────────────────────────────────────

    def _load_entity_registry(self):
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

    # ── Low-level state row insertion ─────────────────────────────────────

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

    # ── Energy injection ──────────────────────────────────────────────────

    def _inject_energy_segment(
        self,
        conn,
        meta_id: int,
        start_ts: float,
        end_ts: float,
        kwh_before: float,
        kwh_after: float,
    ):
        """Per-minute ramp from kwh_before to kwh_after. Caller handles DELETE."""
        seg_dur = max(end_ts - start_ts, 1.0)
        rows = []
        t = start_ts
        while t <= end_ts + 0.5:
            frac = min(1.0, (t - start_ts) / seg_dur)
            val = str(round(kwh_before + frac * (kwh_after - kwh_before), 4))
            if self._has_last_reported:
                rows.append((meta_id, val, t, t, t, None))
            else:
                rows.append((meta_id, val, t, t, None))
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

    def _inject_energy_full(self, conn, meta_id: int, detections: list[dict]):
        """Full wipe then reinsert cumulative ramp across all detections."""
        conn.execute("DELETE FROM states WHERE metadata_id = ?", (meta_id,))
        cum_kwh = 0.0
        for det in detections:
            kwh = det["energy_wh"] / 1000.0
            start_ts = _to_ts(det["start_time"])
            end_ts = _to_ts(det["end_time"])
            self._inject_energy_segment(conn, meta_id, start_ts, end_ts, cum_kwh, cum_kwh + kwh)
            cum_kwh += kwh

    def _inject_energy_incremental(
        self,
        conn,
        meta_id: int,
        appliance_id: int,
        new_dets: list[dict],
    ):
        """Inject new detections. Uses Postgres cumulative before each det to avoid stacking."""
        for det in new_dets:
            kwh = det["energy_wh"] / 1000.0
            start_ts = _to_ts(det["start_time"])
            end_ts = _to_ts(det["end_time"])

            # Query Postgres directly — handles re-detection (old det deleted, new id)
            # without reading back from SQLite (which would stack on re-runs).
            kwh_before = repo.get_cumulative_energy_before_id(appliance_id, det["id"]) / 1000.0
            kwh_after = kwh_before + kwh

            conn.execute(
                "DELETE FROM states WHERE metadata_id = ? "
                "AND last_changed_ts >= ? AND last_changed_ts <= ?",
                (meta_id, start_ts, end_ts),
            )
            self._inject_energy_segment(conn, meta_id, start_ts, end_ts, kwh_before, kwh_after)

    # ── Binary injection ──────────────────────────────────────────────────

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

    # ── Public API ────────────────────────────────────────────────────────

    def full_resync(self):
        """Inject all detections for all active appliances.
        Retried every poll until HA entity registry has all expected entries.
        Energy states are fully wiped and rewritten — corrects any stale data.
        """
        self._load_entity_registry()

        all_ready = True
        for appliance in repo.get_active_appliances():
            aid = appliance["id"]
            sl = make_slug(appliance["ha_entity_id"])

            energy_uid = f"linkya_{sl}_energy"
            binary_uid = f"linkya_{sl}_state"
            energy_eid = self._eid(energy_uid)
            binary_eid = self._eid(binary_uid)

            if not energy_eid or not binary_eid:
                logger.debug(
                    f"{sl}: entity registry not ready "
                    f"(energy={'ok' if energy_eid else 'missing'}, "
                    f"binary={'ok' if binary_eid else 'missing'}) — retry next poll"
                )
                all_ready = False
                continue

            energy_meta = self._metadata_id(energy_eid)
            binary_meta = self._metadata_id(binary_eid)

            if not energy_meta or not binary_meta:
                logger.debug(
                    f"{sl}: states_meta not ready "
                    f"(energy={'ok' if energy_meta else 'missing'}, "
                    f"binary={'ok' if binary_meta else 'missing'}) — retry next poll"
                )
                all_ready = False
                continue

            detections = repo.get_all_detections_ordered(aid)
            try:
                with self._conn() as conn:
                    self._detect_schema(conn)
                    self._inject_binary_full(conn, binary_meta, detections)
                    self._inject_energy_full(conn, energy_meta, detections)
            except sqlite3.OperationalError as e:
                logger.warning(f"HA SQLite locked ({sl}): {e} — will retry next poll")
                all_ready = False
                continue

            if detections:
                self._last_id[aid] = max(d["id"] for d in detections)
            logger.info(f"{sl}: full resync — {len(detections)} cycles injected")

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

        last_seen = self._last_id.get(aid, 0)
        new_dets = repo.get_detections_since_id(aid, last_seen)
        if not new_dets:
            return

        try:
            with self._conn() as conn:
                self._detect_schema(conn)
                if energy_meta and energy_eid:
                    self._inject_energy_incremental(conn, energy_meta, aid, new_dets)
                if binary_meta:
                    for det in new_dets:
                        self._inject_binary_cycle(
                            conn, binary_meta,
                            _to_ts(det["start_time"]),
                            _to_ts(det["end_time"]),
                        )
        except sqlite3.OperationalError as e:
            logger.warning(f"HA SQLite locked ({sl}): {e} — will retry next poll")
            return

        self._last_id[aid] = max(d["id"] for d in new_dets)
        logger.info(f"{sl}: incremental — {len(new_dets)} new cycles injected")
