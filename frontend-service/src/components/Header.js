import {
  AccessTime,
  Description,
  ElectricBolt,
  MenuBook,
  Thermostat,
} from "@mui/icons-material";
import {
  AppBar,
  Box,
  Chip,
  IconButton,
  Toolbar,
  Tooltip,
  Typography,
} from "@mui/material";
import { useEffect, useState } from "react";
import { apiService } from "../services/api";
import { formatFullDateTime, formatTimeWithSeconds } from "../utils/dateUtils";

const Header = () => {
  const [data, setData] = useState(null);

  useEffect(() => {
    const fetchLatestConsumption = async () => {
      try {
        const result = await apiService.getLatestConsumption();
        setData(result);
      } catch (err) {
        console.error("Error fetching consumption:", err);
      }
    };

    fetchLatestConsumption();
  }, []);

  return (
    <AppBar position="static" elevation={2}>
      <Toolbar sx={{ gap: 2, minHeight: "56px", py: 0.5 }}>
        {/* Logo and title */}
        <ElectricBolt sx={{ fontSize: 28 }} />
        <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
          Linkya - Monitoring Linky & NILM
        </Typography>

        {/* Real-time info */}
        {data && (
          <Box sx={{ display: "flex", gap: 2, alignItems: "center" }}>
            {/* Date and time */}
            <Tooltip
              title={`Dernière mise à jour: ${formatFullDateTime(data.time)}`}
            >
              <Chip
                icon={<AccessTime sx={{ fontSize: 19 }} />}
                label={formatTimeWithSeconds(data.time)}
                variant="filled"
                sx={{
                  bgcolor: (theme) => theme.palette.overlay.white[15],
                  color: "white",
                  fontWeight: "normal",
                  fontSize: "1rem",
                  fontFamily: '"Space Mono", monospace',
                  "& .MuiChip-icon": { color: "white" },
                }}
              />
            </Tooltip>

            {/* Power */}
            <Tooltip title="Puissance apparente">
              <Chip
                icon={<ElectricBolt sx={{ fontSize: 19 }} />}
                label={`${data.papp} W`}
                variant="filled"
                sx={{
                  bgcolor: (theme) => theme.palette.overlay.white[15],
                  color: "white",
                  fontWeight: "normal",
                  fontSize: "1rem",
                  fontFamily: '"Space Mono", monospace',
                  "& .MuiChip-icon": { color: "white" },
                }}
              />
            </Tooltip>

            {/* Temperature */}
            {data.temperature && (
              <Tooltip title="Température extérieure">
                <Chip
                  icon={<Thermostat sx={{ fontSize: 19 }} />}
                  label={`${data.temperature.toFixed(0)}°C`}
                  variant="filled"
                  sx={{
                    bgcolor: (theme) => theme.palette.overlay.white[15],
                    color: "white",
                    fontWeight: "normal",
                    fontSize: "1rem",
                    fontFamily: '"Space Mono", monospace',
                    "& .MuiChip-icon": { color: "white" },
                  }}
                />
              </Tooltip>
            )}

            {/* Links to documentation and monitoring tools */}
            <Box sx={{ display: "flex", gap: 0.5, ml: 1 }}>
              <Tooltip title="Swagger UI - Documentation API interactive">
                <IconButton
                  size="small"
                  href="/docs"
                  target="_blank"
                  rel="noopener noreferrer"
                  sx={{
                    color: "white",
                    bgcolor: (theme) => theme.palette.overlay.white[10],
                    "&:hover": {
                      bgcolor: (theme) => theme.palette.overlay.white[20],
                    },
                  }}
                >
                  <Description sx={{ fontSize: 20 }} />
                </IconButton>
              </Tooltip>

              <Tooltip title="ReDoc - Documentation API alternative">
                <IconButton
                  size="small"
                  href="/redoc"
                  target="_blank"
                  rel="noopener noreferrer"
                  sx={{
                    color: "white",
                    bgcolor: (theme) => theme.palette.overlay.white[10],
                    "&:hover": {
                      bgcolor: (theme) => theme.palette.overlay.white[20],
                    },
                  }}
                >
                  <MenuBook sx={{ fontSize: 20 }} />
                </IconButton>
              </Tooltip>
            </Box>
          </Box>
        )}
      </Toolbar>
    </AppBar>
  );
};

export default Header;
