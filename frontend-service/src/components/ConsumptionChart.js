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
import { streamDetections, closeStream } from '../services/sse';
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
  const detectionEventSourceRef = useRef(null);
  const historyIntervalRef = useRef(null);
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
    // Fetch initial
    fetchHistory();

    // Fermer les connexions SSE existantes
    if (detectionEventSourceRef.current) {
      closeStream(detectionEventSourceRef.current);
    }

    // Polling régulier pour graphique glissant
    // Pour courtes périodes: polling rapide (1 seconde)
    // Pour longues périodes: polling lent (30 secondes)
    const pollInterval = timeRange <= 1 ? 1000 : timeRange <= 6 ? 5000 : 30000;
    historyIntervalRef.current = setInterval(fetchHistory, pollInterval);

    // Stream pour détections (moins critique, update toutes les 10s)
    const detectionSource = streamDetections(
      (data) => {
        setDetections(data.detections || []);
      },
      (error) => {
        console.warn('SSE détections failed:', error);
      },
      timeRange,
      10
    );
    detectionEventSourceRef.current = detectionSource;

    return () => {
      if (historyIntervalRef.current) {
        clearInterval(historyIntervalRef.current);
      }
      if (detectionEventSourceRef.current) {
        closeStream(detectionEventSourceRef.current);
      }
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
    // Générer une couleur unique et cohérente basée sur le nom de l'appareil
    let hash = 0;
    for (let i = 0; i < applianceName.length; i++) {
      hash = applianceName.charCodeAt(i) + ((hash << 5) - hash);
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
      console.log('📊 Annotations désactivées ou pas de détections');
      return {};
    }

    const annotations = {};

    detections.forEach((detection) => {
      // Les détections ont directement start_time et end_time
      if (!detection.start_time || !detection.end_time) {
        console.log(`📊 Détection ${detection.id} sans timestamps`);
        return;
      }

      const startTime = new Date(detection.start_time).getTime();
      const endTime = new Date(detection.end_time).getTime();
      
      // Trouver les indices correspondants dans les données
      const startIndex = history.data.findIndex(d => new Date(d.time).getTime() >= startTime);
      const endIndex = history.data.findIndex(d => new Date(d.time).getTime() >= endTime);
      
      if (startIndex === -1) {
        console.log(`📊 Détection ${detection.id} (${detection.name}) hors période graphique`);
        return;
      }
      
      const colors = getApplianceColor(detection.name);

      annotations[`detection-${detection.id}`] = {
        type: 'box',
        xMin: startIndex,
        xMax: endIndex !== -1 ? endIndex : history.data.length - 1,
        backgroundColor: colors.bg,
        borderColor: colors.border,
        borderWidth: 1,
        label: {
          display: true,
          content: `${detection.name} (${detection.avg_power?.toFixed(0)} W)`,
          position: {
            x: 'center',
            y: 'start'
          },
          backgroundColor: 'rgba(255, 255, 255, 0.95)',
          color: colors.dark,
          borderColor: colors.solid,
          borderWidth: 2,
          borderRadius: 4,
          font: {
            size: 11,
            weight: 'bold',
          },
          padding: 6,
          yAdjust: 0,
        },
      };
      
      console.log(`📊 Annotation créée pour ${detection.name} (${startIndex} → ${endIndex})`);
    });

    console.log(`📊 Total annotations créées: ${Object.keys(annotations).length}`);
    return annotations;
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

  const options = {
    responsive: true,
    borderWidth:1,
    maintainAspectRatio: false,
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
      annotation: {
        annotations: createDetectionAnnotations(),
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
