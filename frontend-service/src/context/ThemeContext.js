import React, { createContext, useContext, useState, useEffect } from 'react';
import { themes } from '../themes';
import { createTheme } from '@mui/material/styles';

const ThemeContext = createContext();

export const useThemeContext = () => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useThemeContext must be used within a ThemeProvider');
  }
  return context;
};

// Helper function to convert hex to rgba
const hexToRgba = (hex, alpha) => {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
};

// Create custom theme from color
const createCustomColorTheme = (color) => {
  const baseTheme = themes.darkBrown; // Use first theme as base
  
  return createTheme({
    ...baseTheme,
    name: 'Custom',
    palette: {
      ...baseTheme.palette,
      chart: {
        ...baseTheme.palette.chart,
        consumption: {
          main: color,
          background: hexToRgba(color, 0.31),
        },
      },
    },
    components: {
      ...baseTheme.components,
      MuiCardHeader: {
        styleOverrides: {
          ...baseTheme.components.MuiCardHeader.styleOverrides,
          root: {
            ...baseTheme.components.MuiCardHeader.styleOverrides.root,
            backgroundColor: color,
          },
        },
      },
      MuiAppBar: {
        styleOverrides: {
          root: {
            backgroundColor: color,
          },
        },
      },
    },
  });
};

export const ThemeContextProvider = ({ children }) => {
  const [currentTheme, setCurrentTheme] = useState(() => {
    const savedTheme = localStorage.getItem('selectedTheme');
    if (savedTheme && (themes[savedTheme] || savedTheme === 'custom')) {
      return savedTheme;
    }
    return 'darkBrown';
  });
  
  const [customColor, setCustomColor] = useState(() => {
    return localStorage.getItem('customThemeColor') || null;
  });

  useEffect(() => {
    localStorage.setItem('selectedTheme', currentTheme);
  }, [currentTheme]);

  useEffect(() => {
    if (customColor) {
      localStorage.setItem('customThemeColor', customColor);
    } else {
      localStorage.removeItem('customThemeColor');
    }
  }, [customColor]);

  const changeTheme = (themeName) => {
    if (themes[themeName]) {
      setCurrentTheme(themeName);
      setCustomColor(null); // Clear custom color when selecting preset
    }
  };

  const setCustomThemeColor = (color) => {
    setCustomColor(color);
    setCurrentTheme('custom');
  };

  // Determine active theme
  let activeTheme;
  if (currentTheme === 'custom' && customColor) {
    activeTheme = createCustomColorTheme(customColor);
  } else {
    activeTheme = themes[currentTheme] || themes.darkBrown;
  }

  const value = {
    currentTheme,
    customColor,
    theme: activeTheme,
    changeTheme,
    setCustomThemeColor,
    availableThemes: Object.keys(themes),
  };

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
};
