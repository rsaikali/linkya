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
  // Get the latest consumption
  getLatestConsumption: async () => {
    try {
      const response = await api.get('/api/consumption/latest');
      return response.data;
    } catch (error) {
      console.error('Error fetching latest consumption:', error);
      throw error;
    }
  },

  // Get consumption history
  getConsumptionHistory: async (interval = 'auto') => {
    try {
      const params = { interval };

      const response = await api.get('/api/consumption/history', { params });
      return response.data;
    } catch (error) {
      console.error('Error fetching history:', error);
      throw error;
    }
  },

  // Get all appliances
  getAllAppliances: async () => {
    try {
      const response = await api.get('/api/appliances');
      return response.data;
    } catch (error) {
      console.error('Error fetching appliances:', error);
      throw error;
    }
  },

  // Get detections
  getDetections: async () => {
    try {
      // Fetch all detections
      const response = await api.get('/api/detections');
      return response.data;
    } catch (error) {
      console.error('Error fetching detections:', error);
      throw error;
    }
  },

  // Get signatures
  getSignatures: async () => {
    try {
      const response = await api.get('/api/signatures');
      return response.data;
    } catch (error) {
      console.error('Error fetching signatures:', error);
      throw error;
    }
  },

  // Create a new appliance signature
  createSignature: async (signatureData) => {
    try {
      const response = await api.post('/api/signatures', signatureData);
      return response.data;
    } catch (error) {
      console.error('Error creating signature:', error);
      throw error;
    }
  },

  // Validate a detection (mark as correct)
  validateDetection: async (detectionId) => {
    try {
      const response = await api.patch(`/api/detections/${detectionId}/validate`);
      return response.data;
    } catch (error) {
      console.error('Error validating detection:', error);
      throw error;
    }
  },

  // Invalidate a detection (mark as incorrect)
  invalidateDetection: async (detectionId) => {
    try {
      const response = await api.patch(`/api/detections/${detectionId}/invalidate`);
      return response.data;
    } catch (error) {
      console.error('Error invalidating detection:', error);
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
      console.error('Error reassigning detection:', error);
      throw error;
    }
  },

  // Export all signatures as CSV
  exportSignatures: async () => {
    try {
      const response = await api.get('/api/signatures/export', {
        responseType: 'blob',
      });
      return response.data;
    } catch (error) {
      console.error('Error exporting signatures:', error);
      throw error;
    }
  },

  // Import signatures from a CSV file
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
      console.error('Error importing signatures:', error);
      throw error;
    }
  },

  // Toggle HA publishing for an appliance
  toggleHaPublish: async (applianceId, enabled) => {
    try {
      const response = await api.patch(`/api/appliances/${applianceId}/ha-publish`, { enabled });
      return response.data;
    } catch (error) {
      console.error('Error toggling HA publish:', error);
      throw error;
    }
  },

  // Delete all AI models (database and files)
  deleteAllModels: async () => {
    try {
      const response = await api.delete('/api/nilm/models');
      return response.data;
    } catch (error) {
      console.error('Error deleting models:', error);
      throw error;
    }
  },
};

export default api;
