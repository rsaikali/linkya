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
import { apiService } from '../services/api';
import { consumptionWS } from '../services/websocket';

const LatestConsumption = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [wsConnected, setWsConnected] = useState(false);

  useEffect(() => {
    // Fetch initial data
    const fetchLatestConsumption = async () => {
      try {
        const result = await apiService.getLatestConsumption();
        setData(result);
        setError(null);
        setLoading(false);
      } catch (err) {
        setError('Impossible de récupérer les données de consommation');
        console.error(err);
        setLoading(false);
      }
    };

    fetchLatestConsumption();

    // Setup WebSocket for real-time consumption updates
    const handleNewConsumption = (consumptionData) => {
      console.log('📊 New consumption data received:', consumptionData);
      setData(consumptionData);
      setError(null);
    };

    const handleConnected = () => {
      console.log('✅ Consumption WebSocket connected');
      setWsConnected(true);
    };

    const handleDisconnected = () => {
      console.log('🔌 Consumption WebSocket disconnected');
      setWsConnected(false);
    };

    const handleError = (errorData) => {
      console.error('WebSocket error:', errorData);
      setWsConnected(false);
    };

    // Register event handlers
    consumptionWS.on('new_consumption', handleNewConsumption);
    consumptionWS.on('connected', handleConnected);
    consumptionWS.on('disconnected', handleDisconnected);
    consumptionWS.on('error', handleError);

    // Connect to WebSocket
    consumptionWS.connect();

    // Check initial connection state
    const status = consumptionWS.getStatus();
    setWsConnected(status.isConnected);

    // Cleanup on unmount
    return () => {
      consumptionWS.off('new_consumption', handleNewConsumption);
      consumptionWS.off('connected', handleConnected);
      consumptionWS.off('disconnected', handleDisconnected);
      consumptionWS.off('error', handleError);
      // Don't disconnect permanently - other components might use it
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
    if (!isoString) return 'N/A';
    
    try {
      const date = new Date(isoString);
      if (isNaN(date.getTime())) {
        console.warn('Date invalide:', isoString);
        return 'Date invalide';
      }
      return date.toLocaleString('fr-FR');
    } catch (error) {
      console.error('Erreur de formatage de date:', error, isoString);
      return 'Erreur';
    }
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
              label={wsConnected ? 'Live' : 'Loading'}
              size="small"
              variant="filled"
              color={wsConnected ? 'success' : 'warning'}
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
                  {data.papp} W
                </Typography>
                <Typography variant="body2">
                  Puissance apparente
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
                  {data.temperature ? data.temperature.toFixed(1) + "°C" : 'N/A'}
                </Typography>
                <Typography variant="body2">
                  Température extérieure
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
