import React, { createContext, useContext, useState, useEffect } from 'react';

// French Palette from flatuicolors.com
const COLOR_PALETTE = [
  '#fdcb6e', // Flat Flesh
  '#e17055', // Melon Melody
  '#d63031', // Prunus Avium
  '#e84393', // Carmine Pink
  '#6c5ce7', // Exodus Fruit
  '#a29bfe', // Shy Moment
  '#74b9ff', // Pico-8 Pink
  '#0984e3', // Electron Blue
  '#00b894', // Mint Leaf
  '#00cec9', // Robin's Egg Blue
  '#55efc4', // Light Greenish Blue
  '#81ecec', // Faded Poster
  '#fab1a0', // Orange Ville
  '#ff7675', // Chi-Gong
  '#fd79a8', // Bloom
  '#ffeaa7', // Sour Lemon
  '#dfe6e9', // City Lights
  '#b2bec3', // Amour
  '#636e72', // Grisaille
  '#2d3436', // Dark Slate
];

// Liste d'icônes Material Symbols pour appareils domestiques
const ICON_LIST = [
  { name: 'power', label: 'Generic appliance' },
  { name: 'electrical_services', label: 'Electrical device' },
  { name: 'microwave', label: 'Microwave' },
  { name: 'kitchen', label: 'Refrigerator' },
  { name: 'dishwasher', label: 'Dishwasher' },
  { name: 'local_laundry_service', label: 'Washing machine' },
  { name: 'oven', label: 'Oven' },
  { name: 'water_heater', label: 'Water heater' },
  { name: 'heat_pump', label: 'Heat pump' },
  { name: 'nest_farsight_heat', label: 'Heater' },
  { name: 'coffee_maker', label: 'Coffee maker' },
  { name: 'blender', label: 'Blender' },
  { name: 'tv', label: 'Television' },
  { name: 'speaker', label: 'Speaker' },
  { name: 'computer', label: 'Computer' },
  { name: 'light', label: 'Light' },
  { name: 'lightbulb', label: 'Bulb' },
  { name: 'ac_unit', label: 'Air conditioning' },
  { name: 'thermostat', label: 'Thermostat' },
  { name: 'iron', label: 'Iron' },
  { name: 'vacuum', label: 'Vacuum cleaner' },
  { name: 'phone_android', label: 'Phone charger' },
  { name: 'router', label: 'Router' },
  { name: 'print', label: 'Printer' },
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

const getApplianceIconsFromCookie = () => {
  const icons = getCookie('applianceIcons');
  return icons ? JSON.parse(icons) : {};
};

// Fonction pour obtenir une couleur aléatoire non utilisée
const getRandomUnusedColor = (usedColors) => {
  const availableColors = COLOR_PALETTE.filter(color => !usedColors.includes(color));
  
  if (availableColors.length > 0) {
    return availableColors[Math.floor(Math.random() * availableColors.length)];
  }
  
  // Si toutes les couleurs sont utilisées, retourner une couleur aléatoire
  return COLOR_PALETTE[Math.floor(Math.random() * COLOR_PALETTE.length)];
};

// Fonction pour obtenir une icône par défaut
const getDefaultIcon = () => {
  return ICON_LIST[0].name; // 'power' par défaut
};

// Créer le Context
const ApplianceColorsContext = createContext();

// Provider du Context
export function ApplianceColorsProvider({ children }) {
  const [applianceColors, setApplianceColors] = useState({});
  const [applianceIcons, setApplianceIcons] = useState({});

  // Charger les couleurs et icônes depuis les cookies au montage
  useEffect(() => {
    const savedColors = getApplianceColorsFromCookie();
    const savedIcons = getApplianceIconsFromCookie();
    setApplianceColors(savedColors);
    setApplianceIcons(savedIcons);
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

  // Fonction pour mettre à jour l'icône d'un appareil
  const updateApplianceIcon = (applianceId, icon) => {
    const newIcons = {
      ...applianceIcons,
      [applianceId]: icon,
    };
    setApplianceIcons(newIcons);
    setCookie('applianceIcons', JSON.stringify(newIcons));
  };

  // Fonction pour obtenir la couleur d'un appareil
  const getApplianceColor = (applianceId) => {
    if (applianceColors[applianceId]) {
      return applianceColors[applianceId];
    }
    
    // Si l'appareil n'a pas de couleur, en attribuer une aléatoire non utilisée
    const usedColors = Object.values(applianceColors);
    const newColor = getRandomUnusedColor(usedColors);
    
    // Sauvegarder la nouvelle couleur
    const newColors = {
      ...applianceColors,
      [applianceId]: newColor,
    };
    setApplianceColors(newColors);
    setCookie('applianceColors', JSON.stringify(newColors));
    
    return newColor;
  };

  // Fonction pour obtenir l'icône d'un appareil
  const getApplianceIcon = (applianceId) => {
    if (applianceIcons[applianceId]) {
      return applianceIcons[applianceId];
    }
    
    // Si l'appareil n'a pas d'icône, en attribuer une par défaut
    const defaultIcon = getDefaultIcon();
    
    // Sauvegarder l'icône par défaut
    const newIcons = {
      ...applianceIcons,
      [applianceId]: defaultIcon,
    };
    setApplianceIcons(newIcons);
    setCookie('applianceIcons', JSON.stringify(newIcons));
    
    return defaultIcon;
  };

  const value = {
    applianceColors,
    applianceIcons,
    updateApplianceColor,
    updateApplianceIcon,
    getApplianceColor,
    getApplianceIcon,
    availableIcons: ICON_LIST,
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
