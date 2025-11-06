import React from 'react';

/**
 * Material Symbols Icon component
 * Renders a Material Symbol icon with customizable styling
 * 
 * @param {string} children - The icon name (e.g., 'delete', 'edit', 'home')
 * @param {object} sx - MUI sx prop for styling (fontSize, color, etc.)
 * @param {string} className - Additional CSS class names
 * @param {object} style - Inline styles (use sx instead when possible)
 * @returns {JSX.Element} Material Symbol icon
 * 
 * @example
 * <MaterialIcon sx={{ fontSize: 20, color: 'primary.main' }}>delete</MaterialIcon>
 * <MaterialIcon>home</MaterialIcon>
 */
const MaterialIcon = ({ children, sx = {}, className = '', style = {}, ...props }) => {
  // Combine sx object with inline style for compatibility
  const combinedStyle = {
    fontSize: sx.fontSize || style.fontSize || 'inherit',
    color: sx.color || style.color || 'inherit',
    ...style,
    ...sx,
  };

  return (
    <span 
      className={`material-symbols-outlined ${className}`}
      style={combinedStyle}
      {...props}
    >
      {children}
    </span>
  );
};

export default MaterialIcon;
