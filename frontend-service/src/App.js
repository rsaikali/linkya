import React from 'react';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { Box, Typography, Grid } from '@mui/material';
import Header from './components/Header';
import ChartsContainer from './components/ChartsContainer';
import DetectionsList from './components/DetectionsList';
import SignaturesList from './components/SignaturesList';
import AppliancesList from './components/AppliancesList';
import { DataProvider } from './context/DataContext';
import { ApplianceColorsProvider } from './context/ApplianceColorsContext';
import { ThemeContextProvider, useThemeContext } from './context/ThemeContext';

function AppContent() {
  const { theme } = useThemeContext();
  
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <ApplianceColorsProvider>
        <DataProvider>
          <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
            <Header />

        <Box sx={{ px: 3, py: 3, flexGrow: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <Grid container spacing={2} sx={{ flexGrow: 1, height: 0 }}>
            {/* Colonne 1 - Appareils & Signatures (3/12) */}
            <Grid item xs={12} lg={3} sx={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 2 }}>
              <Box sx={{ flex: '0 0 auto', minHeight: 0, maxHeight: '40%', display: 'flex', width: '100%' }}>
                <AppliancesList />
              </Box>
              <Box sx={{ flex: '1 1 auto', minHeight: 0, display: 'flex', width: '100%' }}>
                <SignaturesList />
              </Box>
            </Grid>

            {/* Colonne 2 - Graphique (6/12) */}
            <Grid item xs={12} lg={6} sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
              <ChartsContainer />
            </Grid>

            {/* Colonne 3 - Détections (3/12) */}
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
        </DataProvider>
      </ApplianceColorsProvider>
    </ThemeProvider>
  );
}

function App() {
  return (
    <ThemeContextProvider>
      <AppContent />
    </ThemeContextProvider>
  );
}

export default App;
