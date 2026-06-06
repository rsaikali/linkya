import { Check, Close, MoreVert, Search, SwapHoriz } from "@mui/icons-material";
import InsightsIcon from "@mui/icons-material/Insights";
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  IconButton,
  LinearProgress,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Skeleton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Toolbar,
  Tooltip,
  Typography,
} from "@mui/material";
import { useTheme } from "@mui/material/styles";
import { useEffect, useState } from "react";
import { useApplianceColors } from "../context/ApplianceColorsContext";
import { useData } from "../context/DataContext";
import { useNotification } from "../context/NotificationContext";
import api, { apiService } from "../services/api";
import websocket from "../services/sse";
import {
  formatDateTime,
  formatDurationMinutes,
  formatHumanizedDate,
  formatTimeOnly,
} from "../utils/dateUtils";
import MaterialIcon from "./common/MaterialIcon";

// Icône Google Material Symbols pour Delete
const DeleteIcon = () => (
  <MaterialIcon sx={{ fontSize: 20 }}>delete</MaterialIcon>
);

// Icône Google Material Symbols pour qualité de détection
const QualityIcon = ({ confidence }) => {
  const theme = useTheme();

  const getColor = () => {
    if (confidence < 0.6) return theme.palette.error.main;
    if (confidence < 0.8) return theme.palette.warning.main;
    return theme.palette.success.main;
  };

  return (
    <MaterialIcon sx={{ fontSize: 20, color: getColor() }}>
      psychology_alt
    </MaterialIcon>
  );
};

/**
 * Composant affichant les détections d'appareils récentes
 */
