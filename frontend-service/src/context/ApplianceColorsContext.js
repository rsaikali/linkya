import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

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

// List of Material Symbols icons for household appliances
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

// Cookie helpers
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

// Function to get an unused random color
const getRandomUnusedColor = (usedColors) => {
  const availableColors = COLOR_PALETTE.filter(color => !usedColors.includes(color));

  if (availableColors.length > 0) {
    return availableColors[Math.floor(Math.random() * availableColors.length)];
  }

  // If all colors are used, return a random one
  return COLOR_PALETTE[Math.floor(Math.random() * COLOR_PALETTE.length)];
};

// Function to get a default icon
const getDefaultIcon = () => {
  return ICON_LIST[0].name; // 'power' by default
};

// Create the Context
const ApplianceColorsContext = createContext();

// Context Provider
export function ApplianceColorsProvider({ children }) {
  const [applianceColors, setApplianceColors] = useState({});
  const [applianceIcons, setApplianceIcons] = useState({});

  // Load colors and icons from cookies on mount
  useEffect(() => {
    const savedColors = getApplianceColorsFromCookie();
    const savedIcons = getApplianceIconsFromCookie();
    setApplianceColors(savedColors);
    setApplianceIcons(savedIcons);
  }, []);

  // Function to update an appliance's color
  const updateApplianceColor = (applianceId, color) => {
    const newColors = {
      ...applianceColors,
      [applianceId]: color,
    };
    setApplianceColors(newColors);
    setCookie('applianceColors', JSON.stringify(newColors));
  };

  // Function to update an appliance's icon
  const updateApplianceIcon = (applianceId, icon) => {
    const newIcons = {
      ...applianceIcons,
      [applianceId]: icon,
    };
    setApplianceIcons(newIcons);
    setCookie('applianceIcons', JSON.stringify(newIcons));
  };

  // Function to get an appliance's color (pure - does not modify state)
  const getApplianceColor = (applianceId) => {
    if (applianceColors[applianceId]) {
      return applianceColors[applianceId];
    }

    // If the appliance has no color, return a random one
    // (it will be saved by ensureApplianceColors if needed)
    const usedColors = Object.values(applianceColors);
    return getRandomUnusedColor(usedColors);
  };

  // Function to get an appliance's icon (pure - does not modify state)
  const getApplianceIcon = (applianceId) => {
    if (applianceIcons[applianceId]) {
      return applianceIcons[applianceId];
    }

    // If the appliance has no icon, return a default one
    return getDefaultIcon();
  };

  // Initialize missing colors/icons for new appliances
  const ensureApplianceColors = useCallback((applianceIds) => {
    let colorsUpdated = false;
    let iconsUpdated = false;
    let newColors = { ...applianceColors };
    let newIcons = { ...applianceIcons };

    applianceIds.forEach(id => {
      if (!newColors[id]) {
        const usedColors = Object.values(newColors);
        newColors[id] = getRandomUnusedColor(usedColors);
        colorsUpdated = true;
      }
      if (!newIcons[id]) {
        newIcons[id] = getDefaultIcon();
        iconsUpdated = true;
      }
    });

    if (colorsUpdated) {
      setApplianceColors(newColors);
      setCookie('applianceColors', JSON.stringify(newColors));
    }
    if (iconsUpdated) {
      setApplianceIcons(newIcons);
      setCookie('applianceIcons', JSON.stringify(newIcons));
    }
  }, [applianceColors, applianceIcons]);

  const value = {
    applianceColors,
    applianceIcons,
    updateApplianceColor,
    updateApplianceIcon,
    getApplianceColor,
    getApplianceIcon,
    ensureApplianceColors,
    availableIcons: ICON_LIST,
  };

  return (
    <ApplianceColorsContext.Provider value={value}>
      {children}
    </ApplianceColorsContext.Provider>
  );
}

// Custom hook to use the Context
export function useApplianceColors() {
  const context = useContext(ApplianceColorsContext);
  if (!context) {
    throw new Error('useApplianceColors must be used within an ApplianceColorsProvider');
  }
  return context;
}
