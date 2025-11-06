import React, { createContext, useContext, useState, useCallback } from 'react';
import { Snackbar, Alert } from '@mui/material';

/**
 * Context pour gérer les notifications globales de l'application
 * Utilise Snackbar + Alert de Material-UI pour un rendu moderne
 */
const NotificationContext = createContext();

export const NotificationProvider = ({ children }) => {
  const [notifications, setNotifications] = useState([]);

  /**
   * Affiche une notification
   * @param {string} message - Le message à afficher
   * @param {string} severity - Le type de notification: 'success', 'error', 'warning', 'info'
   * @param {number} duration - Durée en ms avant fermeture auto (défaut: 6000)
   */
  const showNotification = useCallback((message, severity = 'info', duration = 6000) => {
    const id = Date.now();
    setNotifications(prev => [...prev, { id, message, severity, duration }]);
  }, []);

  const handleClose = useCallback((id) => {
    setNotifications(prev => prev.filter(notif => notif.id !== id));
  }, []);

  return (
    <NotificationContext.Provider value={{ showNotification }}>
      {children}
      {notifications.map((notification, index) => (
        <Snackbar
          key={notification.id}
          open={true}
          autoHideDuration={notification.duration}
          onClose={() => handleClose(notification.id)}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
          sx={{
            bottom: { xs: 8, sm: 24 + (index * 70) },
          }}
        >
          <Alert
            onClose={() => handleClose(notification.id)}
            severity={notification.severity}
            variant="filled"
            sx={{ width: '100%', minWidth: 300 }}
          >
            {notification.message}
          </Alert>
        </Snackbar>
      ))}
    </NotificationContext.Provider>
  );
};

export const useNotification = () => {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error('useNotification must be used within NotificationProvider');
  }
  return context;
};

export default NotificationContext;
