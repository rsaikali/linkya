import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  CircularProgress,
  Alert,
  Grid,
  Chip,
} from '@mui/material';
import {
  ElectricBolt,
  ThermostatAuto,
  AccessTime,
  SignalCellularAlt,
} from '@mui/icons-material';
import { streamLatestConsumption, closeStream } from '../services/sse';
import { apiService } from '../services/api';

const LatestConsumption = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [eventSource, setEventSource] = useState(null);
  const [updateMethod, setUpdateMethod] = useState('sse');

  useEffect(() => {
    const connectSSE = () => {
      try {
        const source = streamLatestConsumption(
          (data) => {
            setData(data);
            setError(null);
            setLoading(false);
            setUpdateMethod('sse');
          },
          (error) => {
            console.warn('SSE failed, falling back to polling:', error);
            fallbackToPolling();
          },
          1
        );
        setEventSource(source);
      } catch (err) {
        console.warn('SSE not supported, falling back to polling:', err);
        fallbackToPolling();
      }
    };

    const fallbackToPolling = () => {
      const fetchLatestConsumption = async () => {
        try {
          const result = await apiService.getLatestConsumption();
          setData(result);
          setError(null);
          setUpdateMethod('polling');
        } catch (err) {
          setError('Impossible de récupérer les données de consommation');
          console.error(err);
        } finally {
          setLoading(false);
        }
      };

      fetchLatestConsumption();
      const interval = setInterval(fetchLatestConsumption, 1000);
      setEventSource({ interval });
      return interval;
    };

    connectSSE();

    return () => {
      if (eventSource) {
        if (eventSource.close) {
          closeStream(eventSource);
        } else if (eventSource.interval) {
          clearInterval(eventSource.interval);
        }
      }
    };
  }, []);

  if (loading && !data) {
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

  if (!data) {
    return (
      <Card>
        <CardContent>
          <Alert severity="info">Aucune donnée disponible</Alert>
        </CardContent>
      </Card>
    );
  }

  const formatDate = (isoString) => {
    const date = new Date(isoString);
    return date.toLocaleString('fr-FR');
  };

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6" component="h2">
            Consommation actuelle
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <Chip
              icon={<AccessTime />}
              label={formatDate(data.time)}
              size="small"
              color="primary"
              variant="outlined"
            />
            <Chip
              icon={<SignalCellularAlt />}
              label={updateMethod === 'sse' ? 'Live (SSE)' : 'Polling (5s)'}
              size="small"
              variant="filled"
              color={updateMethod === 'sse' ? 'success' : 'warning'}
              sx={{ fontSize: '0.75rem' }}
            />
          </Box>
        </Box>

        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                p: 2,
                bgcolor: 'primary.main',
                borderRadius: 2,
                color: 'white',
              }}
            >
              <ElectricBolt sx={{ fontSize: 48, mr: 2 }} />
              <Box>
                <Typography variant="h3" component="div" fontWeight="bold">
                  {data.papp}
                </Typography>
                <Typography variant="body2">
                  Puissance apparente (VA)
                </Typography>
              </Box>
            </Box>
          </Grid>

          <Grid item xs={12} md={6}>
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                p: 2,
                bgcolor: 'secondary.main',
                borderRadius: 2,
                color: 'white',
              }}
            >
              <ThermostatAuto sx={{ fontSize: 48, mr: 2 }} />
              <Box>
                <Typography variant="h3" component="div" fontWeight="bold">
                  {data.temperature ? data.temperature.toFixed(1) : 'N/A'}
                </Typography>
                <Typography variant="body2">
                  Température (°C)
                </Typography>
              </Box>
            </Box>
          </Grid>

          <Grid item xs={12} md={4}>
            <Box sx={{ textAlign: 'center', p: 2 }}>
              <Typography variant="h5" color="primary" fontWeight="bold">
                {(data.hchp / 1000).toFixed(2)}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Index Heures Pleines (kWh)
              </Typography>
            </Box>
          </Grid>

          <Grid item xs={12} md={4}>
            <Box sx={{ textAlign: 'center', p: 2 }}>
              <Typography variant="h5" color="primary" fontWeight="bold">
                {(data.hchc / 1000).toFixed(2)}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Index Heures Creuses (kWh)
              </Typography>
            </Box>
          </Grid>

          <Grid item xs={12} md={4}>
            <Box sx={{ textAlign: 'center', p: 2 }}>
              <Chip
                label={data.libelle_tarif || 'N/A'}
                color="secondary"
                sx={{ fontWeight: 'bold' }}
              />
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                Tarif actuel
              </Typography>
            </Box>
          </Grid>
        </Grid>
      </CardContent>
    </Card>
  );
};

export default LatestConsumption;
