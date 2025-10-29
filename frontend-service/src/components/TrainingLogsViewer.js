import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Box,
  Card,
  CardContent,
  CardHeader,
  Typography,
  LinearProgress,
  Chip,
  Divider,
  Grid,
  Paper,
  IconButton,
  Collapse,
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  PlayArrow as RunningIcon,
} from '@mui/icons-material';
import trainingLogsWS from '../services/websocket';

const TrainingLogsViewer = () => {
  const [isConnected, setIsConnected] = useState(false);
  const [isTraining, setIsTraining] = useState(false);
  const [trainingData, setTrainingData] = useState({
    version: null,
    currentEpoch: 0,
    totalEpochs: 0,
    progress: 0,
    metrics: {},
    elapsedSeconds: 0,
    etaSeconds: 0,
  });
  const [logs, setLogs] = useState([]);
  const [expanded, setExpanded] = useState(true);
  const logsEndRef = useRef(null);

  // Auto-scroll to bottom when new logs arrive
  const scrollToBottom = () => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [logs]);

  // Helper functions wrapped in useCallback to avoid recreating on each render
  const addLog = useCallback((level, message) => {
    setLogs((prev) => [
      ...prev,
      {
        timestamp: new Date(),
        level,
        message,
      },
    ]);
  }, []);

  const formatDuration = useCallback((seconds) => {
    if (!seconds) return '0s';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) return `${h}h ${m}m ${s}s`;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
  }, []);

  // WebSocket event handlers wrapped in useCallback
  const handleConnected = useCallback(() => {
    setIsConnected(true);
    addLog('info', 'Connected to training logs stream');
  }, [addLog]);

  const handleDisconnected = useCallback(() => {
    setIsConnected(false);
    addLog('warning', 'Disconnected from training logs stream');
  }, [addLog]);

  const handleTrainingStart = useCallback((data) => {
    setIsTraining(true);
    setTrainingData({
      version: data.version || 'current',
      currentEpoch: 0,
      totalEpochs: data.total_epochs || 0,
      progress: 0,
      metrics: {},
      elapsedSeconds: 0,
      etaSeconds: 0,
    });
    addLog('success', `Training started: ${data.message}`);
  }, [addLog]);

  const handleEpochStart = useCallback((data) => {
    setTrainingData((prev) => ({
      ...prev,
      currentEpoch: data.epoch,
      progress: data.progress,
    }));
    addLog('info', `Epoch ${data.epoch}/${data.total_epochs} started`);
  }, [addLog]);

  const handleEpochEnd = useCallback((data) => {
    setTrainingData((prev) => ({
      ...prev,
      currentEpoch: data.epoch,
      totalEpochs: data.total_epochs,
      progress: data.progress,
      metrics: data.metrics,
      elapsedSeconds: data.elapsed_seconds,
      etaSeconds: data.eta_seconds,
    }));

    const metricsStr = Object.entries(data.metrics)
      .map(([key, value]) => `${key}=${value.toFixed(4)}`)
      .join(', ');
    addLog('success', `Epoch ${data.epoch} completed: ${metricsStr}`);
  }, [addLog]);

  const handleBatchUpdate = useCallback((data) => {
    // Only update metrics, don't add log for each batch
    setTrainingData((prev) => ({
      ...prev,
      metrics: data.metrics,
    }));
  }, []);

  const handleTrainingComplete = useCallback((data) => {
    setIsTraining(false);
    setTrainingData((prev) => ({
      ...prev,
      progress: 100,
      metrics: data.final_metrics,
    }));
    addLog('success', `Training completed in ${formatDuration(data.total_duration_seconds)}`);
  }, [addLog, formatDuration]);

  const handleError = useCallback((data) => {
    addLog('error', `Error: ${data.error}`);
  }, [addLog]);

  // WebSocket connection and event registration
  useEffect(() => {
    console.log('🔧 TrainingLogsViewer: Registering WebSocket handlers');
    
    // Register handlers (defined above with useCallback)
    trainingLogsWS.on('connected', handleConnected);
    trainingLogsWS.on('disconnected', handleDisconnected);
    trainingLogsWS.on('training_start', handleTrainingStart);
    trainingLogsWS.on('epoch_start', handleEpochStart);
    trainingLogsWS.on('epoch_end', handleEpochEnd);
    trainingLogsWS.on('batch_update', handleBatchUpdate);
    trainingLogsWS.on('training_complete', handleTrainingComplete);
    trainingLogsWS.on('error', handleError);

    // Connect WebSocket
    trainingLogsWS.connect();

    // Cleanup
    return () => {
      console.log('🧹 TrainingLogsViewer: Cleaning up WebSocket handlers');
      trainingLogsWS.off('connected', handleConnected);
      trainingLogsWS.off('disconnected', handleDisconnected);
      trainingLogsWS.off('training_start', handleTrainingStart);
      trainingLogsWS.off('epoch_start', handleEpochStart);
      trainingLogsWS.off('epoch_end', handleEpochEnd);
      trainingLogsWS.off('batch_update', handleBatchUpdate);
      trainingLogsWS.off('training_complete', handleTrainingComplete);
      trainingLogsWS.off('error', handleError);
    };
  }, [handleConnected, handleDisconnected, handleTrainingStart, handleEpochStart, handleEpochEnd, handleBatchUpdate, handleTrainingComplete, handleError]);

  return (
    <Card sx={{ mt: 2 }}>
      <CardHeader
        title={
          <Box display="flex" alignItems="center" gap={1}>
            <Typography variant="h6">Training Logs</Typography>
            <Chip
              label={isConnected ? 'Connected' : 'Disconnected'}
              color={isConnected ? 'success' : 'default'}
              size="small"
            />
            {isTraining && (
              <Chip
                icon={<RunningIcon />}
                label="Training in progress"
                color="primary"
                size="small"
              />
            )}
          </Box>
        }
        action={
          <IconButton
            onClick={() => setExpanded(!expanded)}
            sx={{
              transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
              transition: 'transform 0.3s',
            }}
          >
            <ExpandMoreIcon />
          </IconButton>
        }
      />
      <Collapse in={expanded}>
        <CardContent>
          {isTraining && (
            <Box mb={2}>
              <Grid container spacing={2}>
                <Grid item xs={12} md={6}>
                  <Paper sx={{ p: 2 }}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      Progress
                    </Typography>
                    <Box display="flex" alignItems="center" gap={1} mb={1}>
                      <LinearProgress
                        variant="determinate"
                        value={trainingData.progress}
                        sx={{ flex: 1, height: 8, borderRadius: 4 }}
                      />
                      <Typography variant="body2" fontWeight="bold">
                        {trainingData.progress.toFixed(1)}%
                      </Typography>
                    </Box>
                    <Typography variant="body2">
                      Epoch {trainingData.currentEpoch} / {trainingData.totalEpochs}
                    </Typography>
                  </Paper>
                </Grid>
                <Grid item xs={12} md={6}>
                  <Paper sx={{ p: 2 }}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      Timing
                    </Typography>
                    <Typography variant="body2">
                      Elapsed: {formatDuration(trainingData.elapsedSeconds)}
                    </Typography>
                    <Typography variant="body2">
                      ETA: {formatDuration(trainingData.etaSeconds)}
                    </Typography>
                  </Paper>
                </Grid>
                {Object.keys(trainingData.metrics).length > 0 && (
                  <Grid item xs={12}>
                    <Paper sx={{ p: 2 }}>
                      <Typography variant="body2" color="text.secondary" gutterBottom>
                        Current Metrics
                      </Typography>
                      <Grid container spacing={1}>
                        {Object.entries(trainingData.metrics).map(([key, value]) => (
                          <Grid item xs={6} sm={4} md={3} key={key}>
                            <Typography variant="body2">
                              <strong>{key}:</strong> {typeof value === 'number' ? value.toFixed(4) : value}
                            </Typography>
                          </Grid>
                        ))}
                      </Grid>
                    </Paper>
                  </Grid>
                )}
              </Grid>
            </Box>
          )}

          <Divider sx={{ my: 2 }} />

          <Box>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Event Log
            </Typography>
            {/* Terminal header */}
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 0.75,
                bgcolor: '#2d2d2d',
                borderTopLeftRadius: 4,
                borderTopRightRadius: 4,
                px: 1.5,
                py: 0.75,
                borderBottom: '1px solid #3e3e3e',
              }}
            >
              <Box sx={{ display: 'flex', gap: 0.5 }}>
                <Box
                  sx={{
                    width: 12,
                    height: 12,
                    borderRadius: '50%',
                    bgcolor: '#ff5f56',
                  }}
                />
                <Box
                  sx={{
                    width: 12,
                    height: 12,
                    borderRadius: '50%',
                    bgcolor: '#ffbd2e',
                  }}
                />
                <Box
                  sx={{
                    width: 12,
                    height: 12,
                    borderRadius: '50%',
                    bgcolor: '#27c93f',
                  }}
                />
              </Box>
              <Typography
                sx={{
                  fontSize: '0.75rem',
                  color: '#858585',
                  fontFamily: "'Fira Code', 'Courier New', monospace",
                  ml: 1,
                }}
              >
                nilmia-training.log
              </Typography>
            </Box>
            {/* Terminal content */}
            <Paper
              sx={{
                maxHeight: 400,
                overflow: 'auto',
                bgcolor: '#1e1e1e',
                border: 1,
                borderColor: '#333',
                borderTopLeftRadius: 0,
                borderTopRightRadius: 0,
                borderBottomLeftRadius: 4,
                borderBottomRightRadius: 4,
                p: 2,
                fontFamily: "'Fira Code', 'Courier New', monospace",
                fontSize: '0.875rem',
                lineHeight: 1.6,
                color: '#d4d4d4',
                '&::-webkit-scrollbar': {
                  width: '8px',
                },
                '&::-webkit-scrollbar-track': {
                  background: '#2d2d2d',
                },
                '&::-webkit-scrollbar-thumb': {
                  background: '#555',
                  borderRadius: '4px',
                  '&:hover': {
                    background: '#777',
                  },
                },
              }}
            >
              {logs.length === 0 ? (
                <Box sx={{ color: '#858585', fontStyle: 'italic' }}>
                  $ Waiting for training events...
                </Box>
              ) : (
                <Box>
                  {logs.map((log, index) => {
                    const timestamp = log.timestamp.toLocaleTimeString('fr-FR', {
                      hour: '2-digit',
                      minute: '2-digit',
                      second: '2-digit',
                    });
                    
                    let color = '#d4d4d4';
                    let prefix = '●';
                    
                    switch (log.level) {
                      case 'success':
                        color = '#4ec9b0';
                        prefix = '✓';
                        break;
                      case 'error':
                        color = '#f48771';
                        prefix = '✗';
                        break;
                      case 'warning':
                        color = '#dcdcaa';
                        prefix = '⚠';
                        break;
                      case 'info':
                      default:
                        color = '#569cd6';
                        prefix = '●';
                        break;
                    }
                    
                    return (
                      <Box
                        key={index}
                        sx={{
                          mb: 0.5,
                          display: 'flex',
                          gap: 1,
                          '&:hover': {
                            bgcolor: '#2d2d2d',
                            borderRadius: '2px',
                          },
                        }}
                      >
                        <Typography
                          component="span"
                          sx={{
                            color: '#858585',
                            minWidth: '70px',
                            fontFamily: 'inherit',
                            fontSize: 'inherit',
                          }}
                        >
                          [{timestamp}]
                        </Typography>
                        <Typography
                          component="span"
                          sx={{
                            color,
                            minWidth: '20px',
                            fontFamily: 'inherit',
                            fontSize: 'inherit',
                          }}
                        >
                          {prefix}
                        </Typography>
                        <Typography
                          component="span"
                          sx={{
                            color,
                            flex: 1,
                            fontFamily: 'inherit',
                            fontSize: 'inherit',
                          }}
                        >
                          {log.message}
                        </Typography>
                      </Box>
                    );
                  })}
                  <div ref={logsEndRef} />
                </Box>
              )}
            </Paper>
          </Box>
        </CardContent>
      </Collapse>
    </Card>
  );
};

export default TrainingLogsViewer;
