import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Box,
  Typography,
  Autocomplete,
  Alert,
  CircularProgress,
  FormControlLabel,
  Checkbox,
} from '@mui/material';
import { apiService } from '../services/api';

const SignatureModal = ({ open, onClose, selectedRange, onSignatureSaved }) => {
  const [applianceName, setApplianceName] = useState('');
  const [applianceOptions, setApplianceOptions] = useState([]);
  const [description, setDescription] = useState('');
  const [startTime, setStartTime] = useState('');
  const [endTime, setEndTime] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [allowNewAppliance, setAllowNewAppliance] = useState(true);

  // Initialiser les times et charger les appareils
  useEffect(() => {
    if (open && selectedRange) {
      setStartTime(selectedRange.startTime.toISOString());
      setEndTime(selectedRange.endTime.toISOString());
      loadAppliances();
    }
  }, [open, selectedRange]);

  const loadAppliances = async () => {
    try {
      const data = await apiService.getAllAppliances();
      const names = (data.appliances || []).map(a => a.name);
      setApplianceOptions(names);
    } catch (err) {
      console.error('Erreur lors du chargement des appareils:', err);
    }
  };

  const handleStartTimeChange = (e) => {
    setStartTime(e.target.value);
  };

  const handleEndTimeChange = (e) => {
    setEndTime(e.target.value);
  };

  const validateForm = () => {
    if (!applianceName.trim()) {
      setError('Le nom de l\'appareil est requis');
      return false;
    }
    if (!startTime) {
      setError('L\'heure de début est requise');
      return false;
    }
    if (!endTime) {
      setError('L\'heure de fin est requise');
      return false;
    }

    const start = new Date(startTime);
    const end = new Date(endTime);
    if (start >= end) {
      setError('L\'heure de fin doit être après l\'heure de début');
      return false;
    }

    return true;
  };

  const handleSubmit = async () => {
    setError(null);

    if (!validateForm()) {
      return;
    }

    setLoading(true);
    try {
      const response = await apiService.createSignature({
        appliance_name: applianceName,
        description: description || null,
        start_time: startTime,
        end_time: endTime,
      });

      if (response.status === 'success' || response.status === 'pending') {
        onSignatureSaved();
      } else if (response.status === 'error') {
        setError(response.message || 'Erreur lors de la création de la signature');
      }
    } catch (err) {
      setError('Erreur lors de l\'envoi de la signature: ' + err.message);
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setApplianceName('');
    setDescription('');
    setError(null);
    onClose();
  };

  if (!selectedRange) return null;

  const formatDateTimeLocal = (dateString) => {
    if (!dateString) return '';
    // Convertir ISO string en format local pour l'input datetime-local
    const date = new Date(dateString);
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const seconds = String(date.getSeconds()).padStart(2, '0');
    return `${year}-${month}-${day}T${hours}:${minutes}:${seconds}`;
  };

  const formatTimeDisplay = (dateString) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleString('fr-FR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>Créer une nouvelle signature d'appareil</DialogTitle>

      <DialogContent sx={{ pt: 3 }}>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {/* Nom de l'appareil avec autocomplete */}
          <Autocomplete
            freeSolo={allowNewAppliance}
            options={applianceOptions}
            value={applianceName}
            onChange={(event, newValue) => {
              setApplianceName(newValue || '');
            }}
            onInputChange={(event, newInputValue) => {
              setApplianceName(newInputValue);
            }}
            renderInput={(params) => (
              <TextField
                {...params}
                label="Nom de l'appareil"
                placeholder="Ex: Lave-linge, Frigo, etc."
                required
                fullWidth
              />
            )}
          />

          <FormControlLabel
            control={
              <Checkbox
                checked={allowNewAppliance}
                onChange={(e) => setAllowNewAppliance(e.target.checked)}
              />
            }
            label="Permettre la création d'un nouvel appareil"
          />

          {/* Description */}
          <TextField
            label="Description (optionnel)"
            placeholder="Ex: Lave-linge Samsung, mode éco"
            multiline
            rows={2}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            fullWidth
          />

          {/* Plage horaire */}
          <Box sx={{ pt: 1 }}>
            <Typography variant="subtitle2" sx={{ mb: 2, fontWeight: 600 }}>
              Plage horaire de la signature
            </Typography>

            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
              {/* Start time */}
              <Box>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
                  Heure de début
                </Typography>
                <TextField
                  type="datetime-local"
                  value={formatDateTimeLocal(startTime)}
                  onChange={handleStartTimeChange}
                  fullWidth
                  size="small"
                />
                <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
                  {formatTimeDisplay(startTime)}
                </Typography>
              </Box>

              {/* End time */}
              <Box>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
                  Heure de fin
                </Typography>
                <TextField
                  type="datetime-local"
                  value={formatDateTimeLocal(endTime)}
                  onChange={handleEndTimeChange}
                  fullWidth
                  size="small"
                />
                <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
                  {formatTimeDisplay(endTime)}
                </Typography>
              </Box>

              {/* Durée */}
              {startTime && endTime && (
                <Box sx={{ bgcolor: '#f5f5f5', p: 1.5, borderRadius: 1 }}>
                  <Typography variant="body2" color="text.secondary">
                    <strong>Durée:</strong> {Math.round((new Date(endTime) - new Date(startTime)) / 60000)} minutes
                  </Typography>
                </Box>
              )}
            </Box>
          </Box>
        </Box>
      </DialogContent>

      <DialogActions sx={{ p: 2 }}>
        <Button onClick={handleClose} disabled={loading}>
          Annuler
        </Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          disabled={loading || !applianceName.trim()}
          sx={{ position: 'relative' }}
        >
          {loading ? <CircularProgress size={24} /> : 'Créer la signature'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default SignatureModal;
