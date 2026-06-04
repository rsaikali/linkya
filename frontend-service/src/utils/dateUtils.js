import { formatDistanceToNow, format } from 'date-fns';
import { fr } from 'date-fns/locale';

/**
 * Format a date string to a humanized relative time (e.g., "il y a 2 heures")
 * @param {string|Date} dateString - ISO date string or Date object
 * @returns {string} Humanized date string in French
 */
export const formatHumanizedDate = (dateString) => {
  if (!dateString) {
    return 'N/A';
  }

  try {
    const date = new Date(dateString);
    
    if (isNaN(date.getTime())) {
      console.error('Invalid date:', dateString);
      return 'N/A';
    }

    return formatDistanceToNow(date, { 
      addSuffix: true, 
      locale: fr 
    });
  } catch (error) {
    console.error('Error formatting humanized date:', error);
    return 'N/A';
  }
};

/**
 * Format a date to show date and time (e.g., "15 janv. 14:30")
 * @param {string|Date} dateString - ISO date string or Date object
 * @returns {string} Formatted date and time string
 */
export const formatDateTime = (dateString) => {
  if (!dateString) return 'N/A';
  
  try {
    const date = new Date(dateString);
    
    if (isNaN(date.getTime())) {
      return 'N/A';
    }
    
    return format(date, 'd MMM HH:mm', { locale: fr });
  } catch (error) {
    console.error('Error formatting date time:', error);
    return 'N/A';
  }
};

/**
 * Format a date to show only time (e.g., "14:30")
 * @param {string|Date} dateString - ISO date string or Date object
 * @returns {string} Formatted time string
 */
export const formatTimeOnly = (dateString) => {
  if (!dateString) return 'N/A';
  
  try {
    const date = new Date(dateString);
    
    if (isNaN(date.getTime())) {
      return 'N/A';
    }
    
    return format(date, 'HH:mm', { locale: fr });
  } catch (error) {
    console.error('Error formatting time:', error);
    return 'N/A';
  }
};

/**
 * Format a date to show time with seconds (e.g., "14:30:45")
 * @param {string|Date} dateString - ISO date string or Date object
 * @returns {string} Formatted time string with seconds
 */
export const formatTimeWithSeconds = (dateString) => {
  if (!dateString) return 'N/A';
  
  try {
    const date = new Date(dateString);
    
    if (isNaN(date.getTime())) {
      return 'N/A';
    }
    
    return format(date, 'HH:mm:ss', { locale: fr });
  } catch (error) {
    console.error('Error formatting time with seconds:', error);
    return 'N/A';
  }
};

/**
 * Format a date to show full date (e.g., "15/01/2024")
 * @param {string|Date} dateString - ISO date string or Date object
 * @returns {string} Formatted date string
 */
export const formatDateFull = (dateString) => {
  if (!dateString) return 'N/A';
  
  try {
    const date = new Date(dateString);
    
    if (isNaN(date.getTime())) {
      return 'N/A';
    }
    
    return format(date, 'dd/MM/yyyy', { locale: fr });
  } catch (error) {
    console.error('Error formatting date:', error);
    return 'N/A';
  }
};

/**
 * Format a date to show day name (e.g., "lundi")
 * @param {string|Date} dateString - ISO date string or Date object
 * @returns {string} Formatted day name in French
 */
export const formatDayName = (dateString) => {
  if (!dateString) return 'N/A';
  
  try {
    const date = new Date(dateString);
    
    if (isNaN(date.getTime())) {
      return 'N/A';
    }
    
    return format(date, 'EEEE', { locale: fr });
  } catch (error) {
    console.error('Error formatting day name:', error);
    return 'N/A';
  }
};

/**
 * Format a date to datetime-local input format (e.g., "2024-01-15T14:30")
 * @param {string|Date} dateString - ISO date string or Date object
 * @returns {string} Formatted datetime-local string
 */
export const formatDateTimeLocal = (dateString) => {
  if (!dateString) return '';
  
  try {
    const date = new Date(dateString);
    
    if (isNaN(date.getTime())) {
      return '';
    }
    
    return format(date, "yyyy-MM-dd'T'HH:mm");
  } catch (error) {
    console.error('Error formatting datetime-local:', error);
    return '';
  }
};

/**
 * Format a date to show full date with time for detailed views (e.g., "15/01/2024 14:30:45")
 * @param {string|Date} dateString - ISO date string or Date object
 * @returns {string} Formatted full date and time string
 */
export const formatFullDateTime = (dateString) => {
  if (!dateString) return 'N/A';
  
  try {
    const date = new Date(dateString);
    
    if (isNaN(date.getTime())) {
      return 'N/A';
    }
    
    return format(date, 'dd/MM/yyyy HH:mm:ss', { locale: fr });
  } catch (error) {
    console.error('Error formatting full date time:', error);
    return 'N/A';
  }
};

/**
 * Format a duration in seconds to a human-readable string (e.g., "2h 30min 15s")
 * @param {number} seconds - Duration in seconds
 * @returns {string} Formatted duration string
 */
export const formatDuration = (seconds) => {
  if (!seconds || seconds < 0) return 'N/A';
  
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  
  if (hours > 0) {
    return `${hours}h ${minutes}min ${secs}s`;
  } else if (minutes > 0) {
    return `${minutes}min ${secs}s`;
  } else {
    return `${secs}s`;
  }
};

/**
 * Format a duration in seconds to minutes
 * @param {number} seconds - Duration in seconds
 * @returns {number} Duration in minutes
 */
export const formatDurationMinutes = (seconds) => {
  if (!seconds) return 0;
  return Math.round(seconds / 60);
};
