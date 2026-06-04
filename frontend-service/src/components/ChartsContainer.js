import React, { useState } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  Alert,
  Tooltip as MuiTooltip,
  LinearProgress,
  Toolbar,
  Button,
  Skeleton,
  Box,
} from '@mui/material';
import { ZoomOutMap } from '@mui/icons-material';
import QueryStatsIcon from '@mui/icons-material/QueryStats';
import CombinedChart from './CombinedChart';
import SignatureModal from './SignatureModal';
import { useData } from '../context/DataContext';

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
  } = useData();
  
  const [showSignatureModal, setShowSignatureModal] = useState(false);
  const [selectedRange, setSelectedRange] = useState(null);

  // No need to load data - DataContext handles it all

  const handleResetZoom = () => {
    if (rawData?.data) {
      const now = new Date();
      const fortyEightHoursAgo = new Date(now.getTime() - 48 * 60 * 60 * 1000);
      const minIndex48h = rawData.data.findIndex(d => new Date(d.time) >= fortyEightHoursAgo);
      const visibleMin = minIndex48h !== -1 ? minIndex48h : 0;
      const visibleMax = rawData.data.length - 1;
      
      setZoomState({
        min: visibleMin,
        max: visibleMax,
        dataLength: rawData.data.length,
      });
    }
  };

  const handleSignatureModalOpen = (range) => {
    setSelectedRange(range);
    setShowSignatureModal(true);
  };

  const handleSignatureSaved = async () => {
    setShowSignatureModal(false);
    setSelectedRange(null);
    
    // Trigger signature refresh and notify other components
    await refreshSignatures();
    window.dispatchEvent(new CustomEvent('signature-created'));
  };

  const isLoading = loading.consumption;
  const error = errors.consumption;

  return (
    <>
      <Card>
        <CardHeader
          title="Historique de consommation"
          titleTypographyProps={{ variant: 'h5' }}
          subheader={
            isLoading 
              ? `Chargement des donnees (${loadingProgress}%)...`
              : 'Molette: zoom - Glisser: naviguer sur la période - Clic droit + glisser: créer une signature'
          }
          avatar={<QueryStatsIcon />}
        />
        
        {/* Toolbar avec actions */}
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
            justifyContent: 'flex-start'
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
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>
          )}

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
    </>
  );
};

export default ChartsContainer;
