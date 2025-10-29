import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  Card,
  CardContent,
  CardHeader,
  Typography,
  LinearProgress,
  Chip,
  Alert,
  List,
  ListItem,
  ListItemText,
  Divider,
  Grid,
  Paper,
  IconButton,
  Collapse,
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  CheckCircle as CompleteIcon,
  PlayArrow as RunningIcon,
  Error as ErrorIcon,
  Speed as SpeedIcon,
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

  // WebSocket event handlers
  useEffect(() => {
    const handleConnected = () => {
      setIsConnected(true);
      addLog('info', 'Connected to training logs stream');
    };

    const handleDisconnected = () => {
      setIsConnected(false);
      addLog('warning', 'Disconnected from training logs stream');
    };

    const handleTrainingStart = (data) => {
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
    };

    const handleEpochStart = (data) => {
      setTrainingData((prev) => ({
        ...prev,
        currentEpoch: data.epoch,
        progress: data.progress,
      }));
      addLog('info', `Epoch ${data.epoch}/${data.total_epochs} started`);
    };

    const handleEpochEnd = (data) => {
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
    };

    const handleBatchUpdate = (data) => {
      // Only update metrics, don't add log for each batch
      setTrainingData((prev) => ({
        ...prev,
        metrics: data.metrics,
      }));
    };

    const handleTrainingComplete = (data) => {
      setIsTraining(false);
      setTrainingData((prev) => ({
        ...prev,
        progress: 100,
        metrics: data.final_metrics,
      }));
      addLog('success', `Training completed in ${formatDuration(data.total_duration_seconds)}`);
    };

    const handleError = (data) => {
      addLog('error', `Error: ${data.error}`);
    };

    // Register handlers
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
      trainingLogsWS.off('connected', handleConnected);
      trainingLogsWS.off('disconnected', handleDisconnected);
      trainingLogsWS.off('training_start', handleTrainingStart);
      trainingLogsWS.off('epoch_start', handleEpochStart);
      trainingLogsWS.off('epoch_end', handleEpochEnd);
      trainingLogsWS.off('batch_update', handleBatchUpdate);
      trainingLogsWS.off('training_complete', handleTrainingComplete);
      trainingLogsWS.off('error', handleError);
    };
  }, []);

  const addLog = (level, message) => {
    setLogs((prev) => [
      ...prev,
      {
        timestamp: new Date(),
        level,
        message,
      },
    ]);
  };

  const formatDuration = (seconds) => {
    if (!seconds) return '0s';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) return `${h}h ${m}m ${s}s`;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
  };

  const getLogIcon = (level) => {
    switch (level) {
      case 'success':
        return <CompleteIcon fontSize="small" color="success" />;
      case 'error':
        return <ErrorIcon fontSize="small" color="error" />;
      case 'warning':
        return <ErrorIcon fontSize="small" color="warning" />;
      default:
        return <SpeedIcon fontSize="small" color="info" />;
    }
  };

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
            <Paper
              sx={{
                maxHeight: 300,
                overflow: 'auto',
                bgcolor: 'grey.50',
                border: 1,
                borderColor: 'grey.300',
              }}
            >
              {logs.length === 0 ? (
                <Box p={2}>
                  <Alert severity="info">
                    Waiting for training events...
                  </Alert>
                </Box>
              ) : (
                <List dense>
                  {logs.map((log, index) => (
                    <ListItem key={index} divider={index < logs.length - 1}>
                      <ListItemText
                        primary={
                          <Box display="flex" alignItems="center" gap={1}>
                            {getLogIcon(log.level)}
                            <Typography variant="body2">{log.message}</Typography>
                          </Box>
                        }
                        secondary={log.timestamp.toLocaleTimeString()}
                      />
                    </ListItem>
                  ))}
                  <div ref={logsEndRef} />
                </List>
              )}
            </Paper>
          </Box>
        </CardContent>
      </Collapse>
    </Card>
  );
};

export default TrainingLogsViewer;
