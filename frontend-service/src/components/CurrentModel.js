import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Typography,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Chip,
  Grid,
  Tooltip,
  Alert,
  LinearProgress,
  CircularProgress,
  Paper,
  Snackbar,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Collapse,
  IconButton,
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  Info as InfoIcon,
  ModelTraining as ModelIcon,
  Timer as TimerIcon,
  PlayArrow as TrainIcon,
  Delete as DeleteIcon,
  Close as CloseIcon,
} from '@mui/icons-material';
import api from '../services/api';
import websocket from '../services/websocket';

const CurrentModel = () => {
  const [model, setModel] = useState(null);
  const [loading, setLoading] = useState(true);
  const [modelExpanded, setModelExpanded] = useState(false);
  const [showTerminal, setShowTerminal] = useState(false);
  const [isTraining, setIsTraining] = useState(false);
  const [trainingProgress, setTrainingProgress] = useState(0);
  const [logs, setLogs] = useState([]);
  const [trainLoading, setTrainLoading] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const logsEndRef = useRef(null);
  const logsContainerRef = useRef(null);
  
  // Snackbar pour les notifications
  const [snackbar, setSnackbar] = useState({
    open: false,
    message: '',
    severity: 'info',
  });

  // Charger le modèle actuel
  const loadModel = useCallback(async () => {
    try {
      const response = await api.get('/api/nilm/models?page=1&per_page=1');
      if (response.data.models.length > 0) {
        setModel(response.data.models[0]);
      } else {
        setModel(null);
      }
    } catch (error) {
      console.error('Erreur lors du chargement du modèle:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  // Ajouter un log au terminal
  const addLog = useCallback((level, message) => {
    setLogs((prev) => [
      ...prev,
      {
        timestamp: new Date(),
        level,
        message,
      },
    ]);
  }, []);

  // Auto-scroll vers le bas quand de nouveaux logs arrivent
  const scrollToBottom = () => {
    if (logsContainerRef.current) {
      logsContainerRef.current.scrollTop = logsContainerRef.current.scrollHeight;
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [logs]);

  // Lancer l'entraînement
  const handleTrain = async () => {
    setTrainLoading(true);
    try {
      await api.post('/api/nilm/train');
      setSnackbar({
        open: true,
        message: 'Entraînement lancé avec succès',
        severity: 'success',
      });
    } catch (error) {
      setSnackbar({
        open: true,
        message: `Erreur: ${error.response?.data?.detail || error.message}`,
        severity: 'error',
      });
    } finally {
      setTrainLoading(false);
    }
  };

  // Supprimer le modèle
  const handleDelete = async () => {
    setDeleteLoading(true);
    try {
      await api.delete(`/api/nilm/models/${model.id}`);
      setSnackbar({
        open: true,
        message: 'Modèle supprimé avec succès',
        severity: 'success',
      });
      setDeleteDialogOpen(false);
      setModel(null);
      await loadModel();
    } catch (error) {
      setSnackbar({
        open: true,
        message: `Erreur: ${error.response?.data?.detail || error.message}`,
        severity: 'error',
      });
    } finally {
      setDeleteLoading(false);
    }
  };

  useEffect(() => {
    loadModel();
    const interval = setInterval(loadModel, 30000);
    return () => clearInterval(interval);
  }, [loadModel]);

  // Connexion WebSocket au montage du composant
  useEffect(() => {
    websocket.connect();
    return () => {
      // Ne pas déconnecter car d'autres composants peuvent l'utiliser
    };
  }, []);

  // Gérer les événements WebSocket de training
  useEffect(() => {
    const handleTrainingStart = (data) => {
      setIsTraining(true);
      setTrainingProgress(0);
      setLogs([]);
      setShowTerminal(true); // Afficher le terminal lors du training
      addLog('success', `🚀 Début de l'entraînement du modèle ${data.model_name || ''}`);
    };

    const handleEpochEnd = (data) => {
      const progress = ((data.epoch + 1) / data.total_epochs) * 100;
      setTrainingProgress(progress);
      
      // Log avec métriques
      const metrics = data.metrics || {};
      const loss = metrics.loss ? metrics.loss.toFixed(4) : 'N/A';
      addLog('success', `Epoch ${data.epoch + 1}/${data.total_epochs} - Loss: ${loss}`);
    };

    const handleTrainingComplete = (data) => {
      setIsTraining(false);
      setTrainingProgress(100);
      addLog('success', `✅ Entraînement terminé (${data.total_duration_seconds || 0}s)`);
      
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
  }, [loadModel, addLog]);

  // Formater la date de manière humanisée
  const formatRelativeDate = (dateString) => {
    if (!dateString) return 'N/A';
    
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffSeconds = Math.floor(diffMs / 1000);
    const diffMinutes = Math.floor(diffSeconds / 60);
    const diffHours = Math.floor(diffMinutes / 60);
    const diffDays = Math.floor(diffHours / 24);
    
    let relativeText = '';
    if (diffSeconds < 60) {
      relativeText = 'il y a quelques secondes';
    } else if (diffMinutes < 60) {
      relativeText = `il y a ${diffMinutes} minute${diffMinutes > 1 ? 's' : ''}`;
    } else if (diffHours < 24) {
      relativeText = `il y a ${diffHours} heure${diffHours > 1 ? 's' : ''}`;
    } else if (diffDays < 30) {
      relativeText = `il y a ${diffDays} jour${diffDays > 1 ? 's' : ''}`;
    } else {
      const diffMonths = Math.floor(diffDays / 30);
      relativeText = `il y a ${diffMonths} mois`;
    }
    
    return relativeText;
  };

  const formatAbsoluteDate = (dateString) => {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleString('fr-FR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  // Obtenir le score de qualité
  const getQualityScore = (model) => {
    if (!model || !model.metrics) return null;
    
    const metrics = model.metrics.appliances?.[0]?.metrics || model.metrics;
    
    if (metrics.val_mae !== undefined && metrics.val_mae !== null) {
      const mae = metrics.val_mae;
      let color = 'error';
      let label = 'Faible';
      
      if (mae <= 30) {
        color = 'success';
        label = 'Excellent';
      } else if (mae <= 60) {
        color = 'warning';
        label = 'Bon';
      } else if (mae <= 100) {
        color = 'info';
        label = 'Moyen';
      }
      
      return { score: mae.toFixed(1), color, label, unit: 'W' };
    }
    
    if (!metrics.val_accuracy) return null;
    const score = metrics.val_accuracy * 100;
    
    let color = 'error';
    let label = 'Faible';
    
    if (score >= 90) {
      color = 'success';
      label = 'Excellent';
    } else if (score >= 75) {
      color = 'warning';
      label = 'Bon';
    } else if (score >= 60) {
      color = 'info';
      label = 'Moyen';
    }
    
    return { score: score.toFixed(1), color, label, unit: '%' };
  };

  if (loading) {
    return (
      <Card>
        <CardContent>
          <Box display="flex" justifyContent="center" p={2}>
            <CircularProgress />
          </Box>
        </CardContent>
      </Card>
    );
  }

  if (!model) {
    return (
      <>
      <Card elevation={0} sx={{ border: '1px solid', borderColor: 'divider' }}>
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 2, mb: 2 }}>
            <Alert severity="info" sx={{ flex: 1, mb: 0 }}>
              Aucun modèle NILM entraîné. Lancez un entraînement.
            </Alert>
            <Button
              variant="contained"
              color="primary"
              startIcon={trainLoading ? <CircularProgress size={20} color="inherit" /> : <TrainIcon />}
              onClick={handleTrain}
              disabled={trainLoading}
              sx={{ flexShrink: 0 }}
            >
              {trainLoading ? 'Lancement...' : 'Entraîner'}
            </Button>
          </Box>

          {/* Accordion: Logs d'entraînement */}
          <Accordion expanded={showTerminal} onChange={() => setShowTerminal(!showTerminal)} elevation={0} sx={{ border: '1px solid', borderColor: 'divider' }}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Typography variant="subtitle1" fontWeight="medium">
                  Logs d'entraînement
                </Typography>
                {isTraining && (
                  <Chip label="En cours" color="primary" size="small" />
                )}
              </Box>
            </AccordionSummary>
            <AccordionDetails>
              {/* Barre de progression */}
              {isTraining && (
                <Box sx={{ mb: 2 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                    <Typography variant="caption" color="text.secondary">
                      Progression de l'entraînement
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {Math.round(trainingProgress)}%
                    </Typography>
                  </Box>
                  <LinearProgress variant="determinate" value={trainingProgress} />
                </Box>
              )}

              {/* Terminal header avec les 3 boutons macOS */}
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 0.75,
                  bgcolor: '#2d2d2d',
                  borderTopLeftRadius: 4,
                  borderTopRightRadius: 4,
                  px: 1.5,
                  py: 0.75,
                  borderBottom: '1px solid #3e3e3e',
                }}
              >
                <Box sx={{ display: 'flex', gap: 0.5 }}>
                  <Box sx={{ width: 12, height: 12, borderRadius: '50%', bgcolor: '#ff5f56' }} />
                  <Box sx={{ width: 12, height: 12, borderRadius: '50%', bgcolor: '#ffbd2e' }} />
                  <Box sx={{ width: 12, height: 12, borderRadius: '50%', bgcolor: '#27c93f' }} />
                </Box>
                <Typography
                  sx={{
                    fontSize: '0.75rem',
                    color: '#858585',
                    fontFamily: "'Fira Code', 'Courier New', monospace",
                    ml: 1,
                  }}
                >
                  linkya-training.log
                </Typography>
              </Box>

              {/* Terminal content */}
              <Box
                ref={logsContainerRef}
                sx={{
                  height: 'calc(1.6em * 15 + 32px)',
                  overflow: 'auto',
                  bgcolor: '#1e1e1e',
                  border: 1,
                  borderColor: '#333',
                  borderTopLeftRadius: 0,
                  borderTopRightRadius: 0,
                  borderBottomLeftRadius: 4,
                  borderBottomRightRadius: 4,
                  p: 2,
                  fontFamily: "'Fira Code', 'Courier New', monospace",
                  fontSize: '0.875rem',
                  fontWeight: 'bold',
                  lineHeight: 1.6,
                  color: '#d4d4d4',
                  '&::-webkit-scrollbar': { width: '8px' },
                  '&::-webkit-scrollbar-track': { background: '#2d2d2d' },
                  '&::-webkit-scrollbar-thumb': { background: '#555', borderRadius: '4px', '&:hover': { background: '#777' } },
                }}
              >
                {logs.length === 0 ? (
                  <Box sx={{ color: '#858585', fontStyle: 'italic' }}>
                    $ Waiting for training events...
                  </Box>
                ) : (
                  <Box>
                    {logs.map((log, index) => {
                      const timestamp = log.timestamp.toLocaleTimeString('fr-FR', {
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit',
                      });
                      
                      let color = '#d4d4d4';
                      let prefix = '●';
                      
                      switch (log.level) {
                        case 'success':
                          color = '#4ec9b0';
                          prefix = '✓';
                          break;
                        case 'error':
                          color = '#f48771';
                          prefix = '✗';
                          break;
                        case 'warning':
                          color = '#dcdcaa';
                          prefix = '⚠';
                          break;
                        case 'info':
                        default:
                          color = '#569cd6';
                          prefix = '●';
                          break;
                      }
                      
                      return (
                        <Box
                          key={index}
                          sx={{
                            mb: 0.5,
                            display: 'flex',
                            gap: 1,
                            '&:hover': { bgcolor: '#2d2d2d', borderRadius: '2px' },
                          }}
                        >
                          <Typography component="span" sx={{ color: '#858585', minWidth: '70px', fontFamily: 'inherit', fontSize: 'inherit' }}>
                            [{timestamp}]
                          </Typography>
                          <Typography component="span" sx={{ color, minWidth: '20px', fontFamily: 'inherit', fontSize: 'inherit' }}>
                            {prefix}
                          </Typography>
                          <Typography component="span" sx={{ color, flex: 1, fontFamily: 'inherit', fontSize: 'inherit' }}>
                            {log.message}
                          </Typography>
                        </Box>
                      );
                    })}
                    <div ref={logsEndRef} />
                  </Box>
                )}
              </Box>
            </AccordionDetails>
          </Accordion>
        </CardContent>
      </Card>
      
      {/* Snackbar pour les notifications */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert
          onClose={() => setSnackbar({ ...snackbar, open: false })}
          severity={snackbar.severity}
          variant="filled"
          sx={{ width: '100%' }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
      </>
    );
  }

  const quality = getQualityScore(model);
  const metrics = model.metrics.appliances?.[0]?.metrics || model.metrics;

  return (
    <>
    <Card elevation={0} sx={{ border: '1px solid', borderColor: 'divider' }}>
      <CardContent>
        {/* En-tête du modèle */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <ModelIcon sx={{ mr: 1.5, color: 'primary.main', fontSize: 28 }} />
            <Box>
              <Typography variant="h6" component="h2">
                Modèle NILM Actuel
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Entraîné le {formatAbsoluteDate(model.training_date)} ({formatRelativeDate(model.training_date)})
              </Typography>
            </Box>
          </Box>
          
          {/* Boutons d'action */}
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button
              variant="contained"
              color="primary"
              startIcon={trainLoading ? <CircularProgress size={20} color="inherit" /> : <TrainIcon />}
              onClick={handleTrain}
              disabled={trainLoading || isTraining}
            >
              {trainLoading ? 'Lancement...' : 'Entraîner'}
            </Button>
            <Button
              variant="outlined"
              color="error"
              startIcon={<DeleteIcon />}
              onClick={() => setDeleteDialogOpen(true)}
              disabled={deleteLoading || isTraining}
            >
              Supprimer
            </Button>
          </Box>
        </Box>

        {/* Accordion 1: Informations du modèle */}
        <Accordion expanded={modelExpanded} onChange={() => setModelExpanded(!modelExpanded)} elevation={0} sx={{ border: '1px solid', borderColor: 'divider', mb: 2 }}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="subtitle1" fontWeight="medium">
              Métriques détaillées
            </Typography>
          </AccordionSummary>
          <AccordionDetails>
            {/* Statistiques principales déplacées ici */}
            <Grid container spacing={2} sx={{ mb: 3 }}>
              <Grid item xs={6} sm={3}>
                <Paper elevation={0} sx={{ p: 2, bgcolor: 'white', textAlign: 'center' }}>
                  <Typography variant="caption" color="text.secondary" display="block">
                    Type
                  </Typography>
                  <Typography variant="h6" fontWeight="medium">
                    {model.model_type || 'N/A'}
                  </Typography>
                </Paper>
              </Grid>
              <Grid item xs={6} sm={3}>
                <Paper elevation={0} sx={{ p: 2, bgcolor: 'white', textAlign: 'center' }}>
                  <Typography variant="caption" color="text.secondary" display="block">
                    Signatures
                  </Typography>
                  <Typography variant="h6" fontWeight="medium">
                    {model.num_signatures}
                  </Typography>
                </Paper>
              </Grid>
              <Grid item xs={6} sm={3}>
                <Paper elevation={0} sx={{ p: 2, bgcolor: 'white', textAlign: 'center' }}>
                  <Typography variant="caption" color="text.secondary" display="block">
                    Appareils
                  </Typography>
                  <Typography variant="h6" fontWeight="medium">
                    {model.num_classes}
                  </Typography>
                </Paper>
              </Grid>
              <Grid item xs={6} sm={3}>
                <Paper elevation={0} sx={{ p: 2, bgcolor: 'white', textAlign: 'center' }}>
                  <Typography variant="caption" color="text.secondary" display="block">
                    Qualité
                  </Typography>
                  <Typography variant="h6" fontWeight="medium" color={quality ? `${quality.color}.main` : 'text.primary'}>
                    {quality ? `${quality.score}${quality.unit}` : 'N/A'}
                  </Typography>
                </Paper>
              </Grid>
            </Grid>
            
            <Grid container spacing={2}>
              {/* MAE Train */}
              {metrics.train_mae !== undefined && (
                <Grid item xs={12} sm={6} md={4} >
                  <Box>
                    <Typography variant="caption" color="text.secondary" display="flex" alignItems="center" gutterBottom>
                      MAE (Train)
                      <Tooltip title="Erreur Moyenne Absolue sur les données d'entraînement - Moyenne des écarts entre prédictions et valeurs réelles">
                        <InfoIcon sx={{ ml: 0.5, fontSize: 16 }} />
                      </Tooltip>
                    </Typography>
                    <Typography variant="body1" fontWeight="medium">
                      {metrics.train_mae.toFixed(2)} W
                    </Typography>
                  </Box>
                </Grid>
              )}

              {/* MAE Val */}
              {metrics.val_mae !== undefined && (
                <Grid item xs={12} sm={6} md={4}>
                  <Box>
                    <Typography variant="caption" color="text.secondary" display="flex" alignItems="center" gutterBottom>
                      MAE (Validation)
                      <Tooltip title="Erreur Moyenne Absolue sur les données de validation - Indicateur principal de performance du modèle">
                        <InfoIcon sx={{ ml: 0.5, fontSize: 16 }} />
                      </Tooltip>
                    </Typography>
                    <Typography variant="body1" fontWeight="medium">
                      {metrics.val_mae.toFixed(2)} W
                    </Typography>
                  </Box>
                </Grid>
              )}

              {/* MSE Train */}
              {metrics.train_mse !== undefined && (
                <Grid item xs={12} sm={6} md={4}>
                  <Box>
                    <Typography variant="caption" color="text.secondary" display="flex" alignItems="center" gutterBottom>
                      MSE (Train)
                      <Tooltip title="Erreur Quadratique Moyenne sur les données d'entraînement - Pénalise plus fortement les grandes erreurs">
                        <InfoIcon sx={{ ml: 0.5, fontSize: 16 }} />
                      </Tooltip>
                    </Typography>
                    <Typography variant="body1" fontWeight="medium">
                      {metrics.train_mse.toFixed(4)}
                    </Typography>
                  </Box>
                </Grid>
              )}

              {/* MSE Val */}
              {metrics.val_mse !== undefined && (
                <Grid item xs={12} sm={6} md={4}>
                  <Box>
                    <Typography variant="caption" color="text.secondary" display="flex" alignItems="center" gutterBottom>
                      MSE (Validation)
                      <Tooltip title="Erreur Quadratique Moyenne sur les données de validation">
                        <InfoIcon sx={{ ml: 0.5, fontSize: 16 }} />
                      </Tooltip>
                    </Typography>
                    <Typography variant="body1" fontWeight="medium">
                      {metrics.val_mse.toFixed(4)}
                    </Typography>
                  </Box>
                </Grid>
              )}

              {/* Loss Train */}
              {metrics.train_loss !== undefined && (
                <Grid item xs={12} sm={6} md={4}>
                  <Box>
                    <Typography variant="caption" color="text.secondary" display="flex" alignItems="center" gutterBottom>
                      Loss (Train)
                      <Tooltip title="Fonction de perte sur les données d'entraînement - Combine MAE et pénalités pour les faux positifs">
                        <InfoIcon sx={{ ml: 0.5, fontSize: 16 }} />
                      </Tooltip>
                    </Typography>
                    <Typography variant="body1" fontWeight="medium">
                      {metrics.train_loss.toFixed(4)}
                    </Typography>
                  </Box>
                </Grid>
              )}

              {/* Loss Val */}
              {metrics.val_loss !== undefined && (
                <Grid item xs={12} sm={6} md={4}>
                  <Box>
                    <Typography variant="caption" color="text.secondary" display="flex" alignItems="center" gutterBottom>
                      Loss (Validation)
                      <Tooltip title="Fonction de perte sur les données de validation - Utilisée pour détecter le surapprentissage">
                        <InfoIcon sx={{ ml: 0.5, fontSize: 16 }} />
                      </Tooltip>
                    </Typography>
                    <Typography variant="body1" fontWeight="medium">
                      {metrics.val_loss.toFixed(4)}
                    </Typography>
                  </Box>
                </Grid>
              )}

              {/* Epochs */}
              {metrics.epochs_trained !== undefined && (
                <Grid item xs={12} sm={6} md={4}>
                  <Box>
                    <Typography variant="caption" color="text.secondary" display="flex" alignItems="center" gutterBottom>
                      Epochs entraînés
                      <Tooltip title="Nombre de passages complets sur l'ensemble des données d'entraînement">
                        <InfoIcon sx={{ ml: 0.5, fontSize: 16 }} />
                      </Tooltip>
                    </Typography>
                    <Typography variant="body1" fontWeight="medium">
                      {metrics.epochs_trained}
                    </Typography>
                  </Box>
                </Grid>
              )}

              {/* Durée d'entraînement */}
              <Grid item xs={12} sm={6} md={4}>
                <Box>
                  <Typography variant="caption" color="text.secondary" display="flex" alignItems="center" gutterBottom>
                    Durée d'entraînement
                    <Tooltip title="Temps total nécessaire pour entraîner le modèle">
                      <InfoIcon sx={{ ml: 0.5, fontSize: 16 }} />
                    </Tooltip>
                  </Typography>
                  <Typography variant="body1" fontWeight="medium">
                    {model.training_duration_seconds}s
                  </Typography>
                </Box>
              </Grid>
            </Grid>
          </AccordionDetails>
        </Accordion>

        {/* Accordion 2: Logs d'entraînement */}
        <Accordion expanded={showTerminal} onChange={() => setShowTerminal(!showTerminal)} elevation={0} sx={{ border: '1px solid', borderColor: 'divider' }}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="subtitle1" fontWeight="medium">
                Logs d'entraînement
              </Typography>
              {isTraining && (
                <Chip label="En cours" color="primary" size="small" />
              )}
            </Box>
          </AccordionSummary>
          <AccordionDetails>
            {/* Barre de progression */}
            {isTraining && (
              <Box sx={{ mb: 2 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                  <Typography variant="caption" color="text.secondary">
                    Progression de l'entraînement
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {Math.round(trainingProgress)}%
                  </Typography>
                </Box>
                <LinearProgress variant="determinate" value={trainingProgress} />
              </Box>
            )}

            {/* Terminal header avec les 3 boutons macOS */}
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 0.75,
                bgcolor: '#2d2d2d',
                borderTopLeftRadius: 4,
                borderTopRightRadius: 4,
                px: 1.5,
                py: 0.75,
                borderBottom: '1px solid #3e3e3e',
              }}
            >
              <Box sx={{ display: 'flex', gap: 0.5 }}>
                <Box sx={{ width: 12, height: 12, borderRadius: '50%', bgcolor: '#ff5f56' }} />
                <Box sx={{ width: 12, height: 12, borderRadius: '50%', bgcolor: '#ffbd2e' }} />
                <Box sx={{ width: 12, height: 12, borderRadius: '50%', bgcolor: '#27c93f' }} />
              </Box>
              <Typography
                sx={{
                  fontSize: '0.75rem',
                  color: '#858585',
                  fontFamily: "'Fira Code', 'Courier New', monospace",
                  ml: 1,
                }}
              >
                linkya-training.log
              </Typography>
            </Box>

            {/* Terminal content */}
            <Box
              ref={logsContainerRef}
              sx={{
                height: 'calc(1.6em * 15 + 32px)',
                overflow: 'auto',
                bgcolor: '#1e1e1e',
                border: 1,
                borderColor: '#333',
                borderTopLeftRadius: 0,
                borderTopRightRadius: 0,
                borderBottomLeftRadius: 4,
                borderBottomRightRadius: 4,
                p: 2,
                fontFamily: "'Fira Code', 'Courier New', monospace",
                fontSize: '0.875rem',
                fontWeight: 'bold',
                lineHeight: 1.6,
                color: '#d4d4d4',
                '&::-webkit-scrollbar': { width: '8px' },
                '&::-webkit-scrollbar-track': { background: '#2d2d2d' },
                '&::-webkit-scrollbar-thumb': { background: '#555', borderRadius: '4px', '&:hover': { background: '#777' } },
              }}
            >
              {logs.length === 0 ? (
                <Box sx={{ color: '#858585', fontStyle: 'italic' }}>
                  $ Waiting for training events...
                </Box>
              ) : (
                <Box>
                  {logs.map((log, index) => {
                    const timestamp = log.timestamp.toLocaleTimeString('fr-FR', {
                      hour: '2-digit',
                      minute: '2-digit',
                      second: '2-digit',
                    });
                    
                    let color = '#d4d4d4';
                    let prefix = '●';
                    
                    switch (log.level) {
                      case 'success':
                        color = '#4ec9b0';
                        prefix = '✓';
                        break;
                      case 'error':
                        color = '#f48771';
                        prefix = '✗';
                        break;
                      case 'warning':
                        color = '#dcdcaa';
                        prefix = '⚠';
                        break;
                      case 'info':
                      default:
                        color = '#569cd6';
                        prefix = '●';
                        break;
                    }
                    
                    return (
                      <Box
                        key={index}
                        sx={{
                          mb: 0.5,
                          display: 'flex',
                          gap: 1,
                          '&:hover': { bgcolor: '#2d2d2d', borderRadius: '2px' },
                        }}
                      >
                        <Typography component="span" sx={{ color: '#858585', minWidth: '70px', fontFamily: 'inherit', fontSize: 'inherit' }}>
                          [{timestamp}]
                        </Typography>
                        <Typography component="span" sx={{ color, minWidth: '20px', fontFamily: 'inherit', fontSize: 'inherit' }}>
                          {prefix}
                        </Typography>
                        <Typography component="span" sx={{ color, flex: 1, fontFamily: 'inherit', fontSize: 'inherit' }}>
                          {log.message}
                        </Typography>
                      </Box>
                    );
                  })}
                  <div ref={logsEndRef} />
                </Box>
              )}
            </Box>
          </AccordionDetails>
        </Accordion>
      </CardContent>
    </Card>
    
    {/* Dialog de confirmation de suppression */}
    <Dialog
      open={deleteDialogOpen}
      onClose={() => setDeleteDialogOpen(false)}
    >
      <DialogTitle>Supprimer le modèle ?</DialogTitle>
      <DialogContent>
        <DialogContentText>
          Êtes-vous sûr de vouloir supprimer le modèle <strong>{model?.model_name}</strong> ?
          Cette action est irréversible et supprimera tous les fichiers associés.
        </DialogContentText>
      </DialogContent>
      <DialogActions>
        <Button onClick={() => setDeleteDialogOpen(false)} disabled={deleteLoading}>
          Annuler
        </Button>
        <Button
          onClick={handleDelete}
          color="error"
          variant="contained"
          disabled={deleteLoading}
          startIcon={deleteLoading ? <CircularProgress size={20} color="inherit" /> : null}
        >
          {deleteLoading ? 'Suppression...' : 'Supprimer'}
        </Button>
      </DialogActions>
    </Dialog>
    
    {/* Snackbar pour les notifications */}
    <Snackbar
      open={snackbar.open}
      autoHideDuration={6000}
      onClose={() => setSnackbar({ ...snackbar, open: false })}
      anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
    >
      <Alert
        onClose={() => setSnackbar({ ...snackbar, open: false })}
        severity={snackbar.severity}
        variant="filled"
        sx={{ width: '100%' }}
      >
        {snackbar.message}
      </Alert>
    </Snackbar>
    </>
  );
};

export default CurrentModel;
