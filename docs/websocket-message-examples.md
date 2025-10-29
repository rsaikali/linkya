# WebSocket Training Logs - Message Examples

## Event: training_start

Published when training begins.

```json
{
  "event": "training_start",
  "version": "current",
  "timestamp": "2025-10-29T14:23:45.123Z",
  "data": {
    "total_epochs": 30,
    "message": "Starting training for model current"
  }
}
```

## Event: epoch_start

Published at the beginning of each epoch.

```json
{
  "event": "epoch_start",
  "version": "current",
  "timestamp": "2025-10-29T14:23:50.456Z",
  "data": {
    "epoch": 1,
    "total_epochs": 30,
    "progress": 3.3
  }
}
```

## Event: epoch_end

Published at the end of each epoch with metrics and timing.

```json
{
  "event": "epoch_end",
  "version": "current",
  "timestamp": "2025-10-29T14:24:15.789Z",
  "data": {
    "epoch": 1,
    "total_epochs": 30,
    "progress": 3.3,
    "metrics": {
      "loss": 0.0234,
      "val_loss": 0.0267,
      "mae": 0.0156,
      "val_mae": 0.0178,
      "lr": 0.001
    },
    "elapsed_seconds": 25.3,
    "eta_seconds": 734.0
  }
}
```

## Event: batch_update

Published every N batches (default: 10) during training.

```json
{
  "event": "batch_update",
  "version": "current",
  "timestamp": "2025-10-29T14:24:05.234Z",
  "data": {
    "epoch": 1,
    "batch": 10,
    "metrics": {
      "loss": 0.0245,
      "mae": 0.0162
    }
  }
}
```

## Event: training_complete

Published when training finishes successfully.

```json
{
  "event": "training_complete",
  "version": "current",
  "timestamp": "2025-10-29T14:36:20.567Z",
  "data": {
    "epochs_completed": 30,
    "final_metrics": {
      "loss": 0.0189,
      "val_loss": 0.0212,
      "mae": 0.0134,
      "val_mae": 0.0145
    },
    "total_duration_seconds": 735.4,
    "message": "Training completed for model current"
  }
}
```

## Event: error (client-side)

Published when an error occurs in the WebSocket connection or message parsing.

```json
{
  "event": "error",
  "data": {
    "error": "Connection lost",
    "timestamp": "2025-10-29T14:25:00.123Z"
  }
}
```

## Event: connected (client-side)

Published when WebSocket connection is established.

```json
{
  "event": "connected",
  "data": {
    "timestamp": "2025-10-29T14:23:40.000Z"
  }
}
```

## Event: disconnected (client-side)

Published when WebSocket connection is lost.

```json
{
  "event": "disconnected",
  "data": {
    "timestamp": "2025-10-29T14:35:00.000Z"
  }
}
```

## Complete Training Session Example

Here's what a typical training session looks like:

```javascript
// 1. Connection established
{
  "event": "connected",
  "data": { "timestamp": "2025-10-29T14:23:40.000Z" }
}

// 2. Training starts
{
  "event": "training_start",
  "version": "current",
  "timestamp": "2025-10-29T14:23:45.123Z",
  "data": {
    "total_epochs": 30,
    "message": "Starting training for model current"
  }
}

// 3. First epoch starts
{
  "event": "epoch_start",
  "version": "current",
  "timestamp": "2025-10-29T14:23:50.456Z",
  "data": { "epoch": 1, "total_epochs": 30, "progress": 3.3 }
}

// 4. Batch updates during epoch
{
  "event": "batch_update",
  "version": "current",
  "timestamp": "2025-10-29T14:23:55.234Z",
  "data": {
    "epoch": 1,
    "batch": 10,
    "metrics": { "loss": 0.0245, "mae": 0.0162 }
  }
}

// ... more batch updates ...

// 5. First epoch completes
{
  "event": "epoch_end",
  "version": "current",
  "timestamp": "2025-10-29T14:24:15.789Z",
  "data": {
    "epoch": 1,
    "total_epochs": 30,
    "progress": 3.3,
    "metrics": {
      "loss": 0.0234,
      "val_loss": 0.0267,
      "mae": 0.0156,
      "val_mae": 0.0178
    },
    "elapsed_seconds": 25.3,
    "eta_seconds": 734.0
  }
}

// 6. Subsequent epochs...
// ... epoch_start → batch_update(s) → epoch_end ...

// 7. Training completes
{
  "event": "training_complete",
  "version": "current",
  "timestamp": "2025-10-29T14:36:20.567Z",
  "data": {
    "epochs_completed": 30,
    "final_metrics": {
      "loss": 0.0189,
      "val_loss": 0.0212,
      "mae": 0.0134,
      "val_mae": 0.0145
    },
    "total_duration_seconds": 735.4,
    "message": "Training completed for model current"
  }
}
```

## Message Structure

All messages follow this common structure:

```typescript
interface TrainingLogMessage {
  event: 'training_start' | 'epoch_start' | 'epoch_end' | 'batch_update' | 'training_complete';
  version: string;  // Model version, typically "current"
  timestamp: string;  // ISO 8601 UTC timestamp
  data: {
    // Event-specific data
    [key: string]: any;
  };
}
```

## Metrics Dictionary

Common metrics you'll see in `epoch_end` events:

- `loss`: Training loss (lower is better)
- `val_loss`: Validation loss (lower is better)
- `mae`: Mean Absolute Error on training set
- `val_mae`: Mean Absolute Error on validation set
- `lr`: Current learning rate
- `mse`: Mean Squared Error (if using MSE loss)
- `accuracy`: Classification accuracy (if applicable)

## Timing Fields

- `elapsed_seconds`: Time elapsed since training started
- `eta_seconds`: Estimated time remaining until completion
- `total_duration_seconds`: Total training time (in `training_complete` event)

## Progress Calculation

Progress is calculated as:
```python
progress = (current_epoch / total_epochs) * 100
```

## Frontend Usage Example

```javascript
import trainingLogsWS from '../services/websocket';

// Connect
trainingLogsWS.connect();

// Listen to events
trainingLogsWS.on('epoch_end', (data) => {
  console.log(`Epoch ${data.epoch}/${data.total_epochs}`);
  console.log(`Loss: ${data.metrics.loss.toFixed(4)}`);
  console.log(`ETA: ${formatDuration(data.eta_seconds)}`);
});

trainingLogsWS.on('training_complete', (data) => {
  console.log('Training completed!');
  console.log(`Final loss: ${data.final_metrics.loss.toFixed(4)}`);
  console.log(`Duration: ${formatDuration(data.total_duration_seconds)}`);
});

// Cleanup
trainingLogsWS.disconnect();
```
