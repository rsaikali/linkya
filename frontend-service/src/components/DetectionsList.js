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
  TablePagination,
  CircularProgress,
  Select,
  MenuItem,
  FormControl,
  Box,
} from '@mui/material';
import { Timeline } from '@mui/icons-material';
import { apiService } from '../services/api';

// Options de période disponibles
const TIME_PERIODS = [
  { value: 24, label: 'Dernières 24h' },
  { value: 168, label: 'Dernière semaine' },
  { value: 720, label: 'Mois dernier' },
  { value: 8760, label: 'Année dernière' },
  { value: null, label: 'Toutes' },
];

/**
 * Composant affichant les détections d'appareils récentes avec pagination côté serveur
 */
function DetectionsList() {
  const [detections, setDetections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [totalDetections, setTotalDetections] = useState(0);
  const [selectedPeriod, setSelectedPeriod] = useState(720); // Mois dernier par défaut

  useEffect(() => {
    const fetchDetections = async () => {
      try {
        setLoading(true);
        setError(null);
        
        // Utiliser la pagination côté backend (page commence à 1 pour l'API)
        const data = await apiService.getDetections(
          selectedPeriod,
          page + 1,
          rowsPerPage
        );
        
        // Gérer la réponse de l'API avec pagination
        if (data && data.detections && Array.isArray(data.detections)) {
          setDetections(data.detections);
          setTotalDetections(data.total_detections || data.detections.length);
        } else if (Array.isArray(data)) {
          // Fallback pour l'ancienne API sans pagination
          setDetections(data);
          setTotalDetections(data.length);
        } else {
          setDetections([]);
          setTotalDetections(0);
        }
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
  }, [selectedPeriod, page, rowsPerPage]);

  const handlePeriodChange = (event) => {
    setSelectedPeriod(event.target.value);
    setPage(0); // Revenir à la première page lors du changement de période
  };

  const handleChangePage = (event, newPage) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  if (error) {
    return (
      <Card>
        <CardHeader
          title="Détections"
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
        title="Détections d'appareils"
        subheader={`${totalDetections} détection${totalDetections !== 1 ? 's' : ''} enregistrée${totalDetections !== 1 ? 's' : ''}`}
        avatar={<Timeline />}
        action={
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <FormControl size="small" sx={{ minWidth: 180 }}>
              <Select
                value={selectedPeriod}
                onChange={handlePeriodChange}
                displayEmpty
                sx={{ bgcolor: 'background.paper' }}
              >
                {TIME_PERIODS.map((period) => (
                  <MenuItem key={period.label} value={period.value}>
                    {period.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            {loading && <CircularProgress size={24} />}
          </Box>
        }
      />
      <CardContent>
        {loading && detections.length === 0 && <LinearProgress />}

        {totalDetections === 0 && !loading && (
          <Typography color="textSecondary" align="center">
            Aucune détection pour le moment
          </Typography>
        )}

        {totalDetections > 0 && (
          <>
            <TableContainer sx={{ maxHeight: 600 }}>
              <Table stickyHeader size="small">
                <TableHead>
                  <TableRow sx={{ backgroundColor: '#f5f5f5' }}>
                    <TableCell>Appareil</TableCell>
                    <TableCell align="right">Début</TableCell>
                    <TableCell align="right">Fin</TableCell>
                    <TableCell align="right">Durée</TableCell>
                    <TableCell align="right">Puissance (W)</TableCell>
                    <TableCell align="right">Énergie (Wh)</TableCell>
                    <TableCell align="center">Confiance</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {detections.map((detection) => (
                    <DetectionRow key={detection.id} detection={detection} />
                  ))}
                  {loading && (
                    <TableRow>
                      <TableCell colSpan={7} align="center" sx={{ py: 3 }}>
                        <CircularProgress size={32} />
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>

            <TablePagination
              rowsPerPageOptions={[5, 10, 25, 50]}
              component="div"
              count={totalDetections}
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
        {detection.name || 'Inconnu'}
      </TableCell>
      <TableCell align="right" sx={{ fontSize: 'small' }}>
        {formatTime(startTime)}
      </TableCell>
      <TableCell align="right" sx={{ fontSize: 'small' }}>
        {formatTime(endTime)}
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
