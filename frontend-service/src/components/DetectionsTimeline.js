import React, { useEffect, useState } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  Box,
  Typography,
  Chip,
  LinearProgress,
  Alert,
  Grid,
  Tooltip,
  Stack,
} from '@mui/material';
import { ElectricBolt, InfoOutlined } from '@mui/icons-material';
import { apiService } from '../services/api';

/**
 * Composant affichant une timeline des détections récentes
 */
function DetectionsTimeline({ hours = 12 }) {
  const [detections, setDetections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchDetections = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await apiService.getDetections(hours);
        
        // Gérer les différents formats de réponse de l'API
        let detectionsList = [];
        if (Array.isArray(data)) {
          detectionsList = data;
        } else if (data && data.detections && Array.isArray(data.detections)) {
          detectionsList = data.detections;
        } else if (data && data.data && Array.isArray(data.data)) {
          detectionsList = data.data;
        } else if (typeof data === 'object') {
          detectionsList = Array.isArray(data) ? data : [];
        }
        
        // Trier par date décroissante
        const sorted = detectionsList.sort((a, b) => new Date(b.start_time) - new Date(a.start_time));
        // Limiter à 10 dernières détections
        setDetections(sorted.slice(0, 10));
      } catch (err) {
        console.error('Erreur lors de la récupération des détections:', err);
        setError('Impossible de charger les détections');
      } finally {
        setLoading(false);
      }
    };

    fetchDetections();

    // Rafraîchir toutes les 60 secondes
    const interval = setInterval(fetchDetections, 60000);
    return () => clearInterval(interval);
  }, [hours]);

  if (error) {
    return (
      <Card>
        <CardHeader
          title={`Timeline des détections (${hours}h)`}
          avatar={<ElectricBolt />}
        />
        <CardContent>
          <Alert severity="error">{error}</Alert>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader
        title={`Timeline des détections (${hours}h)`}
        subheader={`${detections.length} détection${detections.length !== 1 ? 's' : ''} récente${detections.length !== 1 ? 's' : ''}`}
        avatar={<ElectricBolt />}
      />
      <CardContent>
        {loading && <LinearProgress />}

        {detections.length === 0 && !loading && (
          <Typography color="textSecondary" align="center" sx={{ py: 4 }}>
            Aucune détection pour le moment
          </Typography>
        )}

        {detections.length > 0 && (
          <Stack spacing={2}>
            {detections.map((detection, index) => (
              <DetectionTimelineCard key={detection.id} detection={detection} index={index} />
            ))}
          </Stack>
        )}
      </CardContent>
    </Card>
  );
}

/**
 * Carte d'une détection dans la timeline
 */
