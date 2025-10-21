import React, { useEffect, useState } from 'react';
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
  Box,
  TablePagination,
  CircularProgress,
} from '@mui/material';
import { Timeline, Cached } from '@mui/icons-material';
import { apiService } from '../services/api';

/**
 * Composant affichant les détections d'appareils récentes
 */
function DetectionsList({ hours = 24 }) {
  const [detections, setDetections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);

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
        
        // Trier par date décroissante (plus récentes en premier)
        const sorted = detectionsList.sort((a, b) => new Date(b.start_time) - new Date(a.start_time));
        setDetections(sorted);
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

  const handleChangePage = (event, newPage) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const paginatedDetections = detections.slice(
    page * rowsPerPage,
    page * rowsPerPage + rowsPerPage
  );

  if (error) {
    return (
      <Card>
        <CardHeader
          title={`Détections (dernières ${hours}h)`}
          avatar={<Timeline />}
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
        title={`Détections (dernières ${hours}h)`}
        subheader={`${detections.length} détection${detections.length !== 1 ? 's' : ''} enregistrée${detections.length !== 1 ? 's' : ''}`}
        avatar={<Timeline />}
      />
      <CardContent>
        {loading && <LinearProgress />}

        {detections.length === 0 && !loading && (
          <Typography color="textSecondary" align="center">
            Aucune détection pour le moment
          </Typography>
        )}

        {detections.length > 0 && !loading && (
          <>
            <TableContainer sx={{ maxHeight: 600 }}>
              <Table stickyHeader size="small">
                <TableHead>
                  <TableRow sx={{ backgroundColor: '#f5f5f5' }}>
                    <TableCell>Appareil</TableCell>
                    <TableCell align="right">Début</TableCell>
                    <TableCell align="right">Durée</TableCell>
                    <TableCell align="right">Puissance (W)</TableCell>
                    <TableCell align="right">Énergie (Wh)</TableCell>
                    <TableCell align="center">Confiance</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {paginatedDetections.map((detection) => (
                    <DetectionRow key={detection.id} detection={detection} />
                  ))}
                </TableBody>
              </Table>
            </TableContainer>

            <TablePagination
              rowsPerPageOptions={[5, 10, 25]}
              component="div"
              count={detections.length}
              rowsPerPage={rowsPerPage}
              page={page}
              onPageChange={handleChangePage}
              onRowsPerPageChange={handleChangeRowsPerPage}
              labelRowsPerPage="Lignes par page:"
              labelDisplayedRows={({ from, to, count }) => `${from}–${to} sur ${count}`}
            />
          </>
        )}
      </CardContent>
    </Card>
  );
}

/**
 * Ligne de tableau pour une détection
 */
function DetectionRow({ detection }) {
  const startTime = new Date(detection.start_time);
  const endTime = new Date(detection.end_time);
  const durationMinutes = Math.round((endTime - startTime) / 60000);

  const formatTime = (date) => {
    return date.toLocaleString('fr-FR', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getConfidenceColor = (score) => {
    if (score >= 0.8) return 'success';
    if (score >= 0.6) return 'warning';
    return 'error';
  };

  const getConfidenceLabel = (score) => {
    if (score >= 0.8) return 'Élevée';
    if (score >= 0.6) return 'Moyenne';
    return 'Faible';
  };

  return (
    <TableRow hover>
      <TableCell sx={{ fontWeight: 500 }}>
        {detection.appliance_name || 'Inconnu'}
      </TableCell>
      <TableCell align="right" sx={{ fontSize: 'small' }}>
        {formatTime(startTime)}
      </TableCell>
      <TableCell align="right">
        <Typography variant="body2">
          {durationMinutes < 60
            ? `${durationMinutes}m`
            : `${Math.floor(durationMinutes / 60)}h ${durationMinutes % 60}m`}
        </Typography>
      </TableCell>
      <TableCell align="right">
        <Typography variant="body2">
          {detection.avg_power?.toFixed(1) || 'N/A'}
        </Typography>
      </TableCell>
      <TableCell align="right">
        <Typography variant="body2">
          {detection.energy_consumed?.toFixed(1) || 'N/A'}
        </Typography>
      </TableCell>
      <TableCell align="center">
        <Chip
          label={getConfidenceLabel(detection.confidence_score || 0)}
          color={getConfidenceColor(detection.confidence_score || 0)}
          size="small"
          variant="outlined"
        />
      </TableCell>
    </TableRow>
  );
}

export default DetectionsList;
