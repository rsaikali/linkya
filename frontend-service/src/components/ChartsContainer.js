import { ZoomOutMap } from '@mui/icons-material';
import QueryStatsIcon from '@mui/icons-material/QueryStats';
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  LinearProgress,
  Skeleton,
  TextField,
  Toolbar,
  Tooltip as MuiTooltip,
  Card,
  CardContent,
  CardHeader,
} from '@mui/material';
import React, { useState } from 'react';
import { useData } from '../context/DataContext';
import { useNotification } from '../context/NotificationContext';
import api, { apiService } from '../services/api';
import CombinedChart from './CombinedChart';
import SignatureModal from './SignatureModal';

const ChartsContainer = () => {
  const {
    rawData,
    detections,
    signatures,
    loading,
    loadingProgress,
    errors,
    setZoomState,
    refreshSignatures,
    refreshDetections,
    appliances,
  } = useData();
  const { showNotification } = useNotification();

  const [showSignatureModal, setShowSignatureModal] = useState(false);
  const [selectedRange, setSelectedRange] = useState(null);

  // Signature delete dialog (from chart click)
  const [deleteSignatureDialog, setDeleteSignatureDialog] = useState({ open: false, item: null });

  // Detection reassign dialog (from chart click)
  const [reassignDialog, setReassignDialog] = useState({ open: false, item: null, applianceName: '', loading: false });

  const handleResetZoom = () => {
    if (rawData?.data) {
      const now = new Date();
      const fortyEightHoursAgo = new Date(now.getTime() - 48 * 60 * 60 * 1000);
      const minIndex48h = rawData.data.findIndex(d => new Date(d.time) >= fortyEightHoursAgo);
      const visibleMin = minIndex48h !== -1 ? minIndex48h : 0;
      const visibleMax = rawData.data.length - 1;
      setZoomState({ min: visibleMin, max: visibleMax, dataLength: rawData.data.length });
    }
  };

  const handleSignatureModalOpen = (range) => {
    setSelectedRange(range);
    setShowSignatureModal(true);
  };

  const handleSignatureSaved = async () => {
    setShowSignatureModal(false);
    setSelectedRange(null);
    await refreshSignatures();
    window.dispatchEvent(new CustomEvent('signature-created'));
  };

  // Chart annotation actions — signatures
  const handleDeleteSignature = (item) => {
    setDeleteSignatureDialog({ open: true, item });
  };

  const handleDeleteSignatureConfirm = async () => {
    const { item } = deleteSignatureDialog;
    if (!item) return;
    try {
      await api.delete(`/api/signatures/${item.id}`);
      showNotification(`Signature supprimée : ${item.name}`, 'success');
      await refreshSignatures();
    } catch (err) {
      showNotification('Erreur lors de la suppression', 'error');
    } finally {
      setDeleteSignatureDialog({ open: false, item: null });
    }
  };

  // Chart annotation actions — detections
  const handleValidateDetection = async (item) => {
    try {
      await apiService.validateDetection(item.id);
      showNotification(`Détection validée : ${item.name}`, 'success');
      refreshDetections();
    } catch (err) {
      showNotification('Erreur lors de la validation', 'error');
    }
  };

  const handleInvalidateDetection = async (item) => {
    try {
      await apiService.invalidateDetection(item.id);
      showNotification(`Détection invalidée : ${item.name}`, 'info');
      refreshDetections();
    } catch (err) {
      showNotification("Erreur lors de l'invalidation", 'error');
    }
  };

  const handleReassignDetection = (item) => {
    setReassignDialog({ open: true, item, applianceName: '', loading: false });
  };

  const handleReassignSubmit = async () => {
    const { item, applianceName } = reassignDialog;
    if (!applianceName.trim()) {
      showNotification("Veuillez saisir le nom de l'appareil", 'error');
      return;
    }
    setReassignDialog(prev => ({ ...prev, loading: true }));
    try {
      await apiService.reassignDetection(item.id, applianceName);
      showNotification(`Détection réassignée à ${applianceName}`, 'success');
      setReassignDialog({ open: false, item: null, applianceName: '', loading: false });
      refreshDetections();
      refreshSignatures();
    } catch (err) {
      showNotification('Erreur lors de la réassignation', 'error');
      setReassignDialog(prev => ({ ...prev, loading: false }));
    }
  };

  const isLoading = loading.consumption;
  const error = errors.consumption;
  const applianceNames = (appliances || []).map(a => a.name);

  return (
    <>
      <Card>
        <CardHeader
          title="Historique de consommation"
          titleTypographyProps={{ variant: 'h5' }}
          subheader={
            isLoading
              ? `Chargement des donnees (${loadingProgress}%)...`
              : 'Molette: zoom - Glisser: naviguer sur la période - Clic droit + glisser: créer une signature - Clic sur annotation: actions'
          }
          avatar={<QueryStatsIcon />}
        />

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
            justifyContent: 'flex-start',
          }}
        >
          <MuiTooltip title="Réinitialiser le zoom (dernières 48h)">
            <span>
              <Button
                variant="outlined"
                size="small"
                startIcon={<ZoomOutMap />}
                onClick={handleResetZoom}
                disabled={isLoading || !rawData}
                sx={{ textTransform: 'none' }}
              >
                Réinitialiser la vue
              </Button>
            </span>
          </MuiTooltip>
        </Toolbar>

        {isLoading && (
          <LinearProgress
            variant="determinate"
            value={loadingProgress}
            sx={{
              height: 2,
              backgroundColor: (theme) => theme.palette.overlay?.black?.[5] || 'rgba(0,0,0,0.05)',
            }}
          />
        )}

        <CardContent sx={{ p: 2 }}>
          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

          {isLoading && (
            <Box>
              <Skeleton variant="rectangular" height={400} sx={{ borderRadius: 1 }} />
            </Box>
          )}

          {!isLoading && (!rawData || !rawData.data || rawData.data.length === 0) && (
            <Alert severity="info">Aucune donnee disponible</Alert>
          )}

          {!isLoading && rawData?.data && rawData.data.length > 0 && (
            <CombinedChart
              rawData={rawData}
              detections={detections}
              signatures={signatures}
              onSignatureModalOpen={handleSignatureModalOpen}
              isModalOpen={showSignatureModal}
              onDeleteSignature={handleDeleteSignature}
              onValidateDetection={handleValidateDetection}
              onInvalidateDetection={handleInvalidateDetection}
              onReassignDetection={handleReassignDetection}
            />
          )}
        </CardContent>
      </Card>

      {selectedRange && (
        <SignatureModal
          open={showSignatureModal}
          onClose={() => {
            setShowSignatureModal(false);
            setSelectedRange(null);
          }}
          selectedRange={selectedRange}
          onSignatureSaved={handleSignatureSaved}
        />
      )}

      {/* Signature delete confirmation dialog (from chart) */}
      <Dialog
        open={deleteSignatureDialog.open}
        onClose={() => setDeleteSignatureDialog({ open: false, item: null })}
      >
        <DialogTitle>Confirmer la suppression</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Voulez-vous vraiment supprimer la signature de{' '}
            <strong>{deleteSignatureDialog.item?.name}</strong> ?
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteSignatureDialog({ open: false, item: null })}>
            Annuler
          </Button>
          <Button onClick={handleDeleteSignatureConfirm} color="error" autoFocus>
            Supprimer
          </Button>
        </DialogActions>
      </Dialog>

      {/* Detection reassign dialog (from chart) */}
      <Dialog
        open={reassignDialog.open}
        onClose={() => !reassignDialog.loading && setReassignDialog({ open: false, item: null, applianceName: '', loading: false })}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Réassigner la détection</DialogTitle>
        <DialogContent>
          <DialogContentText sx={{ mb: 2 }}>
            Cette détection était pour <strong>{reassignDialog.item?.name}</strong>.
            <br />
            Quel est le bon appareil ?
          </DialogContentText>
          <Autocomplete
            freeSolo
            options={applianceNames}
            value={reassignDialog.applianceName}
            onChange={(_, newValue) => setReassignDialog(prev => ({ ...prev, applianceName: newValue || '' }))}
            onInputChange={(_, newInputValue) => setReassignDialog(prev => ({ ...prev, applianceName: newInputValue }))}
            renderInput={(params) => (
              <TextField
                {...params}
                label="Nom de l'appareil"
                placeholder="Sélectionner ou créer un appareil"
                fullWidth
                autoFocus
                helperText="Vous pouvez sélectionner un appareil existant ou en créer un nouveau"
              />
            )}
          />
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => setReassignDialog({ open: false, item: null, applianceName: '', loading: false })}
            disabled={reassignDialog.loading}
          >
            Annuler
          </Button>
          <Button
            onClick={handleReassignSubmit}
            variant="contained"
            color="primary"
            disabled={reassignDialog.loading || !reassignDialog.applianceName.trim()}
            startIcon={reassignDialog.loading ? <CircularProgress size={20} /> : null}
          >
            {reassignDialog.loading ? 'Réassignation...' : 'Réassigner'}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

export default ChartsContainer;
