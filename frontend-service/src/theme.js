import { createTheme } from '@mui/material/styles';

// Palette de couleurs Nilmia
const theme = createTheme({
  palette: {
    primary: {
      main: '#BD2A2E', // Big-Machine-1 (rouge)
      light: '#d14448',
      dark: '#8a1f21',
      contrastText: '#fff',
    },
    secondary: {
      main: '#486966', // Big-Machine-5 (vert foncé)
      light: '#6a8b87',
      dark: '#324a48',
      contrastText: '#fff',
    },
    success: {
      main: '#4caf50',
      light: '#81c784',
      dark: '#388e3c',
      contrastText: '#fff',
    },
    warning: {
      main: '#ff9800',
      light: '#ffb74d',
      dark: '#f57c00',
      contrastText: '#fff',
    },
    error: {
      main: '#f44336',
      light: '#ef5350',
      dark: '#d32f2f',
      contrastText: '#fff',
    },
    background: {
      default: '#ebebebff', // Big-Machine-3 (gris clair)
      paper: '#fff',
    },
    text: {
      primary: '#3B3936', // Big-Machine-2 (gris très foncé)
      secondary: '#889C9B', // Big-Machine-4 (gris moyen)
      tertiary: '#666',
    },
    chart: {
      consumption: {
        main: '#0d6e00',
        background: 'rgba(189, 42, 46, 0.31)',
      },
      selection: {
        background: 'rgba(33, 150, 243, 0.2)',
        border: 'rgba(33, 150, 243, 0.6)',
      },
      negativeSignature: {
        main: '#ef5350',
        border: 'rgba(255, 0, 0, 0.6)',
      },
    },
    overlay: {
      white: {
        10: 'rgba(255, 255, 255, 0.1)',
        15: 'rgba(255, 255, 255, 0.15)',
        20: 'rgba(255, 255, 255, 0.2)',
        30: 'rgba(255, 255, 255, 0.3)',
        80: 'rgba(255, 255, 255, 0.8)',
        90: 'rgba(255, 255, 255, 0.9)',
        95: 'rgba(255, 255, 255, 0.95)',
      },
      black: {
        5: 'rgba(0, 0, 0, 0.05)',
        15: 'rgba(0, 0, 0, 0.15)',
        20: 'rgba(0, 0, 0, 0.2)',
      },
      primary: {
        20: 'rgba(189, 42, 46, 0.2)',
      },
    },
    utility: {
      defaultGray: '#e0e0e0',
      tooltip: {
        background: 'rgba(255, 255, 255, 0.95)',
        shadow: '0 2px 8px rgba(0, 0, 0, 0.15)',
      },
      shadow: {
        light: '0 2px 8px rgba(59, 57, 54, 0.1)',
        medium: '0 2px 8px rgba(0, 0, 0, 0.2)',
      },
    },
  },
  typography: {
    fontFamily: [
      'Montserrat',
      '-apple-system',
      'BlinkMacSystemFont',
      '"Segoe UI"',
      'Roboto',
      '"Helvetica Neue"',
      'Arial',
      'sans-serif',
    ].join(','),
    h1: {
      fontWeight: 600,
    },
    h2: {
      fontWeight: 600,
    },
    h3: {
      fontWeight: 600,
    },
  },
  components: {
    MuiCard: {
      styleOverrides: {
        root: {
          boxShadow: '0 2px 8px rgba(59, 57, 54, 0.1)',
          borderRadius: '10px',
        },
      },
    },
    MuiCardHeader: {
      styleOverrides: {
        root: {
          backgroundColor: '#BD2A2E',
          color: '#fff',
          paddingTop: '8px',
          paddingBottom: '8px',
          '& .MuiIconButton-root': {
            color: '#fff',
            '&:hover': {
              backgroundColor: 'rgba(255, 255, 255, 0.1)',
            },
            '& .MuiSvgIcon-root': {
              color: '#fff',
            },
          },
          '& .MuiSvgIcon-root': {
            color: '#fff',
          },
          '& .MuiSwitch-root': {
            '& .MuiSwitch-switchBase': {
              color: '#fff',
              '&.Mui-checked': {
                color: '#fff',
              },
            },
            '& .MuiSwitch-track': {
              backgroundColor: 'rgba(255, 255, 255, 0.3)',
            },
          },
          '& .MuiTypography-caption': {
            color: 'rgba(255, 255, 255, 0.9)',
          },
        },
        title: {
          color: '#fff',
          fontWeight: 500,
          fontSize: '1rem',
        },
        subheader: {
          color: 'rgba(255, 255, 255, 0.8)',
          fontSize: '0.875rem',
        },
        avatar: {
          '& .MuiSvgIcon-root': {
            color: '#fff',
          },
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 600,
        },
      },
    },
  },
});

export default theme;