function DetectionsList() {
  const { visibleDetections, loading, errors, refreshDetections } = useData();
  const { ensureApplianceColors } = useApplianceColors();
  const { showNotification } = useNotification();
  const [deleteAllDialogOpen, setDeleteAllDialogOpen] = useState(false);
  const [deleteAllLoading, setDeleteAllLoading] = useState(false);
  const [detectLoading, setDetectLoading] = useState(false);
  const [isTraining, setIsTraining] = useState(false);
  const [hasModel, setHasModel] = useState(false);

  // Vérifier si un modèle existe
  useEffect(() => {
    const checkModel = async () => {
      try {
        const response = await api.get("/api/nilm/models");
        setHasModel(response.data.models.length > 0);
      } catch (error) {
        console.error("Erreur lors de la vérification du modèle:", error);
      }
    };
    checkModel();
  }, []);

  // Écouter les événements WebSocket d'entraînement
  useEffect(() => {
    const handleTrainingStart = () => {
      setIsTraining(true);
    };

    const handleTrainingComplete = () => {
      setIsTraining(false);
      // Recharger le statut du modèle
      setTimeout(async () => {
        try {
          const response = await api.get("/api/nilm/models");
          setHasModel(response.data.models.length > 0);
        } catch (error) {
          console.error("Erreur lors de la vérification du modèle:", error);
        }
      }, 1000);
    };

    const handleModelsDeleted = () => {
      setHasModel(false);
    };

    websocket.on("training_start", handleTrainingStart);
    websocket.on("training_complete", handleTrainingComplete);
    window.addEventListener("models-deleted", handleModelsDeleted);

    return () => {
      websocket.off("training_start", handleTrainingStart);
      websocket.off("training_complete", handleTrainingComplete);
      window.removeEventListener("models-deleted", handleModelsDeleted);
    };
  }, []);

  // Initialize colors/icons for all appliances when detections load
  useEffect(() => {
    if (visibleDetections.length > 0) {
      const applianceIds = [
        ...new Set(visibleDetections.map((d) => d.appliance_id)),
      ];
      ensureApplianceColors(applianceIds);
    }
  }, [visibleDetections, ensureApplianceColors]);

  // No need to fetch detections or setup WebSocket - DataContext handles it all
  const totalDetections = visibleDetections.length;
  const error = errors.detections;

  const handleValidate = async (detection) => {
    try {
      await apiService.validateDetection(detection.id);
      showNotification(`Détection validée: ${detection.name}`, "success");
      refreshDetections();
    } catch (err) {
      showNotification("Erreur lors de la validation", "error");
    }
  };

  const handleInvalidate = async (detection) => {
    try {
      await apiService.invalidateDetection(detection.id);
      showNotification(`Détection invalidée: ${detection.name}`, "info");
      refreshDetections();
    } catch (err) {
      showNotification("Erreur lors de l'invalidation", "error");
    }
  };

  const handleOpenDeleteAllDialog = () => {
    setDeleteAllDialogOpen(true);
  };

  const handleCloseDeleteAllDialog = () => {
    setDeleteAllDialogOpen(false);
  };

  const handleConfirmDeleteAll = async () => {
    setDeleteAllLoading(true);
    try {
      const response = await api.delete("/api/detections");
      showNotification(
        response.data.message || "Toutes les détections ont été supprimées",
        "success"
      );
      handleCloseDeleteAllDialog();
      // Rafraîchir la liste
      refreshDetections();
    } catch (error) {
      console.error("Erreur lors de la suppression des détections:", error);
      const errorMsg =
        error.response?.data?.detail ||
        "Erreur lors de la suppression des détections";
      showNotification(errorMsg, "error");
    } finally {
      setDeleteAllLoading(false);
    }
  };

  const handleDetect = async () => {
    setDetectLoading(true);
    try {
      const response = await api.post("/api/nilm/detect");
      showNotification(
        `Détection lancée (Task ID: ${response.data.task_id})`,
        "success"
      );
    } catch (error) {
      showNotification(
        `Erreur: ${error.response?.data?.detail || error.message}`,
        "error"
      );
    } finally {
      setDetectLoading(false);
    }
  };

  if (error) {
    return (
      <Card>
        <CardHeader
          title="Détections IA d'appareils"
          avatar={<InsightsIcon />}
        />
        <CardContent>
          <Alert severity="error">{error}</Alert>
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <Card sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
        <CardHeader
          title="Détections IA d'appareils"
          titleTypographyProps={{ variant: "h5" }}
          subheader={`${totalDetections} détection${
            totalDetections !== 1 ? "s" : ""
          } dans la période visible`}
          avatar={<InsightsIcon />}
        />

        {/* Toolbar avec actions */}
        <Toolbar
          variant="dense"
          sx={{
            px: 2,
            py: 1,
            minHeight: 48,
            bgcolor: "action.hover",
            borderTop: 1,
            borderBottom: 1,
            borderColor: "divider",
            gap: 1,
            justifyContent: "flex-start",
          }}
        >
          <Tooltip title="Lancer un job de détection d'appareils par le modèle IA.">
            <span>
              <Button
                variant="contained"
                size="small"
                color="success"
                startIcon={
                  detectLoading ? (
                    <CircularProgress size={16} color="inherit" />
                  ) : (
                    <Search />
                  )
                }
                onClick={handleDetect}
                disabled={detectLoading || !hasModel || isTraining}
                sx={{ textTransform: "none" }}
              >
                Détecter les appareils par l'IA
              </Button>
            </span>
          </Tooltip>

          <Box sx={{ flexGrow: 1 }} />

          <Tooltip title="Supprimer toutes les détections">
            <span>
              <Button
                variant="outlined"
                size="small"
                color="error"
                startIcon={
                  deleteAllLoading ? (
                    <CircularProgress size={16} color="inherit" />
                  ) : (
                    <DeleteIcon />
                  )
                }
                onClick={handleOpenDeleteAllDialog}
                disabled={deleteAllLoading || totalDetections === 0}
                sx={{ textTransform: "none" }}
              >
                {deleteAllLoading ? "Suppression..." : "Tout supprimer"}
              </Button>
            </span>
          </Tooltip>
        </Toolbar>

        {loading.detections && <LinearProgress sx={{ height: 2 }} />}

        <CardContent
          sx={{
            flexGrow: 1,
            overflow: "hidden",
            p: 0,
            display: "flex",
            flexDirection: "column",
          }}
        >
          {error && (
            <Box sx={{ p: 2 }}>
              <Alert severity="error">{error}</Alert>
            </Box>
          )}

          {loading.detections && visibleDetections.length === 0 && (
            <Box sx={{ p: 2 }}>
              <Skeleton
                variant="rectangular"
                height={60}
                sx={{ mb: 1, borderRadius: 1 }}
              />
              <Skeleton
                variant="rectangular"
                height={60}
                sx={{ mb: 1, borderRadius: 1 }}
              />
              <Skeleton
                variant="rectangular"
                height={60}
                sx={{ borderRadius: 1 }}
              />
            </Box>
          )}

          {!loading.detections && totalDetections === 0 && (
            <Box sx={{ p: 2 }}>
              <Typography color="textSecondary" align="center" variant="body2">
                Aucune détection
              </Typography>
            </Box>
          )}

          {totalDetections > 0 && (
            <>
              <TableContainer sx={{ flexGrow: 1, overflow: "auto" }}>
                <Table stickyHeader size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell sx={{ fontWeight: 600 }}>Appareil</TableCell>
                      <TableCell align="left" sx={{ fontWeight: 600 }}>
                        Détails
                      </TableCell>
                      <TableCell
                        align="center"
                        sx={{ width: "40px", p: 1 }}
                      ></TableCell>
                      <TableCell
                        align="right"
                        sx={{ width: "40px", p: 1 }}
                      ></TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {visibleDetections.map((detection) => (
                      <DetectionRow
                        key={detection.id}
                        detection={detection}
                        onValidate={handleValidate}
                        onInvalidate={handleInvalidate}
                      />
                    ))}
                    {loading.detections && (
                      <TableRow>
                        <TableCell colSpan={4} align="center" sx={{ py: 3 }}>
                          <CircularProgress size={32} />
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </TableContainer>
            </>
          )}
        </CardContent>
      </Card>

      {/* Dialog de confirmation de suppression de toutes les détections */}
      <Dialog
        open={deleteAllDialogOpen}
        onClose={handleCloseDeleteAllDialog}
        aria-labelledby="delete-all-dialog-title"
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle id="delete-all-dialog-title">
          Confirmer la suppression de toutes les détections
        </DialogTitle>
        <DialogContent>
          <DialogContentText>
            Êtes-vous sûr de vouloir supprimer{" "}
            <strong>
              toutes les {totalDetections} détection
              {totalDetections !== 1 ? "s" : ""}
            </strong>{" "}
            ?
            <br />
            <br />
            ⚠️ <strong>Attention :</strong> Cette action supprimera
            définitivement toutes les détections de la base de données.
            <br />
            <br />
            Les signatures négatives créées à partir de détections invalidées
            seront conservées.
            <br />
            <br />
            <strong>Cette action est irréversible.</strong>
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={handleCloseDeleteAllDialog}
            color="inherit"
            disabled={deleteAllLoading}
          >
            Annuler
          </Button>
          <Button
            onClick={handleConfirmDeleteAll}
            color="error"
            variant="contained"
            disabled={deleteAllLoading}
            startIcon={
              deleteAllLoading ? <CircularProgress size={20} /> : <DeleteIcon />
            }
          >
            {deleteAllLoading ? "Suppression..." : "Tout supprimer"}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}

/**
 * Ligne de tableau pour une détection
 */
function DetectionRow({ detection, onValidate, onInvalidate }) {
  const { getApplianceColor, getApplianceIcon } = useApplianceColors();
  const { refreshDetections, refreshSignatures } = useData();
  const { showNotification } = useNotification();
  const [anchorEl, setAnchorEl] = useState(null);
  const [reassignDialogOpen, setReassignDialogOpen] = useState(false);
  const [applianceName, setApplianceName] = useState("");
  const [applianceOptions, setApplianceOptions] = useState([]);
  const [reassignLoading, setReassignLoading] = useState(false);
  const open = Boolean(anchorEl);

  const startTime = new Date(detection.start_time);
  const endTime = new Date(detection.end_time);
  const durationSeconds = Math.round((endTime - startTime) / 1000);

  // Statut de validation
  const isValidated =
    detection.user_validated === true && detection.is_correct === true;
  const isInvalidated =
    detection.user_validated === true && detection.is_correct === false;

  const handleMenuClick = (event) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleValidateClick = () => {
    handleMenuClose();
    onValidate(detection);
  };

  const handleInvalidateClick = () => {
    handleMenuClose();
    onInvalidate(detection);
  };

  const handleReassignClick = () => {
    handleMenuClose();
    setReassignDialogOpen(true);
    loadAppliances();
  };

  const loadAppliances = async () => {
    try {
      const data = await apiService.getAllAppliances();
      const names = (data.appliances || []).map((a) => a.name);
      setApplianceOptions(names);
    } catch (err) {
      console.error("Erreur lors du chargement des appareils:", err);
    }
  };

  const handleReassignSubmit = async () => {
    if (!applianceName.trim()) {
      showNotification("Veuillez saisir le nom de l'appareil", "error");
      return;
    }

    setReassignLoading(true);
    try {
      await apiService.reassignDetection(detection.id, applianceName);
      showNotification(`Détection réassignée à ${applianceName}`, "success");
      setReassignDialogOpen(false);
      setApplianceName("");
      refreshDetections();
      refreshSignatures();
    } catch (err) {
      showNotification("Erreur lors de la réassignation", "error");
    } finally {
      setReassignLoading(false);
    }
  };

  const confidenceScore = detection.confidence_score || 0;

  return (
    <TableRow
      hover
      sx={{
        transition: "background-color 0.2s ease",
      }}
    >
      <TableCell
        sx={{
          fontWeight: 500,
          width: "40%",
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
          <MaterialIcon
            sx={{
              fontSize: "2rem",
              color: getApplianceColor(detection.appliance_id),
            }}
          >
            {getApplianceIcon(detection.appliance_id)}
          </MaterialIcon>
          {isValidated && (
            <Tooltip title="Détection validée comme correcte">
              <Check fontSize="small" color="success" />
            </Tooltip>
          )}
          {isInvalidated && (
            <Tooltip title="Détection marquée comme incorrecte">
              <Close fontSize="small" color="error" />
            </Tooltip>
          )}
          <Typography variant="body1" sx={{ fontWeight: 500 }}>
            {detection.name || "Inconnu"}
          </Typography>
        </Box>
      </TableCell>
      <TableCell
        sx={{
          fontSize: "small",
          verticalAlign: "middle",
          whiteSpace: "normal",
        }}
      >
        <Box sx={{ display: "flex", flexDirection: "column", gap: 0.25 }}>
          <Typography variant="body2" component="div">
            à <strong>{formatTimeOnly(startTime)}</strong> pendant{" "}
            <strong>{formatDurationMinutes(durationSeconds)}min</strong>
          </Typography>
          <Typography
            variant="caption"
            color="text.secondary"
            component="div"
            sx={{ fontWeight: 300, fontSize: "0.7rem" }}
          >
            {formatHumanizedDate(startTime)} ({formatDateTime(startTime)} -{" "}
            {formatTimeOnly(endTime)})
          </Typography>
        </Box>
      </TableCell>
      <TableCell align="center" sx={{ width: "40px", p: 1 }}>
        <Tooltip title={`Confiance: ${Math.round(confidenceScore * 100)}%`}>
          <Box
            sx={{
              display: "flex",
              justifyContent: "center",
              alignItems: "center",
            }}
          >
            <QualityIcon confidence={confidenceScore} />
          </Box>
        </Tooltip>
      </TableCell>
      <TableCell align="right" sx={{ width: "40px", p: 1 }}>
        <IconButton size="small" onClick={handleMenuClick} aria-label="actions">
          <MoreVert fontSize="small" />
        </IconButton>
        <Menu
          anchorEl={anchorEl}
          open={open}
          onClose={handleMenuClose}
          anchorOrigin={{
            vertical: "bottom",
            horizontal: "right",
          }}
          transformOrigin={{
            vertical: "top",
            horizontal: "right",
          }}
        >
          <MenuItem onClick={handleValidateClick} disabled={isValidated}>
            <ListItemIcon>
              <Check
                fontSize="small"
                color={isValidated ? "disabled" : "success"}
              />
            </ListItemIcon>
            <ListItemText>
              {isValidated ? "Déjà validée" : "Cette détection est correcte"}
            </ListItemText>
          </MenuItem>
          <MenuItem onClick={handleInvalidateClick} disabled={isInvalidated}>
            <ListItemIcon>
              <Close
                fontSize="small"
                color={isInvalidated ? "disabled" : "error"}
              />
            </ListItemIcon>
            <ListItemText>
              {isInvalidated
                ? "Déjà invalidée"
                : "Cette détection est incorrecte"}
            </ListItemText>
          </MenuItem>
          <MenuItem onClick={handleReassignClick}>
            <ListItemIcon>
              <SwapHoriz fontSize="small" color="primary" />
            </ListItemIcon>
            <ListItemText>Ce n'est pas le bon appareil</ListItemText>
          </MenuItem>
        </Menu>

        {/* Dialog pour réassigner la détection */}
        <Dialog
          open={reassignDialogOpen}
          onClose={() => setReassignDialogOpen(false)}
          maxWidth="sm"
          fullWidth
        >
          <DialogTitle>Réassigner la détection</DialogTitle>
          <DialogContent>
            <DialogContentText sx={{ mb: 2 }}>
              Cette détection était pour <strong>{detection.name}</strong>.
              <br />
              Quel est le bon appareil ?
            </DialogContentText>
            <Autocomplete
              freeSolo
              options={applianceOptions}
              value={applianceName}
              onChange={(event, newValue) => {
                setApplianceName(newValue || "");
              }}
              onInputChange={(event, newInputValue) => {
                setApplianceName(newInputValue);
              }}
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
              onClick={() => {
                setReassignDialogOpen(false);
                setApplianceName("");
              }}
              disabled={reassignLoading}
            >
              Annuler
            </Button>
            <Button
              onClick={handleReassignSubmit}
              variant="contained"
              color="primary"
              disabled={reassignLoading || !applianceName.trim()}
              startIcon={
                reassignLoading ? <CircularProgress size={20} /> : null
              }
            >
              {reassignLoading ? "Réassignation..." : "Réassigner"}
            </Button>
          </DialogActions>
        </Dialog>
      </TableCell>
    </TableRow>
  );
}

export default DetectionsList;
