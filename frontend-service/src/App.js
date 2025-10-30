import React from 'react';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { Container, Box, Typography } from '@mui/material';
import theme from './theme';
import Header from './components/Header';
import CurrentModel from './components/CurrentModel';
import ConsumptionChart from './components/ConsumptionChart';
import DetectionsList from './components/DetectionsList';
import SignaturesList from './components/SignaturesList';

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ flexGrow: 1 }}>
        <Header />

        <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            <CurrentModel />
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
