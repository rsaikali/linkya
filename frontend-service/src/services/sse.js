/**
 * Service SSE (Server-Sent Events) pour streaming en temps réel
 * Permet de recevoir les mises à jour en temps réel depuis le backend
 */

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

/**
 * Crée une connexion SSE pour la dernière consommation
 * @param {Function} onData - Callback appelé quand des données arrivent
 * @param {Function} onError - Callback appelé en cas d'erreur
 * @param {number} updateInterval - Intervalle de mise à jour en secondes (défaut: 5)
 * @returns {EventSource} La source d'événements
 */
export const streamLatestConsumption = (
  onData,
  onError,
  updateInterval = 5
) => {
  const url = `${API_BASE_URL}/api/stream/consumption/latest?update_interval=${updateInterval}`;
  const eventSource = new EventSource(url);

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onData(data);
    } catch (error) {
      console.error('Erreur parsing données SSE:', error);
      onError?.(error);
    }
  };

  eventSource.onerror = (error) => {
    console.error('Erreur SSE consommation:', error);
    onError?.(error);
    if (eventSource.readyState === EventSource.CLOSED) {
      eventSource.close();
    }
  };

  return eventSource;
};

/**
 * Crée une connexion SSE pour les détections NILM
 * @param {Function} onData - Callback appelé quand des données arrivent
 * @param {Function} onError - Callback appelé en cas d'erreur
 * @param {number} hours - Nombre d'heures d'historique (défaut: 24)
 * @param {number} updateInterval - Intervalle de mise à jour en secondes (défaut: 10)
 * @returns {EventSource} La source d'événements
 */
export const streamDetections = (
  onData,
  onError,
  hours = 24,
  updateInterval = 10
) => {
  const url = `${API_BASE_URL}/api/stream/detections?hours=${hours}&update_interval=${updateInterval}`;
  const eventSource = new EventSource(url);

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onData(data);
    } catch (error) {
      console.error('Erreur parsing données SSE:', error);
      onError?.(error);
    }
  };

  eventSource.onerror = (error) => {
    console.error('Erreur SSE détections:', error);
    onError?.(error);
    if (eventSource.readyState === EventSource.CLOSED) {
      eventSource.close();
    }
  };

  return eventSource;
};

/**
 * Crée une connexion SSE pour la liste des appareils
 * @param {Function} onData - Callback appelé quand des données arrivent
 * @param {Function} onError - Callback appelé en cas d'erreur
 * @param {number} updateInterval - Intervalle de mise à jour en secondes (défaut: 30)
 * @returns {EventSource} La source d'événements
 */
export const streamAppliances = (
  onData,
  onError,
  updateInterval = 30
) => {
  const url = `${API_BASE_URL}/api/stream/appliances?update_interval=${updateInterval}`;
  const eventSource = new EventSource(url);

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onData(data);
    } catch (error) {
      console.error('Erreur parsing données SSE:', error);
      onError?.(error);
    }
  };

  eventSource.onerror = (error) => {
    console.error('Erreur SSE appareils:', error);
    onError?.(error);
    if (eventSource.readyState === EventSource.CLOSED) {
      eventSource.close();
    }
  };

  return eventSource;
};

/**
 * Ferme proprement une connexion SSE
 * @param {EventSource} eventSource - La source d'événements à fermer
 */
export const closeStream = (eventSource) => {
  if (eventSource && eventSource.readyState !== EventSource.CLOSED) {
    eventSource.close();
  }
};

export default {
  streamLatestConsumption,
  streamDetections,
  streamAppliances,
  closeStream,
};
