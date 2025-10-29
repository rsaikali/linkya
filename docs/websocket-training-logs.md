# Real-time Training Logs - WebSocket Implementation

This document explains the WebSocket-based real-time training logs feature.

## Architecture

```
┌─────────────────────┐      ┌──────────────────┐      ┌─────────────────┐      ┌──────────────┐
│  Keras Callback     │──1──>│  Redis Pub/Sub   │<──2──│  FastAPI WS     │<──3──│   Frontend   │
│  (Training Logs)    │      │  training:logs   │      │  /ws/training   │      │  (React)     │
└─────────────────────┘      └──────────────────┘      └─────────────────┘      └──────────────┘
         │                                                                              │
         │ Publishes events:                                                           │
         │ - training_start                                                            │
         │ - epoch_start                                                               │
         │ - epoch_end (with metrics, ETA)                                            │
         │ - batch_update                                                              │
         │ - training_complete                                                         │
         │                                                                              │
         └──────────────────────────────────────────────────────────────────────────> Displays
                                                                                        live progress
```

## Components

### 1. Backend: Keras Callback (nilm-cnn-service)

**File**: `nilm-cnn-service/src/seq2point_nilm.py`

Custom Keras callback `RedisTrainingCallback` that:
- Connects to Redis on initialization
- Publishes training events to `training:logs` channel
- Sends structured JSON messages with event type and data
- Calculates progress, elapsed time, and ETA

**Events published**:
- `training_start`: When training begins
- `epoch_start`: At the start of each epoch (with progress %)
- `epoch_end`: At the end of each epoch (with metrics, ETA)
- `batch_update`: Every N batches (configurable, default=10)
- `training_complete`: When training finishes

### 2. Backend: WebSocket Endpoint (backend-service)

**File**: `backend-service/src/main.py`

**Endpoint**: `WS /ws/training`

- `TrainingLogsManager` class manages WebSocket connections
- Subscribes to Redis `training:logs` channel using `redis.asyncio`
- Broadcasts messages to all connected WebSocket clients
- Handles connection/disconnection and auto-cleanup
- Background task listens to Redis and forwards events

### 3. Frontend: WebSocket Service

**File**: `frontend-service/src/services/websocket.js`

Singleton WebSocket manager with:
- Auto-reconnection with 3-second interval
- Event-based handler system (on/off methods)
- Connection status tracking
- Error handling and logging

**Events exposed**:
- `connected` / `disconnected`
- `training_start` / `training_complete`
- `epoch_start` / `epoch_end`
- `batch_update`
- `error`

### 4. Frontend: UI Component

**File**: `frontend-service/src/components/TrainingLogsViewer.js`

React component displaying:
- Connection status badge
- Training progress bar with percentage
- Current epoch / total epochs
- Real-time metrics (loss, accuracy, etc.)
- Elapsed time and ETA
- Event log with timestamps and severity icons
- Auto-scroll to latest log entry
- Collapsible interface

## Testing

### 1. Start the stack

```bash
cd /home/rsaikali/nilmia
make start
```

### 2. Check Redis connection

```bash
make redis-cli
# In Redis CLI:
> PING
PONG
> SUBSCRIBE training:logs
# Leave this open in one terminal
```

### 3. Open frontend

Navigate to `http://localhost:3000` and go to the Training page.

### 4. Trigger training

Click "Entraîner le modèle" button or use API:

```bash
curl -X POST http://localhost:8000/api/nilm/train
```

### 5. Observe real-time logs

You should see:
- WebSocket connection badge turns green
- Progress bar updates in real-time
- Epoch counter increments
- Metrics update (loss, val_loss, mae, etc.)
- ETA countdown
- Event log fills with timestamped entries

## Message Format

All messages follow this structure:

```json
{
  "event": "epoch_end",
  "version": "current",
  "timestamp": "2025-10-29T12:34:56.789Z",
  "data": {
    "epoch": 5,
    "total_epochs": 30,
    "progress": 16.7,
    "metrics": {
      "loss": 0.0234,
      "val_loss": 0.0267,
      "mae": 0.0156,
      "val_mae": 0.0178
    },
    "elapsed_seconds": 145.2,
    "eta_seconds": 725.0
  }
}
```

## Environment Variables

### Backend (.env)

```env
# Redis connection (already configured via Celery)
CELERY_BROKER_URL=redis://redis:6379/0
```

### Frontend (.env)

```env
# WebSocket URL (defaults to ws://localhost:8000)
REACT_APP_WS_URL=ws://localhost:8000
```

## Troubleshooting

### WebSocket won't connect

1. Check backend is running: `curl http://localhost:8000/health`
2. Check Redis is running: `make redis-cli`
3. Check browser console for WebSocket errors
4. Verify CORS settings in backend allow WebSocket connections

### No training events received

1. Verify Redis Pub/Sub is working:
   ```bash
   make redis-cli
   > SUBSCRIBE training:logs
   ```
2. Trigger training and watch for messages
3. Check nilm-cnn-service logs: `docker logs nilmia-cnn-worker`
4. Verify `RedisTrainingCallback` is initialized (should see "✅ RedisTrainingCallback connected")

### Auto-reconnection not working

1. Check browser console for reconnection attempts
2. Verify `shouldReconnect` flag is true
3. Check for JavaScript errors in console

## Future Enhancements

- [ ] Add pause/resume training commands via WebSocket
- [ ] Add early stopping trigger from frontend
- [ ] Display training charts in real-time (loss curves)
- [ ] Support multiple concurrent training sessions
- [ ] Add notification sound/desktop notification on completion
- [ ] Store training history in database for later review
- [ ] Migrate consumption/detection SSE endpoints to WebSocket
