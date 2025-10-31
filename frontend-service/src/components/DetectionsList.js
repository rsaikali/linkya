import React, { useEffect, useState, useCallback } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  LinearProgress,
  Alert,
  Typography,
  Chip,
  CircularProgress,
  Box,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Button,
  Snackbar,
} from '@mui/material';
import { Timeline, Delete, Search as DetectIcon, CheckCircle, Cancel, DeleteSweep } from '@mui/icons-material';
import api, { apiService } from '../services/api';
import { detectionsWS } from '../services/websocket';
import { useChart } from '../context/ChartContext';

/**
 * Composant affichant les détections d'appareils récentes
 */
function DetectionsList({ compact = false }) {
  const { visibleTimeRange } = useChart();
  const [detections, setDetections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [totalDetections, setTotalDetections] = useState(0);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [detectionToDelete, setDetectionToDelete] = useState(null);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });
  const [detectLoading, setDetectLoading] = useState(false);
  const [deleteAllDialogOpen, setDeleteAllDialogOpen] = useState(false);
  const [deleteAllLoading, setDeleteAllLoading] = useState(false);

  const fetchDetections = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Si on a une période visible depuis le graphique, filtrer les détections
      let allDetections = [];
      if (visibleTimeRange) {
        // Récupérer toutes les détections
        const data = await apiService.getDetections(null);
        const detectionsArray = data?.detections || data || [];
        
        // Filtrer celles qui sont dans la période visible
        const startTime = visibleTimeRange.startTime.getTime();
        const endTime = visibleTimeRange.endTime.getTime();
        
        allDetections = detectionsArray.filter(d => {
          const detectionStart = new Date(d.start_time).getTime();
          const detectionEnd = new Date(d.end_time).getTime();
          
          // Une détection est visible si elle chevauche la période
          return (detectionStart <= endTime && detectionEnd >= startTime);
        });
      } else {
        // Sinon, récupérer toutes les détections (fallback)
        const data = await apiService.getDetections(null);
        allDetections = data?.detections || data || [];
      }
      
      setDetections(allDetections);
      setTotalDetections(allDetections.length);
    } catch (err) {
      console.error('Erreur lors de la récupération des détections:', err);
      setError('Impossible de charger les détections');
    } finally {
      setLoading(false);
    }
  }, [visibleTimeRange]);

  useEffect(() => {
    fetchDetections();

    // Setup WebSocket for real-time detection updates
    const handleNewDetection = (detection) => {
      // Refresh the list to include the new detection
      fetchDetections();
    };

    const handleDetectionStart = (data) => {
    };

    const handleDetectionComplete = (data) => {
      // Refresh the entire list when job is complete
      fetchDetections();
    };

    const handleError = (errorData) => {
      console.error('[DetectionsList] Detections WebSocket error:', errorData);
    };

    // Register event handlers
    detectionsWS.on('new_detection', handleNewDetection);
    detectionsWS.on('detection_start', handleDetectionStart);
    detectionsWS.on('detection_complete', handleDetectionComplete);
    detectionsWS.on('error', handleError);

    // Connect to WebSocket
    detectionsWS.connect();

    // Cleanup on unmount
    return () => {
      detectionsWS.off('new_detection', handleNewDetection);
      detectionsWS.off('detection_start', handleDetectionStart);
      detectionsWS.off('detection_complete', handleDetectionComplete);
      detectionsWS.off('error', handleError);
    };
  }, [fetchDetections]);

  const handleDeleteClick = (detection) => {
    setDetectionToDelete(detection);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!detectionToDelete) return;

    try {
      await apiService.deleteDetection(detectionToDelete.id);
      setSnackbar({
        open: true,
        message: `Détection supprimée: ${detectionToDelete.name}`,
        severity: 'success',
      });
      
      // Rafraîchir la liste
      fetchDetections();
    } catch (err) {
      console.error('Erreur lors de la suppression:', err);
      setSnackbar({
        open: true,
        message: 'Erreur lors de la suppression de la détection',
        severity: 'error',
      });
    } finally {
      setDeleteDialogOpen(false);
      setDetectionToDelete(null);
    }
  };

  const handleDeleteCancel = () => {
    setDeleteDialogOpen(false);
    setDetectionToDelete(null);
  };

  const handleSnackbarClose = () => {
    setSnackbar({ ...snackbar, open: false });
  };

  const handleDetect = async () => {
    setDetectLoading(true);
    try {
      const response = await api.post('/api/nilm/detect');
      setSnackbar({
        open: true,
        message: `Détection lancée (Task ID: ${response.data.task_id})`,
        severity: 'success',
      });
      
      // List will refresh automatically via WebSocket detection_complete event
    } catch (error) {
      console.error('Erreur lors du lancement de la détection:', error);
      const errorMsg = error.response?.data?.detail || 'Erreur lors du lancement de la détection';
      setSnackbar({
        open: true,
        message: errorMsg,
        severity: 'error',
      });
    } finally {
      setDetectLoading(false);
    }
  };

  const handleValidate = async (detection) => {
    try {
      await apiService.validateDetection(detection.id);
      setSnackbar({
        open: true,
        message: `Détection validée: ${detection.name}`,
        severity: 'success',
      });
      fetchDetections();
    } catch (err) {
      setSnackbar({
        open: true,
        message: 'Erreur lors de la validation',
        severity: 'error',
      });
    }
  };

  const handleInvalidate = async (detection) => {
    try {
      await apiService.invalidateDetection(detection.id);
      setSnackbar({
        open: true,
        message: `Détection invalidée: ${detection.name}`,
        severity: 'info',
      });
      fetchDetections();
    } catch (err) {
      setSnackbar({
        open: true,
        message: 'Erreur lors de l\'invalidation',
        severity: 'error',
      });
    }
  };

  const handleOpenDeleteAllDialog = () => {
    setDeleteAllDialogOpen(true);
  };

  const handleCloseDeleteAllDialog = () => {
    setDeleteAllDialogOpen(false);
  };

  const handleConfirmDeleteAll = async () => {
    setDeleteAllLoading(true);
    try {
      const response = await api.delete('/api/detections');
      setSnackbar({
        open: true,
        message: response.data.message || 'Toutes les détections ont été supprimées',
        severity: 'success',
      });
      handleCloseDeleteAllDialog();
      // Rafraîchir la liste
      fetchDetections();
    } catch (error) {
      console.error('Erreur lors de la suppression des détections:', error);
      const errorMsg = error.response?.data?.detail || 'Erreur lors de la suppression des détections';
      setSnackbar({
        open: true,
        message: errorMsg,
        severity: 'error',
      });
    } finally {
      setDeleteAllLoading(false);
    }
  };

  if (error) {
    return (
      <Card>
        <CardHeader
          title="Détections"
          avatar={<Timeline />}
        />
        <CardContent>
          <Alert severity="error">{error}</Alert>
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
        <CardHeader
          title={compact ? "Détections" : "Détections d'appareils"}
          titleTypographyProps={{ variant: compact ? 'h6' : 'h5' }}
          subheader={`${totalDetections} détection${totalDetections !== 1 ? 's' : ''} dans la période visible`}
          avatar={<Timeline />}
          action={
            <Box sx={{ display: 'flex', alignItems: 'center', gap: compact ? 0.5 : 1.5, flexWrap: 'wrap' }}>
              {!compact && (
                <>
                  <Button
                    variant="outlined"
                    color="error"
                    size="small"
                    startIcon={deleteAllLoading ? <CircularProgress size={16} /> : <DeleteSweep />}
                    onClick={handleOpenDeleteAllDialog}
                    disabled={deleteAllLoading || totalDetections === 0}
                    sx={{ whiteSpace: 'nowrap' }}
                  >
                    Tout supprimer
                  </Button>
                  <Button
                    variant="contained"
                    color="secondary"
                    size="small"
                    startIcon={detectLoading ? <CircularProgress size={16} /> : <DetectIcon />}
                    onClick={handleDetect}
                    disabled={detectLoading}
                    sx={{ whiteSpace: 'nowrap' }}
                  >
                    {detectLoading ? 'Détection...' : 'Lancer détection'}
                  </Button>
                </>
              )}
              {compact && (
                <Tooltip title="Lancer détection">
                  <IconButton
                    color="secondary"
                    size="small"
                    onClick={handleDetect}
                    disabled={detectLoading}
                  >
                    {detectLoading ? <CircularProgress size={16} /> : <DetectIcon />}
                  </IconButton>
                </Tooltip>
              )}
              {loading && <CircularProgress size={24} />}
            </Box>
          }
        />
        <CardContent sx={{ flexGrow: 1, overflow: 'auto', p: compact ? 1 : 2 }}>
          {loading && detections.length === 0 && <LinearProgress />}

          {totalDetections === 0 && !loading && (
            <Typography color="textSecondary" align="center" variant="body2">
              Aucune détection
            </Typography>
          )}

          {totalDetections > 0 && (
            <>
              <TableContainer sx={{ maxHeight: compact ? '100%' : 600 }}>
                <Table stickyHeader size="small">
                  <TableHead>
                    <TableRow sx={{ backgroundColor: '#f5f5f5' }}>
                      <TableCell>Appareil</TableCell>
                      {!compact && <TableCell align="right">Plage horaire</TableCell>}
                      {compact && <TableCell align="right">Heure</TableCell>}
                      <TableCell align="right">Durée</TableCell>
                      {!compact && <TableCell align="right">Puissance</TableCell>}
                      {!compact && <TableCell align="center">Confiance</TableCell>}
                      <TableCell align="center">Actions</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {detections.map((detection) => (
                      <DetectionRow
                        key={detection.id}
                        detection={detection}
                        onDelete={handleDeleteClick}
                        onValidate={handleValidate}
                        onInvalidate={handleInvalidate}
                        compact={compact}
                      />
                    ))}
                    {loading && (
                      <TableRow>
                        <TableCell colSpan={compact ? 4 : 6} align="center" sx={{ py: 3 }}>
                          <CircularProgress size={32} />
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </TableContainer>
            </>
          )}
        </CardContent>
      </Card>

      {/* Dialog de confirmation de suppression */}
      <Dialog
        open={deleteDialogOpen}
        onClose={handleDeleteCancel}
        aria-labelledby="delete-dialog-title"
      >
        <DialogTitle id="delete-dialog-title">
          Confirmer la suppression
        </DialogTitle>
        <DialogContent>
          <DialogContentText>
            Êtes-vous sûr de vouloir supprimer cette détection de{' '}
            <strong>{detectionToDelete?.name}</strong> ?
            <br />
            Cette action est irréversible.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleDeleteCancel} color="inherit">
            Annuler
          </Button>
          <Button onClick={handleDeleteConfirm} color="error" variant="contained">
            Supprimer
          </Button>
        </DialogActions>
      </Dialog>

      {/* Dialog de confirmation de suppression de toutes les détections */}
      <Dialog
        open={deleteAllDialogOpen}
        onClose={handleCloseDeleteAllDialog}
        aria-labelledby="delete-all-dialog-title"
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle id="delete-all-dialog-title">
          Confirmer la suppression de toutes les détections
        </DialogTitle>
        <DialogContent>
          <DialogContentText>
            Êtes-vous sûr de vouloir supprimer <strong>toutes les {totalDetections} détection{totalDetections !== 1 ? 's' : ''}</strong> ?
            <br />
            <br />
            ⚠️ <strong>Attention :</strong> Cette action supprimera définitivement toutes les détections de la base de données.
            <br />
            <br />
            Les signatures négatives créées à partir de détections invalidées seront conservées.
            <br />
            <br />
            <strong>Cette action est irréversible.</strong>
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button 
            onClick={handleCloseDeleteAllDialog} 
            color="inherit"
            disabled={deleteAllLoading}
          >
            Annuler
          </Button>
          <Button 
            onClick={handleConfirmDeleteAll} 
            color="error" 
            variant="contained"
            disabled={deleteAllLoading}
            startIcon={deleteAllLoading ? <CircularProgress size={20} /> : <DeleteSweep />}
          >
            {deleteAllLoading ? 'Suppression...' : 'Tout supprimer'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Snackbar pour les notifications */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={handleSnackbarClose}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert
          onClose={handleSnackbarClose}
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

/**
 * Ligne de tableau pour une détection
 */
function DetectionRow({ detection, onDelete, onValidate, onInvalidate, compact = false }) {
  const startTime = new Date(detection.start_time);
  const endTime = new Date(detection.end_time);
  const durationMinutes = Math.round((endTime - startTime) / 60000);

  // Statut de validation
  const isValidated = detection.user_validated === true && detection.is_correct === true;
  const isInvalidated = detection.user_validated === true && detection.is_correct === false;

  const formatDateTime = (date) => {
    return date.toLocaleString('fr-FR', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const formatTimeOnly = (date) => {
    return date.toLocaleTimeString('fr-FR', {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getConfidenceColor = (score) => {
    if (score >= 0.8) return 'success';
    if (score >= 0.6) return 'warning';
    return 'error';
  };

  const getConfidenceLabel = (score) => {
    if (score >= 0.8) return 'Élevée';
    if (score >= 0.6) return 'Moyenne';
    return 'Faible';
  };

  const getConfidenceBackgroundColor = (score) => {
    if (score >= 0.8) return 'rgba(76, 175, 80, 0.08)'; // Vert
    if (score >= 0.6) return 'rgba(255, 152, 0, 0.08)'; // Orange
    return 'rgba(244, 67, 54, 0.08)'; // Rouge
  };

  const getConfidenceHoverColor = (score) => {
    if (score >= 0.8) return 'rgba(76, 175, 80, 0.15)';
    if (score >= 0.6) return 'rgba(255, 152, 0, 0.15)';
    return 'rgba(244, 67, 54, 0.15)';
  };

  // En mode compact, utiliser la confiance pour la couleur de fond
  const backgroundColor = compact 
    ? (isValidated ? 'rgba(76, 175, 80, 0.12)' : isInvalidated ? 'rgba(244, 67, 54, 0.12)' : getConfidenceBackgroundColor(detection.confidence_score || 0))
    : (isValidated ? 'rgba(76, 175, 80, 0.08)' : isInvalidated ? 'rgba(244, 67, 54, 0.08)' : 'inherit');

  const hoverColor = compact
    ? (isValidated ? 'rgba(76, 175, 80, 0.18)' : isInvalidated ? 'rgba(244, 67, 54, 0.18)' : getConfidenceHoverColor(detection.confidence_score || 0))
    : (isValidated ? 'rgba(76, 175, 80, 0.15)' : isInvalidated ? 'rgba(244, 67, 54, 0.15)' : 'rgba(0, 0, 0, 0.04)');

  return (
    <TableRow
      hover
      sx={{
        backgroundColor: backgroundColor,
        '&:hover': {
          backgroundColor: hoverColor,
        },
        transition: 'background-color 0.2s ease',
      }}
    >
      <TableCell sx={{ fontWeight: 500 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
          {isValidated && (
            <Tooltip title="Détection validée comme correcte">
              <CheckCircle fontSize="small" color="success" />
            </Tooltip>
          )}
          {isInvalidated && (
            <Tooltip title="Détection marquée comme incorrecte">
              <Cancel fontSize="small" color="error" />
            </Tooltip>
          )}
          {compact ? (
            <Tooltip title={`${detection.name || 'Inconnu'} - Confiance: ${getConfidenceLabel(detection.confidence_score || 0)}`}>
              <Typography
                variant="body2"
                sx={{
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  maxWidth: '120px',
                }}
              >
                {detection.name || 'Inconnu'}
              </Typography>
            </Tooltip>
          ) : (
            <span>{detection.name || 'Inconnu'}</span>
          )}
        </Box>
      </TableCell>
      {!compact && (
        <TableCell align="right" sx={{ fontSize: 'small', whiteSpace: 'nowrap' }}>
          {`${formatDateTime(startTime)} -> ${formatTimeOnly(endTime)}`}
        </TableCell>
      )}
      {compact && (
        <TableCell align="right" sx={{ fontSize: 'x-small', whiteSpace: 'nowrap' }}>
          {formatTimeOnly(startTime)}
        </TableCell>
      )}
      <TableCell align="right">
        <Typography variant="body2" fontSize={compact ? 'x-small' : 'small'}>
          {durationMinutes < 60
            ? `${durationMinutes}m`
            : `${Math.floor(durationMinutes / 60)}h ${durationMinutes % 60}m`}
        </Typography>
      </TableCell>
      {!compact && (
        <>
          <TableCell align="right">
            <Typography variant="body2">
              {detection.avg_power?.toFixed(1) || 'N/A'}
            </Typography>
          </TableCell>
          <TableCell align="center">
            <Chip
              label={getConfidenceLabel(detection.confidence_score || 0)}
              color={getConfidenceColor(detection.confidence_score || 0)}
              size="small"
              variant="outlined"
            />
          </TableCell>
        </>
      )}
      <TableCell align="center">
        <Box sx={{ display: 'flex', gap: compact ? 0 : 0.5, justifyContent: 'center' }}>
          {!compact && (
            <>
              <Tooltip title={isValidated ? "Déjà validée" : "Marquer comme correcte"}>
                <span>
                  <IconButton
                    size="small"
                    color="success"
                    onClick={() => onValidate(detection)}
                    aria-label="valider"
                    disabled={isValidated}
                  >
                    <CheckCircle fontSize="small" />
                  </IconButton>
                </span>
              </Tooltip>
              <Tooltip title={isInvalidated ? "Déjà invalidée" : "Marquer comme incorrecte"}>
                <span>
                  <IconButton
                    size="small"
                    color="error"
                    onClick={() => onInvalidate(detection)}
                    aria-label="invalider"
                    disabled={isInvalidated}
                  >
                    <Cancel fontSize="small" />
                  </IconButton>
                </span>
              </Tooltip>
            </>
          )}
          <Tooltip title={compact ? `${detection.avg_power?.toFixed(1) || 'N/A'} W - Supprimer` : "Supprimer cette détection"}>
            <IconButton
              size="small"
              color="error"
              onClick={() => onDelete(detection)}
              aria-label="supprimer"
            >
              <Delete fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      </TableCell>
    </TableRow>
  );
}

export default DetectionsList;
