/**
 * SSE client — one EventSource on /api/events, fanned out to subscribers.
 * Replaces the old per-channel WebSocket stack. Exposes the same singletons
 * (trainingLogsWS, detectionsWS, importProgressWS, consumptionWS) with the
 * same .on/.off/.connect/.disconnect API so components need no changes.
 */

const SSE_URL = `${process.env.REACT_APP_API_URL || ""}/api/events`;

// Shared EventSource + dispatch table (sse event name → Set<handler>).
let source = null;
const dispatch = {};

// Backend SSE event names we forward.
const SSE_EVENTS = [
  "signature_added",
  "signature_deleted",
  "signatures_cleared",
  "appliance_updated",
  "detection_new",
  "detection_complete",
  "detection_start",
  "detections_cleared",
  "detection_validated",
  "detection_reassigned",
  "training_progress",
  "training_complete",
  "training_error",
  "import_start",
  "import_progress",
  "import_complete",
  "ha_backfill_start",
  "ha_backfill_complete",
];

function ensureSource() {
  if (source) return;
  source = new EventSource(SSE_URL);
  source.onopen = () => console.log("✅ SSE connected", SSE_URL);
  source.onerror = () => console.warn("SSE error (browser will retry)");
  SSE_EVENTS.forEach((type) => {
    source.addEventListener(type, (e) => {
      let data = {};
      try {
        data = JSON.parse(e.data);
      } catch (_) {
        /* keepalive/comment */
      }
      (dispatch[type] || []).forEach((h) => {
        try {
          h(data);
        } catch (err) {
          console.error(`SSE handler ${type}`, err);
        }
      });
    });
  });
}

function subscribe(sseType, handler) {
  (dispatch[sseType] = dispatch[sseType] || []).push(handler);
}
function unsubscribe(sseType, handler) {
  if (dispatch[sseType]) dispatch[sseType] = dispatch[sseType].filter((h) => h !== handler);
}

/**
 * Thin compat shim. `map` translates the component-facing event name to the
 * backend SSE event name (identity when omitted).
 */
class Channel {
  constructor(map = {}) {
    this.map = map;
  }
  connect() {
    ensureSource();
  }
  disconnect() {
    /* shared source stays open; nothing per-channel to close */
  }
  on(eventName, handler) {
    subscribe(this.map[eventName] || eventName, handler);
  }
  off(eventName, handler) {
    unsubscribe(this.map[eventName] || eventName, handler);
  }
}

// Training: old UI listened to training_start/epoch_end/training_complete.
// New backend emits training_progress/training_complete/training_error.
const trainingLogsWS = new Channel({
  training_start: "training_progress",
  epoch_end: "training_progress",
  batch_update: "training_progress",
  error: "training_error",
});

// Detections: old new_detection → backend detection_new.
const detectionsWS = new Channel({
  new_detection: "detection_new",
});

const importProgressWS = new Channel();

// Consumption live stream was dropped (no value on the front). No-op channel.
const consumptionWS = new Channel();

export default trainingLogsWS;
export { trainingLogsWS, detectionsWS, importProgressWS, consumptionWS };
