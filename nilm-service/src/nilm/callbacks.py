"""Keras callback that streams training progress to the backend SSE bus."""

import logging
from datetime import datetime, timezone

from tensorflow.keras import callbacks

from ..events import emit


logger = logging.getLogger(__name__)


class RedisTrainingCallback(callbacks.Callback):
    """Name kept for backward compat; now pushes progress over HTTP→SSE
    (no Redis). Emits `training_progress` per epoch and `training_complete`
    at the end. The backend fans these out on /api/events."""

    def __init__(self, model_name, total_epochs, batch_update_freq=10):
        super().__init__()
        self.model_name = model_name
        self.total_epochs = total_epochs
        self.current_epoch = 0
        self.start_time = None

    def on_train_begin(self, logs=None):
        self.start_time = datetime.now(timezone.utc)
        emit("training_progress", {"phase": "start", "model_name": self.model_name, "total_epochs": self.total_epochs})

    def on_epoch_begin(self, epoch, logs=None):
        self.current_epoch = epoch + 1

    def on_epoch_end(self, epoch, logs=None):
        logs = logs or {}
        progress = round((self.current_epoch / self.total_epochs) * 100, 1)
        emit("training_progress", {
            "phase": "epoch",
            "epoch": self.current_epoch,
            "total_epochs": self.total_epochs,
            "progress": progress,
            "metrics": {k: float(v) for k, v in logs.items()},
        })

    def on_train_end(self, logs=None):
        logs = logs or {}
        elapsed = (datetime.now(timezone.utc) - self.start_time).total_seconds() if self.start_time else 0
        emit("training_progress", {
            "phase": "done",
            "epochs_completed": self.current_epoch,
            "duration_seconds": round(elapsed, 1),
        })
