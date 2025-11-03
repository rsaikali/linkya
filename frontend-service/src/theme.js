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
    background: {
      default: '#ebebebff', // Big-Machine-3 (gris clair)
      paper: '#fff',
    },
    text: {
      primary: '#3B3936', // Big-Machine-2 (gris très foncé)
      secondary: '#889C9B', // Big-Machine-4 (gris moyen)
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
          borderRadius: '20px',
        },
      },
    },
    MuiCardHeader: {
      styleOverrides: {
        root: {
          backgroundColor: '#BD2A2E',
          color: '#fff',
          paddingTop: '10px',
          paddingBottom: '10px',
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
          fontWeight: 600,
        },
        subheader: {
          color: 'rgba(255, 255, 255, 0.8)',
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
