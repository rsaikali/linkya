import React, { useEffect, useState } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  LinearProgress,
  Box,
  Typography,
  CircularProgress,
  Alert,
  IconButton,
  Menu,
  MenuItem,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  ListItemIcon,
  ListItemText,
  Snackbar,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Collapse,
  Chip,
} from '@mui/material';
import {
  ElectricMeter,
  MoreVert,
  Edit,
  Delete,
  KeyboardArrowDown,
  KeyboardArrowUp,
  FileDownload,
  FileUpload,
} from '@mui/icons-material';
import { apiService } from '../services/api';

/**
 * Composant affichant la liste des appareils détectés avec leurs caractéristiques
 */
function AppliancesList() {
  const [appliances, setAppliances] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });
  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [importLoading, setImportLoading] = useState(false);
  const [importResult, setImportResult] = useState(null);

  const fetchAppliances = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await apiService.getAllAppliances();
      
      // Gérer les différents formats de réponse de l'API
      let appliancesList = [];
      if (Array.isArray(data)) {
        appliancesList = data;
      } else if (data && data.appliances && Array.isArray(data.appliances)) {
        appliancesList = data.appliances;
      } else if (data && data.data && Array.isArray(data.data)) {
        appliancesList = data.data;
      } else if (typeof data === 'object') {
        // Si c'est un objet, essayer de le convertir en array
        appliancesList = Array.isArray(data) ? data : [];
      }
      
      setAppliances(appliancesList);
    } catch (err) {
      console.error('Erreur lors de la récupération des appareils:', err);
      setError('Impossible de charger les appareils');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAppliances();

    // Rafraîchir toutes les 30 secondes
    const interval = setInterval(fetchAppliances, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleApplianceUpdated = () => {
    // Rafraîchir la liste après modification
    fetchAppliances();
  };

  const showSnackbar = (message, severity = 'success') => {
    setSnackbar({ open: true, message, severity });
  };

  const handleCloseSnackbar = () => {
    setSnackbar({ ...snackbar, open: false });
  };

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
        fetchAppliances(); // Rafraîchir la liste
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

  const handleCloseImportDialog = () => {
    setImportDialogOpen(false);
    setSelectedFile(null);
    setImportResult(null);
  };

  if (error) {
    return (
      <Card>
        <CardHeader title="Signature d'appareils" avatar={<ElectricMeter />} />
        <CardContent>
          <Alert severity="error">{error}</Alert>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader
        title="Signature d'appareils"
        subheader={`${appliances.length} appareil${appliances.length !== 1 ? 's' : ''} détectable${appliances.length !== 1 ? 's' : ''}`}
        avatar={<ElectricMeter />}
        action={
          <Box sx={{ display: 'flex', gap: 1 }}>
            <IconButton
              onClick={handleExportCSV}
              title="Exporter les signatures en CSV"
              color="primary"
            >
              <FileDownload />
            </IconButton>
            <IconButton
              onClick={handleImportClick}
              title="Importer des signatures depuis un CSV"
              color="primary"
            >
              <FileUpload />
            </IconButton>
          </Box>
        }
      />
      <CardContent>
        {loading && <LinearProgress />}

        {appliances.length === 0 && !loading && (
          <Typography color="textSecondary" align="center">
            Aucun appareil détecté pour le moment. Entraînez le modèle NILM avec au moins 48h de données.
          </Typography>
        )}

        {appliances.length > 0 && (
          <TableContainer sx={{ maxHeight: 600 }}>
            <Table stickyHeader size="small">
              <TableHead>
                <TableRow sx={{ backgroundColor: '#f5f5f5' }}>
                  <TableCell />
                  <TableCell>Appareil</TableCell>
                  <TableCell align="right">Puissance moy. (W)</TableCell>
                  <TableCell align="right">Variation (σ)</TableCell>
                  <TableCell align="right">Signatures</TableCell>
                  <TableCell align="right">Détections</TableCell>
                  <TableCell align="center">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {appliances.map((appliance) => (
                  <ApplianceRow
                    key={appliance.id}
                    appliance={appliance}
                    onUpdate={handleApplianceUpdated}
                    onShowSnackbar={showSnackbar}
                  />
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </CardContent>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={handleCloseSnackbar}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={handleCloseSnackbar} severity={snackbar.severity} sx={{ width: '100%' }}>
          {snackbar.message}
        </Alert>
      </Snackbar>

      {/* Dialog d'import CSV */}
      <Dialog
        open={importDialogOpen}
        onClose={handleCloseImportDialog}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>Importer des signatures depuis un CSV</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 2 }}>
            <Alert severity="warning">
              <strong>ATTENTION :</strong> L'import d'un fichier CSV remplacera <strong>toutes les signatures existantes</strong>.
              <br />
              Cette action est irréversible.
            </Alert>

            <Alert severity="info">
              Le fichier CSV doit contenir les colonnes suivantes :
              <br />
              <strong>appliance_name, appliance_description, start_time, end_time</strong>
              <br />
              Les dates doivent être au format ISO 8601 (ex: 2025-10-20T14:24:02+02:00)
            </Alert>

            <Button
              variant="outlined"
              component="label"
              startIcon={<FileUpload />}
            >
              Sélectionner un fichier CSV
              <input
                type="file"
                hidden
                accept=".csv"
                onChange={handleFileChange}
              />
            </Button>

            {selectedFile && (
              <Alert severity="success">
                Fichier sélectionné : <strong>{selectedFile.name}</strong>
                <br />
                Taille : {(selectedFile.size / 1024).toFixed(2)} Ko
              </Alert>
            )}

            {importResult && (
              <Box>
                <Alert
                  severity={importResult.error_count === 0 ? 'success' : 'warning'}
                  sx={{ mb: 2 }}
                >
                  <strong>Résultat de l'import :</strong>
                  <br />
                  Signatures supprimées : {importResult.signatures_deleted || 0}
                  <br />
                  Total de lignes importées : {importResult.total_lines}
                  <br />
                  Succès : {importResult.success_count}
                  <br />
                  Erreurs : {importResult.error_count}
                </Alert>

                {importResult.errors && importResult.errors.length > 0 && (
                  <Box>
                    <Typography variant="subtitle2" color="error" sx={{ mb: 1 }}>
                      Détails des erreurs :
                    </Typography>
                    <Box
                      sx={{
                        maxHeight: 200,
                        overflow: 'auto',
                        bgcolor: '#f5f5f5',
                        p: 1,
                        borderRadius: 1,
                      }}
                    >
                      {importResult.errors.map((err, idx) => (
                        <Typography key={idx} variant="body2" color="error" sx={{ mb: 0.5 }}>
                          Ligne {err.line}: {err.error}
                        </Typography>
                      ))}
                    </Box>
                  </Box>
                )}
              </Box>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseImportDialog} disabled={importLoading}>
            {importResult ? 'Fermer' : 'Annuler'}
          </Button>
          {!importResult && (
            <Button
              onClick={handleImportConfirm}
              disabled={!selectedFile || importLoading}
              variant="contained"
            >
              {importLoading ? <CircularProgress size={24} /> : 'Importer'}
            </Button>
          )}
        </DialogActions>
      </Dialog>
    </Card>
  );
}

/**
 * Ligne de table pour un appareil avec expansion pour les signatures
 */
function ApplianceRow({ appliance, onUpdate, onShowSnackbar }) {
  const [open, setOpen] = useState(false);
  const [signatures, setSignatures] = useState([]);
  const [signaturesLoading, setSignaturesLoading] = useState(false);
  const [anchorEl, setAnchorEl] = useState(null);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [newName, setNewName] = useState(appliance.name);
  const [newDescription, setNewDescription] = useState(appliance.description || '');
  const [loading, setLoading] = useState(false);

  // Charger les signatures lors de l'expansion
  useEffect(() => {
    if (open && signatures.length === 0) {
      fetchSignatures();
    }
  }, [open]);

  const fetchSignatures = async () => {
    setSignaturesLoading(true);
    try {
      const data = await apiService.getApplianceSignatures(appliance.id);
      setSignatures(data.signatures || []);
    } catch (error) {
      console.error('Erreur lors du chargement des signatures:', error);
      onShowSnackbar('Impossible de charger les signatures', 'error');
    } finally {
      setSignaturesLoading(false);
    }
  };

  const handleMenuOpen = (event) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleEditClick = () => {
    setNewName(appliance.name);
    setNewDescription(appliance.description || '');
    setEditDialogOpen(true);
    handleMenuClose();
  };

  const handleDeleteClick = () => {
    setDeleteDialogOpen(true);
    handleMenuClose();
  };

  const handleEditConfirm = async () => {
    if (!newName.trim()) {
      onShowSnackbar('Le nom ne peut pas être vide', 'error');
      return;
    }

    const nameChanged = newName.trim() !== appliance.name;
    const descriptionChanged = newDescription.trim() !== (appliance.description || '');

    if (!nameChanged && !descriptionChanged) {
      setEditDialogOpen(false);
      return;
    }

    setLoading(true);
    try {
      await apiService.updateAppliance(appliance.id, {
        name: nameChanged ? newName.trim() : undefined,
        description: descriptionChanged ? newDescription.trim() : undefined,
      });
      onShowSnackbar(`Appareil "${newName.trim()}" mis à jour`, 'success');
      setEditDialogOpen(false);
      onUpdate();
    } catch (error) {
      onShowSnackbar('Erreur lors de la modification de l\'appareil', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteConfirm = async () => {
    setLoading(true);
    try {
      await apiService.deleteAppliance(appliance.id);
      onShowSnackbar(`Appareil "${appliance.name}" supprimé`, 'success');
      setDeleteDialogOpen(false);
      onUpdate();
    } catch (error) {
      onShowSnackbar('Erreur lors de la suppression de l\'appareil', 'error');
    } finally {
      setLoading(false);
    }
  };

  const formatTime = (date) => {
    return new Date(date).toLocaleString('fr-FR', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <>
      <TableRow hover>
        <TableCell>
          <IconButton
            size="small"
            onClick={() => setOpen(!open)}
          >
            {open ? <KeyboardArrowUp /> : <KeyboardArrowDown />}
          </IconButton>
        </TableCell>
        <TableCell>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="body2" sx={{ fontWeight: 500 }}>
              {appliance.name}
            </Typography>
            {appliance.description && (
              <Typography variant="caption" color="textSecondary">
                {appliance.description}
              </Typography>
            )}
          </Box>
        </TableCell>
        <TableCell align="right">
          <Typography variant="body2">
            {appliance.avg_power ? appliance.avg_power.toFixed(1) : 'N/A'}
          </Typography>
        </TableCell>
        <TableCell align="right">
          <Typography variant="body2">
            {appliance.power_std ? `±${appliance.power_std.toFixed(1)}` : 'N/A'}
          </Typography>
        </TableCell>
        <TableCell align="right">
          <Typography variant="body2">
            {appliance.num_signatures || 0}
          </Typography>
        </TableCell>
        <TableCell align="right">
          <Typography variant="body2">
            {appliance.detection_count || 0}
          </Typography>
        </TableCell>
        <TableCell align="center">
          <IconButton
            size="small"
            onClick={handleMenuOpen}
          >
            <MoreVert fontSize="small" />
          </IconButton>
        </TableCell>
      </TableRow>

      {/* Ligne d'expansion avec les signatures */}
      <TableRow>
        <TableCell style={{ paddingBottom: 0, paddingTop: 0 }} colSpan={7}>
          <Collapse in={open} timeout="auto" unmountOnExit>
            <Box sx={{ margin: 2 }}>
              {signaturesLoading && (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
                  <CircularProgress size={24} />
                </Box>
              )}

              {!signaturesLoading && signatures.length === 0 && (
                <Typography variant="body2" color="textSecondary">
                  Aucune signature pour cet appareil
                </Typography>
              )}

              {!signaturesLoading && signatures.length > 0 && (
                <Table size="small" aria-label="signatures">
                  <TableHead>
                    <TableRow>
                      <TableCell>Début</TableCell>
                      <TableCell>Fin</TableCell>
                      <TableCell>Durée</TableCell>
                      <TableCell align="right">Puissance (W)</TableCell>
                      <TableCell align="right">Énergie (Wh)</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {signatures.map((sig) => (
                      <TableRow key={sig.id}>
                        <TableCell sx={{ fontSize: 'small' }}>
                          {formatTime(sig.start_time)}
                        </TableCell>
                        <TableCell sx={{ fontSize: 'small' }}>
                          {formatTime(sig.end_time)}
                        </TableCell>
                        <TableCell>
                          {sig.duration_seconds
                            ? sig.duration_seconds < 3600
                              ? `${Math.round(sig.duration_seconds / 60)}m`
                              : `${Math.floor(sig.duration_seconds / 3600)}h ${Math.round((sig.duration_seconds % 3600) / 60)}m`
                            : 'N/A'}
                        </TableCell>
                        <TableCell align="right">
                          {sig.avg_power?.toFixed(1) || 'N/A'}
                        </TableCell>
                        <TableCell align="right">
                          {sig.energy_consumed?.toFixed(1) || 'N/A'}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </Box>
          </Collapse>
        </TableCell>
      </TableRow>

      {/* Menu contextuel */}
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleMenuClose}
      >
        <MenuItem onClick={handleEditClick}>
          <ListItemIcon>
            <Edit fontSize="small" />
          </ListItemIcon>
          <ListItemText>Modifier</ListItemText>
        </MenuItem>
        <MenuItem onClick={handleDeleteClick} sx={{ color: 'error.main' }}>
          <ListItemIcon>
            <Delete fontSize="small" color="error" />
          </ListItemIcon>
          <ListItemText>Supprimer</ListItemText>
        </MenuItem>
      </Menu>

      {/* Dialog d'édition */}
      <Dialog open={editDialogOpen} onClose={() => !loading && setEditDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Modifier l'appareil</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Nom de l'appareil"
            type="text"
            fullWidth
            variant="outlined"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            disabled={loading}
            sx={{ mb: 2 }}
          />
          <TextField
            margin="dense"
            label="Description (optionnelle)"
            type="text"
            fullWidth
            variant="outlined"
            multiline
            rows={3}
            value={newDescription}
            onChange={(e) => setNewDescription(e.target.value)}
            disabled={loading}
            placeholder="Ajoutez une description pour cet appareil..."
            helperText="Ex: Machine à laver Bosch 7kg, Lave-vaisselle mode éco..."
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditDialogOpen(false)} disabled={loading}>
            Annuler
          </Button>
          <Button onClick={handleEditConfirm} disabled={loading} variant="contained">
            {loading ? <CircularProgress size={24} /> : 'Enregistrer'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Dialog de confirmation de suppression */}
      <Dialog open={deleteDialogOpen} onClose={() => !loading && setDeleteDialogOpen(false)}>
        <DialogTitle>Supprimer l'appareil ?</DialogTitle>
        <DialogContent>
          <Typography>
            Êtes-vous sûr de vouloir supprimer <strong>{appliance.name}</strong> ?
          </Typography>
          <Typography variant="body2" color="textSecondary" sx={{ mt: 1 }}>
            Cette action supprimera également toutes les signatures et détections associées.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)} disabled={loading}>
            Annuler
          </Button>
          <Button
            onClick={handleDeleteConfirm}
            disabled={loading}
            variant="contained"
            color="error"
          >
            {loading ? <CircularProgress size={24} /> : 'Supprimer'}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}

export default AppliancesList;
