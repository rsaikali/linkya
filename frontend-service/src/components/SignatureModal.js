import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Box,
  Typography,
  Autocomplete,
  Alert,
  CircularProgress,
  CardHeader,
} from '@mui/material';
import CreateIcon from '@mui/icons-material/Create';
import { apiService } from '../services/api';
import { formatDateTimeLocal } from '../utils/dateUtils';

const SignatureModal = ({ open, onClose, selectedRange, onSignatureSaved }) => {
  const [applianceName, setApplianceName] = useState('');
  const [applianceOptions, setApplianceOptions] = useState([]);
  const [startTime, setStartTime] = useState('');
  const [endTime, setEndTime] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

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
    // Convertir en ISO string si c'est un datetime-local
    const value = e.target.value;
    if (value && !value.includes('Z') && !value.includes('+')) {
      // Format datetime-local sans timezone -> ajouter la timezone locale
      setStartTime(new Date(value).toISOString());
    } else {
      setStartTime(value);
    }
  };

  const handleEndTimeChange = (e) => {
    // Convertir en ISO string si c'est un datetime-local
    const value = e.target.value;
    if (value && !value.includes('Z') && !value.includes('+')) {
      // Format datetime-local sans timezone -> ajouter la timezone locale
      setEndTime(new Date(value).toISOString());
    } else {
      setEndTime(value);
    }
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
    setError(null);
    onClose();
  };

  if (!selectedRange) return null;

  return (
    <Dialog 
      open={open} 
      onClose={handleClose} 
      maxWidth="sm" 
      fullWidth
      PaperProps={{
        sx: {
          borderRadius: 2,
        }
      }}
    >
      <CardHeader
        title="Créer une nouvelle signature d'appareil"
        titleTypographyProps={{ variant: 'h5' }}
        subheader={<span dangerouslySetInnerHTML={{ __html: `<strong>Durée:</strong> ${Math.round((new Date(endTime) - new Date(startTime)) / 60000)} minutes` }} />  }
        avatar={<CreateIcon />}
      />
      
      <DialogContent sx={{ pt: 3 }}>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {/* Nom de l'appareil avec autocomplete */}
          <Autocomplete
            freeSolo
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
                helperText="Sélectionnez un appareil existant ou créez-en un nouveau"
              />
            )}
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
              </Box>

              
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
