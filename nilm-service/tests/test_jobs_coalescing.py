"""Coalescing behavior of request_training/request_detection in src.jobs.

Bursts (CSV import crossing several auto-train thresholds, rapid UI clicks)
must collapse to a single queued run instead of piling up on the Pi.
"""

import threading
import time

from src import jobs


def _block_until(event, result=None):
    def _fn(*args, **kwargs):
        event.wait(timeout=5)
        return result or {"status": "success"}

    return _fn


def test_request_training_coalesces_concurrent_calls(monkeypatch):
    release = threading.Event()
    monkeypatch.setattr(jobs, "run_training", _block_until(release))

    assert jobs.request_training() is True
    # A second request while the first is still running must coalesce.
    assert jobs.request_training() is False
    assert jobs.request_training() is False

    release.set()
    _wait_until(lambda: not jobs._pending["train"])

    # Once the pending run finished, a new request is queued again.
    release2 = threading.Event()
    monkeypatch.setattr(jobs, "run_training", _block_until(release2))
    assert jobs.request_training() is True
    release2.set()
    _wait_until(lambda: not jobs._pending["train"])


def test_request_detection_coalesces_concurrent_calls(monkeypatch):
    release = threading.Event()
    monkeypatch.setattr(jobs, "run_detection", _block_until(release))

    assert jobs.request_detection() is True
    assert jobs.request_detection() is False

    release.set()
    _wait_until(lambda: not jobs._pending["detect"])

    release2 = threading.Event()
    monkeypatch.setattr(jobs, "run_detection", _block_until(release2))
    assert jobs.request_detection() is True
    release2.set()
    _wait_until(lambda: not jobs._pending["detect"])


def test_training_and_detection_pending_flags_are_independent(monkeypatch):
    train_release = threading.Event()
    detect_release = threading.Event()
    monkeypatch.setattr(jobs, "run_training", _block_until(train_release))
    monkeypatch.setattr(jobs, "run_detection", _block_until(detect_release))

    assert jobs.request_training() is True
    # A pending training run must not block a detection request.
    assert jobs.request_detection() is True
    # But a second training request still coalesces.
    assert jobs.request_training() is False

    train_release.set()
    detect_release.set()
    _wait_until(lambda: not jobs._pending["train"] and not jobs._pending["detect"])


def _wait_until(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition not met within timeout")
