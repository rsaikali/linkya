import axios from 'axios';

// API URL configuration
// In production, use relative URLs to the same origin
// In development, use REACT_APP_API_URL to connect to backend
const API_BASE_URL = process.env.REACT_APP_API_URL || '';

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
  getConsumptionHistory: async (startTime, endTime, interval = 'auto') => {
    try {
      const params = {};
      
      // N'ajouter les paramètres que s'ils sont fournis
      if (startTime !== null && startTime !== undefined) {
        params.start_time = startTime;
      }
      if (endTime !== null && endTime !== undefined) {
        params.end_time = endTime;
      }
      if (interval) {
        params.interval = interval;
      }
      
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
      const params = {};
      // Si hours est null, on envoie 0 pour signifier "toutes"
      if (hours !== null) {
        params.hours = hours;
      } else {
        params.hours = 0;
      }
      
      const response = await api.get('/api/detections', { params });
      return response.data;
    } catch (error) {
      console.error('Erreur lors de la récupération des détections:', error);
      throw error;
    }
  },

  // Récupérer les signatures
  getSignatures: async () => {
    try {
      const response = await api.get('/api/signatures');
      return response.data;
    } catch (error) {
      console.error('Erreur lors de la récupération des signatures:', error);
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

  // Valider une détection (marquer comme correcte)
  validateDetection: async (detectionId) => {
    try {
      const response = await api.patch(`/api/detections/${detectionId}/validate`);
      return response.data;
    } catch (error) {
      console.error('Erreur lors de la validation de la détection:', error);
      throw error;
    }
  },

  // Invalider une détection (marquer comme incorrecte)
  invalidateDetection: async (detectionId) => {
    try {
      const response = await api.patch(`/api/detections/${detectionId}/invalidate`);
      return response.data;
    } catch (error) {
      console.error('Erreur lors de l\'invalidation de la détection:', error);
      throw error;
    }
  },

  // Reassign a detection to the correct appliance
  reassignDetection: async (detectionId, applianceName) => {
    try {
      const response = await api.patch(
        `/api/detections/${detectionId}/reassign`,
        { appliance_name: applianceName }
      );
      return response.data;
    } catch (error) {
      console.error('Erreur lors de la réassignation de la détection:', error);
      throw error;
    }
  },

  // Exporter toutes les signatures en CSV
  exportSignatures: async () => {
    try {
      const response = await api.get('/api/signatures/export', {
        responseType: 'blob',
      });
      return response.data;
    } catch (error) {
      console.error('Erreur lors de l\'export des signatures:', error);
      throw error;
    }
  },

  // Importer des signatures depuis un fichier CSV
  importSignatures: async (file) => {
    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await api.post('/api/signatures/import', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      return response.data;
    } catch (error) {
      console.error('Erreur lors de l\'import des signatures:', error);
      throw error;
    }
  },

  // Delete all AI models (database and files)
  deleteAllModels: async () => {
    try {
      const response = await api.delete('/api/nilm/models');
      return response.data;
    } catch (error) {
      console.error('Erreur lors de la suppression des modèles:', error);
      throw error;
    }
  },
};

export default api;
