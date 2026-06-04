import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import { apiService } from '../services/api';
import { detectionsWS, importProgressWS } from '../services/sse';

/**
 * Contexte centralisé pour toutes les données de l'application
 * Source unique de vérité pour : consommation, détections, signatures, appareils
 * Gère également le zoom et la période visible du graphique
 */
const DataContext = createContext();

export const DataProvider = ({ children }) => {
  // ===== États des données =====
  const [rawData, setRawData] = useState(null);
  const [detections, setDetections] = useState([]);
  const [signatures, setSignatures] = useState([]);
  const [appliances, setAppliances] = useState([]);

  // ===== États de chargement =====
  const [loading, setLoading] = useState({
    consumption: true,
    detections: true,
    signatures: true,
    appliances: true,
  });

  const [loadingProgress, setLoadingProgress] = useState(0);

  // ===== États d'erreur =====
  const [errors, setErrors] = useState({
    consumption: null,
    detections: null,
    signatures: null,
    appliances: null,
  });

  // ===== États du graphique (fusionné depuis ChartContext) =====
  const [visibleTimeRange, setVisibleTimeRange] = useState(null);
  const [zoomState, setZoomState] = useState({ min: null, max: null, dataLength: null });

  // ===== État de progression d'import =====
  const [importProgress, setImportProgress] = useState({
    status: 'idle',
    totalLines: 0,
    successCount: 0,
    errorCount: 0,
    progressPercent: 0,
  });

  // ===== Fonctions de chargement =====
  
  const refreshConsumption = useCallback(async () => {
    try {
      setLoading(prev => ({ ...prev, consumption: true }));
      setLoadingProgress(10);
      setErrors(prev => ({ ...prev, consumption: null }));

      setLoadingProgress(30);
      const result = await apiService.getConsumptionHistory('1 minute');
      setLoadingProgress(70);

      setRawData(result);

      // Initialize visible period for last 48 hours
      if (result?.data && result.data.length > 0) {
        const now = new Date();
        const fortyEightHoursAgo = new Date(now.getTime() - 48 * 60 * 60 * 1000);
        const minIndex48h = result.data.findIndex(d => new Date(d.time) >= fortyEightHoursAgo);
        const visibleMin = minIndex48h !== -1 ? minIndex48h : 0;
        const visibleMax = result.data.length - 1;

        setZoomState({
          min: visibleMin,
          max: visibleMax,
          dataLength: result.data.length,
        });

        // Set visible time range for detections filtering
        if (result.data[visibleMin] && result.data[visibleMax]) {
          const startTime = new Date(result.data[visibleMin].time);
          const endTime = new Date(result.data[visibleMax].time);
          setVisibleTimeRange({ startTime, endTime });
        }
      }

      setLoadingProgress(100);
    } catch (err) {
      console.error('Error loading consumption data:', err);
      setErrors(prev => ({ ...prev, consumption: 'Impossible de recuperer les donnees' }));
    } finally {
      setLoading(prev => ({ ...prev, consumption: false }));
    }
  }, []);

  const refreshDetections = useCallback(async () => {
    try {
      setLoading(prev => ({ ...prev, detections: true }));
      setErrors(prev => ({ ...prev, detections: null }));

      const result = await apiService.getDetections();
      const detectionsArray = result?.detections || result || [];
      setDetections(detectionsArray);
    } catch (err) {
      console.error('Error loading detections:', err);
      setErrors(prev => ({ ...prev, detections: 'Impossible de charger les détections' }));
    } finally {
      setLoading(prev => ({ ...prev, detections: false }));
    }
  }, []);

  const refreshSignatures = useCallback(async () => {
    try {
      setLoading(prev => ({ ...prev, signatures: true }));
      setErrors(prev => ({ ...prev, signatures: null }));

      const result = await apiService.getSignatures();
      setSignatures(result.signatures || []);
    } catch (err) {
      console.error('Error loading signatures:', err);
      setErrors(prev => ({ ...prev, signatures: 'Impossible de charger les signatures' }));
    } finally {
      setLoading(prev => ({ ...prev, signatures: false }));
    }
  }, []);

  const refreshAppliances = useCallback(async () => {
    try {
      setLoading(prev => ({ ...prev, appliances: true }));
      setErrors(prev => ({ ...prev, appliances: null }));

      const result = await apiService.getAllAppliances();
      setAppliances(result.appliances || []);
    } catch (err) {
      console.error('Error loading appliances:', err);
      setErrors(prev => ({ ...prev, appliances: 'Unable to load appliances' }));
    } finally {
      setLoading(prev => ({ ...prev, appliances: false }));
    }
  }, []);

  const refreshAll = useCallback(async () => {
    await Promise.all([
      refreshConsumption(),
      refreshDetections(),
      refreshSignatures(),
      refreshAppliances(),
    ]);
  }, [refreshConsumption, refreshDetections, refreshSignatures, refreshAppliances]);

  // ===== Chargement initial =====
  useEffect(() => {
    refreshAll();
  }, [refreshAll]);

  // ===== WebSocket pour les détections =====
  useEffect(() => {
    const handleNewDetection = (detection) => {
      setDetections(prev => [...prev, detection]);
    };

    const handleDetectionComplete = () => {
      refreshDetections();
    };

    const handleDetectionsCleared = () => {
      setDetections([]);
    };

    detectionsWS.on('new_detection', handleNewDetection);
    detectionsWS.on('detection_complete', handleDetectionComplete);
    detectionsWS.on('detections_cleared', handleDetectionsCleared);
    detectionsWS.connect();

    return () => {
      detectionsWS.off('new_detection', handleNewDetection);
      detectionsWS.off('detection_complete', handleDetectionComplete);
      detectionsWS.off('detections_cleared', handleDetectionsCleared);
    };
  }, [refreshDetections]);

  // ===== WebSocket pour l'import de signatures =====
  useEffect(() => {
    const handleImportStart = (data) => {
      setImportProgress({
        status: 'started',
        totalLines: 0,
        successCount: 0,
        errorCount: 0,
        progressPercent: 0,
      });
    };

    const handleImportProgress = (data) => {
      setImportProgress({
        status: 'processing',
        totalLines: data.total_lines || 0,
        successCount: data.success_count || 0,
        errorCount: data.error_count || 0,
        progressPercent: data.progress_percent || 0,
      });
    };

    const handleImportComplete = (data) => {
      setImportProgress({
        status: 'completed',
        totalLines: data.total_lines || 0,
        successCount: data.success_count || 0,
        errorCount: data.error_count || 0,
        progressPercent: 100,
      });

      // Refresh signatures after import
      setTimeout(() => {
        refreshSignatures();
      }, 2000);
    };

    const handleImportError = (data) => {
      console.error('Import error:', data);
      setImportProgress(prev => ({ ...prev, status: 'error' }));
    };

    importProgressWS.on('import_start', handleImportStart);
    importProgressWS.on('import_progress', handleImportProgress);
    importProgressWS.on('import_complete', handleImportComplete);
    importProgressWS.on('import_error', handleImportError);
    importProgressWS.connect();

    return () => {
      importProgressWS.off('import_start', handleImportStart);
      importProgressWS.off('import_progress', handleImportProgress);
      importProgressWS.off('import_complete', handleImportComplete);
      importProgressWS.off('import_error', handleImportError);
    };
  }, [refreshSignatures]);

  // ===== Événements custom window (pour compatibilité) =====
  useEffect(() => {
    const handleSignatureCreated = () => {
      refreshSignatures();
    };

    window.addEventListener('signature-created', handleSignatureCreated);
    return () => {
      window.removeEventListener('signature-created', handleSignatureCreated);
    };
  }, [refreshSignatures]);

  // ===== Détections filtrées selon la période visible =====
  const visibleDetections = useMemo(() => {
    if (!visibleTimeRange || !detections.length) {
      return detections;
    }

    const startTime = visibleTimeRange.startTime.getTime();
    const endTime = visibleTimeRange.endTime.getTime();

    return detections.filter(d => {
      const detectionStart = new Date(d.start_time).getTime();
      const detectionEnd = new Date(d.end_time).getTime();

      // Une détection est visible si elle chevauche la période
      return (detectionStart <= endTime && detectionEnd >= startTime);
    });
  }, [detections, visibleTimeRange]);

  // ===== Valeur du contexte =====
  const value = {
    // Données
    rawData,
    detections,
    signatures,
    appliances,
    visibleDetections,

    // États de chargement
    loading,
    loadingProgress,

    // Erreurs
    errors,

    // Actions de refresh
    refreshConsumption,
    refreshDetections,
    refreshSignatures,
    refreshAppliances,
    refreshAll,

    // État du graphique
    visibleTimeRange,
    setVisibleTimeRange,
    zoomState,
    setZoomState,

    // Progression d'import
    importProgress,
    setImportProgress,
  };

  return <DataContext.Provider value={value}>{children}</DataContext.Provider>;
};

export const useData = () => {
  const context = useContext(DataContext);
  if (!context) {
    throw new Error('useData must be used within a DataProvider');
  }
  return context;
};