function DetectionTimelineCard({ detection, index }) {
  const startTime = new Date(detection.start_time);
  const endTime = new Date(detection.end_time);
  const durationMinutes = Math.round((endTime - startTime) / 60000);

  const formatFullTime = (date) => {
    return date.toLocaleString('fr-FR', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  const getConfidenceLabel = (score) => {
    if (score >= 0.8) return 'Élevée';
    if (score >= 0.6) return 'Moyenne';
    return 'Faible';
  };

  const getConfidenceColor = (score) => {
    if (score >= 0.8) return 'success';
    if (score >= 0.6) return 'warning';
    return 'error';
  };

  const dotColor = getConfidenceColorValue(detection.confidence_score || 0);

  const buildSignatureTooltip = (det) => {
    const matched = det.matched_signature || null;
    const score = det?.features?.matching?.score ?? null;
    const scorePct = score != null ? `${(score * 100).toFixed(0)}%` : null;
    const sigId = det.signature_id;

    if (!sigId && !scorePct) return '';

    const sigRange = matched
      ? `${new Date(matched.start_time).toLocaleString('fr-FR', { hour: '2-digit', minute: '2-digit', month: 'short', day: 'numeric' })}
         → ${new Date(matched.end_time).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}`
      : null;

    return (
      <Box sx={{ py: 0.5 }}>
        {sigId && (
          <Typography variant="caption" sx={{ display: 'block' }}>
            Signature correspondante: <strong>#{sigId}</strong>
          </Typography>
        )}
        {sigRange && (
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
            Période: {sigRange}
          </Typography>
        )}
        {scorePct && (
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
            Score de correspondance: {scorePct}
          </Typography>
        )}
      </Box>
    );
  };

  const hasMatchInfo = Boolean(
    detection?.signature_id || (detection?.features?.matching?.score != null)
  );

  return (
    <Box
      sx={{
        display: 'flex',
        gap: 2,
      }}
    >
      {/* Indicateur visuel (timeline dot) */}
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          mt: 0.5,
        }}
      >
        <Box
          sx={{
            width: 40,
            height: 40,
            borderRadius: '50%',
            backgroundColor: dotColor,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            boxShadow: 1,
          }}
        >
          <ElectricBolt sx={{ fontSize: 20 }} />
        </Box>
      </Box>

      {/* Contenu de la détection */}
      <Box
        sx={{
          flex: 1,
          backgroundColor: '#f9f9f9',
          border: '1px solid #e0e0e0',
          borderRadius: 1,
          p: 1.5,
          '&:hover': {
            boxShadow: 1,
            backgroundColor: '#fff',
          },
        }}
      >
        {/* Nom de l'appareil (icône info à gauche si correspondance) */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
            {hasMatchInfo && (
              <Tooltip placement="top-start" arrow title={buildSignatureTooltip(detection)}>
                <InfoOutlined fontSize="small" color="info" sx={{ cursor: 'help' }} />
              </Tooltip>
            )}
            <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
              {detection.appliance_name || 'Appareil inconnu'}
            </Typography>
          </Box>
          <Chip
            label={getConfidenceLabel(detection.confidence_score || 0)}
            color={getConfidenceColor(detection.confidence_score || 0)}
            size="small"
          />
        </Box>

        {/* Timestamp relatif */}
        <Typography variant="caption" color="textSecondary" sx={{ display: 'block', mb: 1 }}>
          {formatRelativeTime(detection.start_time)} • {formatFullTime(startTime)}
        </Typography>

        {/* Infos de puissance et durée */}
        <Grid container spacing={1}>
          <Grid item xs={6} sm={3}>
            <Box>
              <Typography variant="caption" color="textSecondary">
                Puissance
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 500 }}>
                {detection.avg_power?.toFixed(1) || 'N/A'} W
              </Typography>
            </Box>
          </Grid>
          <Grid item xs={6} sm={3}>
            <Box>
              <Typography variant="caption" color="textSecondary">
                Durée
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 500 }}>
                {durationMinutes < 60
                  ? `${durationMinutes}m`
                  : `${Math.floor(durationMinutes / 60)}h ${durationMinutes % 60}m`}
              </Typography>
            </Box>
          </Grid>
          <Grid item xs={6} sm={3}>
            <Box>
              <Typography variant="caption" color="textSecondary">
                Énergie
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 500 }}>
                {detection.energy_consumed?.toFixed(1) || 'N/A'} Wh
              </Typography>
            </Box>
          </Grid>
          <Grid item xs={6} sm={3}>
            <Box>
              <Typography variant="caption" color="textSecondary">
                Confiance
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 500 }}>
                {((detection.confidence_score || 0) * 100).toFixed(0)}%
              </Typography>
            </Box>
          </Grid>
        </Grid>
      </Box>
    </Box>
  );
}

/**
 * Formate le temps relatif (e.g., "il y a 5 minutes")
 */
function formatRelativeTime(dateString) {
  const date = new Date(dateString);
  const now = new Date();
  const diffSeconds = Math.floor((now - date) / 1000);

  if (diffSeconds < 60) return 'à l\'instant';
  const diffMinutes = Math.floor(diffSeconds / 60);
  if (diffMinutes < 60) return `il y a ${diffMinutes}m`;
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `il y a ${diffHours}h`;
  const diffDays = Math.floor(diffHours / 24);
  return `il y a ${diffDays}j`;
}

/**
 * Retourne la couleur en fonction du score de confiance
 */
function getConfidenceColor(score) {
  if (score >= 0.8) return '#4caf50';
  if (score >= 0.6) return '#ff9800';
  return '#f44336';
}

function getConfidenceColorValue(score) {
  if (score >= 0.8) return '#4caf50';
  if (score >= 0.6) return '#ff9800';
  return '#f44336';
}

export default DetectionsTimeline;
