"""_build_full_hourly_stats: proportional hour split + carry-forward.

NILM always detects a cycle after it happened, so re-detections rewrite
history — the hourly bucketing must (a) split energy proportionally when a
cycle straddles an hour boundary (e.g. 23:54-00:13) and (b) carry the
cumulative sum forward through hours with no detections, so HA never sees
the total drop or reset.
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.ha_backfill import _build_full_hourly_stats
import src.ha_backfill as ha_backfill_module


class _FrozenDatetime(datetime):
    """Freezes datetime.now() while leaving normal datetime instances untouched."""

    _now = None

    @classmethod
    def now(cls, tz=None):
        return cls._now if tz else cls._now.replace(tzinfo=None)


@pytest.fixture
def freeze_now(monkeypatch):
    def _freeze(fixed):
        _FrozenDatetime._now = fixed
        monkeypatch.setattr(ha_backfill_module, "datetime", _FrozenDatetime)
        return fixed

    return _freeze


def test_no_detections_returns_empty_list():
    assert _build_full_hourly_stats([]) == []


def test_single_detection_within_one_hour_bucket(freeze_now):
    hour = datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc)
    freeze_now(hour)

    detections = [{
        "start_time": hour + timedelta(minutes=5),
        "end_time": hour + timedelta(minutes=35),
        "energy_wh": 900.0,
    }]

    stats = _build_full_hourly_stats(detections)

    assert len(stats) == 1
    assert stats[0]["start"] == hour.isoformat()
    assert stats[0]["sum"] == pytest.approx(0.9, abs=1e-6)
    assert stats[0]["state"] == stats[0]["sum"]


def test_cycle_straddling_hour_boundary_splits_proportionally(freeze_now):
    # Cycle from 23:54 to 00:13 the next hour — the exact case that motivated
    # proportional splitting (see CLAUDE.md ha_backfill.py notes).
    start = datetime(2026, 6, 1, 23, 54, tzinfo=timezone.utc)
    end = datetime(2026, 6, 2, 0, 13, tzinfo=timezone.utc)
    freeze_now(end.replace(minute=0))

    detections = [{"start_time": start, "end_time": end, "energy_wh": 1000.0}]

    stats = _build_full_hourly_stats(detections)

    assert len(stats) == 2
    total_secs = (end - start).total_seconds()
    first_hour_secs = 6 * 60   # 23:54 -> 00:00
    second_hour_secs = 13 * 60  # 00:00 -> 00:13
    assert first_hour_secs + second_hour_secs == total_secs

    expected_first = 1.0 * first_hour_secs / total_secs
    expected_total = 1.0  # 1000 Wh = 1 kWh, fully allocated across both hours

    assert stats[0]["start"] == start.replace(minute=0).isoformat()
    assert stats[0]["sum"] == pytest.approx(expected_first, abs=1e-4)
    assert stats[1]["start"] == end.replace(minute=0).isoformat()
    assert stats[1]["sum"] == pytest.approx(expected_total, abs=1e-4)


def test_carry_forward_fills_gap_hours_without_reset(freeze_now):
    hour0 = datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc)
    # A second detection 3 hours later — hours 11:00 and 12:00 have no
    # detections and must carry the hour0 cumulative sum forward.
    hour3 = hour0 + timedelta(hours=3)
    freeze_now(hour3)

    detections = [
        {"start_time": hour0 + timedelta(minutes=1), "end_time": hour0 + timedelta(minutes=10), "energy_wh": 500.0},
        {"start_time": hour3 + timedelta(minutes=1), "end_time": hour3 + timedelta(minutes=10), "energy_wh": 300.0},
    ]

    stats = _build_full_hourly_stats(detections)

    assert [s["start"] for s in stats] == [
        hour0.isoformat(),
        (hour0 + timedelta(hours=1)).isoformat(),
        (hour0 + timedelta(hours=2)).isoformat(),
        hour3.isoformat(),
    ]
    # Gap hours (11:00, 12:00) carry the same cumulative sum forward.
    assert stats[0]["sum"] == pytest.approx(0.5, abs=1e-6)
    assert stats[1]["sum"] == pytest.approx(0.5, abs=1e-6)
    assert stats[2]["sum"] == pytest.approx(0.5, abs=1e-6)
    # The next detection adds on top, never resets.
    assert stats[3]["sum"] == pytest.approx(0.8, abs=1e-6)
