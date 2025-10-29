/**
 * WebSocket service for real-time training logs
 * Handles connection, reconnection, and event processing
 */

const WS_BASE_URL = process.env.REACT_APP_WS_URL || 'ws://localhost:8000';

/**
 * WebSocket manager for training logs
 */
class TrainingLogsWebSocket {
  constructor() {
    this.ws = null;
    this.url = `${WS_BASE_URL}/ws/training`;
    this.reconnectInterval = 3000; // 3 seconds
    this.reconnectTimer = null;
    this.eventHandlers = {
      training_start: [],
      epoch_start: [],
      epoch_end: [],
      batch_update: [],
      training_complete: [],
      error: [],
      connected: [],
      disconnected: [],
    };
    this.isConnected = false;
    this.shouldReconnect = true;
  }

  /**
   * Connect to WebSocket server
   */
  connect() {
    // If already connected, don't create a new connection
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      console.log('⚠️ WebSocket already connected, skipping');
      return;
    }
    
    // Close existing connection if any
    if (this.ws) {
      this.ws.close();
    }
    
    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        console.log('✅ WebSocket connected to training logs');
        this.isConnected = true;
        this.shouldReconnect = true;
        
        // Clear reconnect timer
        if (this.reconnectTimer) {
          clearTimeout(this.reconnectTimer);
          this.reconnectTimer = null;
        }

        // Trigger connected handlers
        this.triggerEvent('connected', { timestamp: new Date() });
      };

      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          const { event: eventType, data } = message;

          console.log(`📨 Training log event: ${eventType}`, data);

          // Trigger event-specific handlers
          if (this.eventHandlers[eventType]) {
            this.triggerEvent(eventType, data);
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
          this.triggerEvent('error', { error: error.message });
        }
      };

      this.ws.onerror = (error) => {
        console.error('❌ WebSocket error:', error);
        this.triggerEvent('error', { error: error.message || 'WebSocket error' });
      };

      this.ws.onclose = () => {
        console.log('🔌 WebSocket disconnected');
        this.isConnected = false;
        this.triggerEvent('disconnected', { timestamp: new Date() });

        // Attempt reconnection if desired
        if (this.shouldReconnect) {
          this.scheduleReconnect();
        }
      };
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      this.triggerEvent('error', { error: error.message });
      this.scheduleReconnect();
    }
  }

  /**
   * Schedule automatic reconnection
   */
  scheduleReconnect() {
    if (this.reconnectTimer) {
      return; // Already scheduled
    }

    console.log(`🔄 Reconnecting in ${this.reconnectInterval / 1000}s...`);
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      if (this.shouldReconnect) {
        this.connect();
      }
    }, this.reconnectInterval);
  }

  /**
   * Disconnect WebSocket
   * @param {boolean} permanent - If true, don't auto-reconnect
   */
  disconnect(permanent = false) {
    this.shouldReconnect = !permanent;

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    this.isConnected = false;
  }

  /**
   * Send message to server (for future commands)
   * @param {object} message - Message to send
   */
  send(message) {
    if (this.isConnected && this.ws) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.warn('Cannot send message: WebSocket not connected');
    }
  }

  /**
   * Register event handler
   * @param {string} eventType - Event type to listen for
   * @param {function} handler - Handler function
   */
  on(eventType, handler) {
    if (this.eventHandlers[eventType]) {
      this.eventHandlers[eventType].push(handler);
    } else {
      console.warn(`Unknown event type: ${eventType}`);
    }
  }

  /**
   * Unregister event handler
   * @param {string} eventType - Event type
   * @param {function} handler - Handler function to remove
   */
  off(eventType, handler) {
    if (this.eventHandlers[eventType]) {
      this.eventHandlers[eventType] = this.eventHandlers[eventType].filter(
        (h) => h !== handler
      );
    }
  }

  /**
   * Trigger all handlers for an event type
   * @param {string} eventType - Event type
   * @param {object} data - Event data
   */
  triggerEvent(eventType, data) {
    if (this.eventHandlers[eventType]) {
      this.eventHandlers[eventType].forEach((handler) => {
        try {
          handler(data);
        } catch (error) {
          console.error(`Error in ${eventType} handler:`, error);
        }
      });
    }
  }

  /**
   * Get connection status
   */
  getStatus() {
    return {
      isConnected: this.isConnected,
      shouldReconnect: this.shouldReconnect,
      url: this.url,
    };
  }
}

