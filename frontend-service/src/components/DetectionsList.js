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
import { Timeline, DeleteSweep, CheckCircle, Cancel, Search } from '@mui/icons-material';
import api, { apiService } from '../services/api';
import { detectionsWS } from '../services/websocket';
import { useChart } from '../context/ChartContext';

/**
 * Composant affichant les détections d'appareils récentes
 */
function DetectionsList() {
  const { visibleTimeRange } = useChart();
  const [detections, setDetections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [totalDetections, setTotalDetections] = useState(0);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });
  const [deleteAllDialogOpen, setDeleteAllDialogOpen] = useState(false);
  const [deleteAllLoading, setDeleteAllLoading] = useState(false);
  const [detectLoading, setDetectLoading] = useState(false);

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

  const handleSnackbarClose = () => {
    setSnackbar({ ...snackbar, open: false });
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

  const handleDetect = async () => {
    setDetectLoading(true);
    try {
      const response = await api.post('/api/nilm/detect');
      setSnackbar({
        open: true,
        message: `Détection lancée (Task ID: ${response.data.task_id})`,
        severity: 'success',
      });
    } catch (error) {
      setSnackbar({
        open: true,
        message: `Erreur: ${error.response?.data?.detail || error.message}`,
        severity: 'error',
      });
    } finally {
      setDetectLoading(false);
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
          title="Détections d'appareils"
          titleTypographyProps={{ variant: 'h5' }}
          subheader={`${totalDetections} détection${totalDetections !== 1 ? 's' : ''} dans la période visible`}
          avatar={<Timeline />}
          action={
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
              <Tooltip title="Lancer la détection des appareils">
                <span>
                  <IconButton
                    color="success"
                    onClick={handleDetect}
                    disabled={detectLoading}
                  >
                    {detectLoading ? <CircularProgress size={24} /> : <Search />}
                  </IconButton>
                </span>
              </Tooltip>
              <Tooltip title="Supprimer toutes les détections">
                <span>
                  <IconButton
                    color="error"
                    onClick={handleOpenDeleteAllDialog}
                    disabled={deleteAllLoading || totalDetections === 0}
                  >
                    {deleteAllLoading ? <CircularProgress size={24} /> : <DeleteSweep />}
                  </IconButton>
                </span>
              </Tooltip>
            </Box>
          }
        />
        <CardContent sx={{ flexGrow: 1, overflow: 'hidden', p: 2, display: 'flex', flexDirection: 'column' }}>
          {loading && detections.length === 0 && <LinearProgress />}

          {totalDetections === 0 && !loading && (
            <Typography color="textSecondary" align="center" variant="body2">
              Aucune détection
            </Typography>
          )}

          {totalDetections > 0 && (
            <>
              <TableContainer sx={{ flexGrow: 1, overflow: 'auto' }}>
                <Table stickyHeader size="small">
                  <TableHead>
                    <TableRow sx={{ backgroundColor: '#f5f5f5' }}>
                      <TableCell>Appareil</TableCell>
                      <TableCell align="right">Plage horaire</TableCell>
                      <TableCell align="right" sx={{ width: '100px', padding: '6px 16px' }}></TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {detections.map((detection) => (
                      <DetectionRow
                        key={detection.id}
                        detection={detection}
                        onValidate={handleValidate}
                        onInvalidate={handleInvalidate}
                      />
                    ))}
                    {loading && (
                      <TableRow>
                        <TableCell colSpan={3} align="center" sx={{ py: 3 }}>
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
function DetectionRow({ detection, onValidate, onInvalidate }) {
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

  const formatDuration = (minutes) => {
    if (minutes < 60) {
      return `${minutes} ${minutes === 1 ? 'minute' : 'minutes'}`;
    } else {
      const hours = Math.floor(minutes / 60);
      const remainingMinutes = minutes % 60;
      if (remainingMinutes === 0) {
        return `${hours} ${hours === 1 ? 'heure' : 'heures'}`;
      }
      return `${hours} ${hours === 1 ? 'heure' : 'heures'} et ${remainingMinutes} ${remainingMinutes === 1 ? 'minute' : 'minutes'}`;
    }
  };

  // Background selon la confiance : rouge si < 0.6, orange si >= 0.6 et < 0.8
  const confidenceScore = detection.confidence_score || 0;
  const hasLowConfidence = confidenceScore < 0.6;
  const hasMediumConfidence = confidenceScore >= 0.6 && confidenceScore < 0.8;
  
  const backgroundColor = isValidated 
    ? 'rgba(76, 175, 80, 0.08)' 
    : isInvalidated 
    ? 'rgba(244, 67, 54, 0.08)' 
    : hasLowConfidence 
    ? 'rgba(244, 67, 54, 0.05)' 
    : hasMediumConfidence
    ? 'rgba(255, 152, 0, 0.05)'
    : 'inherit';
    
  const hoverColor = isValidated 
    ? 'rgba(76, 175, 80, 0.15)' 
    : isInvalidated 
    ? 'rgba(244, 67, 54, 0.15)' 
    : hasLowConfidence 
    ? 'rgba(244, 67, 54, 0.1)' 
    : hasMediumConfidence
    ? 'rgba(255, 152, 0, 0.1)'
    : 'rgba(0, 0, 0, 0.04)';

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
          <Box>
            <Typography variant="body2" component="div" fontWeight="medium">
              {detection.name || 'Inconnu'}
            </Typography>
            <Typography variant="caption" color="text.secondary" component="div" sx={{ fontWeight: 300, fontSize: '0.7rem' }}>
              {detection.avg_power ? `${Math.round(detection.avg_power / 100) * 100} W` : 'N/A'}
            </Typography>
          </Box>
        </Box>
      </TableCell>
      <TableCell align="right" sx={{ fontSize: 'small', whiteSpace: 'nowrap' }}>
        <Box>
          <Typography variant="body2" component="div">
            {`${formatDateTime(startTime)} -> ${formatTimeOnly(endTime)}`}
          </Typography>
          <Typography variant="caption" color="text.secondary" component="div" sx={{ fontWeight: 300, fontSize: '0.7rem' }}>
            {formatDuration(durationMinutes)}
          </Typography>
        </Box>
      </TableCell>
      <TableCell align="right" sx={{ width: '100px', padding: '6px 16px' }}>
        <Box sx={{ display: 'flex', gap: 0.5, justifyContent: 'flex-end' }}>
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
        </Box>
      </TableCell>
    </TableRow>
  );
}

export default DetectionsList;
