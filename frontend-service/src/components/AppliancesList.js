import React, { useEffect, useState } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  Grid,
  LinearProgress,
  Chip,
  Box,
  Typography,
  CircularProgress,
  Alert,
  Tooltip,
} from '@mui/material';
import { ElectricMeter, CheckCircle, HelpOutline } from '@mui/icons-material';
import { apiService } from '../services/api';

/**
 * Composant affichant la liste des appareils détectés avec leurs caractéristiques
 */
function AppliancesList() {
  const [appliances, setAppliances] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
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

    fetchAppliances();

    // Rafraîchir toutes les 30 secondes
    const interval = setInterval(fetchAppliances, 30000);
    return () => clearInterval(interval);
  }, []);

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
              <ApplianceCard appliance={appliance} />
            </Grid>
          ))}
        </Grid>
      </CardContent>
    </Card>
  );
}

/**
 * Carte individuelle pour un appareil
 */
function ApplianceCard({ appliance }) {
  const formatDateTime = (dateString) => {
    if (!dateString) return 'Jamais';
    const date = new Date(dateString);
    return date.toLocaleString('fr-FR', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
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
        <Box>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            {appliance.name}
          </Typography>
          {appliance.description && (
            <Typography variant="caption" color="textSecondary">
              {appliance.description}
            </Typography>
          )}
        </Box>
        {appliance.is_validated && (
          <Tooltip title="Appareil validé">
            <CheckCircle sx={{ color: 'success.main', fontSize: 20 }} />
          </Tooltip>
        )}
        {!appliance.is_validated && (
          <Tooltip title="Non validé">
            <HelpOutline sx={{ color: 'warning.main', fontSize: 20 }} />
          </Tooltip>
        )}
      </Box>

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

      {/* Timestamps de détection */}
      {appliance.last_signature_start && (
        <Box sx={{ mb: 1.5, p: 1, backgroundColor: '#f0f7f7', borderRadius: 0.5 }}>
          <Typography variant="caption" color="textSecondary" sx={{ display: 'block', mb: 0.3 }}>
            Dernière signature
          </Typography>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.2 }}>
            <Typography variant="caption" sx={{ fontSize: '0.7rem' }}>
              Début:
            </Typography>
            <Typography variant="caption" sx={{ fontSize: '0.7rem', fontWeight: 500 }}>
              {formatDateTime(appliance.last_signature_start)}
            </Typography>
          </Box>
          {appliance.last_signature_end && (
            <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
              <Typography variant="caption" sx={{ fontSize: '0.7rem' }}>
                Fin:
              </Typography>
              <Typography variant="caption" sx={{ fontSize: '0.7rem', fontWeight: 500 }}>
                {formatDateTime(appliance.last_signature_end)}
              </Typography>
            </Box>
          )}
        </Box>
      )}

      {/* Status */}
      <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
        <Chip
          label={appliance.is_validated ? 'Validé' : 'En apprentissage'}
          color={appliance.is_validated ? 'success' : 'warning'}
          size="small"
          variant="outlined"
        />
      </Box>
    </Box>
  );
}

export default AppliancesList;
