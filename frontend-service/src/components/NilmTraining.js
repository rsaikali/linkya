import React, { useState, useEffect } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  Typography,
  Alert,
  Snackbar,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  IconButton,
  Pagination,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Tooltip,
} from '@mui/material';
import {
  PlayArrow as TrainIcon,
  CheckCircle as SuccessIcon,
  Refresh as RefreshIcon,
  Delete as DeleteIcon,
  Save as BackupIcon,
} from '@mui/icons-material';
import api from '../services/api';
import TrainingLogsViewer from './TrainingLogsViewer';

const NilmTraining = () => {
  // État
  const [models, setModels] = useState([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [trainLoading, setTrainLoading] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [backupLoading, setBackupLoading] = useState(false);
  
  // Dialog de confirmation de suppression
  const [deleteDialog, setDeleteDialog] = useState({
    open: false,
    modelId: null,
    modelVersion: '',
    modelStatus: '',
  });
  
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
      const response = await api.get(`/api/nilm/models?page=${currentPage}&per_page=3`);
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

  // Ouvrir le dialog de confirmation de suppression
  const handleOpenDeleteDialog = (modelId, modelVersion, modelStatus) => {
    setDeleteDialog({
      open: true,
      modelId,
      modelVersion,
      modelStatus,
    });
  };

  // Fermer le dialog de suppression
  const handleCloseDeleteDialog = () => {
    setDeleteDialog({
      open: false,
      modelId: null,
      modelVersion: '',
      modelStatus: '',
    });
  };

  // Confirmer et supprimer le modèle
  const handleConfirmDelete = async () => {
    const { modelId, modelVersion } = deleteDialog;
    setDeleteLoading(true);
    
    try {
      await api.delete(`/api/nilm/models/${modelId}`);
      showSnackbar(
        `Modèle ${modelVersion} supprimé avec succès`,
        'success'
      );
      handleCloseDeleteDialog();
      // Recharger la liste
      loadModels();
    } catch (error) {
      console.error('Erreur lors de la suppression du modèle:', error);
      const errorMsg = error.response?.data?.detail || 'Erreur lors de la suppression du modèle';
      showSnackbar(errorMsg, 'error');
    } finally {
      setDeleteLoading(false);
    }
  };

  // Créer un backup manuel
  const handleCreateBackup = async () => {
    setBackupLoading(true);
    try {
      const response = await api.post('/api/nilm/models/backup');
      showSnackbar(
        `Backup créé: ${response.data.backup_version}`,
        'success'
      );
      // Recharger la liste après 2 secondes
      setTimeout(() => loadModels(), 2000);
    } catch (error) {
      console.error('Erreur lors de la création du backup:', error);
      const errorMsg = error.response?.data?.detail || 'Erreur lors de la création du backup';
      showSnackbar(errorMsg, 'error');
    } finally {
      setBackupLoading(false);
    }
  };

  // Formater une date

  // Extraire les métriques selon le type de modèle
  const extractMetrics = (model) => {
    if (!model || !model.metrics) return null;
    
    // Pour les modèles S2P, les métriques sont dans appliances[0].metrics
    if (model.model_type?.startsWith('S2P') && model.metrics.appliances?.length > 0) {
      return model.metrics.appliances[0].metrics;
    }
    
    // Pour les modèles CNN classiques, les métriques sont directement dans model.metrics
    return model.metrics;
  };

  // Formater les métriques pour l'affichage
  const formatMetrics = (model) => {
    const metrics = extractMetrics(model);
    if (!metrics) return 'N/A';
    
    const {
      train_accuracy,
      val_accuracy,
      train_loss,
      val_loss,
      train_mae,
      val_mae,
      train_mse,
      val_mse,
      epochs_trained,
    } = metrics;

    // Pour les modèles S2P (régression), on utilise MAE au lieu de accuracy
    const isS2P = train_mae !== undefined && train_mae !== null;

    if (isS2P) {
      return (
        <Box>
          <Typography variant="caption" display="block">
            MAE: <strong>{train_mae?.toFixed(2) || 'N/A'}W</strong> / <strong>{val_mae?.toFixed(2) || 'N/A'}W</strong>
          </Typography>
          <Typography variant="caption" display="block">
            MSE: <strong>{train_mse?.toFixed(4) || 'N/A'}</strong> / <strong>{val_mse?.toFixed(4) || 'N/A'}</strong>
          </Typography>
          <Typography variant="caption" display="block" color="text.secondary">
            (Train/Val · {epochs_trained || 'N/A'} epochs)
          </Typography>
        </Box>
      );
    }

    // Pour les modèles CNN (classification)
    return (
      <Box>
        <Typography variant="caption" display="block">
          Accuracy: <strong>{train_accuracy ? (train_accuracy * 100).toFixed(1) : 'N/A'}%</strong> / <strong>{val_accuracy ? (val_accuracy * 100).toFixed(1) : 'N/A'}%</strong>
        </Typography>
        <Typography variant="caption" display="block">
          Loss: <strong>{train_loss?.toFixed(4) || 'N/A'}</strong> / <strong>{val_loss?.toFixed(4) || 'N/A'}</strong>
        </Typography>
        <Typography variant="caption" display="block" color="text.secondary">
          (Train/Val · {epochs_trained || 'N/A'} epochs)
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

  // Obtenir le score de qualité (basé sur val_accuracy pour CNN, val_mae pour S2P)
  const getQualityScore = (model) => {
    const metrics = extractMetrics(model);
    if (!metrics) return null;
    
    // Pour les modèles S2P (régression avec MAE)
    if (metrics.val_mae !== undefined && metrics.val_mae !== null) {
      const mae = metrics.val_mae;
      let color = 'error';
      let label = 'Faible';
      
      // MAE plus bas = meilleur (inversé par rapport à accuracy)
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
    
    // Pour les modèles CNN (classification avec accuracy)
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

  // Obtenir le badge de statut du modèle
  const getStatusBadge = (modelStatus) => {
    switch (modelStatus) {
      case 'current':
        return (
          <Chip
            icon={<SuccessIcon />}
            label="Actif"
            color="success"
            size="small"
          />
        );
      case 'backup':
        return (
          <Chip
            label="Backup"
            color="warning"
            size="small"
          />
        );
      case 'archived':
        return (
          <Chip
            label="Archivé"
            color="default"
            size="small"
            variant="outlined"
          />
        );
      default:
        return (
          <Chip
            label={modelStatus || 'Inconnu'}
            size="small"
            variant="outlined"
          />
        );
    }
  };

  // Message d'avertissement pour la suppression
  const getDeleteWarning = (modelStatus) => {
    if (modelStatus === 'current') {
      return (
        <Alert severity="warning" sx={{ mt: 2 }}>
          ⚠️ <strong>Attention :</strong> Vous supprimez le modèle actif.
          Le modèle 'backup' sera automatiquement promu en 'current'.
        </Alert>
      );
    } else if (modelStatus === 'backup') {
      return (
        <Alert severity="info" sx={{ mt: 2 }}>
          ℹ️ Vous supprimez le modèle de sauvegarde.
          Vous ne pourrez plus revenir en arrière en cas de problème.
        </Alert>
      );
    }
    return null;
  };

  return (
    <>
      <Card>
        <CardHeader
          title="Historique des entraînements"
          subheader={`${total} modèle${total !== 1 ? 's' : ''} entraîné${total !== 1 ? 's' : ''}`}
          avatar={<TrainIcon />}
          action={
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <Button
                variant="outlined"
                color="warning"
                size="small"
                startIcon={backupLoading ? <CircularProgress size={16} /> : <BackupIcon />}
                onClick={handleCreateBackup}
                disabled={backupLoading || trainLoading}
                sx={{ whiteSpace: 'nowrap' }}
              >
                {backupLoading ? 'Sauvegarde...' : 'Backup manuel'}
              </Button>
              <Button
                variant="contained"
                color="primary"
                size="small"
                startIcon={trainLoading ? <CircularProgress size={16} /> : <TrainIcon />}
                onClick={handleTrain}
                disabled={trainLoading}
                sx={{ whiteSpace: 'nowrap' }}
              >
                {trainLoading ? 'Entraînement...' : 'Lancer entraînement'}
              </Button>
              <IconButton onClick={() => loadModels()} disabled={loading} size="small">
                <RefreshIcon />
              </IconButton>
            </Box>
          }
        />
        <CardContent>
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
            <TableContainer sx={{ maxHeight: 600 }}>
              <Table stickyHeader size="small">
                <TableHead>
                  <TableRow sx={{ backgroundColor: '#f5f5f5' }}>
                    <TableCell>État</TableCell>
                    <TableCell>Qualité</TableCell>
                    <TableCell>Date</TableCell>
                    <TableCell>Durée</TableCell>
                    <TableCell>Signatures</TableCell>
                    <TableCell>Classes</TableCell>
                    <TableCell>Métriques</TableCell>
                    <TableCell align="center">Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {models.map((model) => {
                    const quality = getQualityScore(model);
                    return (
                      <TableRow key={model.id} hover>
                        <TableCell>
                          {getStatusBadge(model.model_status)}
                        </TableCell>
                        <TableCell>
                            {quality ? (
                              <Chip
                                label={`${quality.label} (${quality.score}${quality.unit})`}
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
                            {formatMetrics(model)}
                          </TableCell>
                          <TableCell align="center">
                            <Tooltip title="Supprimer ce modèle">
                              <span>
                                <IconButton
                                  size="small"
                                  color="error"
                                  onClick={() => handleOpenDeleteDialog(
                                    model.id, 
                                    model.version,
                                    model.model_status
                                  )}
                                  disabled={deleteLoading}
                                >
                                  <DeleteIcon />
                                </IconButton>
                              </span>
                            </Tooltip>
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

      {/* Dialog de confirmation de suppression */}
      <Dialog
        open={deleteDialog.open}
        onClose={handleCloseDeleteDialog}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Confirmer la suppression</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Êtes-vous sûr de vouloir supprimer le modèle <strong>{deleteDialog.modelVersion}</strong> ?
            <br />
            <br />
            Cette action supprimera :
            <ul style={{ marginTop: '8px', marginBottom: '8px' }}>
              <li>L'entrée dans la base de données</li>
              <li>Le fichier du modèle (.keras)</li>
              <li>Les métadonnées associées (.json)</li>
              <li>Les logs TensorBoard</li>
            </ul>
            <br />
            <strong>Cette action est irréversible.</strong>
          </DialogContentText>
          
          {getDeleteWarning(deleteDialog.modelStatus)}
        </DialogContent>
        <DialogActions>
          <Button 
            onClick={handleCloseDeleteDialog} 
            disabled={deleteLoading}
          >
            Annuler
          </Button>
          <Button
            onClick={handleConfirmDelete}
            color="error"
            variant="contained"
            disabled={deleteLoading}
            startIcon={deleteLoading ? <CircularProgress size={20} /> : <DeleteIcon />}
          >
            {deleteLoading ? 'Suppression...' : 'Supprimer'}
          </Button>
        </DialogActions>
      </Dialog>

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

      {/* Training Logs Viewer */}
      <TrainingLogsViewer />
    </>
  );
};

export default NilmTraining;
