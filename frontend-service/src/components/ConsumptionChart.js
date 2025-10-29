import React, { useState, useEffect, useRef } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  Typography,
  Box,
  CircularProgress,
  Alert,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  FormControlLabel,
  Switch,
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
import { Line } from 'react-chartjs-2';
import { ShowChart } from '@mui/icons-material';
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
  annotationPlugin
);

const ConsumptionChart = () => {
  const [history, setHistory] = useState(null);
  const [detections, setDetections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [timeRange, setTimeRange] = useState(24);
  const [showSignatureModal, setShowSignatureModal] = useState(false);
  const [selectedRange, setSelectedRange] = useState(null);
  const [showAnnotations, setShowAnnotations] = useState(true);
  const chartRef = useRef(null);
  const selectionStartRef = useRef(null);

  // Déterminer l'intervalle d'agrégation selon la période
  const getIntervalForTimeRange = (range) => {
    if (range <= 6) {
      // 1 hour ou moins: pas d'agrégation (données brutes)
      return 'raw';
    } else if (range <= 24) {
      // Jusqu'à 24 heures: agrégation à 15 minutes
      return '1 minutes';
    } else if (range <= 48) {
      // Jusqu'à 48 heures: agrégation à 30 minutes
      return '1 minutes';
    } else {
      // Plus de 48 heures: agrégation à 1 heure
      return '5 minutes';
    }
  };

  const fetchHistory = async () => {
    try {
      const interval = getIntervalForTimeRange(timeRange);
      const result = await apiService.getConsumptionHistory(timeRange, interval);
      setHistory(result);
      setError(null);
    } catch (err) {
      setError('Impossible de récupérer les données');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    // Fetch initial data
    fetchHistory();
    
    // Fetch initial detections
    const fetchDetections = async () => {
      try {
        const result = await apiService.getDetections(timeRange);
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
        const result = await apiService.getDetections(timeRange);
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

    // Cleanup on unmount or timeRange change
    return () => {
      detectionsWS.off('new_detection', handleNewDetection);
      detectionsWS.off('detection_start', handleDetectionStart);
      detectionsWS.off('detection_complete', handleDetectionComplete);
      detectionsWS.off('detection_deleted', handleDetectionDeleted);
      detectionsWS.off('detections_cleared', handleDetectionsCleared);
      detectionsWS.off('error', handleError);
    };
  }, [timeRange]);

  // Gestion du clic sur le graphique pour sélectionner une plage
  const handleChartClick = (dataIndex) => {
    if (selectionStartRef.current === null) {
      // Premier clic - début de la sélection
      selectionStartRef.current = dataIndex;
    } else {
      // Deuxième clic - fin de la sélection
      const startIndex = Math.min(selectionStartRef.current, dataIndex);
      const endIndex = Math.max(selectionStartRef.current, dataIndex);
      
      const startTime = new Date(history.data[startIndex].time);
      const endTime = new Date(history.data[endIndex].time);
      
      setSelectedRange({
        startIndex,
        endIndex,
        startTime,
        endTime,
      });
      
      setShowSignatureModal(true);
      selectionStartRef.current = null;
    }
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
    layout: {
      padding: {
        top: topPadding,
      },
    },
    onClick: (event, elements) => {
      // Extraire l'index du point cliqué
      if (elements.length > 0) {
        handleChartClick(elements[0].index);
      }
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
          subheader={
            selectionStartRef.current !== null
              ? "💡 Cliquez sur un deuxième point pour finaliser la sélection"
              : "Cliquez sur deux points du graphique pour créer une signature"
          }
          avatar={<ShowChart />}
          action={
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
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
              <FormControl size="small" sx={{ minWidth: 150 }}>
                <InputLabel>Période</InputLabel>
                <Select
                  value={timeRange}
                  label="Période"
                  onChange={(e) => setTimeRange(e.target.value)}
                >
                  <MenuItem value={1/60}>1 minute</MenuItem>
                  <MenuItem value={15/60}>15 minutes</MenuItem>
                  <MenuItem value={30/60}>30 minutes</MenuItem>
                  <MenuItem value={1}>1 heure</MenuItem>
                  <MenuItem value={2}>2 heures</MenuItem>
                  <MenuItem value={4}>4 heures</MenuItem>
                  <MenuItem value={6}>6 heures</MenuItem>
                  <MenuItem value={12}>12 heures</MenuItem>
                  <MenuItem value={24}>24 heures</MenuItem>
                  <MenuItem value={48}>48 heures</MenuItem>
                  <MenuItem value={168}>7 jours</MenuItem>
                </Select>
              </FormControl>
              
              {loading && <CircularProgress size={24} />}
            </Box>
          }
        />
        <CardContent>
          <Box sx={{ height: 400, mb: 3, cursor: 'crosshair' }}>
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
            fetchHistory();
          }}
        />
      )}
    </>
  );
};

export default ConsumptionChart;
