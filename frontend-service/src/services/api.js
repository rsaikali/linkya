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

  // Récupérer les détections avec pagination optionnelle
  getDetections: async (hours = 24, page = null, perPage = null) => {
    try {
      const params = {};
      // Si hours est null, on envoie 0 pour signifier "toutes"
      if (hours !== null) {
        params.hours = hours;
      } else {
        params.hours = 0;
      }
      if (page !== null) params.page = page;
      if (perPage !== null) params.per_page = perPage;
      
      const response = await api.get('/api/detections', { params });
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

  // Modifier un appareil (nom et/ou description)
  updateAppliance: async (applianceId, { name, description }) => {
    try {
      const response = await api.patch(`/api/appliances/${applianceId}`, {
        name,
        description,
      });
      return response.data;
    } catch (error) {
      console.error('Erreur lors de la modification de l\'appareil:', error);
      throw error;
    }
  },

  // Supprimer un appareil
  deleteAppliance: async (applianceId) => {
    try {
      const response = await api.delete(`/api/appliances/${applianceId}`);
      return response.data;
    } catch (error) {
      console.error('Erreur lors de la suppression de l\'appareil:', error);
      throw error;
    }
  },
};

export default api;
