import React, { createContext, useContext, useState, useEffect } from 'react';
import { themes } from '../themes';

const ThemeContext = createContext();

export const useThemeContext = () => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useThemeContext must be used within a ThemeProvider');
  }
  return context;
};

export const ThemeContextProvider = ({ children }) => {
  const [currentTheme, setCurrentTheme] = useState(() => {
    const savedTheme = localStorage.getItem('selectedTheme');
    // Validate saved theme exists, otherwise use default
    if (savedTheme && themes[savedTheme]) {
      return savedTheme;
    }
    return 'red';
  });

  useEffect(() => {
    localStorage.setItem('selectedTheme', currentTheme);
  }, [currentTheme]);

  const changeTheme = (themeName) => {
    if (themes[themeName]) {
      setCurrentTheme(themeName);
    }
  };

  // Ensure we always have a valid theme
  const activeTheme = themes[currentTheme] || themes.red;

  const value = {
    currentTheme,
    theme: activeTheme,
    changeTheme,
    availableThemes: Object.keys(themes),
  };

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
};
