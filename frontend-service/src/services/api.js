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
  getConsumptionHistory: async (hours = 24, interval = '5 minutes') => {
    try {
      const response = await api.get('/api/consumption/history', {
        params: { hours, interval },
      });
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
};

export default api;
