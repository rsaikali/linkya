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
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Divider,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import { FileDownload, FileUpload, ModelTraining, MoreVert } from '@mui/icons-material';
import TrackChangesIcon from '@mui/icons-material/TrackChanges';
import api, { apiService } from '../services/api';
import { useData } from '../context/DataContext';
import { useApplianceColors } from '../context/ApplianceColorsContext';

// Custom Material Symbols Icon component
const MaterialIcon = ({ children, sx = {} }) => (
  <span 
    className="material-symbols-outlined" 
    style={{
      fontSize: sx.fontSize || 'inherit',
      color: sx.color || 'inherit',
      ...sx,
    }}
  >
    {children}
  </span>
);

/**
 * Composant affichant la liste des signatures
 */
function SignaturesList() {
  const { getApplianceColor, getApplianceIcon } = useApplianceColors();
  const { signatures, loading, errors, importProgress, refreshSignatures } = useData();
  
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [signatureToDelete, setSignatureToDelete] = useState(null);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });
  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [importLoading, setImportLoading] = useState(false);
  const [importResult, setImportResult] = useState(null);
  const [trainLoading, setTrainLoading] = useState(false);
  const [deleteModelsDialogOpen, setDeleteModelsDialogOpen] = useState(false);
  const [deleteModelsLoading, setDeleteModelsLoading] = useState(false);

  // Use data from context
  const totalSignatures = signatures.length;
  const isLoading = loading.signatures;
  const error = errors.signatures;

  // No need to fetch signatures or setup WebSocket - DataContext handles it all

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

  const handleDeleteAllModels = async () => {
    setDeleteModelsLoading(true);
    try {
      const response = await apiService.deleteAllModels();
      showSnackbar(
        response.message || 'Tous les modèles IA ont été supprimés',
        'success'
      );
      setDeleteModelsDialogOpen(false);
    } catch (error) {
      showSnackbar(
        `Erreur: ${error.response?.data?.detail || error.message}`,
        'error'
      );
    } finally {
      setDeleteModelsLoading(false);
    }
  };

  // Remove the fetchSignatures function and all WebSocket setup - handled by DataContext

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
      await refreshSignatures();
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

  const formatDurationMinutes = (seconds) => {
    if (!seconds) return '0';
    return Math.round(seconds / 60);
  };

  const formatConsumption = (watts, durationSeconds) => {
    if (watts === null || watts === undefined || !durationSeconds) return 'N/A';
    const kWh = (watts * durationSeconds) / (1000 * 3600);
    return `${kWh.toFixed(1)} kWh`;
  };

  const formatHumanizedDate = (dateString) => {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
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



  return (
    <Card sx={{ height: '100%', width: '100%', display: 'flex', flexDirection: 'column' }}>
      <CardHeader 
        title="Signatures d'appareils"
        titleTypographyProps={{ variant: 'h5' }}
        subheader={`${totalSignatures} signature${totalSignatures > 1 ? 's' : ''} utilisées pour l'apprentissage de l'IA`}
        avatar={<TrackChangesIcon />}
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
        <Tooltip title="Lancer un job d'entraînement du modèle d'IA à partir des signatures décrites.">
          <span>
            <Button
              variant="contained"
              size="small"
              startIcon={trainLoading ? <CircularProgress size={16} color="inherit" /> : <MaterialIcon sx={{ fontSize: 20 }}>cognition</MaterialIcon>}
              onClick={handleTrain}
              disabled={trainLoading || totalSignatures === 0}
              sx={{ textTransform: 'none' }}
            >
              Entraîner l'IA
            </Button>
          </span>
        </Tooltip>
        
        <Tooltip title="Supprimer le modèle d'IA">
          <span>
            <Button
              variant="outlined"
              size="small"
              color="error"
              startIcon={<MaterialIcon sx={{ fontSize: 20 }}>delete</MaterialIcon>}
              onClick={() => setDeleteModelsDialogOpen(true)}
              sx={{ textTransform: 'none' }}
            >
              Supprimer le modèle
            </Button>
          </span>
        </Tooltip>
        
        <Box sx={{ flexGrow: 1 }} />
        
        <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />
        
        <Tooltip title="Exporter les signatures en CSV">
          <IconButton
            size="small"
            onClick={handleExportCSV}
            sx={{ border: 1, borderColor: 'divider' }}
          >
            <FileDownload fontSize="small" />
          </IconButton>
        </Tooltip>
        
        <Tooltip title="Importer des signatures depuis un CSV">
          <IconButton
            size="small"
            onClick={handleImportClick}
            sx={{ border: 1, borderColor: 'divider' }}
          >
            <FileUpload fontSize="small" />
          </IconButton>
        </Tooltip>
      </Toolbar>

      <CardContent sx={{ flexGrow: 1, overflow: 'auto', p: 0 }}>
        {(error || importProgress.status !== 'idle' || loading) && (
          <Box sx={{ p: 2 }}>
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
          </Box>
        )}

        <TableContainer>
          <Table stickyHeader size="small">
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 600 }}>Appareil</TableCell>
                <TableCell align="left" sx={{ fontWeight: 600 }}>Détails</TableCell>
                <TableCell align="right" sx={{ width: '40px', p: 1 }}></TableCell>
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
                <SignatureRow
                  key={signature.id}
                  signature={signature}
                  onDelete={handleDeleteClick}
                  getApplianceColor={getApplianceColor}
                  getApplianceIcon={getApplianceIcon}
                  formatTimeOnly={formatTimeOnly}
                  formatDurationMinutes={formatDurationMinutes}
                  formatConsumption={formatConsumption}
                  formatHumanizedDate={formatHumanizedDate}
                  formatDateTime={formatDateTime}
                />
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

      {/* Dialog de confirmation de suppression de tous les modèles IA */}
      <Dialog
        open={deleteModelsDialogOpen}
        onClose={() => setDeleteModelsDialogOpen(false)}
        aria-labelledby="delete-models-dialog-title"
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle id="delete-models-dialog-title">
          Supprimer tous les modèles IA
        </DialogTitle>
        <DialogContent>
          <DialogContentText>
            Êtes-vous sûr de vouloir supprimer <strong>tous les modèles IA</strong> ?
            <br />
            <br />
            ⚠️ <strong>Attention :</strong> Cette action supprimera :
            <br />
            • Tous les enregistrements de modèles de la base de données
            <br />
            • Tous les fichiers .keras et .metadata.json du système de fichiers
            <br />
            • Les fichiers orphelins dans le dossier /models
            <br />
            <br />
            Les signatures d'entraînement seront conservées. Vous pourrez réentraîner de nouveaux modèles par la suite.
            <br />
            <br />
            <strong>Cette action est irréversible.</strong>
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button 
            onClick={() => setDeleteModelsDialogOpen(false)} 
            color="inherit"
            disabled={deleteModelsLoading}
          >
            Annuler
          </Button>
          <Button 
            onClick={handleDeleteAllModels} 
            color="error" 
            variant="contained"
            disabled={deleteModelsLoading}
            startIcon={deleteModelsLoading ? <CircularProgress size={20} /> : <MaterialIcon>delete_sweep</MaterialIcon>}
          >
            {deleteModelsLoading ? 'Suppression...' : 'Tout supprimer'}
          </Button>
        </DialogActions>
      </Dialog>
    </Card>
  );
}

