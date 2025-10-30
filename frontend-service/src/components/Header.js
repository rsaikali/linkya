import React, { useState, useEffect, useRef } from 'react';
import {
  AppBar,
  Toolbar,
  Typography,
  Box,
  Chip,
  Tooltip,
  keyframes,
} from '@mui/material';
import {
  ElectricBolt,
  ThermostatAuto,
  AccessTime,
  FiberManualRecord,
} from '@mui/icons-material';
import { apiService } from '../services/api';
import { consumptionWS } from '../services/websocket';

// Animation de pulsation douce
const pulse = keyframes`
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.5;
    transform: scale(1.2);
  }
`;

const Header = () => {
  const [data, setData] = useState(null);
  const [isUpdating, setIsUpdating] = useState(false);
  const updateTimeoutRef = useRef(null);

  useEffect(() => {
    // Fetch initial data
    const fetchLatestConsumption = async () => {
      try {
        const result = await apiService.getLatestConsumption();
        setData(result);
      } catch (err) {
        console.error('Error fetching consumption:', err);
      }
    };

    fetchLatestConsumption();

    // Setup WebSocket for real-time consumption updates
    const handleNewConsumption = (consumptionData) => {
      setData(consumptionData);
      
      // Déclencher l'animation de mise à jour
      setIsUpdating(true);
      
      // Arrêter l'animation après 800ms
      if (updateTimeoutRef.current) {
        clearTimeout(updateTimeoutRef.current);
      }
      updateTimeoutRef.current = setTimeout(() => {
        setIsUpdating(false);
      }, 800);
    };

    const handleConnected = () => {
      console.log('✅ Consumption WebSocket connected');
    };

    const handleDisconnected = () => {
      console.log('🔌 Consumption WebSocket disconnected');
    };

    const handleError = (errorData) => {
      console.error('WebSocket error:', errorData);
    };

    // Register event handlers
    consumptionWS.on('new_consumption', handleNewConsumption);
    consumptionWS.on('connected', handleConnected);
    consumptionWS.on('disconnected', handleDisconnected);
    consumptionWS.on('error', handleError);

    // Connect to WebSocket
    consumptionWS.connect();

    // Cleanup on unmount
    return () => {
      consumptionWS.off('new_consumption', handleNewConsumption);
      consumptionWS.off('connected', handleConnected);
      consumptionWS.off('disconnected', handleDisconnected);
      consumptionWS.off('error', handleError);
      
      // Nettoyer le timeout
      if (updateTimeoutRef.current) {
        clearTimeout(updateTimeoutRef.current);
      }
    };
  }, []);

  const formatDate = (isoString) => {
    if (!isoString) return 'N/A';
    
    try {
      const date = new Date(isoString);
      if (isNaN(date.getTime())) return 'N/A';
      return date.toLocaleTimeString('fr-FR', { 
        hour: '2-digit', 
        minute: '2-digit',
        second: '2-digit'
      });
    } catch (error) {
      return 'N/A';
    }
  };

  const formatFullDate = (isoString) => {
    if (!isoString) return 'N/A';
    
    try {
      const date = new Date(isoString);
      if (isNaN(date.getTime())) return 'N/A';
      return date.toLocaleString('fr-FR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      });
    } catch (error) {
      return 'N/A';
    }
  };

  return (
    <AppBar position="static" elevation={2}>
      <Toolbar sx={{ gap: 2 }}>
        {/* Logo et titre */}
        <ElectricBolt sx={{ fontSize: 28 }} />
        <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
          Linkya - Monitoring Linky & NILM
        </Typography>

        {/* Informations en temps réel */}
        {data && (
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
            {/* Date et heure */}
            <Tooltip title={`Dernière mise à jour: ${formatFullDate(data.time)}`}>
              <Chip
                icon={<AccessTime sx={{ fontSize: 18 }} />}
                label={formatDate(data.time)}
                variant="filled"
                sx={{
                  bgcolor: 'rgba(255, 255, 255, 0.15)',
                  color: 'white',
                  fontWeight: 'bold',
                  fontSize: '0.85rem',
                  '& .MuiChip-icon': { color: 'white' },
                }}
              />
            </Tooltip>

            {/* Puissance */}
            <Tooltip title="Puissance apparente">
              <Chip
                icon={<ElectricBolt sx={{ fontSize: 18 }} />}
                label={`${data.papp} W`}
                variant="filled"
                sx={{
                  bgcolor: 'rgba(255, 255, 255, 0.15)',
                  color: 'white',
                  fontWeight: 'bold',
                  fontSize: '0.9rem',
                  '& .MuiChip-icon': { color: 'white' },
                }}
              />
            </Tooltip>

            {/* Température */}
            {data.temperature && (
              <Tooltip title="Température extérieure">
                <Chip
                  icon={<ThermostatAuto sx={{ fontSize: 18 }} />}
                  label={`${data.temperature.toFixed(1)}°C`}
                  variant="filled"
                  sx={{
                    bgcolor: 'rgba(255, 255, 255, 0.15)',
                    color: 'white',
                    fontWeight: 'bold',
                    fontSize: '0.9rem',
                    '& .MuiChip-icon': { color: 'white' },
                  }}
                />
              </Tooltip>
            )}

            {/* Indicateur de mise à jour clignotant */}
            <Tooltip title={isUpdating ? 'Mise à jour en cours...' : 'En attente de données'}>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: 32,
                  height: 32,
                  borderRadius: '50%',
                  bgcolor: 'transparent',
                  animation: isUpdating ? `${pulse} 0.6s ease-in-out infinite` : 'none',
                }}
              >
                <FiberManualRecord
                  sx={{
                    fontSize: 16,
                    color: isUpdating ? 'white' : 'transparent',
                    transition: 'color 0.1s linear',
                  }}
                />
              </Box>
            </Tooltip>
          </Box>
        )}
      </Toolbar>
    </AppBar>
  );
};

export default Header;
