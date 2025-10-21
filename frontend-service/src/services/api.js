import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Services API
export const apiService = {
  // Récupérer la dernière consommation
  getLatestConsumption: async () => {
    try {
      const response = await api.get('/api/consumption/latest');
      return response.data;
    } catch (error) {
      console.error('Erreur lors de la récupération de la dernière consommation:', error);
      throw error;
    }
  },

  // Récupérer l'historique de consommation
  getConsumptionHistory: async (timeRange = 24, interval = '5 minutes') => {
    try {
      const params = {};
      
      // Convertir les courtes périodes en minutes
      if (timeRange < 1) {
        // Utiliser Math.ceil pour éviter les problèmes d'arrondi
        params.minutes = Math.ceil(timeRange * 60);
      } else {
        params.hours = Math.ceil(timeRange);
      }
      params.interval = interval;
      
      const response = await api.get('/api/consumption/history', { params });
      return response.data;
    } catch (error) {
      console.error('Erreur lors de la récupération de l\'historique:', error);
      throw error;
    }
  },

  // Récupérer tous les appareils
  getAllAppliances: async () => {
    try {
      const response = await api.get('/api/appliances');
      return response.data;
    } catch (error) {
      console.error('Erreur lors de la récupération des appareils:', error);
      throw error;
    }
  },

  // Récupérer les détections
  getDetections: async (hours = 24) => {
    try {
      const response = await api.get('/api/detections', {
        params: { hours },
      });
      return response.data;
    } catch (error) {
      console.error('Erreur lors de la récupération des détections:', error);
      throw error;
    }
  },

  // Créer une nouvelle signature d'appareil
  createSignature: async (signatureData) => {
    try {
      const response = await api.post('/api/signatures', signatureData);
      return response.data;
    } catch (error) {
      console.error('Erreur lors de la création de la signature:', error);
      throw error;
    }
  },
};

export default api;
