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
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Toolbar,
} from '@mui/material';
import { Check, Close, Search, MoreVert } from '@mui/icons-material';
import InsightsIcon from '@mui/icons-material/Insights';
import api, { apiService } from '../services/api';
import { detectionsWS } from '../services/websocket';
import { useChart } from '../context/ChartContext';
import { useApplianceColors } from '../context/ApplianceColorsContext';

// Icône Google Material Symbols pour Delete
const DeleteIcon = () => (
  <span className="material-symbols-outlined" style={{ fontSize: '20px' }}>
    delete
  </span>
);

// Icône Google Material Symbols pour qualité de détection
const QualityIcon = ({ confidence }) => {
  const getColor = () => {
    if (confidence < 0.6) return '#f44336'; // Rouge
    if (confidence < 0.8) return '#ff9800'; // Orange
    return '#4caf50'; // Vert
  };

  return (
    <span 
      className="material-symbols-outlined" 
      style={{ 
        fontSize: '20px',
        color: getColor()
      }}
    >
      psychology_alt
    </span>
  );
};

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
          title="Détections IA d'appareils"
          avatar={<InsightsIcon />}
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
          title="Détections IA d'appareils"
          titleTypographyProps={{ variant: 'h5' }}
          subheader={`${totalDetections} détection${totalDetections !== 1 ? 's' : ''} dans la période visible`}
          avatar={<InsightsIcon />}
        />
        
        {/* Toolbar avec actions */}
        <Toolbar 
          variant="dense" 
          sx={{ 
            px: 2,
            py: 1,
            minHeight: 48,
            bgcolor: 'action.hover',
            borderTop: 1,
            borderBottom: 1,
            borderColor: 'divider',
            gap: 1,
            justifyContent: 'flex-start'
          }}
        >
          <Tooltip title="Lancer la détection des appareils">
            <span>
              <Button
                variant="contained"
                size="small"
                color="success"
                startIcon={detectLoading ? <CircularProgress size={16} color="inherit" /> : <Search />}
                onClick={handleDetect}
                disabled={detectLoading}
                sx={{ textTransform: 'none' }}
              >
                Détecter
              </Button>
            </span>
          </Tooltip>
          
          <Box sx={{ flexGrow: 1 }} />
          
          <Tooltip title="Supprimer toutes les détections">
            <span>
              <Button
                variant="outlined"
                size="small"
                color="error"
                startIcon={deleteAllLoading ? <CircularProgress size={16} color="inherit" /> : <DeleteIcon />}
                onClick={handleOpenDeleteAllDialog}
                disabled={deleteAllLoading || totalDetections === 0}
                sx={{ textTransform: 'none' }}
              >
                {deleteAllLoading ? 'Suppression...' : 'Tout supprimer'}
              </Button>
            </span>
          </Tooltip>
        </Toolbar>

        <CardContent sx={{ flexGrow: 1, overflow: 'hidden', p: 0, display: 'flex', flexDirection: 'column' }}>
          {((loading && detections.length === 0) || totalDetections === 0) && (
            <Box sx={{ p: 2 }}>
              {loading && detections.length === 0 && <LinearProgress />}

              {totalDetections === 0 && !loading && (
                <Typography color="textSecondary" align="center" variant="body2">
                  Aucune détection
                </Typography>
              )}
            </Box>
          )}

          {totalDetections > 0 && (
            <>
              <TableContainer sx={{ flexGrow: 1, overflow: 'auto' }}>
                <Table stickyHeader size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell sx={{ fontWeight: 600 }}>Appareil</TableCell>
                      <TableCell align="left" sx={{ fontWeight: 600 }}>Détails</TableCell>
                      <TableCell align="center" sx={{ width: '40px', p: 1 }}></TableCell>
                      <TableCell align="right" sx={{ width: '40px', p: 1 }}></TableCell>
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
                        <TableCell colSpan={4} align="center" sx={{ py: 3 }}>
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
            startIcon={deleteAllLoading ? <CircularProgress size={20} /> : <DeleteIcon />}
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
  const { getApplianceColor } = useApplianceColors();
  const [anchorEl, setAnchorEl] = useState(null);
  const open = Boolean(anchorEl);
  
  const startTime = new Date(detection.start_time);
  const endTime = new Date(detection.end_time);
  const durationSeconds = Math.round((endTime - startTime) / 1000);

  // Statut de validation
  const isValidated = detection.user_validated === true && detection.is_correct === true;
  const isInvalidated = detection.user_validated === true && detection.is_correct === false;

  const handleMenuClick = (event) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleValidateClick = () => {
    handleMenuClose();
    onValidate(detection);
  };

  const handleInvalidateClick = () => {
    handleMenuClose();
    onInvalidate(detection);
  };

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

  const formatHumanizedDate = (date) => {
    const now = new Date();
    const diffMs = now - date;
    const diffSeconds = Math.floor(diffMs / 1000);
    const diffMinutes = Math.floor(diffSeconds / 60);
    const diffHours = Math.floor(diffMinutes / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffSeconds < 60) {
      return `il y a ${diffSeconds} seconde${diffSeconds !== 1 ? 's' : ''}`;
    } else if (diffMinutes < 60) {
      return `il y a ${diffMinutes} minute${diffMinutes !== 1 ? 's' : ''}`;
    } else if (diffHours < 24) {
      return `il y a ${diffHours} heure${diffHours !== 1 ? 's' : ''}`;
    } else if (diffDays < 7) {
      return `il y a ${diffDays} jour${diffDays !== 1 ? 's' : ''}`;
    } else if (diffDays < 30) {
      const weeks = Math.floor(diffDays / 7);
      return `il y a ${weeks} semaine${weeks !== 1 ? 's' : ''}`;
    } else if (diffDays < 365) {
      const months = Math.floor(diffDays / 30);
      return `il y a ${months} mois`;
    } else {
      const years = Math.floor(diffDays / 365);
      return `il y a ${years} an${years !== 1 ? 's' : ''}`;
    }
  };

  const formatDurationMinutes = (seconds) => {
    if (!seconds) return '0';
    return Math.round(seconds / 60);
  };

  const confidenceScore = detection.confidence_score || 0;

  return (
    <TableRow
      hover
      sx={{
        transition: 'background-color 0.2s ease',
      }}
    >
      <TableCell sx={{ fontWeight: 500, width: '40%', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
          <Box
            sx={{
              width: 20,
              height: 20,
              borderRadius: '50%',
              backgroundColor: getApplianceColor(detection.appliance_id),
              flexShrink: 0,
            }}
          />
          {isValidated && (
            <Tooltip title="Détection validée comme correcte">
              <Check fontSize="small" color="success" />
            </Tooltip>
          )}
          {isInvalidated && (
            <Tooltip title="Détection marquée comme incorrecte">
              <Close fontSize="small" color="error" />
            </Tooltip>
          )}
          <Typography variant="body1" sx={{ fontWeight: 500, color: getApplianceColor(detection.appliance_id) }}>
            {detection.name || 'Inconnu'}
          </Typography>
        </Box>
      </TableCell>
      <TableCell sx={{ fontSize: 'small', verticalAlign: 'middle', whiteSpace: 'normal' }}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.25 }}>
          <Typography variant="body2" component="div">
            à <strong>{formatTimeOnly(startTime)}</strong> pendant <strong>{formatDurationMinutes(durationSeconds)}min</strong>
          </Typography>
          <Typography variant="caption" color="text.secondary" component="div" sx={{ fontWeight: 300, fontSize: '0.7rem' }}>
            {formatHumanizedDate(startTime)} ({formatDateTime(startTime)} - {formatTimeOnly(endTime)})
          </Typography>
        </Box>
      </TableCell>
      <TableCell align="center" sx={{ width: '40px', p: 1 }}>
        <Tooltip title={`Confiance: ${Math.round(confidenceScore * 100)}%`}>
          <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
            <QualityIcon confidence={confidenceScore} />
          </Box>
        </Tooltip>
      </TableCell>
      <TableCell align="right" sx={{ width: '40px', p: 1 }}>
        <IconButton
          size="small"
          onClick={handleMenuClick}
          aria-label="actions"
        >
          <MoreVert fontSize="small" />
        </IconButton>
        <Menu
          anchorEl={anchorEl}
          open={open}
          onClose={handleMenuClose}
          anchorOrigin={{
            vertical: 'bottom',
            horizontal: 'right',
          }}
          transformOrigin={{
            vertical: 'top',
            horizontal: 'right',
          }}
        >
          <MenuItem onClick={handleValidateClick} disabled={isValidated}>
            <ListItemIcon>
              <Check fontSize="small" color={isValidated ? "disabled" : "success"} />
            </ListItemIcon>
            <ListItemText>
              {isValidated ? "Déjà validée" : "Cette détection est correcte"}
            </ListItemText>
          </MenuItem>
          <MenuItem onClick={handleInvalidateClick} disabled={isInvalidated}>
            <ListItemIcon>
              <Close fontSize="small" color={isInvalidated ? "disabled" : "error"} />
            </ListItemIcon>
            <ListItemText>
              {isInvalidated ? "Déjà invalidée" : "Cette détection est incorrecte"}
            </ListItemText>
          </MenuItem>
        </Menu>
      </TableCell>
    </TableRow>
  );
}

export default DetectionsList;
