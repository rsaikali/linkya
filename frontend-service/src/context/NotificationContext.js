import React, { createContext, useContext, useState, useCallback } from 'react';
import { Snackbar, Alert } from '@mui/material';

/**
 * Context to manage global app notifications
 * Uses Material-UI Snackbar + Alert for a modern look
 */
const NotificationContext = createContext();

export const NotificationProvider = ({ children }) => {
  const [notifications, setNotifications] = useState([]);

  /**
   * Show a notification
   * @param {string} message - The message to display
   * @param {string} severity - Notification type: 'success', 'error', 'warning', 'info'
   * @param {number} duration - Duration in ms before auto-close (default: 6000)
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
