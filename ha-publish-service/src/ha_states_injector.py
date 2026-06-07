"""Inject NILM detection cycles into HA SQLite states as per-minute energy ramps.

Each detection cycle [start_time, end_time] becomes ~N minute-level state rows
for the energy sensor (sensor.nilm_<slug>_energy).  Values form a linear ramp
(slope) from the cumulative kWh just before the cycle to the cumulative kWh
just after — matching the baseline-adjusted scale that ha-publish sends via MQTT.

Existing HA states inside each cycle window are deleted first (idempotent).
The History panel in HA will then show slopes instead of flat-line + step.

Requires HA_SQLITE_PATH to be set to the HA database path (mounted volume).
Feature is silently disabled when the variable is empty or the file is absent.
"""

import sqlite3
from datetime import timezone

from loguru import logger

from .database import repo
from .discovery import slug as make_slug


class HAStatesInjector:
    def __init__(self, sqlite_path: str):
        self.path = sqlite_path
        self.synced = False                         # True after first full_resync completes
        self._meta: dict[str, int | None] = {}     # entity_id → metadata_id
        self._attrs: dict[str, int | None] = {}    # entity_id → attributes_id
        self._has_last_reported: bool | None = None
        self._last_id: dict[int, int] = {}         # appliance_id → last processed detection id

    # ── SQLite connection ─────────────────────────────────────────────────

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _detect_schema(self, conn: sqlite3.Connection):
        if self._has_last_reported is not None:
            return
        cols = {r[1] for r in conn.execute("PRAGMA table_info(states)")}
        self._has_last_reported = "last_reported_ts" in cols

    # ── HA metadata helpers ───────────────────────────────────────────────

    def _metadata_id(self, entity_id: str) -> int | None:
        if entity_id in self._meta:
            return self._meta[entity_id]
        with self._conn() as conn:
            row = conn.execute(
                "SELECT metadata_id FROM states_meta WHERE entity_id = ?",
                (entity_id,),
            ).fetchone()
        result = row[0] if row else None
        self._meta[entity_id] = result
        return result

    def _attributes_id(self, entity_id: str, metadata_id: int) -> int | None:
        """Reuse the attributes blob from the most recent live state for this entity."""
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

    # ── Core injection ────────────────────────────────────────────────────

    def _inject_cycle(
        self,
        conn: sqlite3.Connection,
        metadata_id: int,
        attrs_id: int | None,
        start_ts: float,
        end_ts: float,
        kwh_before: float,
        kwh_after: float,
    ):
        """Delete + re-insert per-minute states for one detection cycle."""
        conn.execute(
            "DELETE FROM states WHERE metadata_id = ? "
            "AND last_changed_ts >= ? AND last_changed_ts <= ?",
            (metadata_id, start_ts, end_ts),
        )

        duration = max(end_ts - start_ts, 1.0)
        delta = kwh_after - kwh_before
        rows = []
        t = start_ts
        while t <= end_ts + 0.5:
            frac = min(1.0, (t - start_ts) / duration)
            val = str(round(kwh_before + frac * delta, 4))
            if self._has_last_reported:
                rows.append((metadata_id, val, t, t, t, attrs_id))
            else:
                rows.append((metadata_id, val, t, t, attrs_id))
            t += 60.0

        if self._has_last_reported:
            conn.executemany(
                "INSERT INTO states "
                "(metadata_id, state, last_changed_ts, last_updated_ts, "
                "last_reported_ts, attributes_id) VALUES (?,?,?,?,?,?)",
                rows,
            )
        else:
            conn.executemany(
                "INSERT INTO states "
                "(metadata_id, state, last_changed_ts, last_updated_ts, "
                "attributes_id) VALUES (?,?,?,?,?)",
                rows,
            )

    def _insert_state(
        self,
        conn: sqlite3.Connection,
        metadata_id: int,
        state: str,
        ts: float,
        attrs_id: int | None = None,
    ):
        if self._has_last_reported:
            conn.execute(
                "INSERT INTO states "
                "(metadata_id, state, last_changed_ts, last_updated_ts, "
                "last_reported_ts, attributes_id) VALUES (?,?,?,?,?,?)",
                (metadata_id, state, ts, ts, ts, attrs_id),
            )
        else:
            conn.execute(
                "INSERT INTO states "
                "(metadata_id, state, last_changed_ts, last_updated_ts, "
                "attributes_id) VALUES (?,?,?,?,?)",
                (metadata_id, state, ts, ts, attrs_id),
            )

    def _inject_binary_full(
        self,
        conn: sqlite3.Connection,
        metadata_id: int,
        detections: list[dict],
    ):
        """Full resync for binary sensor: delete entire history, re-insert on/off."""
        if not detections:
            return
        first_ts = _to_ts(detections[0]["start_time"])
        conn.execute(
            "DELETE FROM states WHERE metadata_id = ? AND last_changed_ts >= ?",
            (metadata_id, first_ts - 120),
        )
        self._insert_state(conn, metadata_id, "off", first_ts - 60)
        for det in detections:
            self._insert_state(conn, metadata_id, "on", _to_ts(det["start_time"]))
            self._insert_state(conn, metadata_id, "off", _to_ts(det["end_time"]))

    def _inject_binary_cycle(
        self,
        conn: sqlite3.Connection,
        metadata_id: int,
        start_ts: float,
        end_ts: float,
    ):
        """Incremental: delete window, insert on/off for one cycle."""
        conn.execute(
            "DELETE FROM states WHERE metadata_id = ? "
            "AND last_changed_ts >= ? AND last_changed_ts <= ?",
            (metadata_id, start_ts - 60, end_ts + 1),
        )
        self._insert_state(conn, metadata_id, "on", start_ts)
        self._insert_state(conn, metadata_id, "off", end_ts)

    def _process(
        self,
        appliance: dict,
        detections: list[dict],
        baseline_kwh: float,
        cum_start: float = 0.0,
        full_binary: bool = False,
    ) -> int:
        """Inject energy (per-minute ramps) + binary (on/off) for a detection list."""
        ha_eid = appliance["ha_entity_id"]
        sl = make_slug(ha_eid)
        energy_eid = f"sensor.{sl}_energy"
        binary_eid = f"binary_sensor.{sl}"

        energy_meta = self._metadata_id(energy_eid)
        binary_meta = self._metadata_id(binary_eid)

        if energy_meta is None and binary_meta is None:
            logger.debug(f"No states_meta for {energy_eid} or {binary_eid} — skip")
            return 0

        attrs_id = self._attributes_id(energy_eid, energy_meta) if energy_meta else None
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
                        kwh_before = max(0.0, cum - baseline_kwh)
                        kwh_after = max(0.0, cum + kwh - baseline_kwh)
                        self._inject_cycle(conn, energy_meta, attrs_id, start_ts, end_ts, kwh_before, kwh_after)

                    if binary_meta is not None and not full_binary:
                        self._inject_binary_cycle(conn, binary_meta, start_ts, end_ts)

                    cum += kwh
                    injected += 1
        except sqlite3.OperationalError as e:
            logger.warning(f"HA SQLite locked ({sl}): {e} — will retry next poll")
            return 0

        if injected:
            total = round(max(0.0, cum - baseline_kwh), 3)
            logger.info(
                f"nilm_{sl}: injected {injected} cycles"
                f"{f' → {total} kWh' if energy_meta else ''}"
                f"{' + ON/OFF' if binary_meta else ''}"
            )
        return injected

    # ── Public API ────────────────────────────────────────────────────────

    def full_resync(self):
        """Process all detections for all active appliances.  Called once on startup."""
        for appliance in repo.get_active_appliances():
            aid = appliance["id"]
            baseline = repo.get_energy_baseline_kwh(aid)
            if baseline is None:
                logger.debug(f"HWM baseline not set for appliance {aid} — run ha-publish loop first")
                continue
            detections = repo.get_all_detections_ordered(aid)
            self._process(appliance, detections, baseline, full_binary=True)
            if detections:
                self._last_id[aid] = max(d["id"] for d in detections)
        self.synced = True

    def incremental(self, appliance: dict):
        """Inject new detections since last seen.  Called every poll."""
        aid = appliance["id"]
        baseline = repo.get_energy_baseline_kwh(aid)
        if baseline is None:
            return

        last_seen = self._last_id.get(aid, 0)
        new_dets = repo.get_detections_since_id(aid, last_seen)
        if not new_dets:
            return

        # Cumulative energy of all earlier detections (to compute correct kwh_before).
        cum_before = repo.get_cumulative_energy_before_id(aid, new_dets[0]["id"])
        self._process(appliance, new_dets, baseline, cum_start=cum_before)
        self._last_id[aid] = max(d["id"] for d in new_dets)


def _to_ts(dt) -> float:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()
