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
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Button,
  Snackbar,
  Box,
  CircularProgress,
} from '@mui/material';
import { Delete, DeleteSweep, FileDownload, FileUpload, Assignment, ModelTraining } from '@mui/icons-material';
import api, { apiService } from '../services/api';
import { importProgressWS } from '../services/websocket';

/**
 * Composant affichant la liste des signatures
 */
function SignaturesList() {
  const [signatures, setSignatures] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [totalSignatures, setTotalSignatures] = useState(0);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [signatureToDelete, setSignatureToDelete] = useState(null);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });
  const [deleteAllDialogOpen, setDeleteAllDialogOpen] = useState(false);
  const [deleteAllLoading, setDeleteAllLoading] = useState(false);
  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [importLoading, setImportLoading] = useState(false);
  const [importResult, setImportResult] = useState(null);
  const [importProgress, setImportProgress] = useState({
    status: 'idle',
    totalLines: 0,
    successCount: 0,
    errorCount: 0,
    progressPercent: 0
  });
  const [trainLoading, setTrainLoading] = useState(false);

  const showSnackbar = (message, severity = 'success') => {
    setSnackbar({ open: true, message, severity });
  };

  const handleTrain = async () => {
    setTrainLoading(true);
    try {
      await api.post('/api/nilm/train');
      showSnackbar('Entraînement lancé avec succès', 'success');
    } catch (error) {
      showSnackbar(`Erreur: ${error.response?.data?.detail || error.message}`, 'error');
    } finally {
      setTrainLoading(false);
    }
  };

  const fetchSignatures = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Récupérer toutes les signatures
      const response = await api.get('/api/signatures');
      
      const data = response.data;
      
      if (data && data.signatures && Array.isArray(data.signatures)) {
        setSignatures(data.signatures);
        setTotalSignatures(data.total || data.signatures.length);
      } else {
        setSignatures([]);
        setTotalSignatures(0);
      }
    } catch (err) {
      console.error('Erreur lors de la récupération des signatures:', err);
      setError('Impossible de charger les signatures');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSignatures();
  }, [fetchSignatures]);

  // Setup WebSocket for import progress
  useEffect(() => {
    const handleImportStart = (data) => {
      console.log('✅ Import started:', data);
      setImportProgress({
        status: 'started',
        totalLines: 0,
        successCount: 0,
        errorCount: 0,
        progressPercent: 0
      });
    };

    const handleImportProgress = (data) => {
      console.log('📊 Import progress:', data);
      setImportProgress({
        status: 'processing',
        totalLines: data.total_lines || 0,
        successCount: data.success_count || 0,
        errorCount: data.error_count || 0,
        progressPercent: data.progress_percent || 0
      });
    };

    const handleImportComplete = (data) => {
      console.log('🎉 Import completed:', data);
      setImportProgress({
        status: 'completed',
        totalLines: data.total_lines || 0,
        successCount: data.success_count || 0,
        errorCount: data.error_count || 0,
        progressPercent: 100
      });
      
      // Rafraîchir la liste après 2 secondes
      setTimeout(() => {
        console.log('🔄 Rafraîchissement de la liste (1/3)');
        fetchSignatures();
        // Rafraîchir encore 2 fois
        setTimeout(() => {
          console.log('🔄 Rafraîchissement de la liste (2/3)');
          fetchSignatures();
        }, 2000);
        setTimeout(() => {
          console.log('🔄 Rafraîchissement de la liste (3/3)');
          fetchSignatures();
        }, 4000);
      }, 2000);
    };

    const handleImportError = (data) => {
      console.error('❌ Import error:', data);
      showSnackbar(data.error || 'Erreur lors de l\'import', 'error');
    };

    const handleConnected = () => {
      console.log('🔌 WebSocket Import connecté');
    };

    const handleDisconnected = () => {
      console.log('🔌 WebSocket Import déconnecté');
    };

    // Register WebSocket handlers
    importProgressWS.on('import_start', handleImportStart);
    importProgressWS.on('import_progress', handleImportProgress);
    importProgressWS.on('import_complete', handleImportComplete);
    importProgressWS.on('import_error', handleImportError);
    importProgressWS.on('connected', handleConnected);
    importProgressWS.on('disconnected', handleDisconnected);

    // Connect to WebSocket
    console.log('🚀 Connexion au WebSocket Import...');
    importProgressWS.connect();

    // Cleanup on unmount
    return () => {
      importProgressWS.off('import_start', handleImportStart);
      importProgressWS.off('import_progress', handleImportProgress);
      importProgressWS.off('import_complete', handleImportComplete);
      importProgressWS.off('import_error', handleImportError);
      importProgressWS.off('connected', handleConnected);
      importProgressWS.off('disconnected', handleDisconnected);
    };
  }, [fetchSignatures]);

  const handleExportCSV = async () => {
    try {
      const blob = await apiService.exportSignatures();

      // Créer un lien de téléchargement
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;

      // Générer le nom du fichier avec timestamp
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
      link.download = `nilmia_signatures_${timestamp}.csv`;

      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      showSnackbar('Signatures exportées avec succès', 'success');
    } catch (error) {
      showSnackbar('Erreur lors de l\'export des signatures', 'error');
    }
  };

  const handleImportClick = () => {
    setImportDialogOpen(true);
    setSelectedFile(null);
    setImportResult(null);
    setImportProgress({
      status: 'idle',
      totalLines: 0,
      successCount: 0,
      errorCount: 0,
      progressPercent: 0
    });
  };

  const handleFileChange = (event) => {
    const file = event.target.files[0];
    if (file) {
      if (file.type !== 'text/csv' && !file.name.endsWith('.csv')) {
        showSnackbar('Veuillez sélectionner un fichier CSV', 'error');
        return;
      }
      setSelectedFile(file);
    }
  };

  const handleImportConfirm = async () => {
    if (!selectedFile) {
      showSnackbar('Veuillez sélectionner un fichier', 'error');
      return;
    }

    setImportLoading(true);
    setImportProgress({
      status: 'uploading',
      totalLines: 0,
      successCount: 0,
      errorCount: 0,
      progressPercent: 0
    });

    try {
      const result = await apiService.importSignatures(selectedFile);
      setImportResult(result);

      if (result.error_count === 0) {
        showSnackbar(`${result.success_count} signature(s) importée(s) avec succès`, 'success');
        setImportDialogOpen(false);
      } else {
        showSnackbar(
          `Import terminé: ${result.success_count} succès, ${result.error_count} erreur(s)`,
          'warning'
        );
      }
    } catch (error) {
      showSnackbar('Erreur lors de l\'import des signatures', 'error');
      setImportResult({
        status: 'error',
        total_lines: 0,
        success_count: 0,
        error_count: 1,
        errors: [{ line: 0, error: error.message }]
      });
      setImportProgress({
        status: 'error',
        totalLines: 0,
        successCount: 0,
        errorCount: 1,
        progressPercent: 0
      });
    } finally {
      setImportLoading(false);
    }
  };

  const handleDeleteClick = (signature) => {
    setSignatureToDelete(signature);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!signatureToDelete) return;

    try {
      await api.delete(`/api/signatures/${signatureToDelete.id}`);
      
      setSnackbar({
        open: true,
        message: `Signature supprimée: ${signatureToDelete.appliance_name}`,
        severity: 'success'
      });
      
      // Rafraîchir la liste
      await fetchSignatures();
    } catch (err) {
      console.error('Erreur lors de la suppression de la signature:', err);
      setSnackbar({
        open: true,
        message: 'Erreur lors de la suppression',
        severity: 'error'
      });
    } finally {
      setDeleteDialogOpen(false);
      setSignatureToDelete(null);
    }
  };

  const handleDeleteAllClick = () => {
    setDeleteAllDialogOpen(true);
  };

  const handleDeleteAllConfirm = async () => {
    try {
      setDeleteAllLoading(true);
      const response = await api.delete('/api/signatures');
      
      setSnackbar({
        open: true,
        message: `${response.data.signatures_deleted} signature(s) supprimée(s)`,
        severity: 'success'
      });
      
      // Rafraîchir la liste
      await fetchSignatures();
    } catch (err) {
      console.error('Erreur lors de la suppression de toutes les signatures:', err);
      setSnackbar({
        open: true,
        message: 'Erreur lors de la suppression',
        severity: 'error'
      });
    } finally {
      setDeleteAllLoading(false);
      setDeleteAllDialogOpen(false);
    }
  };

  const formatDateTime = (dateString) => {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleString('fr-FR', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const formatTimeOnly = (dateString) => {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleTimeString('fr-FR', {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const formatDurationFull = (seconds) => {
    if (!seconds) return 'N/A';
    const minutes = Math.round(seconds / 60);
    
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

  const formatPower = (watts) => {
    if (watts === null || watts === undefined) return 'N/A';
    return `${Math.round(watts / 100) * 100} W`;
  };

  const getRowBackgroundColor = (isNegative) => {
    if (isNegative) {
      // Rouge très clair pour les signatures négatives
      return 'rgba(244, 67, 54, 0.08)';
    }
    // Vert très clair pour les signatures positives
    return 'rgba(76, 175, 80, 0.08)';
  };

  const getRowHoverBackgroundColor = (isNegative) => {
    if (isNegative) {
      // Rouge plus marqué au hover
      return 'rgba(244, 67, 54, 0.15)';
    }
    // Vert plus marqué au hover
    return 'rgba(76, 175, 80, 0.15)';
  };

  return (
    <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <CardHeader 
        title="Signatures d'appareils"
        titleTypographyProps={{ variant: 'h5' }}
        subheader={`${totalSignatures} signature(s)`}
        avatar={<Assignment />}
        action={
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
            <Tooltip title="Entraîner le modèle">
              <span>
                <IconButton
                  color="primary"
                  onClick={handleTrain}
                  disabled={trainLoading || totalSignatures === 0}
                >
                  {trainLoading ? <CircularProgress size={24} /> : <ModelTraining />}
                </IconButton>
              </span>
            </Tooltip>
            <Tooltip title="Exporter les signatures en CSV">
              <IconButton
                color="primary"
                onClick={handleExportCSV}
              >
                <FileDownload />
              </IconButton>
            </Tooltip>
            <Tooltip title="Importer des signatures depuis un CSV">
              <IconButton
                color="primary"
                onClick={handleImportClick}
              >
                <FileUpload />
              </IconButton>
            </Tooltip>
            <Tooltip title="Supprimer toutes les signatures">
              <span>
                <IconButton
                  color="error"
                  onClick={handleDeleteAllClick}
                  disabled={deleteAllLoading || totalSignatures === 0}
                >
                  {deleteAllLoading ? <CircularProgress size={24} /> : <DeleteSweep />}
                </IconButton>
              </span>
            </Tooltip>
          </Box>
        }
      />
      <CardContent sx={{ flexGrow: 1, overflow: 'auto', p: 2 }}>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {/* Section de progression d'importation */}
        {importProgress.status !== 'idle' && importProgress.status !== 'completed' && (
          <Box sx={{ mb: 2 }}>
            <Alert 
              severity="info" 
              icon={false}
              sx={{ 
                py: 2,
                backgroundColor: 'primary.50',
                borderLeft: 4,
                borderColor: 'primary.main'
              }}
            >
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <Typography variant="subtitle2" fontWeight="600" color="primary">
                    {importProgress.status === 'uploading' && '📤 Upload du fichier...'}
                    {importProgress.status === 'started' && '🚀 Initialisation de l\'import...'}
                    {importProgress.status === 'processing' && '⚙️ Traitement des signatures...'}
                  </Typography>
                  {importProgress.progressPercent > 0 && (
                    <Typography variant="body2" fontWeight="600" color="primary">
                      {importProgress.progressPercent}%
                    </Typography>
                  )}
                </Box>
                
                <LinearProgress 
                  variant={importProgress.progressPercent > 0 ? 'determinate' : 'indeterminate'}
                  value={importProgress.progressPercent}
                  sx={{ height: 8, borderRadius: 1 }}
                />
                
                {importProgress.totalLines > 0 && (
                  <Box sx={{ display: 'flex', gap: 3, mt: 0.5 }}>
                    <Typography variant="caption" color="text.secondary">
                      📊 Lignes: <strong>{importProgress.totalLines}</strong>
                    </Typography>
                    <Typography variant="caption" color="success.main">
                      ✅ Succès: <strong>{importProgress.successCount}</strong>
                    </Typography>
                    {importProgress.errorCount > 0 && (
                      <Typography variant="caption" color="error.main">
                        ❌ Erreurs: <strong>{importProgress.errorCount}</strong>
                      </Typography>
                    )}
                  </Box>
                )}
              </Box>
            </Alert>
          </Box>
        )}

        {/* Message de succès après import terminé */}
        {importProgress.status === 'completed' && importProgress.errorCount === 0 && (
          <Alert 
            severity="success" 
            onClose={() => setImportProgress({ ...importProgress, status: 'idle' })}
            sx={{ mb: 2 }}
          >
            <Typography variant="body2">
              🎉 Import terminé avec succès ! {importProgress.successCount} signature(s) importée(s).
              <br />
              <em>La liste se met à jour automatiquement...</em>
            </Typography>
          </Alert>
        )}

        {loading && <LinearProgress sx={{ mb: 2 }} />}

        <TableContainer>
          <Table stickyHeader size="small">
            <TableHead>
              <TableRow sx={{ backgroundColor: '#f5f5f5' }}>
                <TableCell>Appareil</TableCell>
                <TableCell align="right">Plage horaire</TableCell>
                <TableCell align="right" sx={{ width: '60px', padding: '6px 16px' }}></TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {signatures.length === 0 && !loading && (
                <TableRow>
                  <TableCell colSpan={3} align="center">
                    <Typography variant="body2" color="text.secondary">
                      Aucune signature enregistrée
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
              {signatures.map((signature) => (
                <TableRow 
                  key={signature.id}
                  sx={{
                    backgroundColor: getRowBackgroundColor(signature.is_negative),
                    '&:hover': {
                      backgroundColor: getRowHoverBackgroundColor(signature.is_negative),
                    },
                    transition: 'background-color 0.2s ease',
                  }}
                >
                  <TableCell>
                    <Box>
                      <Typography variant="body2" fontWeight="medium" component="div">
                        {signature.appliance_name}
                      </Typography>
                      <Typography variant="caption" color="text.secondary" component="div" sx={{ fontWeight: 300, fontSize: '0.7rem' }}>
                        {formatPower(signature.avg_power)}
                      </Typography>
                    </Box>
                  </TableCell>
                  <TableCell align="right" sx={{ fontSize: 'small', whiteSpace: 'nowrap' }}>
                    <Box>
                      <Typography variant="body2" component="div">
                        {`${formatDateTime(signature.start_time)} -> ${formatTimeOnly(signature.end_time)}`}
                      </Typography>
                      <Typography variant="caption" color="text.secondary" component="div" sx={{ fontWeight: 300, fontSize: '0.7rem' }}>
                        {formatDurationFull(signature.duration_seconds)}
                      </Typography>
                    </Box>
                  </TableCell>
                  <TableCell align="right" sx={{ width: '60px', padding: '6px 16px' }}>
                    <Tooltip title="Supprimer">
                      <IconButton
                        color="error"
                        size="small"
                        onClick={() => handleDeleteClick(signature)}
                      >
                        <Delete fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>

      </CardContent>

      {/* Dialog de confirmation de suppression */}
      <Dialog
        open={deleteDialogOpen}
        onClose={() => setDeleteDialogOpen(false)}
      >
        <DialogTitle>Confirmer la suppression</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Voulez-vous vraiment supprimer la signature de{' '}
            <strong>{signatureToDelete?.appliance_name}</strong> ?
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)}>
            Annuler
          </Button>
          <Button onClick={handleDeleteConfirm} color="error" autoFocus>
            Supprimer
          </Button>
        </DialogActions>
      </Dialog>

      {/* Dialog de confirmation de suppression totale */}
      <Dialog
        open={deleteAllDialogOpen}
        onClose={() => !deleteAllLoading && setDeleteAllDialogOpen(false)}
      >
        <DialogTitle>Supprimer toutes les signatures</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Voulez-vous vraiment supprimer <strong>toutes les {totalSignatures} signature(s)</strong> ?
            <br />
            Cette action est irréversible.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button 
            onClick={() => setDeleteAllDialogOpen(false)}
            disabled={deleteAllLoading}
          >
            Annuler
          </Button>
          <Button 
            onClick={handleDeleteAllConfirm} 
            color="error" 
            autoFocus
            disabled={deleteAllLoading}
          >
            {deleteAllLoading ? 'Suppression...' : 'Supprimer tout'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Dialog d'import de signatures */}
      <Dialog
        open={importDialogOpen}
        onClose={() => !importLoading && setImportDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Importer des signatures</DialogTitle>
        <DialogContent>
          <DialogContentText sx={{ mb: 2 }}>
            Sélectionnez un fichier CSV contenant les signatures à importer.
            <br />
            Format attendu: appliance_name, start_time, end_time
          </DialogContentText>

          <input
            accept=".csv"
            style={{ display: 'none' }}
            id="csv-file-input"
            type="file"
            onChange={handleFileChange}
          />
          <label htmlFor="csv-file-input">
            <Button
              variant="outlined"
              component="span"
              fullWidth
              disabled={importLoading}
            >
              {selectedFile ? selectedFile.name : 'Choisir un fichier CSV'}
            </Button>
          </label>

          {/* Barre de progression en temps réel */}
          {importLoading && importProgress.status !== 'idle' && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {importProgress.status === 'uploading' && 'Upload du fichier...'}
                {importProgress.status === 'started' && 'Initialisation de l\'import...'}
                {importProgress.status === 'processing' && 'Traitement des signatures...'}
                {importProgress.status === 'completed' && 'Import terminé !'}
              </Typography>
              
              <LinearProgress 
                variant={importProgress.progressPercent > 0 ? 'determinate' : 'indeterminate'}
                value={importProgress.progressPercent}
                sx={{ mb: 1 }}
              />
              
              {importProgress.totalLines > 0 && (
                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography variant="caption" color="text.secondary">
                    Lignes traitées: {importProgress.totalLines}
                  </Typography>
                  <Typography variant="caption" color="success.main">
                    Succès: {importProgress.successCount}
                  </Typography>
                  {importProgress.errorCount > 0 && (
                    <Typography variant="caption" color="error.main">
                      Erreurs: {importProgress.errorCount}
                    </Typography>
                  )}
                </Box>
              )}
            </Box>
          )}

          {importResult && !importLoading && (
            <Box sx={{ mt: 2 }}>
              <Alert severity={importResult.error_count === 0 ? 'success' : 'warning'}>
                <Typography variant="body2">
                  Lignes traitées: {importResult.total_lines}
                  <br />
                  Succès: {importResult.success_count}
                  <br />
                  Erreurs: {importResult.error_count}
                </Typography>
              </Alert>

              {importResult.errors && importResult.errors.length > 0 && (
                <Box sx={{ mt: 1, maxHeight: 200, overflow: 'auto' }}>
                  {importResult.errors.map((err, idx) => (
                    <Typography key={idx} variant="caption" color="error" display="block">
                      Ligne {err.line}: {err.error}
                    </Typography>
                  ))}
                </Box>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => setImportDialogOpen(false)}
            disabled={importLoading}
          >
            {importLoading ? 'Fermer' : 'Annuler'}
          </Button>
          <Button
            onClick={handleImportConfirm}
            variant="contained"
            disabled={!selectedFile || importLoading}
          >
            {importLoading ? 'Import en cours...' : 'Importer'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Snackbar pour les notifications */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          onClose={() => setSnackbar({ ...snackbar, open: false })}
          severity={snackbar.severity}
          sx={{ width: '100%' }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Card>
  );
}

export default SignaturesList;

