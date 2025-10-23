import React from 'react';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { Container, Box, Typography, AppBar, Toolbar } from '@mui/material';
import { ElectricBolt } from '@mui/icons-material';
import theme from './theme';
import LatestConsumption from './components/LatestConsumption';
import ConsumptionChart from './components/ConsumptionChart';
import AppliancesList from './components/AppliancesList';
import NilmTraining from './components/NilmTraining';
import DetectionsList from './components/DetectionsList';

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ flexGrow: 1 }}>
        <AppBar position="static">
          <Toolbar>
            <ElectricBolt sx={{ mr: 2 }} />
            <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
              Nilmia - Monitoring Linky & NILM
            </Typography>
          </Toolbar>
        </AppBar>

        <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            <LatestConsumption />
            <ConsumptionChart />
            <DetectionsList />
            <AppliancesList />
            <NilmTraining />
          </Box>
        </Container>

        <Box
          component="footer"
          sx={{
            py: 3,
            px: 2,
            mt: 'auto',
            backgroundColor: 'background.paper',
            textAlign: 'center',
          }}
        >
          <Typography variant="body2" color="text.secondary">
            Nilmia © {new Date().getFullYear()} - Plateforme de monitoring intelligent
          </Typography>
        </Box>
      </Box>
    </ThemeProvider>
  );
}

export default App;
