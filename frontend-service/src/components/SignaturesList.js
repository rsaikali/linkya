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
  TablePagination,
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
} from '@mui/material';
import { Delete, DeleteSweep, FileDownload, FileUpload, Assignment } from '@mui/icons-material';
import api, { apiService } from '../services/api';

/**
 * Composant affichant la liste des signatures avec pagination côté serveur
 */
function SignaturesList() {
  const [signatures, setSignatures] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(20);
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

  const showSnackbar = (message, severity = 'success') => {
    setSnackbar({ open: true, message, severity });
  };

  const fetchSignatures = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Utiliser la pagination côté backend (page commence à 1 pour l'API)
      const response = await api.get('/api/signatures', {
        params: {
          page: page + 1,
          per_page: rowsPerPage
        }
      });
      
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
  }, [page, rowsPerPage]);

  useEffect(() => {
    fetchSignatures();
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
    try {
      const result = await apiService.importSignatures(selectedFile);
      setImportResult(result);

      if (result.error_count === 0) {
        showSnackbar(`${result.success_count} signature(s) importée(s) avec succès`, 'success');
        fetchSignatures(); // Rafraîchir la liste
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
    } finally {
      setImportLoading(false);
    }
  };

  const handleChangePage = (event, newPage) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
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

  const formatDuration = (seconds) => {
    if (!seconds) return 'N/A';
    const minutes = Math.round(seconds / 60);
    
    if (minutes < 60) {
      return `${minutes}m`;
    } else {
      const hours = Math.floor(minutes / 60);
      const remainingMinutes = minutes % 60;
      return `${hours}h ${remainingMinutes}m`;
    }
  };

  const formatPower = (watts) => {
    if (watts === null || watts === undefined) return 'N/A';
    return `${watts.toFixed(0)} W`;
  };

  const getTypeChip = (isNegative) => {
    if (isNegative) {
      return (
        <Chip
          label="Négative"
          size="small"
          color="error"
          variant="outlined"
        />
      );
    }
    return (
      <Chip
        label="Positive"
        size="small"
        color="success"
        variant="outlined"
      />
    );
  };

  return (
    <Card>
      <CardHeader 
        title="Signatures d'appareils"
        subheader={`${totalSignatures} signature(s) enregistrée(s)`}
        avatar={<Assignment />}
        action={
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Tooltip title="Exporter les signatures en CSV">
              <IconButton
                onClick={handleExportCSV}
                color="primary"
              >
                <FileDownload />
              </IconButton>
            </Tooltip>
            <Tooltip title="Importer des signatures depuis un CSV">
              <IconButton
                onClick={handleImportClick}
                color="primary"
              >
                <FileUpload />
              </IconButton>
            </Tooltip>
            <Tooltip title="Supprimer toutes les signatures">
              <span>
                <IconButton
                  color="error"
                  onClick={handleDeleteAllClick}
                  disabled={totalSignatures === 0}
                >
                  <DeleteSweep />
                </IconButton>
              </span>
            </Tooltip>
          </Box>
        }
      />
      <CardContent>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {loading && <LinearProgress sx={{ mb: 2 }} />}

        <TableContainer>
          <Table stickyHeader size="small">
            <TableHead>
              <TableRow sx={{ backgroundColor: '#f5f5f5' }}>
                <TableCell>Appareil</TableCell>
                <TableCell align="right">Plage horaire</TableCell>
                <TableCell align="right">Durée</TableCell>
                <TableCell align="right">Puissance moy.</TableCell>
                <TableCell align="center">Type</TableCell>
                <TableCell align="center">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {signatures.length === 0 && !loading && (
                <TableRow>
                  <TableCell colSpan={6} align="center">
                    <Typography variant="body2" color="text.secondary">
                      Aucune signature enregistrée
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
              {signatures.map((signature) => (
                <TableRow key={signature.id} hover>
                  <TableCell>
                    <Typography variant="body2" fontWeight="medium">
                      {signature.appliance_name}
                    </Typography>
                  </TableCell>
                  <TableCell align="right" sx={{ fontSize: 'small', whiteSpace: 'nowrap' }}>
                    {`${formatDateTime(signature.start_time)} -> ${formatTimeOnly(signature.end_time)}`}
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2">
                      {formatDuration(signature.duration_seconds)}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2" fontWeight="medium">
                      {formatPower(signature.avg_power)}
                    </Typography>
                  </TableCell>
                  <TableCell align="center">
                    {getTypeChip(signature.is_negative)}
                  </TableCell>
                  <TableCell align="center">
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

        <TablePagination
          component="div"
          count={totalSignatures}
          page={page}
          onPageChange={handleChangePage}
          rowsPerPage={rowsPerPage}
          onRowsPerPageChange={handleChangeRowsPerPage}
          rowsPerPageOptions={[10, 20, 50, 100]}
          labelRowsPerPage="Signatures par page:"
          labelDisplayedRows={({ from, to, count }) =>
            `${from}-${to} sur ${count !== -1 ? count : `plus de ${to}`}`
          }
        />
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
            Format attendu: appliance_name, appliance_description, start_time, end_time
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

          {importResult && (
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
            Annuler
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