/**
 * Generic WebSocket manager for real-time updates
 */
class GenericWebSocket {
  constructor(endpoint, eventTypes = []) {
    this.ws = null;
    this.url = `${WS_BASE_URL}${endpoint}`;
    this.reconnectInterval = 3000;
    this.reconnectTimer = null;
    this.eventHandlers = {
      connected: [],
      disconnected: [],
      error: [],
    };
    
    // Add custom event types
    eventTypes.forEach(type => {
      this.eventHandlers[type] = [];
    });
    
    this.isConnected = false;
    this.shouldReconnect = true;
  }

  connect() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      console.log(`⚠️ WebSocket already connected to ${this.url}`);
      return;
    }
    
    if (this.ws) {
      this.ws.close();
    }
    
    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        console.log(`✅ WebSocket connected to ${this.url}`);
        this.isConnected = true;
        this.shouldReconnect = true;
        
        if (this.reconnectTimer) {
          clearTimeout(this.reconnectTimer);
          this.reconnectTimer = null;
        }

        this.triggerEvent('connected', { timestamp: new Date() });
      };

      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          const { event: eventType, data } = message;

          console.log(`📨 WS event [${this.url}]: ${eventType}`, data);

          if (this.eventHandlers[eventType]) {
            this.triggerEvent(eventType, data);
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
          this.triggerEvent('error', { error: error.message });
        }
      };

      this.ws.onerror = (error) => {
        console.error(`❌ WebSocket error [${this.url}]:`, error);
        this.triggerEvent('error', { error: error.message || 'WebSocket error' });
      };

      this.ws.onclose = () => {
        console.log(`🔌 WebSocket disconnected from ${this.url}`);
        this.isConnected = false;
        this.triggerEvent('disconnected', { timestamp: new Date() });

        if (this.shouldReconnect) {
          this.scheduleReconnect();
        }
      };
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      this.triggerEvent('error', { error: error.message });
      this.scheduleReconnect();
    }
  }

  scheduleReconnect() {
    if (this.reconnectTimer) {
      return;
    }

    console.log(`🔄 Reconnecting to ${this.url} in ${this.reconnectInterval / 1000}s...`);
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      if (this.shouldReconnect) {
        this.connect();
      }
    }, this.reconnectInterval);
  }

  disconnect(permanent = false) {
    this.shouldReconnect = !permanent;

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    this.isConnected = false;
  }

  send(message) {
    if (this.isConnected && this.ws) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.warn('Cannot send message: WebSocket not connected');
    }
  }

  on(eventType, handler) {
    if (this.eventHandlers[eventType]) {
      this.eventHandlers[eventType].push(handler);
    } else {
      this.eventHandlers[eventType] = [handler];
    }
  }

  off(eventType, handler) {
    if (this.eventHandlers[eventType]) {
      this.eventHandlers[eventType] = this.eventHandlers[eventType].filter(
        (h) => h !== handler
      );
    }
  }

  triggerEvent(eventType, data) {
    if (this.eventHandlers[eventType]) {
      this.eventHandlers[eventType].forEach((handler) => {
        try {
          handler(data);
        } catch (error) {
          console.error(`Error in ${eventType} handler:`, error);
        }
      });
    }
  }

  getStatus() {
    return {
      isConnected: this.isConnected,
      shouldReconnect: this.shouldReconnect,
      url: this.url,
    };
  }
}

// Singleton instances
const trainingLogsWS = new TrainingLogsWebSocket();
const consumptionWS = new GenericWebSocket('/ws/consumption', ['new_consumption']);
const detectionsWS = new GenericWebSocket('/ws/detections', ['new_detection']);

export default trainingLogsWS;
export { consumptionWS, detectionsWS };
