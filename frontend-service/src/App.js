import React from 'react';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { Container, Box, Typography, AppBar, Toolbar } from '@mui/material';
import { ElectricBolt } from '@mui/icons-material';
import theme from './theme';
import CurrentModel from './components/CurrentModel';
import LatestConsumption from './components/LatestConsumption';
import ConsumptionChart from './components/ConsumptionChart';
import DetectionsList from './components/DetectionsList';
import SignaturesList from './components/SignaturesList';

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ flexGrow: 1 }}>
        <AppBar position="static">
          <Toolbar>
            <ElectricBolt sx={{ mr: 2 }} />
            <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
              Linkya - Monitoring Linky & NILM
            </Typography>
          </Toolbar>
        </AppBar>

        <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            <CurrentModel />
            <LatestConsumption />
            <ConsumptionChart />
            <DetectionsList />
            <SignaturesList />
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
            Linkya © {new Date().getFullYear()} - Plateforme de monitoring intelligent
          </Typography>
        </Box>
      </Box>
    </ThemeProvider>
  );
}

export default App;
