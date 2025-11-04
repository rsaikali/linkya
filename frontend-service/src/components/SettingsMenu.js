import React, { useState } from 'react';
import {
  IconButton,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Dialog,
  DialogTitle,
  DialogContent,
  Box,
  Typography,
  Tooltip,
  Divider,
  Grid,
  Paper,
  TextField,
  DialogActions,
  Button,
} from '@mui/material';
import { Settings as SettingsIcon, Palette, Check, ColorLens } from '@mui/icons-material';
import { useThemeContext } from '../context/ThemeContext';

const SettingsMenu = () => {
  const { currentTheme, customColor, changeTheme, setCustomThemeColor } = useThemeContext();
  const [anchorEl, setAnchorEl] = useState(null);
  const [themeDialogOpen, setThemeDialogOpen] = useState(false);
  const [colorPickerValue, setColorPickerValue] = useState(customColor || '#582f0e');
  const open = Boolean(anchorEl);

  const handleClick = (event) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleThemeMenuClick = () => {
    setThemeDialogOpen(true);
    handleClose();
  };

  const handleThemeDialogClose = () => {
    setThemeDialogOpen(false);
  };

  const handleThemeChange = (themeName) => {
    changeTheme(themeName);
  };

  const handleColorPickerChange = (event) => {
    const newColor = event.target.value;
    setColorPickerValue(newColor);
    setCustomThemeColor(newColor);
  };

  const themeColors = {
    darkBrown: '#582f0e',
    brown: '#7f4f24',
    lightBrown: '#936639',
    sand: '#a68a64',
    khaki: '#b6ad90',
    sage: '#c2c5aa',
    oliveGreen: '#a4ac86',
    fern: '#656d4a',
    forest: '#414833',
    darkForest: '#333d29',
  };

  const themeLabels = {
    darkBrown: 'Dark Brown',
    brown: 'Brown',
    lightBrown: 'Light Brown',
    sand: 'Sand',
    khaki: 'Khaki',
    sage: 'Sage',
    oliveGreen: 'Olive Green',
    fern: 'Fern',
    forest: 'Forest',
    darkForest: 'Dark Forest',
  };

  const presetThemes = Object.keys(themeColors);

  const isLightColor = (color) => {
    const hex = color.replace('#', '');
    const r = parseInt(hex.substr(0, 2), 16);
    const g = parseInt(hex.substr(2, 2), 16);
    const b = parseInt(hex.substr(4, 2), 16);
    const brightness = (r * 299 + g * 587 + b * 114) / 1000;
    return brightness > 180;
  };

  const displayedColor = currentTheme === 'custom' && customColor ? customColor : themeColors[currentTheme];

  return (
    <>
      <Tooltip title="Settings">
        <IconButton
          onClick={handleClick}
          sx={{
            color: 'white',
            '&:hover': {
              backgroundColor: 'rgba(255, 255, 255, 0.1)',
            },
          }}
        >
          <SettingsIcon />
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
            minWidth: 200,
          },
        }}
      >
        <MenuItem onClick={handleThemeMenuClick}>
          <ListItemIcon>
            <Palette fontSize="small" />
          </ListItemIcon>
          <ListItemText>Theme</ListItemText>
        </MenuItem>
      </Menu>

      <Dialog
        open={themeDialogOpen}
        onClose={handleThemeDialogClose}
        maxWidth="sm"
        fullWidth
        PaperProps={{
          sx: {
            borderRadius: 2,
          },
        }}
      >
        <DialogTitle sx={{ pb: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Palette />
            <Typography variant="h6">Choose Theme</Typography>
          </Box>
        </DialogTitle>
        <Divider />

        <DialogContent sx={{ pt: 3, pb: 3 }}>
          {/* Preset Themes */}
          <Typography variant="subtitle2" sx={{ mb: 2, fontWeight: 600 }}>
            Preset Colors
          </Typography>
          <Grid container spacing={1.5} sx={{ mb: 4 }}>
            {presetThemes.map((themeName) => {
              const color = themeColors[themeName];
              const isLight = isLightColor(color);
              const isSelected = currentTheme === themeName;

              return (
                <Grid item xs={4} sm={3} key={themeName}>
                  <Tooltip title={themeLabels[themeName]} placement="top">
                    <Paper
                      onClick={() => handleThemeChange(themeName)}
                      elevation={isSelected ? 8 : 2}
                      sx={{
                        position: 'relative',
                        backgroundColor: color,
                        height: 70,
                        cursor: 'pointer',
                        transition: 'all 0.2s ease-in-out',
                        border: isSelected ? '3px solid' : '2px solid transparent',
                        borderColor: isSelected ? 'primary.main' : 'transparent',
                        '&:hover': {
                          transform: 'scale(1.05)',
                          elevation: 4,
                          border: '2px solid',
                          borderColor: 'primary.light',
                        },
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        borderRadius: 1.5,
                      }}
                    >
                      {isSelected && (
                        <Box
                          sx={{
                            position: 'absolute',
                            top: 4,
                            right: 4,
                            backgroundColor: isLight ? 'rgba(0,0,0,0.7)' : 'rgba(255,255,255,0.9)',
                            borderRadius: '50%',
                            width: 24,
                            height: 24,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                          }}
                        >
                          <Check
                            sx={{
                              fontSize: 16,
                              color: isLight ? 'white' : 'black',
                            }}
                          />
                        </Box>
                      )}
                      <Typography
                        variant="caption"
                        sx={{
                          position: 'absolute',
                          bottom: 4,
                          left: 0,
                          right: 0,
                          textAlign: 'center',
                          color: isLight ? 'rgba(0,0,0,0.7)' : 'rgba(255,255,255,0.9)',
                          fontSize: '0.65rem',
                          fontWeight: 600,
                          textShadow: isLight
                            ? '0 1px 2px rgba(255,255,255,0.8)'
                            : '0 1px 2px rgba(0,0,0,0.8)',
                          px: 0.5,
                        }}
                      >
                        {themeLabels[themeName]}
                      </Typography>
                    </Paper>
                  </Tooltip>
                </Grid>
              );
            })}
          </Grid>

          <Divider sx={{ my: 2 }} />

          {/* Custom Color Picker */}
          <Typography variant="subtitle2" sx={{ mb: 2, fontWeight: 600 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <ColorLens fontSize="small" />
              Custom Color
            </Box>
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
            <TextField
              type="color"
              value={colorPickerValue}
              onChange={handleColorPickerChange}
              sx={{
                width: 80,
                '& input': {
                  height: 60,
                  cursor: 'pointer',
                },
              }}
            />
            <Box sx={{ flex: 1 }}>
              <TextField
                fullWidth
                value={colorPickerValue}
                onChange={(e) => {
                  const value = e.target.value;
                  if (/^#[0-9A-Fa-f]{0,6}$/.test(value)) {
                    setColorPickerValue(value);
                    if (value.length === 7) {
                      setCustomThemeColor(value);
                    }
                  }
                }}
                label="Hex Color"
                placeholder="#582f0e"
                size="small"
                helperText="Enter a hex color code"
              />
            </Box>
          </Box>
        </DialogContent>

        <Divider />
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flex: 1 }}>
            <Box
              sx={{
                width: 24,
                height: 24,
                borderRadius: '50%',
                backgroundColor: displayedColor,
                border: '2px solid',
                borderColor: 'divider',
              }}
            />
            <Typography variant="body2" color="text.secondary">
              Current: {currentTheme === 'custom' ? 'Custom' : themeLabels[currentTheme]}
            </Typography>
          </Box>
          <Button onClick={handleThemeDialogClose}>Close</Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

export default SettingsMenu;
