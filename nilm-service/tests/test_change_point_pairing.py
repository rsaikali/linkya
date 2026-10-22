"""Concurrent loads must not break change point pairing (water heater vs radiators).

Regression: on 2026-10-22 a radiator switching off closed the water heater's cycle
and the dishwasher closed itself, so the heater was never matched.
"""

from datetime import datetime, timedelta, timezone

import numpy as np

from src.nilm.detectors.change_point_detector import ChangePointPatternDetector, fill_gaps

BASE, HEATER, RADIATOR = 250.0, 3200.0, 2840.0
STEP_S = 8


def _series(*loads, n=900):
    """loads = (start, end, watts) in samples; returns (timestamps, power)."""
    y = np.full(n, BASE) + np.random.default_rng(0).normal(0, 5, n)
    for start, end, watts in loads:
        y[start:end] += watts
    t0 = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
    return [t0 + timedelta(seconds=STEP_S * i) for i in range(n)], y


def _patterns(timestamps, y):
    d = ChangePointPatternDetector(min_power_change=500, min_duration=60)
    return d.extract_patterns(y, d.detect_change_points(y), timestamps=timestamps)


def _heater(patterns, start=100, end=600):
    return next(p for p in patterns if abs(p["start_idx"] - start) < 6 and abs(p["end_idx"] - end) < 6)


def test_single_cycle_unchanged():
    ts, y = _series((100, 600, HEATER))
    (p,) = _patterns(ts, y)
    assert abs(p["avg_power"] - (BASE + HEATER)) < 50


def test_nested_radiator_is_subtracted():
    ts, y = _series((100, 600, HEATER), (200, 350, RADIATOR))
    p = _heater(_patterns(ts, y))
    assert abs(p["avg_power"] - (BASE + HEATER)) < 50


def test_simultaneous_start_radiator_stops_first():
    # Heater and radiator start together (one merged edge), radiator stops first.
    ts, y = _series((100, 600, HEATER), (100, 250, RADIATOR))
    p = _heater(_patterns(ts, y))
    assert abs(p["avg_power"] - (BASE + HEATER)) < 50


def test_dishwasher_does_not_close_heater():
    ts, y = _series((100, 700, HEATER), (300, 450, 2050.0))
    p = _heater(_patterns(ts, y), end=700)
    assert abs(p["avg_power"] - (BASE + HEATER)) < 50


def test_fill_gaps_forward_fills_stable_periods():
    t0 = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
    ts = [t0 + timedelta(seconds=STEP_S * i) for i in range(10)]
    ts += [ts[-1] + timedelta(minutes=78) + timedelta(seconds=STEP_S * i) for i in range(10)]
    y = np.array([226.0] * 10 + [5891.0] * 10, dtype=np.float32)

    ts2, y2 = fill_gaps(ts, y)

    assert abs((ts2[-1] - ts2[0]) - (ts[-1] - ts[0])) < timedelta(seconds=STEP_S)
    assert len(ts2) > 500  # 78 min / 8 s
    assert set(np.unique(y2)) == {226.0, 5891.0}  # flat fill, no interpolation
    assert np.all(np.diff(y2) >= 0)  # the step stays at the end of the hole


def test_fill_gaps_keeps_real_outage_as_hole():
    t0 = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
    ts = [t0, t0 + timedelta(seconds=STEP_S), t0 + timedelta(hours=5)]
    ts2, _ = fill_gaps(ts, np.array([1.0, 1.0, 1.0]))
    assert len(ts2) < 10


def test_loads_stopping_together_each_get_a_cycle():
    # One merged down edge (-5.7 kW) ends three loads that started separately.
    ts, y = _series((100, 500, 1175.0), (200, 500, 1508.0), (300, 500, 2994.0))
    p = next(p for p in _patterns(ts, y) if abs(p["start_idx"] - 300) < 6)
    assert abs(p["avg_power"] - (BASE + 2994.0)) < 50
