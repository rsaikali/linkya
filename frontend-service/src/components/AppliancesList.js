import React, { useEffect, useState } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  Grid,
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
} from '@mui/material';
import {
  ElectricMeter,
  MoreVert,
  Edit,
  Delete,
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

  if (error) {
    return (
      <Card>
        <CardHeader title="Appareils détectés" avatar={<ElectricMeter />} />
        <CardContent>
          <Alert severity="error">{error}</Alert>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader
        title="Appareils détectés"
        subheader={`${appliances.length} appareil${appliances.length !== 1 ? 's' : ''} détecté${appliances.length !== 1 ? 's' : ''}`}
        avatar={<ElectricMeter />}
      />
      <CardContent>
        {loading && <LinearProgress />}

        {appliances.length === 0 && !loading && (
          <Typography color="textSecondary" align="center">
            Aucun appareil détecté pour le moment. Entraînez le modèle NILM avec au moins 48h de données.
          </Typography>
        )}

        <Grid container spacing={2} sx={{ mt: 1 }}>
          {appliances.map((appliance) => (
            <Grid item xs={12} sm={6} md={4} key={appliance.id}>
              <ApplianceCard
                appliance={appliance}
                onUpdate={handleApplianceUpdated}
                onShowSnackbar={showSnackbar}
              />
            </Grid>
          ))}
        </Grid>
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
    </Card>
  );
}

/**
 * Carte individuelle pour un appareil
 */
function ApplianceCard({ appliance, onUpdate, onShowSnackbar }) {
  const [anchorEl, setAnchorEl] = useState(null);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [newName, setNewName] = useState(appliance.name);
  const [newDescription, setNewDescription] = useState(appliance.description || '');
  const [loading, setLoading] = useState(false);

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

  return (
    <Box
      sx={{
        border: '1px solid #e0e0e0',
        borderRadius: 1,
        p: 2,
        backgroundColor: '#f9f9f9',
        '&:hover': {
          boxShadow: 2,
          backgroundColor: '#fff',
        },
      }}
    >
      {/* En-tête de l'appareil */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', mb: 1.5 }}>
        <Box sx={{ flex: 1 }}>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            {appliance.name}
          </Typography>
          {appliance.description && (
            <Typography variant="caption" color="textSecondary">
              {appliance.description}
            </Typography>
          )}
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <IconButton
            size="small"
            onClick={handleMenuOpen}
            sx={{ ml: 0.5 }}
          >
            <MoreVert fontSize="small" />
          </IconButton>
        </Box>
      </Box>

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

      {/* Caractéristiques de puissance */}
      <Box sx={{ mb: 1.5 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
          <Typography variant="caption" color="textSecondary">
            Puissance moyenne
          </Typography>
          <Typography variant="caption" sx={{ fontWeight: 600 }}>
            {appliance.avg_power ? `${appliance.avg_power.toFixed(1)} W` : 'N/A'}
          </Typography>
        </Box>

        {appliance.power_std && (
          <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
            <Typography variant="caption" color="textSecondary">
              Variation (σ)
            </Typography>
            <Typography variant="caption">
              ±{appliance.power_std.toFixed(1)} W
            </Typography>
          </Box>
        )}
        
        {appliance.signature_count !== undefined && (
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 0.5 }}>
            <Typography variant="caption" color="textSecondary">
              Signatures
            </Typography>
            <Typography variant="caption">
              {appliance.signature_count}
            </Typography>
          </Box>
        )}
      </Box>

    </Box>
  );
}

export default AppliancesList;
