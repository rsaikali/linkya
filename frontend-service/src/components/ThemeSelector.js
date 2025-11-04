import React, { useState } from 'react';
import { IconButton, Menu, MenuItem, Box, Tooltip } from '@mui/material';
import { useThemeContext } from '../context/ThemeContext';

const ThemeSelector = () => {
  const { currentTheme, changeTheme, availableThemes } = useThemeContext();
  const [anchorEl, setAnchorEl] = useState(null);
  const open = Boolean(anchorEl);

  const handleClick = (event) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleThemeChange = (themeName) => {
    changeTheme(themeName);
    handleClose();
  };

  const themeColors = {
    red: '#BD2A2E',
    darkBlue: '#001219',
    teal: '#005f73',
    turquoise: '#0a9396',
    mint: '#94d2bd',
    beige: '#e9d8a6',
    orange: '#ee9b00',
    darkOrange: '#ca6702',
    rust: '#bb3e03',
    crimson: '#ae2012',
    burgundy: '#9b2226',
  };

  const createThemeIcon = (color, isSelected) => (
    <Box
      sx={{
        width: 32,
        height: 32,
        borderRadius: '50%',
        backgroundColor: color,
        border: isSelected ? '3px solid white' : '2px solid rgba(255, 255, 255, 0.5)',
        boxShadow: isSelected ? '0 0 8px rgba(0, 0, 0, 0.3)' : 'none',
      }}
    />
  );

  return (
    <>
      <Tooltip title="Change theme">
        <IconButton
          onClick={handleClick}
          sx={{
            color: 'white',
            '&:hover': {
              backgroundColor: 'rgba(255, 255, 255, 0.1)',
            },
          }}
        >
          <span className="material-symbols-outlined">palette</span>
        </IconButton>
      </Tooltip>
      <Menu
        anchorEl={anchorEl}
        open={open}
        onClose={handleClose}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'right',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'right',
        }}
        PaperProps={{
          sx: {
            display: 'flex',
            flexDirection: 'row',
            flexWrap: 'wrap',
            padding: 1,
            maxWidth: 200,
          },
        }}
      >
        {availableThemes.map((themeName) => (
          <MenuItem
            key={themeName}
            onClick={() => handleThemeChange(themeName)}
            selected={currentTheme === themeName}
            sx={{
              padding: 0.5,
              minWidth: 'auto',
              justifyContent: 'center',
            }}
          >
            {createThemeIcon(themeColors[themeName], currentTheme === themeName)}
          </MenuItem>
        ))}
      </Menu>
    </>
  );
};

export default ThemeSelector;
