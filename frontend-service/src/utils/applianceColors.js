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
  '#fdcb6e', // Flat Flesh
  '#ffeaa7', // Sour Lemon
  '#dfe6e9', // City Lights
  '#b2bec3', // Amour
  '#636e72', // Grisaille
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
