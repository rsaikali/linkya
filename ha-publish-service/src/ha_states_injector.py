"""Inject NILM detection cycles into HA SQLite states.

Energy sensors: per-minute cumulative ramps (total_increasing, no daily reset).
Binary sensors: exact ON/OFF transitions.

Requires HA_SQLITE_PATH pointing to home-assistant_v2.db (mounted volume).
Silently disabled when variable is empty or file absent.

Safe concurrent writes: all writes go through _upsert_rows() which does a
SELECT for existing timestamps, then UPDATE in-place for matches and INSERT
for new rows.  No DELETE anywhere — avoids the SQLAlchemy StaleDataError
caused by HA's periodic bulk UPDATE on last_reported_ts: HA always finds its
rows by primary key because we never remove them.
"""

import json
import sqlite3
import time
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

    # ── Core UPSERT — never DELETEs ───────────────────────────────────────

    def _upsert_rows(self, conn, meta_id: int, points: list[tuple[float, str]]):
        """Write (ts, state) pairs as UPDATE-then-INSERT.

        All linkya-injected rows have attributes_id IS NULL (no HA attributes
        blob needed).  Scoping every query to attributes_id IS NULL ensures we
        never touch HA-native rows for the same entity, and the row primary key
        is never changed — HA's SQLAlchemy bulk UPDATE on last_reported_ts
        always finds its rows.
        """
        if not points:
            return

        ts_min = points[0][0]
        ts_max = points[-1][0]

        existing_ts = {
            row[0]
            for row in conn.execute(
                "SELECT last_changed_ts FROM states "
                "WHERE metadata_id=? AND attributes_id IS NULL "
                "AND last_changed_ts >= ? AND last_changed_ts <= ?",
                (meta_id, ts_min - 0.5, ts_max + 0.5),
            )
        }

        if self._has_last_reported:
            to_update = [
                (val, ts, ts, meta_id, ts)
                for ts, val in points if ts in existing_ts
            ]
            to_insert = [
                (meta_id, val, ts, ts, ts)
                for ts, val in points if ts not in existing_ts
            ]
            if to_update:
                conn.executemany(
                    "UPDATE states "
                    "SET state=?, last_updated_ts=?, last_reported_ts=? "
                    "WHERE metadata_id=? AND last_changed_ts=? AND attributes_id IS NULL",
                    to_update,
                )
            if to_insert:
                conn.executemany(
                    "INSERT INTO states (metadata_id, state, last_changed_ts, "
                    "last_updated_ts, last_reported_ts, attributes_id) "
                    "VALUES (?,?,?,?,?,NULL)",
                    to_insert,
                )
        else:
            to_update = [
                (val, ts, meta_id, ts)
                for ts, val in points if ts in existing_ts
            ]
            to_insert = [
                (meta_id, val, ts, ts)
                for ts, val in points if ts not in existing_ts
            ]
            if to_update:
                conn.executemany(
                    "UPDATE states SET state=?, last_updated_ts=? "
                    "WHERE metadata_id=? AND last_changed_ts=? AND attributes_id IS NULL",
                    to_update,
                )
            if to_insert:
                conn.executemany(
                    "INSERT INTO states (metadata_id, state, last_changed_ts, "
                    "last_updated_ts, attributes_id) VALUES (?,?,?,?,NULL)",
                    to_insert,
                )

    # ── Energy injection ──────────────────────────────────────────────────

    def _energy_points(
        self,
        start_ts: float,
        end_ts: float,
        kwh_before: float,
        kwh_after: float,
    ) -> list[tuple[float, str]]:
        """Per-minute ramp from kwh_before to kwh_after (pure computation)."""
        seg_dur = max(end_ts - start_ts, 1.0)
        points = []
        t = start_ts
        while t <= end_ts + 0.5:
            frac = min(1.0, (t - start_ts) / seg_dur)
            val = str(round(kwh_before + frac * (kwh_after - kwh_before), 4))
            points.append((t, val))
            t += 60.0
        return points

    def _inject_energy_full(self, conn, meta_id: int, detections: list[dict]):
        """Upsert cumulative ramp across all detections (no wipe)."""
        cum_kwh = 0.0
        for det in detections:
            kwh = det["energy_wh"] / 1000.0
            start_ts = _to_ts(det["start_time"])
            end_ts = _to_ts(det["end_time"])
            points = self._energy_points(start_ts, end_ts, cum_kwh, cum_kwh + kwh)
            self._upsert_rows(conn, meta_id, points)
            cum_kwh += kwh

    def _inject_energy_incremental(self, conn, meta_id: int, new_dets: list[dict]):
        """Upsert new detections continuing from last known SQLite state.

        Baseline is read from SQLite (linkya rows only, attributes_id IS NULL)
        rather than Postgres so a full NILM re-detect — which wipes Postgres
        detection IDs — doesn't reset the cumulative sum to zero.
        """
        for det in new_dets:
            kwh = det["energy_wh"] / 1000.0
            start_ts = _to_ts(det["start_time"])
            end_ts = _to_ts(det["end_time"])

            row = conn.execute(
                "SELECT state FROM states "
                "WHERE metadata_id=? AND attributes_id IS NULL "
                "AND last_changed_ts < ? "
                "ORDER BY last_changed_ts DESC LIMIT 1",
                (meta_id, start_ts),
            ).fetchone()
            try:
                kwh_before = float(row[0]) if row else 0.0
            except (TypeError, ValueError):
                kwh_before = 0.0

            points = self._energy_points(start_ts, end_ts, kwh_before, kwh_before + kwh)
            self._upsert_rows(conn, meta_id, points)

    # ── Binary injection ──────────────────────────────────────────────────

    def _inject_binary_full(self, conn, meta_id, detections):
        if not detections:
            return
        first_ts = _to_ts(detections[0]["start_time"])
        points = [(first_ts - 60, "off")]
        for det in detections:
            points.append((_to_ts(det["start_time"]), "on"))
            points.append((_to_ts(det["end_time"]), "off"))
        self._upsert_rows(conn, meta_id, points)

    def _inject_binary_cycle(self, conn, meta_id, start_ts, end_ts):
        self._upsert_rows(conn, meta_id, [(start_ts, "on"), (end_ts, "off")])

    # ── Public API ────────────────────────────────────────────────────────

    def full_resync(self):
        """Upsert all detections for all active appliances.
        Retried every poll until HA entity registry has all expected entries.
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
        """Upsert new detections since last seen — called every poll."""
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

        # Full re-detect: NILM wiped all IDs and re-created the full history.
        # New detections span more than 3h back → trigger full_resync to
        # recompute the cumulative baseline from scratch.
        if len(new_dets) > 5 and time.time() - _to_ts(new_dets[0]["start_time"]) > 3 * 3600:
            logger.info(
                f"{sl}: full re-detect detected ({len(new_dets)} cycles spanning history)"
                " — triggering full resync"
            )
            self.synced = False
            self._last_id.pop(aid, None)
            return

        try:
            with self._conn() as conn:
                self._detect_schema(conn)
                if energy_meta and energy_eid:
                    self._inject_energy_incremental(conn, energy_meta, new_dets)
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
