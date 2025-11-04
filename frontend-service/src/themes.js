import { createTheme } from '@mui/material/styles';

// Base theme configuration (shared by all themes)
const baseThemeConfig = {
  palette: {
    primary: {
      main: '#BD2A2E',
      light: '#d14448',
      dark: '#8a1f21',
      contrastText: '#fff',
    },
    secondary: {
      main: '#486966',
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
      default: '#ebebebff',
      paper: '#fff',
    },
    text: {
      primary: '#3B3936',
      secondary: '#889C9B',
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
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 600,
        },
      },
    },
  },
};

// Helper function to create a theme with custom header color
const createCustomTheme = (name, headerColor) => {
  return createTheme({
    ...baseThemeConfig,
    name,
    components: {
      ...baseThemeConfig.components,
      MuiCardHeader: {
        styleOverrides: {
          root: {
            backgroundColor: headerColor,
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
      MuiAppBar: {
        styleOverrides: {
          root: {
            backgroundColor: headerColor,
          },
        },
      },
    },
  });
};

// Theme definitions with different header colors from the palette
export const redTheme = createCustomTheme('Red', '#BD2A2E');
export const darkBlueTheme = createCustomTheme('Dark Blue', '#001219');
export const tealTheme = createCustomTheme('Teal', '#005f73');
export const turquoiseTheme = createCustomTheme('Turquoise', '#0a9396');
export const mintTheme = createCustomTheme('Mint', '#94d2bd');
export const beigeTheme = createCustomTheme('Beige', '#e9d8a6');
export const orangeTheme = createCustomTheme('Orange', '#ee9b00');
export const darkOrangeTheme = createCustomTheme('Dark Orange', '#ca6702');
export const rustTheme = createCustomTheme('Rust', '#bb3e03');
export const crimsonTheme = createCustomTheme('Crimson', '#ae2012');
export const burgundyTheme = createCustomTheme('Burgundy', '#9b2226');

export const themes = {
  red: redTheme,
  darkBlue: darkBlueTheme,
  teal: tealTheme,
  turquoise: turquoiseTheme,
  mint: mintTheme,
  beige: beigeTheme,
  orange: orangeTheme,
  darkOrange: darkOrangeTheme,
  rust: rustTheme,
  crimson: crimsonTheme,
  burgundy: burgundyTheme,
};

export default redTheme;
