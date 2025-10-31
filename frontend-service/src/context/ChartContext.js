import React, { createContext, useContext, useState } from 'react';

/**
 * Context pour partager l'état du graphique (période visible) entre composants
 */
const ChartContext = createContext();

export const ChartProvider = ({ children }) => {
  const [visibleTimeRange, setVisibleTimeRange] = useState(null);

  return (
    <ChartContext.Provider value={{ visibleTimeRange, setVisibleTimeRange }}>
      {children}
    </ChartContext.Provider>
  );
};

export const useChart = () => {
  const context = useContext(ChartContext);
  if (!context) {
    throw new Error('useChart must be used within a ChartProvider');
  }
  return context;
};
