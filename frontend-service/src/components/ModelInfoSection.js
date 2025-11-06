import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Collapse,
  IconButton,
  Typography,
  LinearProgress,
  Chip,
  Grid,
  Paper,
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  ModelTraining,
  Schedule,
  Speed,
  TrendingDown,
  CheckCircle,
  Analytics,
} from '@mui/icons-material';
import { useTheme } from '@mui/material/styles';
import api from '../services/api';
import websocket from '../services/websocket';
import { formatDuration, formatFullDateTime } from '../utils/dateUtils';
import MaterialIcon from './common/MaterialIcon';

/**
 * Composant affichant les informations du modèle actuel et la progression de l'entraînement
 */
function ModelInfoSection() {
  const theme = useTheme();
  const [expanded, setExpanded] = useState(false);
  const [model, setModel] = useState(null);
  const [isTraining, setIsTraining] = useState(false);
  const [trainingProgress, setTrainingProgress] = useState(0);
  const [currentEpoch, setCurrentEpoch] = useState(0);
  const [totalEpochs, setTotalEpochs] = useState(0);

  // Charger le modèle actuel
  const loadModel = useCallback(async () => {
    try {
      const response = await api.get('/api/nilm/models?page=1&per_page=1');
      if (response.data.models.length > 0) {
        const modelData = response.data.models[0];
        setModel(modelData);
      } else {
        setModel(null);
      }
    } catch (error) {
      console.error('Erreur lors du chargement du modèle:', error);
    }
  }, []);

  useEffect(() => {
    loadModel();
  }, [loadModel]);

  // Gérer les événements WebSocket d'entraînement
  useEffect(() => {
    websocket.connect();

    const handleTrainingStart = (data) => {
      setIsTraining(true);
      setTrainingProgress(0);
      setCurrentEpoch(0);
      setTotalEpochs(data.total_epochs || 0);
      setExpanded(true); // Auto-expansion au démarrage de l'entraînement
    };

    const handleEpochEnd = (data) => {
      const progress = ((data.epoch + 1) / data.total_epochs) * 100;
      setTrainingProgress(progress);
      setCurrentEpoch(data.epoch + 1);
      setTotalEpochs(data.total_epochs);
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

  const handleToggle = () => {
    setExpanded(!expanded);
  };

  // Afficher le badge de statut
  const getStatusBadge = () => {
    if (isTraining) {
      return (
        <Chip
          icon={<ModelTraining sx={{ fontSize: 16 }} />}
          label="Entraînement en cours"
          size="small"
          color="primary"
          sx={{ fontWeight: 'bold' }}
        />
      );
    } else if (model) {
      return (
        <Chip
          icon={<CheckCircle sx={{ fontSize: 16 }} />}
          label="Modèle prêt"
          size="small"
          color="success"
          sx={{ fontWeight: 'bold' }}
        />
      );
    } else {
      return (
        <Chip
          icon={<MaterialIcon sx={{ fontSize: 16 }}>error</MaterialIcon>}
          label="Aucun modèle"
          size="small"
          color="warning"
          sx={{ fontWeight: 'bold' }}
        />
      );
    }
  };

  // Extraire les métriques
  const getMetrics = (metricsData) => {
    if (!metricsData) return null;
    
    try {
      const parsed = typeof metricsData === 'string' ? JSON.parse(metricsData) : metricsData;
      
      // Si les métriques sont dans appliances[].metrics, on extrait et on fait la moyenne
      if (parsed.appliances && Array.isArray(parsed.appliances) && parsed.appliances.length > 0) {
        const aggregated = {
          appliances: parsed.appliances,
          num_appliances: parsed.num_appliances || parsed.appliances.length,
        };
        
        // Calculer les moyennes des métriques
        const valLosses = parsed.appliances
          .map(app => app.metrics?.val_loss)
          .filter(v => v !== undefined && v !== null);
        
        const valMAEs = parsed.appliances
          .map(app => app.metrics?.val_mae)
          .filter(v => v !== undefined && v !== null);
        
        const epochs = parsed.appliances
          .map(app => app.metrics?.epochs_trained)
          .filter(v => v !== undefined && v !== null);
        
        if (valLosses.length > 0) {
          aggregated.val_loss = valLosses.reduce((sum, v) => sum + v, 0) / valLosses.length;
        }
        
        if (valMAEs.length > 0) {
          aggregated.val_mae = valMAEs.reduce((sum, v) => sum + v, 0) / valMAEs.length;
        }
        
        if (epochs.length > 0) {
          aggregated.epochs = Math.max(...epochs);
        }
        
        return aggregated;
      }
      
      return parsed;
    } catch (error) {
      console.error('Erreur parsing metrics:', error);
      return null;
    }
  };

  const metrics = model ? getMetrics(model.metrics) : null;

  return (
    <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
      {/* En-tête collapsible */}
      <Box
        sx={{
          px: 2,
          py: 1,
          bgcolor: theme.palette.mode === 'dark' ? 'grey.900' : 'grey.50',
          cursor: 'pointer',
          '&:hover': {
            bgcolor: theme.palette.mode === 'dark' ? 'grey.800' : 'grey.100',
          },
        }}
        onClick={handleToggle}
      >
        <Grid container spacing={1} alignItems="center">
          <Grid item>
            <IconButton
              size="small"
              sx={{
                transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
                transition: 'transform 0.3s',
              }}
            >
              <ExpandMoreIcon />
            </IconButton>
          </Grid>

          <Grid item>
            <MaterialIcon sx={{ fontSize: 20, color: 'primary.main' }}>
              cognition
            </MaterialIcon>
          </Grid>

          <Grid item>
            <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
              Modèle IA
            </Typography>
          </Grid>

          <Grid item>
            {getStatusBadge()}
          </Grid>

          <Grid item xs />

          {model && !isTraining && (
            <Grid item>
              <Typography variant="caption" color="text.secondary">
                Dernier entraînement : {formatFullDateTime(model.training_date)}
              </Typography>
            </Grid>
          )}
        </Grid>
      </Box>

      {/* Barre de progression d'entraînement (toujours visible pendant l'entraînement) */}
      {isTraining && (
        <Box sx={{ px: 2, pb: 1.5, bgcolor: theme.palette.mode === 'dark' ? 'grey.900' : 'grey.50' }}>
          <Grid container spacing={1} alignItems="center" sx={{ mb: 0.5 }}>
            <Grid item xs>
              <Typography variant="caption" fontWeight="600" color="primary.main">
                Entraînement en cours...
              </Typography>
            </Grid>
            <Grid item>
              <Typography variant="caption" fontWeight="600" color="primary.main">
                Époque {currentEpoch}/{totalEpochs} - {Math.round(trainingProgress)}%
              </Typography>
            </Grid>
          </Grid>
          <LinearProgress
            variant="determinate"
            value={trainingProgress}
            sx={{
              height: 8,
              borderRadius: 1,
              backgroundColor: theme.palette.mode === 'dark' ? 'grey.700' : 'grey.300',
            }}
          />
        </Box>
      )}

      {/* Contenu collapsible */}
      <Collapse in={expanded} timeout="auto" unmountOnExit>
        <Box sx={{ p: 2 }}>
          {model ? (
            <Grid container spacing={2}>
              {/* Date d'entraînement */}
              <Grid item xs={12} md={6}>
                <Paper variant="outlined" sx={{ p: 1.5, height: '100%' }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                    <Schedule sx={{ fontSize: 18, color: 'text.secondary' }} />
                    <Typography variant="caption" color="text.secondary" fontWeight="600">
                      Date d'entraînement
                    </Typography>
                  </Box>
                  <Typography variant="body2" fontWeight="500">
                    {formatFullDateTime(model.training_date)}
                  </Typography>
                </Paper>
              </Grid>

              {/* Durée d'entraînement */}
              {model.training_duration_seconds && (
                <Grid item xs={12} md={6}>
                  <Paper variant="outlined" sx={{ p: 1.5, height: '100%' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                      <Speed sx={{ fontSize: 18, color: 'text.secondary' }} />
                      <Typography variant="caption" color="text.secondary" fontWeight="600">
                        Durée d'entraînement
                      </Typography>
                    </Box>
                    <Typography variant="body2" fontWeight="500">
                      {formatDuration(model.training_duration_seconds)}
                    </Typography>
                  </Paper>
                </Grid>
              )}

              {/* Nombre d'appareils */}
              {model.num_classes && (
                <Grid item xs={12} md={6}>
                  <Paper variant="outlined" sx={{ p: 1.5, height: '100%' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                      <MaterialIcon sx={{ fontSize: 18, color: 'text.secondary' }}>
                        devices
                      </MaterialIcon>
                      <Typography variant="caption" color="text.secondary" fontWeight="600">
                        Nombre d'appareils
                      </Typography>
                    </Box>
                    <Typography variant="body2" fontWeight="500">
                      {model.num_classes}
                    </Typography>
                  </Paper>
                </Grid>
              )}

              {/* Nombre de signatures */}
              {model.num_signatures && (
                <Grid item xs={12} md={6}>
                  <Paper variant="outlined" sx={{ p: 1.5, height: '100%' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                      <MaterialIcon sx={{ fontSize: 18, color: 'text.secondary' }}>
                        database
                      </MaterialIcon>
                      <Typography variant="caption" color="text.secondary" fontWeight="600">
                        Signatures utilisées
                      </Typography>
                    </Box>
                    <Typography variant="body2" fontWeight="500">
                      {model.num_signatures}
                    </Typography>
                  </Paper>
                </Grid>
              )}

              {/* Nombre d'époques */}
              {metrics && metrics.epochs && (
                <Grid item xs={12} md={6}>
                  <Paper variant="outlined" sx={{ p: 1.5, height: '100%' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                      <MaterialIcon sx={{ fontSize: 18, color: 'text.secondary' }}>
                        autorenew
                      </MaterialIcon>
                      <Typography variant="caption" color="text.secondary" fontWeight="600">
                        Époques totales
                      </Typography>
                    </Box>
                    <Typography variant="body2" fontWeight="500">
                      {metrics.epochs}
                    </Typography>
                  </Paper>
                </Grid>
              )}

              {/* Loss de validation */}
              {metrics && metrics.val_loss !== undefined && metrics.val_loss !== null && (
                <Grid item xs={12} md={6}>
                  <Paper variant="outlined" sx={{ p: 1.5, height: '100%' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                      <TrendingDown sx={{ fontSize: 18, color: 'text.secondary' }} />
                      <Typography variant="caption" color="text.secondary" fontWeight="600">
                        Loss de validation
                      </Typography>
                    </Box>
                    <Typography variant="body2" fontWeight="500">
                      {typeof metrics.val_loss === 'number' ? metrics.val_loss.toFixed(4) : metrics.val_loss}
                    </Typography>
                  </Paper>
                </Grid>
              )}

              {/* MAE de validation (si disponible) */}
              {metrics && metrics.val_mae !== undefined && metrics.val_mae !== null && (
                <Grid item xs={12} md={6}>
                  <Paper variant="outlined" sx={{ p: 1.5, height: '100%' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                      <Analytics sx={{ fontSize: 18, color: 'text.secondary' }} />
                      <Typography variant="caption" color="text.secondary" fontWeight="600">
                        MAE de validation
                      </Typography>
                    </Box>
                    <Typography variant="body2" fontWeight="500">
                      {typeof metrics.val_mae === 'number' ? metrics.val_mae.toFixed(4) : metrics.val_mae}
                    </Typography>
                  </Paper>
                </Grid>
              )}

              {/* Métriques par appareil */}
              {metrics && metrics.appliances && metrics.appliances.length > 0 && (
                <Grid item xs={12}>
                  <Paper variant="outlined" sx={{ p: 1.5, mt: 1 }}>
                    <Typography variant="caption" color="text.secondary" fontWeight="600" sx={{ mb: 1.5, display: 'block' }}>
                      Métriques détaillées par appareil
                    </Typography>
                    <Grid container spacing={1.5}>
                      {metrics.appliances.map((appliance, index) => (
                        <Grid item xs={12} md={6} key={index}>
                          <Box sx={{ 
                            p: 1.5, 
                            bgcolor: theme.palette.mode === 'dark' ? 'grey.800' : 'grey.50',
                            borderRadius: 1,
                          }}>
                            <Typography variant="body2" fontWeight="600" sx={{ mb: 1 }}>
                              {appliance.name}
                            </Typography>
                            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                              {appliance.metrics?.val_loss !== undefined && appliance.metrics?.val_loss !== null && (
                                <Typography variant="caption" color="text.secondary">
                                  Loss validation : <strong>{appliance.metrics.val_loss.toFixed(4)}</strong>
                                </Typography>
                              )}
                              {appliance.metrics?.val_mae !== undefined && appliance.metrics?.val_mae !== null && (
                                <Typography variant="caption" color="text.secondary">
                                  MAE validation : <strong>{appliance.metrics.val_mae.toFixed(4)}</strong>
                                </Typography>
                              )}
                              {appliance.metrics?.epochs_trained && (
                                <Typography variant="caption" color="text.secondary">
                                  Époques : <strong>{appliance.metrics.epochs_trained}</strong>
                                </Typography>
                              )}
                              {appliance.num_signatures && (
                                <Typography variant="caption" color="text.secondary">
                                  Signatures : <strong>{appliance.num_signatures}</strong>
                                </Typography>
                              )}
                            </Box>
                          </Box>
                        </Grid>
                      ))}
                    </Grid>
                  </Paper>
                </Grid>
              )}
            </Grid>
          ) : (
            <Box sx={{ textAlign: 'center', py: 3 }}>
              <MaterialIcon sx={{ fontSize: 48, color: 'text.disabled', mb: 1 }}>
                model_training
              </MaterialIcon>
              <Typography variant="body2" color="text.secondary">
                Aucun modèle n'a encore été entraîné. Cliquez sur "Entraîner le modèle" pour commencer.
              </Typography>
            </Box>
          )}
        </Box>
      </Collapse>
    </Box>
  );
}

export default ModelInfoSection;
