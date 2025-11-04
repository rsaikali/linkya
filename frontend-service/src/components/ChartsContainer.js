import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  Typography,
  CircularProgress,
  Alert,
  Tooltip as MuiTooltip,
  LinearProgress,
  Toolbar,
  Button,
} from '@mui/material';
import { ZoomOutMap } from '@mui/icons-material';
import QueryStatsIcon from '@mui/icons-material/QueryStats';
import { apiService } from '../services/api';
import { detectionsWS } from '../services/websocket';
import CombinedChart from './CombinedChart';
import SignatureModal from './SignatureModal';
import { useChart } from '../context/ChartContext';

const ChartsContainer = () => {
  const { setZoomState, setVisibleTimeRange } = useChart();
  const [rawData, setRawData] = useState(null);
  const [detections, setDetections] = useState([]);
  const [signatures, setSignatures] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingProgress, setLoadingProgress] = useState(0);
  const [error, setError] = useState(null);
  const [showSignatureModal, setShowSignatureModal] = useState(false);
  const [selectedRange, setSelectedRange] = useState(null);

  // Load all data on mount
  useEffect(() => {
    const loadAllData = async () => {
      try {
        setLoading(true);
        setLoadingProgress(10);
        
        setLoadingProgress(30);
        const result = await apiService.getConsumptionHistory(null, null, '30 seconds');
        setLoadingProgress(70);
        
        setRawData(result);
        
        // Initialize visible period for last 48 hours
        if (result?.data && result.data.length > 0) {
          const now = new Date();
          const fortyEightHoursAgo = new Date(now.getTime() - 48 * 60 * 60 * 1000);
          const minIndex48h = result.data.findIndex(d => new Date(d.time) >= fortyEightHoursAgo);
          const visibleMin = minIndex48h !== -1 ? minIndex48h : 0;
          const visibleMax = result.data.length - 1;
          
          setZoomState({
            min: visibleMin,
            max: visibleMax,
            dataLength: result.data.length,
          });
          
          // Set visible time range for DetectionsList filtering
          if (result.data[visibleMin] && result.data[visibleMax]) {
            const startTime = new Date(result.data[visibleMin].time);
            const endTime = new Date(result.data[visibleMax].time);
            setVisibleTimeRange({ startTime, endTime });
          }
        }
        
        setLoadingProgress(100);
        setError(null);
      } catch (err) {
        setError('Impossible de recuperer les donnees');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    loadAllData();

    // Load detections
    const fetchDetections = async () => {
      try {
        const result = await apiService.getDetections(0);
        setDetections(result.detections || []);
      } catch (err) {
        console.error('Failed to fetch detections:', err);
      }
    };
    fetchDetections();

    // Load signatures
    const fetchSignatures = async () => {
      try {
        const result = await apiService.getSignatures();
        setSignatures(result.signatures || []);
      } catch (err) {
        console.error('Failed to fetch signatures:', err);
      }
    };
    fetchSignatures();

    // Setup WebSocket for real-time updates
    const handleNewDetection = (detection) => {
      setDetections(prev => [...prev, detection]);
    };

    const handleDetectionComplete = async () => {
      try {
        const result = await apiService.getDetections(0);
        setDetections(result.detections || []);
      } catch (err) {
        console.error('Failed to refresh detections:', err);
      }
    };

    const handleDetectionsCleared = () => {
      setDetections([]);
    };

    detectionsWS.on('new_detection', handleNewDetection);
    detectionsWS.on('detection_complete', handleDetectionComplete);
    detectionsWS.on('detections_cleared', handleDetectionsCleared);
    detectionsWS.connect();

    return () => {
      detectionsWS.off('new_detection', handleNewDetection);
      detectionsWS.off('detection_complete', handleDetectionComplete);
      detectionsWS.off('detections_cleared', handleDetectionsCleared);
    };
  }, [setZoomState, setVisibleTimeRange]);

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
    
    try {
      const result = await apiService.getSignatures();
      setSignatures(result.signatures || []);
      window.dispatchEvent(new CustomEvent('signature-created'));
    } catch (err) {
      console.error('Failed to refresh signatures:', err);
    }
  };

  if (loading) {
    return (
      <Card>
        <CardContent sx={{ textAlign: 'center', py: 4 }}>
          <CircularProgress />
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            Chargement des donnees...
          </Typography>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent>
          <Alert severity="error">{error}</Alert>
        </CardContent>
      </Card>
    );
  }

  if (!rawData || !rawData.data || rawData.data.length === 0) {
    return (
      <Card>
        <CardContent>
          <Alert severity="info">Aucune donnee disponible</Alert>
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <Card>
        <CardHeader
          title="Historique de consommation"
          titleTypographyProps={{ variant: 'h5' }}
          subheader={
            loading 
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
                disabled={loading}
                sx={{ textTransform: 'none' }}
              >
                Réinitialiser la vue
              </Button>
            </span>
          </MuiTooltip>
        </Toolbar>
        
        {loading && (
          <LinearProgress 
            variant="determinate" 
            value={loadingProgress} 
            sx={{ 
              height: 2,
              backgroundColor: (theme) => theme.palette.overlay.black[5],
            }} 
          />
        )}
        <CardContent sx={{ p: 2 }}>
          <CombinedChart 
            rawData={rawData} 
            detections={detections}
            signatures={signatures}
            onSignatureModalOpen={handleSignatureModalOpen}
            isModalOpen={showSignatureModal}
          />
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
