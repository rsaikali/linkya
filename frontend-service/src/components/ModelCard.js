import {
  ModelTraining,
  CheckCircle,
} from "@mui/icons-material";
import {
  Box,
  Card,
  CardContent,
  CardHeader,
  Chip,
  LinearProgress,
  Skeleton,
  Tooltip,
  Typography,
} from "@mui/material";
import { useCallback, useEffect, useState } from "react";
import api from "../services/api";
import websocket from "../services/sse";
import {
  formatDuration,
  formatHumanizedDate,
} from "../utils/dateUtils";
import MaterialIcon from "./common/MaterialIcon";

function ModelCard() {
  const [model, setModel] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isTraining, setIsTraining] = useState(false);
  const [trainingProgress, setTrainingProgress] = useState(0);
  const [currentEpoch, setCurrentEpoch] = useState(0);
  const [totalEpochs, setTotalEpochs] = useState(0);

  const loadModel = useCallback(async () => {
    try {
      const res = await api.get("/api/nilm/models");
      setModel(res.data.models.length > 0 ? res.data.models[0] : null);
    } catch {
      setModel(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadModel();
    const onDeleted = () => loadModel();
    window.addEventListener("models-deleted", onDeleted);
    return () => window.removeEventListener("models-deleted", onDeleted);
  }, [loadModel]);

  useEffect(() => {
    const onStart = (data) => {
      setIsTraining(true);
      setTrainingProgress(0);
      setCurrentEpoch(0);
      setTotalEpochs(data.total_epochs || 0);
    };
    const onEpoch = (data) => {
      setTrainingProgress(((data.epoch + 1) / data.total_epochs) * 100);
      setCurrentEpoch(data.epoch + 1);
      setTotalEpochs(data.total_epochs);
    };
    const onComplete = () => {
      setIsTraining(false);
      setTrainingProgress(100);
      setTimeout(loadModel, 2000);
    };
    websocket.on("training_start", onStart);
    websocket.on("epoch_end", onEpoch);
    websocket.on("training_complete", onComplete);
    return () => {
      websocket.off("training_start", onStart);
      websocket.off("epoch_end", onEpoch);
      websocket.off("training_complete", onComplete);
    };
  }, [loadModel]);

  const getMetrics = (metricsData) => {
    if (!metricsData) return null;
    try {
      const parsed = typeof metricsData === "string" ? JSON.parse(metricsData) : metricsData;
      if (parsed.appliances?.length > 0) {
        const valLosses = parsed.appliances.map((a) => a.metrics?.val_loss).filter((v) => v != null);
        const epochs = parsed.appliances.map((a) => a.metrics?.epochs_trained).filter((v) => v != null);
        return {
          val_loss: valLosses.length ? valLosses.reduce((s, v) => s + v, 0) / valLosses.length : null,
          epochs: epochs.length ? Math.max(...epochs) : null,
        };
      }
      return parsed;
    } catch {
      return null;
    }
  };

  const metrics = model ? getMetrics(model.metrics) : null;

  const statusBadge = isTraining ? (
    <Tooltip title="Entraînement en cours">
      <Chip
        icon={<ModelTraining sx={{ fontSize: 14 }} />}
        label={`${currentEpoch}/${totalEpochs} époques`}
        size="small"
        color="primary"
        sx={{ height: 22, fontSize: "0.7rem" }}
      />
    </Tooltip>
  ) : model ? (
    <Tooltip title="Modèle actif">
      <Chip
        icon={<CheckCircle sx={{ fontSize: 14 }} />}
        label="Actif"
        size="small"
        color="success"
        sx={{ height: 22, fontSize: "0.7rem" }}
      />
    </Tooltip>
  ) : (
    <Chip
      icon={<MaterialIcon sx={{ fontSize: 14 }}>error</MaterialIcon>}
      label="Aucun modèle"
      size="small"
      color="warning"
      sx={{ height: 22, fontSize: "0.7rem" }}
    />
  );

  return (
    <Card>
      <CardHeader
        avatar={
          <MaterialIcon sx={{ fontSize: 20, color: "primary.main" }}>
            cognition
          </MaterialIcon>
        }
        title="Modèle IA"
        titleTypographyProps={{ variant: "subtitle1", fontWeight: 600 }}
        subheader={
          model && !isTraining
            ? `entraîné ${formatHumanizedDate(model.training_date)}`
            : isTraining
            ? "Entraînement en cours..."
            : "Aucun modèle entraîné"
        }
        action={<Box sx={{ pt: 1, pr: 1 }}>{statusBadge}</Box>}
        sx={{ pb: 0 }}
      />

      {isTraining && (
        <Box sx={{ px: 2, pt: 1 }}>
          <LinearProgress
            variant="determinate"
            value={trainingProgress}
            sx={{ height: 6, borderRadius: 1 }}
          />
          <Typography variant="caption" color="primary.main" sx={{ mt: 0.5, display: "block" }}>
            {Math.round(trainingProgress)}% — époque {currentEpoch}/{totalEpochs}
          </Typography>
        </Box>
      )}

      <CardContent sx={{ pt: 1, pb: "12px !important" }}>
        {loading && (
          <Box sx={{ display: "flex", gap: 1 }}>
            <Skeleton variant="rounded" width={80} height={24} />
            <Skeleton variant="rounded" width={80} height={24} />
            <Skeleton variant="rounded" width={80} height={24} />
          </Box>
        )}

        {!loading && !model && !isTraining && (
          <Typography variant="body2" color="text.secondary">
            Entraîner le modèle depuis l'onglet Signatures.
          </Typography>
        )}

        {!loading && model && (
          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.75 }}>
            <StatChip
              icon="devices"
              label={`${model.num_classes ?? "?"} appareil${(model.num_classes ?? 0) > 1 ? "s" : ""}`}
              tooltip="Appareils dans le modèle"
            />
            <StatChip
              icon="database"
              label={`${model.num_signatures ?? "?"} signatures`}
              tooltip="Signatures d'entraînement"
            />
            {metrics?.val_loss != null && (
              <StatChip
                icon="trending_down"
                label={`val_loss ${metrics.val_loss.toFixed(4)}`}
                tooltip="Loss de validation (plus bas = meilleur)"
              />
            )}
            {metrics?.epochs != null && (
              <StatChip
                icon="autorenew"
                label={`${metrics.epochs} époques`}
                tooltip="Époques d'entraînement"
              />
            )}
            {model.training_duration_seconds != null && (
              <StatChip
                icon="timer"
                label={formatDuration(model.training_duration_seconds)}
                tooltip="Durée d'entraînement"
              />
            )}
            {model.model_type && (
              <StatChip
                icon="chip"
                label={model.model_type}
                tooltip="Architecture"
              />
            )}
          </Box>
        )}
      </CardContent>
    </Card>
  );
}

function StatChip({ icon, label, tooltip }) {
  return (
    <Tooltip title={tooltip}>
      <Box
        sx={{
          display: "inline-flex",
          alignItems: "center",
          gap: 0.4,
          px: 0.75,
          py: 0.25,
          borderRadius: 1,
          bgcolor: "action.hover",
          border: "1px solid",
          borderColor: "divider",
        }}
      >
        <MaterialIcon sx={{ fontSize: 13, color: "text.secondary" }}>{icon}</MaterialIcon>
        <Typography variant="caption" color="text.secondary" sx={{ fontSize: "0.7rem", lineHeight: 1.4 }}>
          {label}
        </Typography>
      </Box>
    </Tooltip>
  );
}

export default ModelCard;
