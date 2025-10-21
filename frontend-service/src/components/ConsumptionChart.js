import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
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
import { apiService } from '../services/api';
import { streamDetections, closeStream } from '../services/sse';

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
  const [timeRange, setTimeRange] = useState(24);
  const [detectionEventSource, setDetectionEventSource] = useState(null);

  const fetchHistory = async () => {
    try {
      const interval = timeRange <= 6 ? '1 minute' : '5 minutes';
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

  useEffect(() => {
    fetchHistory();

    const source = streamDetections(
      (data) => {
        setDetections(data.detections || []);
      },
      (error) => {
        console.warn('SSE détections failed:', error);
      },
      timeRange,
      10
    );
    setDetectionEventSource(source);

    const historyInterval = setInterval(fetchHistory, 30000);

    return () => {
      clearInterval(historyInterval);
      if (detectionEventSource) {
        closeStream(detectionEventSource);
      }
    };
  }, [timeRange]);

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
      day: '2-digit',
      month: '2-digit',
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
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: 'index',
      intersect: false,
    },
    plugins: {
      legend: {
        position: 'top',
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
          display: true,
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
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h6" component="h2">
            Historique de consommation
          </Typography>
          <FormControl size="small" sx={{ minWidth: 150 }}>
            <InputLabel>Période</InputLabel>
            <Select
              value={timeRange}
              label="Période"
              onChange={(e) => setTimeRange(e.target.value)}
            >
              <MenuItem value={1}>1 heure</MenuItem>
              <MenuItem value={6}>6 heures</MenuItem>
              <MenuItem value={12}>12 heures</MenuItem>
              <MenuItem value={24}>24 heures</MenuItem>
              <MenuItem value={48}>48 heures</MenuItem>
              <MenuItem value={168}>7 jours</MenuItem>
            </Select>
          </FormControl>
        </Box>

        <Box sx={{ height: 400, mb: 3 }}>
          <Line data={chartData} options={options} />
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
  );
};

export default ConsumptionChart;
