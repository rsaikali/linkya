import React, { useState, useEffect } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Typography,
  Alert,
  Snackbar,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  IconButton,
  Pagination,
  CircularProgress,
  Grid,
  Divider,
} from '@mui/material';
import {
  PlayArrow as TrainIcon,
  Search as DetectIcon,
  CheckCircle as SuccessIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import api from '../services/api';

const NilmTraining = () => {
  // État
  const [models, setModels] = useState([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [trainLoading, setTrainLoading] = useState(false);
  const [detectLoading, setDetectLoading] = useState(false);
  
  // Snackbar pour les notifications
  const [snackbar, setSnackbar] = useState({
    open: false,
    message: '',
    severity: 'info',
  });

  // Charger les modèles
  const loadModels = async (currentPage = page) => {
    setLoading(true);
    try {
      const response = await api.get(`/api/nilm/models?page=${currentPage}&per_page=10`);
      setModels(response.data.models);
      setTotalPages(response.data.total_pages);
      setTotal(response.data.total);
    } catch (error) {
      console.error('Erreur lors du chargement des modèles:', error);
      showSnackbar('Erreur lors du chargement des modèles', 'error');
    } finally {
      setLoading(false);
    }
  };

  // Charger au démarrage et toutes les 30 secondes
  useEffect(() => {
    loadModels();
    const interval = setInterval(() => loadModels(), 30000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Recharger quand la page change
  useEffect(() => {
    loadModels(page);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  // Afficher une notification
  const showSnackbar = (message, severity = 'info') => {
    setSnackbar({ open: true, message, severity });
  };

  const handleCloseSnackbar = () => {
    setSnackbar({ ...snackbar, open: false });
  };

  // Lancer l'entraînement
  const handleTrain = async () => {
    setTrainLoading(true);
    try {
      const response = await api.post('/api/nilm/train');
      showSnackbar(
        `Entraînement lancé (Task ID: ${response.data.task_id})`,
        'success'
      );
      // Recharger la liste après 5 secondes
      setTimeout(() => loadModels(), 5000);
    } catch (error) {
      console.error('Erreur lors du lancement de l\'entraînement:', error);
      showSnackbar(
        'Erreur lors du lancement de l\'entraînement',
        'error'
      );
    } finally {
      setTrainLoading(false);
    }
  };

  // Lancer la détection
  const handleDetect = async () => {
    setDetectLoading(true);
    try {
      const response = await api.post('/api/nilm/detect');
      showSnackbar(
        `Détection lancée (Task ID: ${response.data.task_id})`,
        'success'
      );
    } catch (error) {
      console.error('Erreur lors du lancement de la détection:', error);
      showSnackbar(
        'Erreur lors du lancement de la détection',
        'error'
      );
    } finally {
      setDetectLoading(false);
    }
  };

  // Formater les métriques pour l'affichage
  const formatMetrics = (metrics) => {
    if (!metrics) return 'N/A';
    
    const {
      train_accuracy,
      val_accuracy,
      train_loss,
      val_loss,
      epochs_trained,
    } = metrics;

    return (
      <Box>
        <Typography variant="caption" display="block">
          Train Acc: <strong>{(train_accuracy * 100).toFixed(1)}%</strong>
        </Typography>
        <Typography variant="caption" display="block">
          Val Acc: <strong>{(val_accuracy * 100).toFixed(1)}%</strong>
        </Typography>
        <Typography variant="caption" display="block">
          Train Loss: <strong>{train_loss.toFixed(4)}</strong>
        </Typography>
        <Typography variant="caption" display="block">
          Val Loss: <strong>{val_loss.toFixed(4)}</strong>
        </Typography>
        <Typography variant="caption" display="block" color="text.secondary">
          Epochs: {epochs_trained}
        </Typography>
      </Box>
    );
  };

  // Formater la date
  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleString('fr-FR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // Formater la durée d'entraînement
  const formatDuration = (seconds) => {
    if (!seconds && seconds !== 0) return 'N/A';
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    
    if (hours > 0) {
      return `${hours}h ${minutes}m ${secs}s`;
    } else if (minutes > 0) {
      return `${minutes}m ${secs}s`;
    } else {
      return `${secs}s`;
    }
  };

  // Obtenir le score de qualité (basé sur val_accuracy)
  const getQualityScore = (metrics) => {
    if (!metrics || !metrics.val_accuracy) return null;
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
    
    return { score, color, label };
  };

  return (
    <Box>
      {/* En-tête avec boutons d'actions */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} md={6}>
              <Typography variant="h5" gutterBottom>
                Gestion NILM
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Entraînez le modèle et lancez des détections d'appareils
              </Typography>
            </Grid>
            <Grid item xs={12} md={6}>
              <Box display="flex" gap={2} justifyContent="flex-end">
                <Button
                  variant="contained"
                  color="primary"
                  startIcon={trainLoading ? <CircularProgress size={20} /> : <TrainIcon />}
                  onClick={handleTrain}
                  disabled={trainLoading}
                >
                  {trainLoading ? 'Entraînement...' : 'Lancer Entraînement'}
                </Button>
                <Button
                  variant="outlined"
                  color="secondary"
                  startIcon={detectLoading ? <CircularProgress size={20} /> : <DetectIcon />}
                  onClick={handleDetect}
                  disabled={detectLoading}
                >
                  {detectLoading ? 'Détection...' : 'Lancer Détection'}
                </Button>
                <IconButton onClick={() => loadModels()} disabled={loading}>
                  <RefreshIcon />
                </IconButton>
              </Box>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Historique des entraînements */}
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Historique des entraînements ({total} modèle{total > 1 ? 's' : ''})
          </Typography>
          <Divider sx={{ mb: 2 }} />

          {loading && models.length === 0 ? (
            <Box display="flex" justifyContent="center" p={4}>
              <CircularProgress />
            </Box>
          ) : models.length === 0 ? (
            <Alert severity="info">
              Aucun modèle entraîné. Lancez un premier entraînement pour commencer !
            </Alert>
          ) : (
            <>
              <TableContainer component={Paper} variant="outlined">
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell>Version</TableCell>
                      <TableCell>Date</TableCell>
                      <TableCell>Durée</TableCell>
                      <TableCell>Signatures</TableCell>
                      <TableCell>Classes</TableCell>
                      <TableCell>Métriques</TableCell>
                      <TableCell>Qualité</TableCell>
                      <TableCell>État</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {models.map((model) => {
                      const quality = getQualityScore(model.metrics);
                      return (
                        <TableRow key={model.id} hover>
                          <TableCell>
                            <Typography variant="body2" fontFamily="monospace">
                              {model.version}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2">
                              {formatDate(model.training_date)}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Chip
                              label={formatDuration(model.training_duration_seconds)}
                              size="small"
                              variant="outlined"
                            />
                          </TableCell>
                          <TableCell>
                            <Chip
                              label={model.num_signatures}
                              size="small"
                              color="primary"
                              variant="outlined"
                            />
                          </TableCell>
                          <TableCell>
                            <Chip
                              label={model.num_classes}
                              size="small"
                              color="secondary"
                              variant="outlined"
                            />
                          </TableCell>
                          <TableCell>
                            {formatMetrics(model.metrics)}
                          </TableCell>
                          <TableCell>
                            {quality ? (
                              <Chip
                                label={`${quality.label} (${quality.score.toFixed(1)}%)`}
                                color={quality.color}
                                size="small"
                              />
                            ) : (
                              <Typography variant="caption" color="text.secondary">
                                N/A
                              </Typography>
                            )}
                          </TableCell>
                          <TableCell>
                            {model.is_active ? (
                              <Chip
                                icon={<SuccessIcon />}
                                label="Actif"
                                color="success"
                                size="small"
                              />
                            ) : (
                              <Chip
                                label="Inactif"
                                size="small"
                                variant="outlined"
                              />
                            )}
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </TableContainer>

              {/* Pagination */}
              {totalPages > 1 && (
                <Box display="flex" justifyContent="center" mt={3}>
                  <Pagination
                    count={totalPages}
                    page={page}
                    onChange={(e, value) => setPage(value)}
                    color="primary"
                    showFirstButton
                    showLastButton
                  />
                </Box>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* Snackbar pour les notifications */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={handleCloseSnackbar}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert
          onClose={handleCloseSnackbar}
          severity={snackbar.severity}
          variant="filled"
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default NilmTraining;
