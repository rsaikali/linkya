import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  AppBar,
  Toolbar,
  Typography,
  Box,
  Chip,
  Tooltip,
  LinearProgress,
  IconButton,
  keyframes,
} from '@mui/material';
import {
  ElectricBolt,
  Thermostat,
  AccessTime,
  FiberManualRecord,
  ModelTraining,
  Description,
  MenuBook,
  Storage,
} from '@mui/icons-material';
import api, { apiService } from '../services/api';
import { consumptionWS } from '../services/websocket';
import websocket from '../services/websocket';

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
  
  // États pour le modèle NILM
  const [model, setModel] = useState(null);
  const [isTraining, setIsTraining] = useState(false);
  const [trainingProgress, setTrainingProgress] = useState(0);

  // Charger le modèle actuel
  const loadModel = useCallback(async () => {
    try {
      const response = await api.get('/api/nilm/models?page=1&per_page=1');
      if (response.data.models.length > 0) {
        const modelData = response.data.models[0];
        console.log('Model loaded:', modelData);
        setModel(modelData);
      } else {
        setModel(null);
      }
    } catch (error) {
      console.error('Erreur lors du chargement du modèle:', error);
    }
  }, []);

  // Formater la date de manière humanisée
  const formatHumanizedDate = (dateString) => {
    if (!dateString) {
      console.log('formatHumanizedDate: dateString is empty', dateString);
      return 'N/A';
    }
    
    const date = new Date(dateString);
    
    // Vérifier si la date est valide
    if (isNaN(date.getTime())) {
      console.log('formatHumanizedDate: invalid date', dateString);
      return 'N/A';
    }
    
    const now = new Date();
    const diffMs = now - date;
    const diffSeconds = Math.floor(diffMs / 1000);
    const diffMinutes = Math.floor(diffSeconds / 60);
    const diffHours = Math.floor(diffMinutes / 60);
    const diffDays = Math.floor(diffHours / 24);
    
    if (diffSeconds < 60) {
      return 'il y a quelques secondes';
    } else if (diffMinutes < 60) {
      return `il y a ${diffMinutes} minute${diffMinutes > 1 ? 's' : ''}`;
    } else if (diffHours < 24) {
      return `il y a ${diffHours} heure${diffHours > 1 ? 's' : ''}`;
    } else if (diffDays < 30) {
      return `il y a ${diffDays} jour${diffDays > 1 ? 's' : ''}`;
    } else {
      const diffMonths = Math.floor(diffDays / 30);
      return `il y a ${diffMonths} mois`;
    }
  };

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
    loadModel();

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
  }, [loadModel]);

  // Gérer les événements WebSocket de training
  useEffect(() => {
    websocket.connect();

    const handleTrainingStart = (data) => {
      setIsTraining(true);
      setTrainingProgress(0);
    };

    const handleEpochEnd = (data) => {
      const progress = ((data.epoch + 1) / data.total_epochs) * 100;
      setTrainingProgress(progress);
    };

    const handleTrainingComplete = (data) => {
      setIsTraining(false);
      setTrainingProgress(100);
      
      // Recharger le modèle après 2 secondes
      setTimeout(() => {
        loadModel();
      }, 2000);
    };

    websocket.on('training_start', handleTrainingStart);
    websocket.on('epoch_end', handleEpochEnd);
    websocket.on('training_complete', handleTrainingComplete);

    return () => {
      websocket.off('training_start', handleTrainingStart);
      websocket.off('epoch_end', handleEpochEnd);
      websocket.off('training_complete', handleTrainingComplete);
    };
  }, [loadModel]);

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
      <Toolbar sx={{ gap: 2, minHeight: '56px', py: 0.5 }}>
        {/* Logo et titre */}
        <ElectricBolt sx={{ fontSize: 28 }} />
        <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
          Linkya - Monitoring Linky & NILM
        </Typography>

        {/* Informations en temps réel */}
        {data && (
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
            {/* Informations NILM Model */}
            {isTraining ? (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <ModelTraining sx={{ color: 'white', fontSize: 20 }} />
                <Box sx={{ minWidth: 200 }}>
                  <Typography variant="caption" sx={{ color: 'white', display: 'block', mb: 0.5 }}>
                    Entraînement en cours... {Math.round(trainingProgress)}%
                  </Typography>
                  <LinearProgress 
                    variant="determinate" 
                    value={trainingProgress}
                    sx={{
                      height: 6,
                      borderRadius: 1,
                      backgroundColor: (theme) => theme.palette.overlay.white[20],
                      '& .MuiLinearProgress-bar': {
                        backgroundColor: 'white',
                      },
                    }}
                  />
                </Box>
              </Box>
            ) : model ? (
              <Tooltip title={`Modèle: ${model.model_name || 'N/A'}`}>
                <Chip
                  icon={<ModelTraining sx={{ fontSize: 18 }} />}
                  label={`Dernier modèle entraîné ${formatHumanizedDate(model.training_date)}`}
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
            ) : (
              <Chip
                icon={<ModelTraining sx={{ fontSize: 19 }} />}
                label="Aucun modèle entraîné"
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
            )}

            {/* Date et heure */}
            <Tooltip title={`Dernière mise à jour: ${formatFullDate(data.time)}`}>
              <Chip
                icon={<AccessTime sx={{ fontSize: 19 }} />}
                label={formatDate(data.time)}
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
