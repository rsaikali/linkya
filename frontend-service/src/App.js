import React from 'react';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { Box, Typography, Grid } from '@mui/material';
import theme from './theme';
import Header from './components/Header';
import CurrentModel from './components/CurrentModel';
import ConsumptionChart from './components/ConsumptionChart';
import DetectionsList from './components/DetectionsList';
import SignaturesList from './components/SignaturesList';
import { ChartProvider } from './context/ChartContext';

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <ChartProvider>
        <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
          <Header />

        <Box sx={{ px: 3, py: 3, flexGrow: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <Grid container spacing={2} sx={{ flexGrow: 1, height: 0 }}>
            {/* Colonne 1 - Signatures (3/12) */}
            <Grid item xs={12} lg={3} sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
              <SignaturesList />
            </Grid>

            {/* Colonnes 2 et 3 - Modèle et Graphique (6/12) */}
            <Grid item xs={12} lg={6} sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
              <Box sx={{ mb: 2 }}>
                <CurrentModel />
              </Box>
              <ConsumptionChart />
            </Grid>

            {/* Colonne 4 - Détections (3/12) */}
            <Grid item xs={12} lg={3} sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
              <DetectionsList />
            </Grid>
          </Grid>
        </Box>

        <Box
          component="footer"
          sx={{
            py: 2,
            px: 2,
            backgroundColor: 'background.paper',
            textAlign: 'center',
            borderTop: 1,
            borderColor: 'divider',
          }}
        >
          <Typography variant="body2" color="text.secondary">
            Linkya © {new Date().getFullYear()} - Plateforme de monitoring intelligent
          </Typography>
        </Box>
      </Box>
      </ChartProvider>
    </ThemeProvider>
  );
}

export default App;
