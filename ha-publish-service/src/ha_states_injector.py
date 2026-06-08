"""Inject NILM detection cycles into HA SQLite states.

Energy sensors: per-minute ramps with daily reset at UTC midnight.
  - state_class: total, last_reset attribute updated per-day.
  - Detections crossing midnight are split proportionally.
Binary sensors: exact ON/OFF transitions.

Requires HA_SQLITE_PATH pointing to home-assistant_v2.db (mounted volume).
Silently disabled when variable is empty or file absent.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from .database import repo
from .discovery import slug as make_slug


_ENERGY_BASE_ATTRS = {
    "unit_of_measurement": "kWh",
    "device_class": "energy",
    "state_class": "total",
}


def _fnv1a_32(data: str) -> int:
    """FNV-1a 32-bit — matches HA state_attributes dedup hash."""
    h = 0x811C9DC5
    for b in data.encode("utf-8"):
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def _day_midnight_ts(ts: float) -> float:
    """UTC midnight (float) for the calendar day containing ts."""
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc).timestamp()


def _to_ts(dt) -> float:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _split_by_midnight(start_ts: float, end_ts: float, total_kwh: float):
    """Yield (seg_start, seg_end, seg_kwh, day_midnight_ts) splitting at UTC midnights."""
    duration = max(end_ts - start_ts, 1.0)
    seg_start = start_ts
    while seg_start < end_ts:
        day_midnight = _day_midnight_ts(seg_start)
        seg_end = min(end_ts, day_midnight + 86400.0)
        frac_start = (seg_start - start_ts) / duration
        frac_end = min(1.0, (seg_end - start_ts) / duration)
        seg_kwh = total_kwh * (frac_end - frac_start)
        yield seg_start, seg_end, seg_kwh, day_midnight
        seg_start = seg_end


class HAStatesInjector:
    def __init__(self, sqlite_path: str):
        self.path = sqlite_path
        self.synced = False
        self._uid_to_eid: dict[str, str] = {}
        self._meta: dict[str, int] = {}
        self._has_last_reported: bool | None = None
        self._last_id: dict[int, int] = {}
        # entity_id → {day_midnight_ts → attributes_id}
        self._attrs_by_day: dict[str, dict[float, int]] = {}

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

    # ── Attrs management (per-day last_reset) ─────────────────────────────

    def _attrs_id_for_day(self, conn, entity_id: str, day_midnight_ts: float) -> int | None:
        """Find or create a state_attributes row for this day's last_reset."""
        cache = self._attrs_by_day.setdefault(entity_id, {})
        if day_midnight_ts in cache:
            return cache[day_midnight_ts]

        last_reset = datetime.fromtimestamp(day_midnight_ts, tz=timezone.utc).isoformat()
        attrs = {**_ENERGY_BASE_ATTRS, "last_reset": last_reset}
        attrs_json = json.dumps(attrs, sort_keys=True, separators=(",", ":"))
        h = _fnv1a_32(attrs_json)

        row = conn.execute(
            "SELECT attributes_id FROM state_attributes WHERE hash = ?", (h,)
        ).fetchone()
        if row:
            attrs_id = row[0]
        else:
            conn.execute(
                "INSERT INTO state_attributes (hash, shared_attrs) VALUES (?, ?)",
                (h, attrs_json),
            )
            attrs_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        cache[day_midnight_ts] = attrs_id
        return attrs_id

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
        entity_id: str,
        seg_start: float,
        seg_end: float,
        kwh_before: float,
        kwh_after: float,
        day_midnight: float,
    ):
        """Minute-by-minute ramp for one day segment. Caller handles DELETE."""
        attrs_id = self._attrs_id_for_day(conn, entity_id, day_midnight)
        seg_dur = max(seg_end - seg_start, 1.0)
        rows = []
        t = seg_start
        while t <= seg_end + 0.5:
            frac = min(1.0, (t - seg_start) / seg_dur)
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

    def _inject_energy_full(
        self, conn, meta_id: int, entity_id: str, detections: list[dict]
    ):
        """Full wipe then reinsert all detections with daily reset."""
        conn.execute("DELETE FROM states WHERE metadata_id = ?", (meta_id,))
        day_cum: dict[float, float] = {}
        for det in detections:
            kwh_total = det["energy_wh"] / 1000.0
            start_ts = _to_ts(det["start_time"])
            end_ts = _to_ts(det["end_time"])
            for seg_start, seg_end, seg_kwh, day_midnight in _split_by_midnight(
                start_ts, end_ts, kwh_total
            ):
                kwh_before = day_cum.get(day_midnight, 0.0)
                kwh_after = kwh_before + seg_kwh
                day_cum[day_midnight] = kwh_after
                self._inject_energy_segment(
                    conn, meta_id, entity_id,
                    seg_start, seg_end, kwh_before, kwh_after, day_midnight,
                )

    def _inject_energy_incremental(
        self,
        conn,
        meta_id: int,
        entity_id: str,
        new_dets: list[dict],
    ):
        """Inject new detections, reading back last state per day for continuation."""
        day_cum: dict[float, float] = {}
        for det in new_dets:
            kwh_total = det["energy_wh"] / 1000.0
            start_ts = _to_ts(det["start_time"])
            end_ts = _to_ts(det["end_time"])
            for seg_start, seg_end, seg_kwh, day_midnight in _split_by_midnight(
                start_ts, end_ts, kwh_total
            ):
                if day_midnight not in day_cum:
                    # Read accumulated kWh BEFORE this segment starts.
                    # Using seg_start (not end-of-day) ensures a re-detected window
                    # (same time range, new DB id) starts from the correct baseline
                    # instead of stacking on top of its own previous injection.
                    row = conn.execute(
                        "SELECT state FROM states WHERE metadata_id = ? "
                        "AND last_changed_ts >= ? AND last_changed_ts < ? "
                        "ORDER BY last_changed_ts DESC LIMIT 1",
                        (meta_id, day_midnight, seg_start),
                    ).fetchone()
                    try:
                        day_cum[day_midnight] = float(row[0]) if row else 0.0
                    except (TypeError, ValueError):
                        day_cum[day_midnight] = 0.0

                kwh_before = day_cum[day_midnight]
                kwh_after = kwh_before + seg_kwh
                day_cum[day_midnight] = kwh_after

                conn.execute(
                    "DELETE FROM states WHERE metadata_id = ? "
                    "AND last_changed_ts >= ? AND last_changed_ts <= ?",
                    (meta_id, seg_start, seg_end),
                )
                self._inject_energy_segment(
                    conn, meta_id, entity_id,
                    seg_start, seg_end, kwh_before, kwh_after, day_midnight,
                )

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
                    self._inject_energy_full(conn, energy_meta, energy_eid, detections)
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
                    self._inject_energy_incremental(conn, energy_meta, energy_eid, new_dets)
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