/**
 * Ligne de tableau pour une signature
 */
function SignatureRow({ 
  signature, 
  onDelete, 
  getApplianceColor,
  getApplianceIcon,
  formatTimeOnly,
  formatDurationMinutes,
  formatConsumption,
  formatHumanizedDate,
  formatDateTime,
}) {
  const theme = useTheme();
  const [anchorEl, setAnchorEl] = useState(null);
  const open = Boolean(anchorEl);

  const handleMenuClick = (event) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleDeleteClick = () => {
    handleMenuClose();
    onDelete(signature);
  };

  return (
    <TableRow hover>
      <TableCell>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <Tooltip
            title={
              signature.is_negative
                ? <div style={{ whiteSpace: 'pre-line' }}>Issue d'une détection déclarée comme incorrecte par l'utilisateur.<br/>Elle aide le modèle IA à apprendre de ses erreurs.</div>                
                : ""
            }
            placement="right"
            arrow
          >
            <Box sx={{ display: 'flex', alignItems: 'center', position: 'relative' }}>
              <MaterialIcon 
                sx={{ 
                  fontSize: '2rem', 
                  color: getApplianceColor(signature.appliance_id),
                  ...(signature.is_negative && {
                    filter: `drop-shadow(0 0 3px ${signature.appliance_id ? 'white' : 'transparent'}) drop-shadow(0 0 5px var(--negative-color))`,
                  }),
                }}
              >
                {getApplianceIcon(signature.appliance_id)}
              </MaterialIcon>
              {signature.is_negative && (
                <Box
                  sx={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    borderRadius: '50%',
                    border: '2px solid',
                    borderColor: (theme) => theme.palette.chart.negativeSignature.main,
                    pointerEvents: 'none',
                  }}
                />
              )}
            </Box>
          </Tooltip>
          <Typography variant="body1" sx={{ fontWeight: 500, color: getApplianceColor(signature.appliance_id) }}>
            {signature.appliance_name}
          </Typography>
        </Box>
      </TableCell>
      <TableCell align="left" sx={{ fontSize: 'small' }}>
        <Box>
          <Typography variant="body2" component="div">
            à <strong>{formatTimeOnly(signature.start_time)}</strong> pendant <strong>{formatDurationMinutes(signature.duration_seconds)}min</strong>
          </Typography>
          <Typography variant="caption" color="text.secondary" component="div" sx={{ fontWeight: 300, fontSize: '0.7rem' }}>
            {formatHumanizedDate(signature.start_time)} ({formatDateTime(signature.start_time)} - {formatTimeOnly(signature.end_time)})
          </Typography>
        </Box>
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
          <MenuItem onClick={handleDeleteClick}>
            <ListItemIcon>
              <span className="material-symbols-outlined" style={{ fontSize: '20px', color: theme.palette.error.dark }}>
                delete
              </span>
            </ListItemIcon>
            <ListItemText>
              Supprimer cette signature
            </ListItemText>
          </MenuItem>
        </Menu>
      </TableCell>
    </TableRow>
  );
}

export default SignaturesList;

