import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  Typography,
  Box,
  CircularProgress,
  Alert,
  FormControlLabel,
  Switch,
  Button,
} from '@mui/material';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import annotationPlugin from 'chartjs-plugin-annotation';
import zoomPlugin from 'chartjs-plugin-zoom';
import { Line } from 'react-chartjs-2';
import { ShowChart, ZoomOutMap } from '@mui/icons-material';
import { apiService } from '../services/api';
import { detectionsWS } from '../services/websocket';
import SignatureModal from './SignatureModal';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
  annotationPlugin,
  zoomPlugin
);

const ConsumptionChart = () => {
  const [history, setHistory] = useState(null);
  const [detections, setDetections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showSignatureModal, setShowSignatureModal] = useState(false);
  const [selectedRange, setSelectedRange] = useState(null);
  const [showAnnotations, setShowAnnotations] = useState(true);
  const [isReloading, setIsReloading] = useState(false);
  const chartRef = useRef(null);
  const zoomTimeoutRef = useRef(null);
  const pendingZoomRef = useRef(null); // Pour restaurer le zoom après rechargement

  // Calculer l'intervalle d'agrégation selon la plage de temps visible
  const getOptimalInterval = useCallback((visibleHours) => {
    if (visibleHours <= 1) return 'raw';           // < 1h : données brutes
    if (visibleHours <= 6) return '1 minutes';     // < 6h : 1 minute
    if (visibleHours <= 24) return '5 minutes';    // < 24h : 5 minutes
    if (visibleHours <= 72) return '15 minutes';   // < 3 jours : 15 minutes
    return '1 hour';                                // > 3 jours : 1 heure
  }, []);

  const fetchHistory = useCallback(async (startTime, endTime, customInterval = null) => {
    try {
      // Calculer la durée en heures pour déterminer l'intervalle optimal
      const durationMs = new Date(endTime) - new Date(startTime);
      const durationHours = durationMs / (1000 * 60 * 60);
      
      const interval = customInterval || getOptimalInterval(durationHours);
      
      console.log(`📊 Loading from ${startTime} to ${endTime} with ${interval} interval (${durationHours.toFixed(1)}h)`);
      const result = await apiService.getConsumptionHistory(startTime, endTime, interval);
      setHistory(result);
      setError(null);
    } catch (err) {
      setError('Impossible de récupérer les données');
      console.error(err);
    } finally {
      setLoading(false);
      setIsReloading(false);
    }
  }, [getOptimalInterval]);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    // Fetch initial data - 168h (7 days) ending now
    // Mais avec intervalle optimal pour vue initiale de 48h
    const now = new Date();
    const sevenDaysAgo = new Date(now.getTime() - 168 * 60 * 60 * 1000);
    const optimalIntervalFor48h = getOptimalInterval(48); // Intervalle pour 48h visible
    fetchHistory(sevenDaysAgo.toISOString(), now.toISOString(), optimalIntervalFor48h);
    
    // Fetch initial detections (toutes les détections disponibles)
    const fetchDetections = async () => {
      try {
        const result = await apiService.getDetections(168);
        setDetections(result.detections || []);
      } catch (err) {
        console.error('Failed to fetch detections:', err);
      }
    };
    fetchDetections();

    // Setup WebSocket for real-time detection updates
    const handleNewDetection = (detection) => {
      // Add new detection to the list
      setDetections(prev => [...prev, detection]);
    };

    const handleDetectionStart = (data) => {
    };

    const handleDetectionComplete = async (data) => {
      console.log('✅ Detection job completed:', data);
      // Refresh the entire detection list when job is complete
      try {
        const result = await apiService.getDetections(168);
        setDetections(result.detections || []);
      } catch (err) {
        console.error('Failed to refresh detections after job completion:', err);
      }
    };

    const handleDetectionDeleted = (data) => {
      console.log('🗑️ Detection deleted:', data.detection_id);
      // Remove the deleted detection from the list
      setDetections(prev => prev.filter(d => d.id !== data.detection_id));
    };

    const handleDetectionsCleared = (data) => {
      console.log('🧹 All detections cleared:', data.deleted_count);
      // Clear all detections from the list
      setDetections([]);
    };

    const handleError = (errorData) => {
      console.error('Detections WebSocket error:', errorData);
    };

    // Register event handlers
    detectionsWS.on('new_detection', handleNewDetection);
    detectionsWS.on('detection_start', handleDetectionStart);
    detectionsWS.on('detection_complete', handleDetectionComplete);
    detectionsWS.on('detection_deleted', handleDetectionDeleted);
    detectionsWS.on('detections_cleared', handleDetectionsCleared);
    detectionsWS.on('error', handleError);

    // Connect to WebSocket
    detectionsWS.connect();

    // Cleanup on unmount
    return () => {
      detectionsWS.off('new_detection', handleNewDetection);
      detectionsWS.off('detection_start', handleDetectionStart);
      detectionsWS.off('detection_complete', handleDetectionComplete);
      detectionsWS.off('detection_deleted', handleDetectionDeleted);
      detectionsWS.off('detections_cleared', handleDetectionsCleared);
      detectionsWS.off('error', handleError);
      
      // Clear zoom timeout
      if (zoomTimeoutRef.current) {
        clearTimeout(zoomTimeoutRef.current);
      }
    };
  }, [fetchHistory]);

  // Restaurer le zoom après rechargement des données
  useEffect(() => {
    if (pendingZoomRef.current && history && history.data && history.data.length > 0 && chartRef.current) {
      const { minTime, maxTime } = pendingZoomRef.current;
      
      // Trouver les index correspondant aux timestamps sauvegardés
      const minIndex = history.data.findIndex(d => new Date(d.time).getTime() >= minTime);
      const maxIndex = history.data.findIndex(d => new Date(d.time).getTime() >= maxTime);
      
      const finalMinIndex = minIndex !== -1 ? minIndex : 0;
      const finalMaxIndex = maxIndex !== -1 ? maxIndex : history.data.length - 1;
      
      // Restaurer le zoom
      if (chartRef.current && chartRef.current.scales && chartRef.current.scales.x) {
        chartRef.current.scales.x.min = finalMinIndex;
        chartRef.current.scales.x.max = finalMaxIndex;
        chartRef.current.update('none'); // Update sans animation
      }
      
      pendingZoomRef.current = null;
      console.log('🔍 Zoom restored after reload');
    }
  }, [history]);

  // Fonction pour réinitialiser le zoom
  const handleResetZoom = useCallback(() => {
    if (chartRef.current) {
      chartRef.current.resetZoom();
    }
    // Recharger les données initiales (7 jours avec intervalle optimal pour 48h)
    const now = new Date();
    const sevenDaysAgo = new Date(now.getTime() - 168 * 60 * 60 * 1000);
    const optimalIntervalFor48h = getOptimalInterval(48); // Intervalle pour 48h visible
    setIsReloading(true);
    fetchHistory(sevenDaysAgo.toISOString(), now.toISOString(), optimalIntervalFor48h);
  }, [getOptimalInterval, fetchHistory]);

  // Callback appelé après un zoom ou pan
  const handleZoomPanComplete = ({ chart }) => {
    // Annuler le timeout précédent pour éviter les requêtes multiples
    if (zoomTimeoutRef.current) {
      clearTimeout(zoomTimeoutRef.current);
    }

    // Debounce de 500ms avant de recharger les données
    zoomTimeoutRef.current = setTimeout(() => {
      if (!history || !history.data || history.data.length === 0) return;

      const xScale = chart.scales.x;
      const visibleMin = Math.floor(xScale.min);
      const visibleMax = Math.ceil(xScale.max);

      // Calculer la plage de temps visible
      const minIndex = Math.max(0, visibleMin);
      const maxIndex = Math.min(history.data.length - 1, visibleMax);
      const minTimeStr = history.data[minIndex]?.time;
      const maxTimeStr = history.data[maxIndex]?.time;
      
      // Vérifier que les timestamps sont valides
      if (!minTimeStr || !maxTimeStr) {
        console.warn('Invalid timestamps in visible range');
        return;
      }
      
      const minTime = new Date(minTimeStr);
      const maxTime = new Date(maxTimeStr);
      
      // Vérifier que les dates sont valides
      if (isNaN(minTime.getTime()) || isNaN(maxTime.getTime())) {
        console.warn('Invalid date objects');
        return;
      }
      
      const visibleHours = (maxTime - minTime) / (1000 * 60 * 60);

      console.log(`🔍 Visible range: ${visibleHours.toFixed(2)}h (${minTime.toLocaleTimeString()} → ${maxTime.toLocaleTimeString()})`);

      // Recharger les données avec l'intervalle optimal
      const newInterval = getOptimalInterval(visibleHours);
      const currentInterval = history.interval;

      // Ne recharger que si l'intervalle a changé
      if (newInterval !== currentInterval) {
        console.log(`🔄 Reloading with new interval: ${currentInterval} → ${newInterval}`);
        
        // Sauvegarder la plage visible actuelle (en timestamp) pour la restaurer après rechargement
        pendingZoomRef.current = {
          minTime: minTime.getTime(),
          maxTime: maxTime.getTime(),
        };
        
        setIsReloading(true);
        
        // Calculer la plage avec une marge de 20% de chaque côté pour permettre le pan
        const timeRange = maxTime - minTime;
        const margin = timeRange * 0.2;
        const startTime = new Date(minTime.getTime() - margin).toISOString();
        const endTime = new Date(maxTime.getTime() + margin).toISOString();
        
        fetchHistory(startTime, endTime, newInterval);
      }
    }, 500);
  };

  if (loading && !history) {
    return (
      <Card>
        <CardContent sx={{ textAlign: 'center', py: 4 }}>
          <CircularProgress />
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent>
          <Alert severity="error">{error}</Alert>
        </CardContent>
      </Card>
    );
  }

  if (!history || !history.data || history.data.length === 0) {
    return (
      <Card>
        <CardContent>
          <Alert severity="info">Aucune donnée disponible pour cette période</Alert>
        </CardContent>
      </Card>
    );
  }

  const labels = history.data.map(d => {
    const date = new Date(d.time);
    return date.toLocaleString('fr-FR', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      day: '2-digit',
      month: '2-digit',
      year: '2-digit'
    });
  });

  const powerData = history.data.map(d => d.avg_papp);

  // Calculer l'index de départ pour les dernières 48h (vue initiale)
  const now = new Date();
  const fortyEightHoursAgo = new Date(now.getTime() - 48 * 60 * 60 * 1000);
  const startIndex = history.data.findIndex(d => new Date(d.time) >= fortyEightHoursAgo);
  const initialMinIndex = startIndex !== -1 ? startIndex : 0;

  // Créer une palette de couleurs par appareil
  const getApplianceColor = (applianceName) => {
    // Valeur par défaut si le nom est undefined/null
    const name = applianceName || 'Unknown';
    
    // Générer une couleur unique et cohérente basée sur le nom de l'appareil
    let hash = 0;
    for (let i = 0; i < name.length; i++) {
      hash = name.charCodeAt(i) + ((hash << 5) - hash);
    }
    
    // Utiliser le hash pour choisir une teinte (hue) cohérente
    const hue = Math.abs(hash % 360);
    
    return {
      bg: `hsla(${hue}, 70%, 60%, 0.15)`,
      border: `hsla(${hue}, 70%, 60%, 0.6)`,
      solid: `hsl(${hue}, 70%, 60%)`,
      dark: `hsl(${hue}, 70%, 35%)` // Version sombre pour le texte
    };
  };

  // Créer les annotations pour les périodes de détection
  const createDetectionAnnotations = () => {
    if (!showAnnotations || !detections || detections.length === 0) {
      return {};
    }

    const annotations = {};
    
    // Préparer les détections avec leurs indices de graphique
    const detectionWithIndices = detections
      .filter(d => d.start_time && d.end_time && d.name)
      .map(d => {
        const startTime = new Date(d.start_time).getTime();
        const endTime = new Date(d.end_time).getTime();
        const startIndex = history.data.findIndex(dt => new Date(dt.time).getTime() >= startTime);
        const endIndex = history.data.findIndex(dt => new Date(dt.time).getTime() >= endTime);
        
        return {
          ...d,
          startIndex: startIndex !== -1 ? startIndex : 0,
          endIndex: endIndex !== -1 ? endIndex : history.data.length - 1,
          centerIndex: startIndex !== -1 ? (startIndex + (endIndex !== -1 ? endIndex : history.data.length - 1)) / 2 : 0,
        };
      })
      .filter(d => d.startIndex !== -1)
      .sort((a, b) => a.startIndex - b.startIndex);

    // Calculer le niveau (row) de chaque label pour éviter les superpositions visuelles
    // On considère qu'un label occupe environ 15% de la largeur du graphique autour de son centre
    const labelWidth = history.data.length * 0.15;
    
    const detectionRows = [];
    detectionWithIndices.forEach((detection) => {
      let row = 0;
      const labelStart = detection.centerIndex - labelWidth / 2;
      const labelEnd = detection.centerIndex + labelWidth / 2;
      
      // Trouver la première ligne disponible sans chevauchement de labels
      while (detectionRows[row]) {
        const hasOverlap = detectionRows[row].some(d => {
          const dLabelStart = d.centerIndex - labelWidth / 2;
          const dLabelEnd = d.centerIndex + labelWidth / 2;
          // Chevauchement si les labels se superposent visuellement
          const overlap = labelStart < dLabelEnd && dLabelStart < labelEnd;
          return overlap;
        });
        
        if (!hasOverlap) break;
        row++;
      }
      
      if (!detectionRows[row]) detectionRows[row] = [];
      detectionRows[row].push(detection);
      detection.row = row;
    });

    // Calculer le nombre maximum de lignes nécessaires
    const maxRow = detectionWithIndices.reduce((max, d) => Math.max(max, d.row), 0);

    detectionWithIndices.forEach((detection) => {
      const colors = getApplianceColor(detection.name);
      
      // Les labels sont positionnés AU-DESSUS de la zone de tracé
      // Hauteur estimée d'un label : ~30px
      const labelHeight = 30;
      const rowSpacing = 2;
      // yAdjust négatif pour remonter au-dessus de la zone de tracé
      // Row 0 : -10px (juste au-dessus), row 1 : -42px, row 2 : -74px
      const yAdjust = -30 - (detection.row * (labelHeight + rowSpacing));

      annotations[`detection-${detection.id}`] = {
        type: 'box',
        xMin: detection.startIndex,
        xMax: detection.endIndex,
        backgroundColor: colors.bg,
        borderColor: colors.border,
        borderWidth: 1,
        label: {
          display: true,
          content: `${detection.name}`,
          position: {
            x: 'center',
            y: 'start'
          },
          backgroundColor: 'rgba(255, 255, 255, 0.95)',
          color: colors.dark,
          borderColor: 'rgba(114, 114, 114, 0.95)',
          borderWidth: 0.5,
          borderRadius: 8,
          font: {
            family: 'monospace',
            size: 14,
            weight: 'normal',
          },
          padding: 3,
          yAdjust: yAdjust,
        },
      };
      
    });

    return { annotations, maxRows: maxRow + 1 };
  };

  // Créer la légende des appareils détectés
  const getLegendItems = () => {
    if (!detections || detections.length === 0) return [];
    
    // Grouper par nom d'appareil pour éviter les doublons
    const applianceMap = new Map();
    detections.forEach(detection => {
      if (!applianceMap.has(detection.name)) {
        applianceMap.set(detection.name, {
          name: detection.name,
          color: getApplianceColor(detection.name).solid,
          count: 1,
          totalEnergy: detection.energy_consumed || 0,
        });
      } else {
        const item = applianceMap.get(detection.name);
        item.count += 1;
        item.totalEnergy += detection.energy_consumed || 0;
      }
    });
    
    return Array.from(applianceMap.values());
  };

  const chartData = {
    labels,
    datasets: [
      {
        label: 'Puissance moyenne (VA)',
        data: powerData,
        borderColor: '#BD2A2E',
        backgroundColor: 'rgba(189, 42, 46, 0.1)',
        fill: true,
        tension: 0.4,
        pointRadius: 0,
        pointHoverRadius: 0,
      },
    ],
  };

  // Calculer les annotations et le nombre de lignes nécessaires
  const annotationsData = createDetectionAnnotations();
  const maxRows = annotationsData.maxRows || 0;
  
  // Calculer le padding dynamiquement : hauteur de label (30px) * nombre de lignes + marge (20px)
  const topPadding = showAnnotations && maxRows > 0 ? (maxRows * 32) : 10;

  const options = {
    responsive: true,
    borderWidth:1,
    maintainAspectRatio: false,
    animation: false, // Désactiver les animations pour éviter l'effet troublant lors du zoom
    layout: {
      padding: {
        top: topPadding,
      },
    },
    interaction: {
      mode: 'index',
      intersect: false,
    },
    plugins: {
      annotation: {
        clip: false, // Ne pas clipper les annotations en dehors de la zone
        annotations: annotationsData.annotations,
      },
      legend: {
        display: false,
      },
      title: {
        display: false,
      },
      tooltip: {
        callbacks: {
          label: (context) => {
            return `${context.dataset.label}: ${context.parsed.y.toFixed(0)} VA`;
          },
        },
      },
      zoom: {
        zoom: {
          wheel: {
            enabled: true,
            speed: 0.1,
          },
          pinch: {
            enabled: true,
          },
          mode: 'x',
          onZoomComplete: handleZoomPanComplete,
        },
        pan: {
          enabled: true,
          mode: 'x',
          onPanComplete: handleZoomPanComplete,
        },
        limits: {
          x: {
            min: 0,
            max: history.data.length - 1,
          },
        },
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        title: {
          display: true,
          text: 'Puissance (VA)',
        },
      },
      x: {
        min: initialMinIndex,
        max: history.data.length - 1,
        title: {
          display: false,
          text: 'Temps',
        },
        ticks: {
          maxRotation: 45,
          minRotation: 45,
        },
      },
    },
  };

  return (
    <>
      <Card>
        <CardHeader
          title="Historique de consommation"
          subheader="Utilisez la molette pour zoomer et glisser-déposer pour naviguer"
          avatar={<ShowChart />}
          action={
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <Button
                size="small"
                variant="outlined"
                startIcon={<ZoomOutMap />}
                onClick={handleResetZoom}
                sx={{ textTransform: 'none' }}
              >
                Réinitialiser
              </Button>
              <FormControlLabel
                control={
                  <Switch
                    checked={showAnnotations}
                    onChange={(e) => setShowAnnotations(e.target.checked)}
                    size="small"
                    color="primary"
                  />
                }
                label={
                  <Typography variant="caption" sx={{ fontSize: '0.8rem' }}>
                    Détections
                  </Typography>
                }
                sx={{ ml: 1 }}
              />
              
              {(loading || isReloading) && <CircularProgress size={24} />}
            </Box>
          }
        />
        <CardContent>
          <Box sx={{ height: 400, mb: 3, position: 'relative' }}>
            {isReloading && (
              <Box
                sx={{
                  position: 'absolute',
                  top: 8,
                  right: 8,
                  zIndex: 10,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1,
                  backgroundColor: 'rgba(255, 255, 255, 0.9)',
                  padding: '4px 12px',
                  borderRadius: 1,
                  boxShadow: 1,
                }}
              >
                <CircularProgress size={16} />
                <Typography variant="caption" color="text.secondary">
                  Rechargement...
                </Typography>
              </Box>
            )}
            <Line ref={chartRef} data={chartData} options={options} />
          </Box>

          {getLegendItems().length > 0 && (
            <Box>
              <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1.5, fontWeight: 600 }}>
                Légende des appareils détectés
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
                {getLegendItems().map((item) => (
                  <Box
                    key={item.name}
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 1,
                      px: 1.5,
                      py: 0.75,
                      borderRadius: 1,
                      backgroundColor: 'background.paper',
                      border: '1px solid',
                      borderColor: 'divider',
                    }}
                  >
                    <Box
                      sx={{
                        width: 16,
                        height: 16,
                        borderRadius: 0.5,
                        backgroundColor: item.color,
                      }}
                    />
                    <Typography variant="body2" sx={{ fontWeight: 500 }}>
                      {item.name}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      ({item.count} détection{item.count > 1 ? 's' : ''}, {item.totalEnergy.toFixed(0)} Wh)
                    </Typography>
                  </Box>
                ))}
              </Box>
            </Box>
          )}
        </CardContent>
      </Card>

      {selectedRange && (
        <SignatureModal
          open={showSignatureModal}
          onClose={() => {
            setShowSignatureModal(false);
            setSelectedRange(null);
          }}
          selectedRange={selectedRange}
          onSignatureSaved={() => {
            setShowSignatureModal(false);
            setSelectedRange(null);
            // Optionnellement, refetch les data pour voir les changements
            // Recharger les 7 derniers jours
            const now = new Date();
            const sevenDaysAgo = new Date(now.getTime() - 168 * 60 * 60 * 1000);
            fetchHistory(sevenDaysAgo.toISOString(), now.toISOString());
          }}
        />
      )}
    </>
  );
};

export default ConsumptionChart;
