// Palette de couleurs par défaut pour les appareils
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
export const getCookie = (name) => {
  const nameEQ = name + '=';
  const ca = document.cookie.split(';');
  for (let i = 0; i < ca.length; i++) {
    let c = ca[i];
    while (c.charAt(0) === ' ') c = c.substring(1, c.length);
    if (c.indexOf(nameEQ) === 0) return c.substring(nameEQ.length, c.length);
  }
  return null;
};

export const getApplianceColors = () => {
  const colors = getCookie('applianceColors');
  return colors ? JSON.parse(colors) : {};
};

export const getApplianceColor = (applianceId) => {
  const colors = getApplianceColors();
  return colors[applianceId] || COLOR_PALETTE[0];
};
