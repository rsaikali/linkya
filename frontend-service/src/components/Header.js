import React, { useState, useEffect, useRef } from 'react';
import {
  AppBar,
  Toolbar,
  Typography,
  Box,
  Chip,
  Tooltip,
  IconButton,
  keyframes,
} from '@mui/material';
import {
  ElectricBolt,
  Thermostat,
  AccessTime,
  FiberManualRecord,
  Description,
  MenuBook,
  Storage,
} from '@mui/icons-material';
import { apiService } from '../services/api';
import { consumptionWS } from '../services/websocket';
import websocket from '../services/websocket';
import { formatTimeOnly, formatFullDateTime } from '../utils/dateUtils';

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

  return (
    <AppBar position="static" elevation={2}>
      <Toolbar sx={{ gap: 2, minHeight: '56px', py: 0.5 }}>
        {/* Logo et titre */}
        <ElectricBolt sx={{ fontSize: 28 }} />
        <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
          Linkya - Monitoring Linky & NILM
        </Typography>

        {/* Informations en temps réel */}
        {data && (
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
            {/* Date et heure */}
            <Tooltip title={`Dernière mise à jour: ${formatFullDateTime(data.time)}`}>
              <Chip
                icon={<AccessTime sx={{ fontSize: 19 }} />}
                label={formatTimeOnly(data.time)}
                variant="filled"
                sx={{
                  bgcolor: (theme) => theme.palette.overlay.white[15],
                  color: 'white',
                  fontWeight: 'bold',
                  fontSize: '1rem',
                  fontFamily: '"Space Mono", monospace',
                  '& .MuiChip-icon': { color: 'white' },
                }}
              />
            </Tooltip>

            {/* Puissance */}
            <Tooltip title="Puissance apparente">
              <Chip
                icon={<ElectricBolt sx={{ fontSize: 19 }} />}
                label={`${data.papp} W`}
                variant="filled"
                sx={{
                  bgcolor: (theme) => theme.palette.overlay.white[15],
                  color: 'white',
                  fontWeight: 'bold',
                  fontSize: '1rem',
                  fontFamily: '"Space Mono", monospace',
                  '& .MuiChip-icon': { color: 'white' },
                }}
              />
            </Tooltip>

            {/* Température */}
            {data.temperature && (
              <Tooltip title="Température extérieure">
                <Chip
                  icon={<Thermostat sx={{ fontSize: 19 }} />}
                  label={`${data.temperature.toFixed(0)}°C`}
                  variant="filled"
                  sx={{
                    bgcolor: (theme) => theme.palette.overlay.white[15],
                    color: 'white',
                    fontWeight: 'bold',
                    fontSize: '1rem',
                    fontFamily: '"Space Mono", monospace',
                    '& .MuiChip-icon': { color: 'white' },
                  }}
                />
              </Tooltip>
            )}

            {/* Liens vers les outils de documentation et monitoring */}
            <Box sx={{ display: 'flex', gap: 0.5, ml: 1 }}>
              <Tooltip title="Swagger UI - Documentation API interactive">
                <IconButton
                  size="small"
                  href="/docs"
                  target="_blank"
                  rel="noopener noreferrer"
                  sx={{
                    color: 'white',
                    bgcolor: (theme) => theme.palette.overlay.white[10],
                    '&:hover': {
                      bgcolor: (theme) => theme.palette.overlay.white[20],
                    },
                  }}
                >
                  <Description sx={{ fontSize: 20 }} />
                </IconButton>
              </Tooltip>

              <Tooltip title="ReDoc - Documentation API alternative">
                <IconButton
                  size="small"
                  href="/redoc"
                  target="_blank"
                  rel="noopener noreferrer"
                  sx={{
                    color: 'white',
                    bgcolor: (theme) => theme.palette.overlay.white[10],
                    '&:hover': {
                      bgcolor: (theme) => theme.palette.overlay.white[20],
                    },
                  }}
                >
                  <MenuBook sx={{ fontSize: 20 }} />
                </IconButton>
              </Tooltip>

              <Tooltip title="pgweb - Interface TimescaleDB">
                <IconButton
                  size="small"
                  href="http://localhost:8081"
                  target="_blank"
                  rel="noopener noreferrer"
                  sx={{
                    color: 'white',
                    bgcolor: (theme) => theme.palette.overlay.white[10],
                    '&:hover': {
                      bgcolor: (theme) => theme.palette.overlay.white[20],
                    },
                  }}
                >
                  <Storage sx={{ fontSize: 20 }} />
                </IconButton>
              </Tooltip>
            </Box>

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
                  animation: isUpdating ? `${pulse} 0.5s ease-in-out` : 'none',
                }}
              >
                <FiberManualRecord
                  sx={{
                    fontSize: 32,
                    color: isUpdating ? 'white' : 'transparent',
                    transition: 'color 0.5s ease-in-out',
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
