import {
  ModelTraining,
  CheckCircle,
  EmojiEvents,
} from "@mui/icons-material";
import {
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  LinearProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from "@mui/material";
import { useCallback, useEffect, useState } from "react";
import api from "../services/api";
import websocket, { detectionsWS } from "../services/sse";
import { formatHumanizedDate } from "../utils/dateUtils";
import MaterialIcon from "./common/MaterialIcon";

function ModelCard() {
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isTraining, setIsTraining] = useState(false);
  const [trainingProgress, setTrainingProgress] = useState(0);
  const [currentEpoch, setCurrentEpoch] = useState(0);
  const [totalEpochs, setTotalEpochs] = useState(0);
  const [promoteDialog, setPromoteDialog] = useState({ open: false, model: null });
  const [promoting, setPromoting] = useState(false);

  const loadModels = useCallback(async () => {
    try {
      const res = await api.get("/api/nilm/models");
      setModels(res.data.models || []);
    } catch {
      setModels([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadModels();
    const onDeleted = () => { setModels([]); setLoading(false); };
    window.addEventListener("models-deleted", onDeleted);
    return () => window.removeEventListener("models-deleted", onDeleted);
  }, [loadModels]);

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
      setTimeout(loadModels, 2000);
    };
    websocket.on("training_start", onStart);
    websocket.on("epoch_end", onEpoch);
    websocket.on("training_complete", onComplete);
    return () => {
      websocket.off("training_start", onStart);
      websocket.off("epoch_end", onEpoch);
      websocket.off("training_complete", onComplete);
    };
  }, [loadModels]);

  // Refresh after backfill (detect run) in case a new model was trained
  useEffect(() => {
    const onBackfill = () => loadModels();
    detectionsWS.on("ha_backfill_complete", onBackfill);
    return () => detectionsWS.off("ha_backfill_complete", onBackfill);
  }, [loadModels]);

  const champion = models.find((m) => m.is_champion);

  const handlePromote = async () => {
    if (!promoteDialog.model) return;
    setPromoting(true);
    try {
      await api.post(`/api/nilm/models/${promoteDialog.model.id}/promote`);
      setPromoteDialog({ open: false, model: null });
      await loadModels();
    } catch (err) {
      console.error("promote failed", err);
    } finally {
      setPromoting(false);
    }
  };

  const getMetricsSummary = (model) => {
    if (!model?.metrics) return null;
    try {
      const m = typeof model.metrics === "string" ? JSON.parse(model.metrics) : model.metrics;
      const apps = m.appliances || [];
      const valLosses = apps.map((a) => a.metrics?.val_loss).filter((v) => v != null);
      const epochs = apps.map((a) => a.metrics?.epochs_trained).filter((v) => v != null);
      return {
        val_loss: valLosses.length ? (valLosses.reduce((s, v) => s + v, 0) / valLosses.length).toFixed(4) : null,
        epochs: epochs.length ? Math.max(...epochs) : null,
      };
    } catch {
      return null;
    }
  };

  const statusChip = isTraining ? (
    <Chip
      icon={<ModelTraining sx={{ fontSize: 14 }} />}
      label={`${currentEpoch}/${totalEpochs}`}
      size="small"
      color="primary"
      sx={{ height: 22, fontSize: "0.7rem" }}
    />
  ) : champion ? (
    <Chip
      icon={<CheckCircle sx={{ fontSize: 14 }} />}
      label="Champion actif"
      size="small"
      color="success"
      sx={{ height: 22, fontSize: "0.7rem" }}
    />
  ) : (
    <Chip label="Aucun modèle" size="small" color="warning" sx={{ height: 22, fontSize: "0.7rem" }} />
  );

  return (
    <>
      <Card>
        <CardHeader
          avatar={
            <MaterialIcon sx={{ fontSize: 20, color: "primary.main" }}>cognition</MaterialIcon>
          }
          title="Modèle IA"
          titleTypographyProps={{ variant: "subtitle1", fontWeight: 600 }}
          subheader={
            isTraining
              ? `Entraînement en cours — ${Math.round(trainingProgress)}%`
              : champion
              ? `Champion : ${champion.model_name} · entraîné ${formatHumanizedDate(champion.training_date)}`
              : "Aucun modèle entraîné"
          }
          action={<Box sx={{ pt: 1, pr: 1 }}>{statusChip}</Box>}
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
              époque {currentEpoch}/{totalEpochs}
            </Typography>
          </Box>
        )}

        <CardContent sx={{ pt: 1, pb: "8px !important" }}>
          {loading && (
            <Box sx={{ display: "flex", gap: 1 }}>
              <CircularProgress size={16} />
              <Typography variant="caption" color="text.secondary">Chargement…</Typography>
            </Box>
          )}

          {!loading && models.length === 0 && !isTraining && (
            <Typography variant="body2" color="text.secondary">
              Entraîner le modèle depuis les Signatures.
            </Typography>
          )}

          {!loading && models.length > 0 && (
            <TableContainer>
              <Table size="small" sx={{ "& td, & th": { py: 0.5, px: 1, fontSize: "0.72rem" } }}>
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 600 }}>Modèle</TableCell>
                    <TableCell align="center" sx={{ fontWeight: 600 }}>Appareils</TableCell>
                    <TableCell align="center" sx={{ fontWeight: 600 }}>Sigs</TableCell>
                    <TableCell align="center" sx={{ fontWeight: 600 }}>val_loss</TableCell>
                    <TableCell align="center" sx={{ fontWeight: 600 }}>Époques</TableCell>
                    <TableCell align="center" sx={{ fontWeight: 600 }}>Entraîné</TableCell>
                    <TableCell />
                  </TableRow>
                </TableHead>
                <TableBody>
                  {models.map((model) => {
                    const ms = getMetricsSummary(model);
                    return (
                      <TableRow
                        key={model.id}
                        sx={{
                          bgcolor: model.is_champion ? "success.main" : "transparent",
                          "& td": { color: model.is_champion ? "success.contrastText" : "inherit" },
                          opacity: model.is_champion ? 1 : 0.75,
                        }}
                      >
                        <TableCell>
                          <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                            {model.is_champion && (
                              <Tooltip title="Champion — modèle utilisé pour la détection">
                                <EmojiEvents sx={{ fontSize: 14 }} />
                              </Tooltip>
                            )}
                            <Typography variant="caption" sx={{ fontFamily: "monospace", fontSize: "0.68rem" }}>
                              {model.model_name.replace("linkya_model_", "")}
                            </Typography>
                          </Box>
                        </TableCell>
                        <TableCell align="center">{model.num_classes ?? "—"}</TableCell>
                        <TableCell align="center">{model.num_signatures ?? "—"}</TableCell>
                        <TableCell align="center">{ms?.val_loss ?? "—"}</TableCell>
                        <TableCell align="center">{ms?.epochs ?? "—"}</TableCell>
                        <TableCell align="center">{formatHumanizedDate(model.training_date)}</TableCell>
                        <TableCell align="right">
                          {!model.is_champion && (
                            <Tooltip title="Promouvoir comme champion">
                              <Button
                                size="small"
                                variant="outlined"
                                color="warning"
                                sx={{ py: 0, px: 0.75, minWidth: 0, fontSize: "0.65rem", textTransform: "none" }}
                                onClick={() => setPromoteDialog({ open: true, model })}
                              >
                                Promouvoir
                              </Button>
                            </Tooltip>
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </CardContent>
      </Card>

      <Dialog
        open={promoteDialog.open}
        onClose={() => !promoting && setPromoteDialog({ open: false, model: null })}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>Promouvoir ce modèle ?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            <strong>{promoteDialog.model?.model_name}</strong> deviendra le champion.
            La détection utilisera ce modèle immédiatement.{" "}
            {champion && <>Le champion actuel (<strong>{champion.model_name}</strong>) sera rétrogradé.</>}
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPromoteDialog({ open: false, model: null })} disabled={promoting}>
            Annuler
          </Button>
          <Button
            onClick={handlePromote}
            variant="contained"
            color="warning"
            disabled={promoting}
            startIcon={promoting ? <CircularProgress size={16} /> : <EmojiEvents />}
          >
            {promoting ? "Promotion…" : "Promouvoir"}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}

export default ModelCard;
