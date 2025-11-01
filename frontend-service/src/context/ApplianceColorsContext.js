import React, { createContext, useContext, useState, useEffect } from 'react';

// Palette de couleurs par défaut
const COLOR_PALETTE = [
  '#f94144',
  '#f3722c',
  '#f8961e',
  '#f9844a',
  '#f9c74f',
  '#90be6d',
  '#43aa8b',
  '#4d908e',
  '#577590',
  '#277da1',
];

// Utilitaires pour gérer les cookies
const setCookie = (name, value, days = 365) => {
  const expires = new Date();
  expires.setTime(expires.getTime() + days * 24 * 60 * 60 * 1000);
  document.cookie = `${name}=${value};expires=${expires.toUTCString()};path=/`;
};

const getCookie = (name) => {
  const nameEQ = name + '=';
  const ca = document.cookie.split(';');
  for (let i = 0; i < ca.length; i++) {
    let c = ca[i];
    while (c.charAt(0) === ' ') c = c.substring(1, c.length);
    if (c.indexOf(nameEQ) === 0) return c.substring(nameEQ.length, c.length);
  }
  return null;
};

const getApplianceColorsFromCookie = () => {
  const colors = getCookie('applianceColors');
  return colors ? JSON.parse(colors) : {};
};

// Créer le Context
const ApplianceColorsContext = createContext();

// Provider du Context
export function ApplianceColorsProvider({ children }) {
  const [applianceColors, setApplianceColors] = useState({});

  // Charger les couleurs depuis les cookies au montage
  useEffect(() => {
    const savedColors = getApplianceColorsFromCookie();
    setApplianceColors(savedColors);
  }, []);

  // Fonction pour mettre à jour la couleur d'un appareil
  const updateApplianceColor = (applianceId, color) => {
    const newColors = {
      ...applianceColors,
      [applianceId]: color,
    };
    setApplianceColors(newColors);
    setCookie('applianceColors', JSON.stringify(newColors));
  };

  // Fonction pour obtenir la couleur d'un appareil
  const getApplianceColor = (applianceId) => {
    return applianceColors[applianceId] || COLOR_PALETTE[0];
  };

  const value = {
    applianceColors,
    updateApplianceColor,
    getApplianceColor,
  };

  return (
    <ApplianceColorsContext.Provider value={value}>
      {children}
    </ApplianceColorsContext.Provider>
  );
}

// Hook personnalisé pour utiliser le Context
export function useApplianceColors() {
  const context = useContext(ApplianceColorsContext);
  if (!context) {
    throw new Error('useApplianceColors must be used within an ApplianceColorsProvider');
  }
  return context;
}
