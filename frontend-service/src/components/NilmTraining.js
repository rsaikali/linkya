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
  Chip,
  IconButton,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
} from '@mui/material';
import {
  PlayArrow as TrainIcon,
  Refresh as RefreshIcon,
  Delete as DeleteIcon,
} from '@mui/icons-material';
import api from '../services/api';

const NilmTraining = () => {
  // État
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [trainLoading, setTrainLoading] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);
  
  // Dialog de confirmation de suppression
  const [deleteDialog, setDeleteDialog] = useState({
    open: false,
    modelId: null,
    modelName: '',
  });
  
  // Snackbar pour les notifications
  const [snackbar, setSnackbar] = useState({
    open: false,
    message: '',
    severity: 'info',
  });

  // Charger les modèles (simplifié - on récupère juste le premier)
  const loadModels = async () => {
    setLoading(true);
    try {
      const response = await api.get(`/api/nilm/models?page=1&per_page=1`);
      setModels(response.data.models);
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
  const handleOpenDeleteDialog = (modelId, modelName) => {
    setDeleteDialog({
      open: true,
      modelId,
      modelName,
    });
  };

  // Fermer le dialog de suppression
  const handleCloseDeleteDialog = () => {
    setDeleteDialog({
      open: false,
      modelId: null,
      modelName: '',
    });
  };

  // Confirmer et supprimer le modèle
  const handleConfirmDelete = async () => {
    const { modelId, modelName } = deleteDialog;
    setDeleteLoading(true);
    
    try {
      await api.delete(`/api/nilm/models/${modelId}`);
      showSnackbar(
        `Modèle ${modelName} supprimé avec succès`,
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

  // Formater la date de manière relative
  const formatRelativeDate = (dateString) => {
    if (!dateString) return 'N/A';
    
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffSeconds = Math.floor(diffMs / 1000);
    const diffMinutes = Math.floor(diffSeconds / 60);
    const diffHours = Math.floor(diffMinutes / 60);
    const diffDays = Math.floor(diffHours / 24);
    
    // Format absolu pour affichage entre parenthèses
    const absoluteDate = date.toLocaleString('fr-FR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
    
    // Format relatif
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
    
    return `${relativeText} (${absoluteDate})`;
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

  // Obtenir le badge de statut du modèle (supprimé - un seul modèle maintenant)
  
  // Message d'avertissement pour la suppression (simplifié)
  const getDeleteWarning = () => {
    return (
      <Alert severity="warning" sx={{ mt: 2 }}>
        ⚠️ <strong>Attention :</strong> Vous supprimez le seul modèle existant.
        Il faudra réentraîner un nouveau modèle pour continuer les détections.
      </Alert>
    );
  };

  const currentModel = models.length > 0 ? models[0] : null;
  const quality = currentModel ? getQualityScore(currentModel) : null;

  return (
    <>
      {/* Modèle Courant */}
      <Card sx={{ mb: 3 }}>
        <CardHeader
          title="Modèle NILM Actuel"
          avatar={<TrainIcon />}
          action={
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <Button
                variant="contained"
                color="primary"
                size="small"
                startIcon={trainLoading ? <CircularProgress size={16} /> : <TrainIcon />}
                onClick={handleTrain}
                disabled={trainLoading}
                sx={{ whiteSpace: 'nowrap' }}
              >
                {trainLoading ? 'Entraînement...' : currentModel ? 'Réentraîner' : 'Lancer entraînement'}
              </Button>
              <IconButton onClick={() => loadModels()} disabled={loading} size="small">
                <RefreshIcon />
              </IconButton>
            </Box>
          }
        />
        <CardContent>
          {loading ? (
            <Box display="flex" justifyContent="center" p={4}>
              <CircularProgress />
            </Box>
          ) : !currentModel ? (
            <Alert severity="info">
              Aucun modèle entraîné. Lancez un premier entraînement pour commencer !
            </Alert>
          ) : (
            <Box>
              {/* En-tête du modèle */}
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 3 }}>
                <Box>
                  <Typography variant="h6" gutterBottom>
                    {currentModel.model_name}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Entraîné {formatRelativeDate(currentModel.training_date)}
                  </Typography>
                </Box>
                <Box sx={{ textAlign: 'right' }}>
                  {quality && (
                    <Chip
                      label={`${quality.label}`}
                      color={quality.color}
                      sx={{ mb: 1, fontSize: '0.9rem', fontWeight: 'bold' }}
                    />
                  )}
                  <Typography variant="caption" display="block" color="text.secondary">
                    Durée: {formatDuration(currentModel.training_duration_seconds)}
                  </Typography>
                </Box>
              </Box>

              {/* Statistiques du modèle */}
              <Box sx={{ 
                display: 'grid', 
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
                gap: 2,
                mb: 3 
              }}>
                <Card variant="outlined" sx={{ p: 2 }}>
                  <Typography variant="caption" color="text.secondary" display="block" gutterBottom>
                    Type de modèle
                  </Typography>
                  <Typography variant="h6">
                    {currentModel.model_type || 'N/A'}
                  </Typography>
                </Card>
                
                <Card variant="outlined" sx={{ p: 2 }}>
                  <Typography variant="caption" color="text.secondary" display="block" gutterBottom>
                    Signatures utilisées
                  </Typography>
                  <Typography variant="h6">
                    {currentModel.num_signatures}
                  </Typography>
                </Card>
                
                <Card variant="outlined" sx={{ p: 2 }}>
                  <Typography variant="caption" color="text.secondary" display="block" gutterBottom>
                    Appareils détectés
                  </Typography>
                  <Typography variant="h6">
                    {currentModel.num_classes}
                  </Typography>
                </Card>
                
                <Card variant="outlined" sx={{ p: 2 }}>
                  <Typography variant="caption" color="text.secondary" display="block" gutterBottom>
                    Score de qualité
                  </Typography>
                  <Typography variant="h6" color={quality ? `${quality.color}.main` : 'text.primary'}>
                    {quality ? `${quality.score}${quality.unit}` : 'N/A'}
                  </Typography>
                </Card>
              </Box>

              {/* Métriques détaillées */}
              <Card variant="outlined" sx={{ p: 2, mb: 2 }}>
                <Typography variant="subtitle2" gutterBottom>
                  Métriques d'entraînement
                </Typography>
                {formatMetrics(currentModel)}
              </Card>

              {/* Actions */}
              <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
                <Button
                  variant="outlined"
                  color="error"
                  size="small"
                  startIcon={<DeleteIcon />}
                  onClick={() => handleOpenDeleteDialog(
                    currentModel.id, 
                    currentModel.model_name
                  )}
                  disabled={deleteLoading}
                >
                  Supprimer le modèle
                </Button>
              </Box>
            </Box>
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
            Êtes-vous sûr de vouloir supprimer le modèle <strong>{deleteDialog.modelName}</strong> ?
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
          
          {getDeleteWarning()}
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
    </>
  );
};

export default NilmTraining;
