import {
  Analytics,
  CheckCircle,
  ExpandMore as ExpandMoreIcon,
  ModelTraining,
  Schedule,
  Speed,
  TrendingDown,
} from "@mui/icons-material";
import {
  Box,
  Chip,
  Collapse,
  Grid,
  IconButton,
  LinearProgress,
  Paper,
  Tooltip,
  Typography,
} from "@mui/material";
import { useTheme } from "@mui/material/styles";
import { useCallback, useEffect, useState } from "react";
import api from "../services/api";
import websocket from "../services/sse";
import {
  formatDuration,
  formatFullDateTime,
  formatHumanizedDate,
} from "../utils/dateUtils";
import MaterialIcon from "./common/MaterialIcon";

/**
 * Component showing the current model's info and training progress
 */
function ModelInfoSection() {
  const theme = useTheme();
  const [expanded, setExpanded] = useState(false);
  const [model, setModel] = useState(null);
  const [isTraining, setIsTraining] = useState(false);
  const [trainingProgress, setTrainingProgress] = useState(0);
  const [currentEpoch, setCurrentEpoch] = useState(0);
  const [totalEpochs, setTotalEpochs] = useState(0);
  const [trainingLogs, setTrainingLogs] = useState([]);

  // Load the current model
  const loadModel = useCallback(async () => {
    try {
      const response = await api.get("/api/nilm/models");
      if (response.data.models.length > 0) {
        const modelData = response.data.models[0];
        setModel(modelData);
      } else {
        setModel(null);
      }
    } catch (error) {
      console.error("Error loading model:", error);
    }
  }, []);

  useEffect(() => {
    loadModel();

    // Listen for the custom model-deleted event
    const handleModelDeleted = () => {
      loadModel();
    };

    window.addEventListener("models-deleted", handleModelDeleted);

    return () => {
      window.removeEventListener("models-deleted", handleModelDeleted);
    };
  }, [loadModel]);

  // Handle training SSE events
  useEffect(() => {
    websocket.connect();

    const handleTrainingStart = (data) => {
      setIsTraining(true);
      setTrainingProgress(0);
      setCurrentEpoch(0);
      setTotalEpochs(data.total_epochs || 0);
      setTrainingLogs([
        {
          type: "info",
          message: `Démarrage de l'entraînement - ${data.total_epochs} époques`,
          timestamp: new Date(),
        },
      ]);
      setExpanded(true); // Auto-expand when training starts
    };

    const handleEpochEnd = (data) => {
      const progress = ((data.epoch + 1) / data.total_epochs) * 100;
      setTrainingProgress(progress);
      setCurrentEpoch(data.epoch + 1);
      setTotalEpochs(data.total_epochs);

      // Add a log entry for the epoch
      const logMessage = `Époque ${data.epoch + 1}/${
        data.total_epochs
      } terminée`;
      const details = [];
      if (data.loss !== undefined)
        details.push(`loss: ${data.loss.toFixed(4)}`);
      if (data.val_loss !== undefined)
        details.push(`val_loss: ${data.val_loss.toFixed(4)}`);
      if (data.mae !== undefined) details.push(`mae: ${data.mae.toFixed(4)}`);
      if (data.val_mae !== undefined)
        details.push(`val_mae: ${data.val_mae.toFixed(4)}`);

      const fullMessage =
        details.length > 0
          ? `${logMessage} - ${details.join(", ")}`
          : logMessage;

      setTrainingLogs((prev) => [
        ...prev,
        { type: "success", message: fullMessage, timestamp: new Date() },
      ]);
    };

    const handleTrainingComplete = (data) => {
      setIsTraining(false);
      setTrainingProgress(100);
      setTrainingLogs((prev) => [
        ...prev,
        {
          type: "success",
          message: "Entraînement terminé avec succès!",
          timestamp: new Date(),
        },
      ]);

      // Reload the model after 2 seconds
      setTimeout(() => {
        loadModel();
      }, 2000);
    };

    websocket.on("training_start", handleTrainingStart);
    websocket.on("epoch_end", handleEpochEnd);
    websocket.on("training_complete", handleTrainingComplete);

    return () => {
      websocket.off("training_start", handleTrainingStart);
      websocket.off("epoch_end", handleEpochEnd);
      websocket.off("training_complete", handleTrainingComplete);
    };
  }, [loadModel]);

  const handleToggle = () => {
    setExpanded(!expanded);
  };

  // Show the status badge
  const getStatusBadge = () => {
    if (isTraining) {
      return (
        <Tooltip title="Entraînement en cours">
          <Chip
            icon={<ModelTraining sx={{ fontSize: 16 }} />}
            size="small"
            color="primary"
            sx={{
              height: 24,
              width: 24,
              borderRadius: "50%",
              "& .MuiChip-icon": {
                margin: 0,
                marginLeft: 0,
                marginRight: 0,
              },
              "& .MuiChip-label": {
                display: "none",
              },
            }}
          />
        </Tooltip>
      );
    } else if (model) {
      return (
        <Tooltip title="Modèle prêt">
          <Chip
            icon={<CheckCircle sx={{ fontSize: 16 }} />}
            size="small"
            color="success"
            sx={{
              height: 24,
              width: 24,
              borderRadius: "50%",
              "& .MuiChip-icon": {
                margin: 0,
                marginLeft: 0,
                marginRight: 0,
              },
              "& .MuiChip-label": {
                display: "none",
              },
            }}
          />
        </Tooltip>
      );
    } else {
      return (
        <Tooltip title="Aucun modèle">
          <Chip
            icon={<MaterialIcon sx={{ fontSize: 16 }}>error</MaterialIcon>}
            size="small"
            color="warning"
            sx={{
              height: 24,
              width: 24,
              borderRadius: "50%",
              "& .MuiChip-icon": {
                margin: 0,
                marginLeft: 0,
                marginRight: 0,
              },
              "& .MuiChip-label": {
                display: "none",
              },
            }}
          />
        </Tooltip>
      );
    }
  };

  // Extract metrics
  const getMetrics = (metricsData) => {
    if (!metricsData) return null;

    try {
      const parsed =
        typeof metricsData === "string" ? JSON.parse(metricsData) : metricsData;

      // If metrics are under appliances[].metrics, extract and average them
      if (
        parsed.appliances &&
        Array.isArray(parsed.appliances) &&
        parsed.appliances.length > 0
      ) {
        const aggregated = {
          appliances: parsed.appliances,
          num_appliances: parsed.num_appliances || parsed.appliances.length,
        };

        // Compute metric averages
        const valLosses = parsed.appliances
          .map((app) => app.metrics?.val_loss)
          .filter((v) => v !== undefined && v !== null);

        const valMAEs = parsed.appliances
          .map((app) => app.metrics?.val_mae)
          .filter((v) => v !== undefined && v !== null);

        const epochs = parsed.appliances
          .map((app) => app.metrics?.epochs_trained)
          .filter((v) => v !== undefined && v !== null);

        if (valLosses.length > 0) {
          aggregated.val_loss =
            valLosses.reduce((sum, v) => sum + v, 0) / valLosses.length;
        }

        if (valMAEs.length > 0) {
          aggregated.val_mae =
            valMAEs.reduce((sum, v) => sum + v, 0) / valMAEs.length;
        }

        if (epochs.length > 0) {
          aggregated.epochs = Math.max(...epochs);
        }

        return aggregated;
      }

      return parsed;
    } catch (error) {
      console.error("Error parsing metrics:", error);
      return null;
    }
  };

  const metrics = model ? getMetrics(model.metrics) : null;

  return (
    <Box sx={{ borderBottom: 1, borderColor: "divider" }}>
      {/* Collapsible header */}
      <Box
        sx={{
          px: 2,
          py: 1,
          bgcolor: theme.palette.mode === "dark" ? "grey.900" : "grey.50",
          cursor: "pointer",
          "&:hover": {
            bgcolor: theme.palette.mode === "dark" ? "grey.800" : "grey.100",
          },
        }}
        onClick={handleToggle}
      >
        <Grid container spacing={1} alignItems="center">
          <Grid item>
            <IconButton
              size="small"
              sx={{
                transform: expanded ? "rotate(180deg)" : "rotate(270deg)",
                transition: "transform 0.3s",
              }}
            >
              <ExpandMoreIcon />
            </IconButton>
          </Grid>

          <Grid item>
            <MaterialIcon sx={{ fontSize: 20, color: "primary.main" }}>
              cognition
            </MaterialIcon>
          </Grid>

          <Grid item>
            <Box sx={{ display: "flex", alignItems: "baseline", gap: 1 }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                Modèle IA Linkya
              </Typography>
              {model && !isTraining && (
                <Typography variant="caption" color="text.secondary">
                  entraîné {formatHumanizedDate(model.training_date)}
                </Typography>
              )}
            </Box>
          </Grid>

          <Grid item xs />

          <Grid item>{getStatusBadge()}</Grid>
        </Grid>
      </Box>

      {/* Barre de progression d'entraînement (toujours visible pendant l'entraînement) */}
      {isTraining && (
        <Box
          sx={{
            px: 2,
            pb: 1.5,
            bgcolor: theme.palette.mode === "dark" ? "grey.900" : "grey.50",
          }}
        >
          <Grid container spacing={1} alignItems="center" sx={{ mb: 0.5 }}>
            <Grid item xs>
              <Typography
                variant="caption"
                fontWeight="600"
                color="primary.main"
              >
                Entraînement en cours...
              </Typography>
            </Grid>
            <Grid item>
              <Typography
                variant="caption"
                fontWeight="600"
                color="primary.main"
              >
                Époque {currentEpoch}/{totalEpochs} -{" "}
                {Math.round(trainingProgress)}%
              </Typography>
            </Grid>
          </Grid>
          <LinearProgress
            variant="determinate"
            value={trainingProgress}
            sx={{
              height: 8,
              borderRadius: 1,
              backgroundColor:
                theme.palette.mode === "dark" ? "grey.700" : "grey.300",
            }}
          />
        </Box>
      )}

      {/* Contenu collapsible */}
      <Collapse in={expanded} timeout="auto" unmountOnExit>
        <Box sx={{ p: 2 }}>
          {isTraining ? (
            // Real-time training logs display
            <Paper
              variant="outlined"
              sx={{
                bgcolor: theme.palette.mode === "dark" ? "grey.900" : "#1e1e1e",
                color: theme.palette.mode === "dark" ? "grey.100" : "#d4d4d4",
                p: 2,
                fontFamily: "monospace",
                fontSize: "0.875rem",
              }}
            >
              <Box
                sx={{
                  display: "flex",
                  alignItems: "center",
                  gap: 1,
                  mb: 2,
                  pb: 1,
                  borderBottom: 1,
                  borderColor: "divider",
                }}
              >
                <MaterialIcon sx={{ fontSize: 18, color: "primary.main" }}>
                  terminal
                </MaterialIcon>
                <Typography
                  variant="caption"
                  sx={{
                    color: "primary.main",
                    fontWeight: 600,
                    fontFamily: "monospace",
                  }}
                >
                  Logs d'entraînement
                </Typography>
              </Box>
              {/* Show the last 5 rows */}
              {Array.from({ length: 5 }).map((_, index) => {
                const logIndex = trainingLogs.length - 5 + index;
                const log = logIndex >= 0 ? trainingLogs[logIndex] : null;

                return (
                  <Box
                    key={index}
                    sx={{
                      mb: 1,
                      display: "flex",
                      gap: 1,
                      alignItems: "flex-start",
                      minHeight: "24px",
                    }}
                  >
                    {log ? (
                      <>
                        <Typography
                          variant="caption"
                          sx={{
                            color:
                              theme.palette.mode === "dark"
                                ? "grey.500"
                                : "#858585",
                            fontFamily: "monospace",
                            minWidth: "60px",
                            flexShrink: 0,
                          }}
                        >
                          {log.timestamp.toLocaleTimeString("fr-FR", {
                            hour: "2-digit",
                            minute: "2-digit",
                            second: "2-digit",
                          })}
                        </Typography>
                        <Box
                          sx={{
                            width: 6,
                            height: 6,
                            borderRadius: "50%",
                            bgcolor:
                              log.type === "success"
                                ? "success.main"
                                : log.type === "error"
                                ? "error.main"
                                : "info.main",
                            mt: 0.5,
                            flexShrink: 0,
                          }}
                        />
                        <Typography
                          variant="body2"
                          sx={{
                            fontFamily: "monospace",
                            fontSize: "0.875rem",
                            color:
                              log.type === "success"
                                ? "#4caf50"
                                : log.type === "error"
                                ? "#f44336"
                                : "#90caf9",
                            wordBreak: "break-word",
                          }}
                        >
                          {log.message}
                        </Typography>
                      </>
                    ) : (
                      <Typography
                        variant="body2"
                        sx={{
                          color:
                            theme.palette.mode === "dark"
                              ? "grey.700"
                              : "#404040",
                          fontFamily: "monospace",
                          fontSize: "0.875rem",
                        }}
                      >
                        &nbsp;
                      </Typography>
                    )}
                  </Box>
                );
              })}
            </Paper>
          ) : model ? (
            <Grid container spacing={2}>
              {/* Training date */}
              <Grid item xs={12} md={6}>
                <Paper variant="outlined" sx={{ p: 1.5, height: "100%" }}>
                  <Box
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      gap: 1,
                      mb: 0.5,
                    }}
                  >
                    <Schedule sx={{ fontSize: 18, color: "text.secondary" }} />
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      fontWeight="600"
                    >
                      Date d'entraînement
                    </Typography>
                  </Box>
                  <Typography variant="body2" fontWeight="500">
                    {formatFullDateTime(model.training_date)}
                  </Typography>
                </Paper>
              </Grid>

              {/* Training duration */}
              {model.training_duration_seconds && (
                <Grid item xs={12} md={6}>
                  <Paper variant="outlined" sx={{ p: 1.5, height: "100%" }}>
                    <Box
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        gap: 1,
                        mb: 0.5,
                      }}
                    >
                      <Speed sx={{ fontSize: 18, color: "text.secondary" }} />
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        fontWeight="600"
                      >
                        Durée d'entraînement
                      </Typography>
                    </Box>
                    <Typography variant="body2" fontWeight="500">
                      {formatDuration(model.training_duration_seconds)}
                    </Typography>
                  </Paper>
                </Grid>
              )}

              {/* Number of appliances */}
              {model.num_classes && (
                <Grid item xs={12} md={6}>
                  <Paper variant="outlined" sx={{ p: 1.5, height: "100%" }}>
                    <Box
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        gap: 1,
                        mb: 0.5,
                      }}
                    >
                      <MaterialIcon
                        sx={{ fontSize: 18, color: "text.secondary" }}
                      >
                        devices
                      </MaterialIcon>
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        fontWeight="600"
                      >
                        Nombre d'appareils
                      </Typography>
                    </Box>
                    <Typography variant="body2" fontWeight="500">
                      {model.num_classes}
                    </Typography>
                  </Paper>
                </Grid>
              )}

              {/* Number of signatures */}
              {model.num_signatures && (
                <Grid item xs={12} md={6}>
                  <Paper variant="outlined" sx={{ p: 1.5, height: "100%" }}>
                    <Box
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        gap: 1,
                        mb: 0.5,
                      }}
                    >
                      <MaterialIcon
                        sx={{ fontSize: 18, color: "text.secondary" }}
                      >
                        database
                      </MaterialIcon>
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        fontWeight="600"
                      >
                        Signatures utilisées
                      </Typography>
                    </Box>
                    <Typography variant="body2" fontWeight="500">
                      {model.num_signatures}
                    </Typography>
                  </Paper>
                </Grid>
              )}

              {/* Number of epochs */}
              {metrics && metrics.epochs && (
                <Grid item xs={12} md={6}>
                  <Paper variant="outlined" sx={{ p: 1.5, height: "100%" }}>
                    <Box
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        gap: 1,
                        mb: 0.5,
                      }}
                    >
                      <MaterialIcon
                        sx={{ fontSize: 18, color: "text.secondary" }}
                      >
                        autorenew
                      </MaterialIcon>
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        fontWeight="600"
                      >
                        Époques totales
                      </Typography>
                    </Box>
                    <Typography variant="body2" fontWeight="500">
                      {metrics.epochs}
                    </Typography>
                  </Paper>
                </Grid>
              )}

              {/* Validation loss */}
              {metrics &&
                metrics.val_loss !== undefined &&
                metrics.val_loss !== null && (
                  <Grid item xs={12} md={6}>
                    <Paper variant="outlined" sx={{ p: 1.5, height: "100%" }}>
                      <Box
                        sx={{
                          display: "flex",
                          alignItems: "center",
                          gap: 1,
                          mb: 0.5,
                        }}
                      >
                        <TrendingDown
                          sx={{ fontSize: 18, color: "text.secondary" }}
                        />
                        <Typography
                          variant="caption"
                          color="text.secondary"
                          fontWeight="600"
                        >
                          Loss de validation
                        </Typography>
                      </Box>
                      <Typography variant="body2" fontWeight="500">
                        {typeof metrics.val_loss === "number"
                          ? metrics.val_loss.toFixed(4)
                          : metrics.val_loss}
                      </Typography>
                    </Paper>
                  </Grid>
                )}

              {/* Validation MAE (if available) */}
              {metrics &&
                metrics.val_mae !== undefined &&
                metrics.val_mae !== null && (
                  <Grid item xs={12} md={6}>
                    <Paper variant="outlined" sx={{ p: 1.5, height: "100%" }}>
                      <Box
                        sx={{
                          display: "flex",
                          alignItems: "center",
                          gap: 1,
                          mb: 0.5,
                        }}
                      >
                        <Analytics
                          sx={{ fontSize: 18, color: "text.secondary" }}
                        />
                        <Typography
                          variant="caption"
                          color="text.secondary"
                          fontWeight="600"
                        >
                          MAE de validation
                        </Typography>
                      </Box>
                      <Typography variant="body2" fontWeight="500">
                        {typeof metrics.val_mae === "number"
                          ? metrics.val_mae.toFixed(4)
                          : metrics.val_mae}
                      </Typography>
                    </Paper>
                  </Grid>
                )}
            </Grid>
          ) : (
            <Box sx={{ textAlign: "center", py: 3 }}>
              <MaterialIcon
                sx={{ fontSize: 48, color: "text.disabled", mb: 1 }}
              >
                model_training
              </MaterialIcon>
              <Typography variant="body2" color="text.secondary">
                Aucun modèle n'a encore été entraîné. Cliquez sur "Entraîner le
                modèle" pour commencer.
              </Typography>
            </Box>
          )}
        </Box>
      </Collapse>
    </Box>
  );
}

export default ModelInfoSection;
