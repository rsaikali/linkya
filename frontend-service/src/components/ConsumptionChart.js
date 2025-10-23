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
  Chip,
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
  Filler
);

const ConsumptionChart = () => {
  const [history, setHistory] = useState(null);
  const [detections, setDetections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [timeRange, setTimeRange] = useState(15/60);
  const [showSignatureModal, setShowSignatureModal] = useState(false);
  const [selectedRange, setSelectedRange] = useState(null);
  const detectionEventSourceRef = useRef(null);
  const historyIntervalRef = useRef(null);
  const chartRef = useRef(null);
  const selectionStartRef = useRef(null);

  // Déterminer l'intervalle d'agrégation selon la période
  const getIntervalForTimeRange = (range) => {
    if (range <= 1) {
      // 1 hour ou moins: pas d'agrégation (données brutes)
      return 'raw';
    } else if (range <= 6) {
      // Jusqu'à 6 heures: agrégation à 5 minutes
      return '1 minutes';
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

          {detections.length > 0 && (
            <Box>
              <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
                Appareils détectés ({detections.length})
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {detections.map((detection) => (
                  <Chip
                    key={detection.id}
                    label={`${detection.name} (${detection.avg_power?.toFixed(0)} W)`}
                    size="small"
                    color="primary"
                    variant="outlined"
                    sx={{ fontWeight: 500 }}
                  />
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
