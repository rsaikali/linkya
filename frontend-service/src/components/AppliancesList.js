import React, { useEffect, useState, useCallback } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  LinearProgress,
  Alert,
  Typography,
  IconButton,
  Tooltip,
  Box,
  TextField,
  Menu,
  Chip,
  Divider,
  Popover,
} from '@mui/material';
import { Edit, Close, Palette } from '@mui/icons-material';
import ElectricalServicesIcon from '@mui/icons-material/ElectricalServices';
import { SketchPicker } from 'react-color';
import api from '../services/api';
import { useApplianceColors } from '../context/ApplianceColorsContext';

// Palette de couleurs pour les appareils
const COLOR_PALETTE = [
  { name: 'Red', value: '#f94144' },
  { name: 'Orange Red', value: '#f3722c' },
  { name: 'Orange', value: '#f8961e' },
  { name: 'Light Orange', value: '#f9844a' },
  { name: 'Yellow', value: '#f9c74f' },
  { name: 'Green', value: '#90be6d' },
  { name: 'Teal Green', value: '#43aa8b' },
  { name: 'Teal', value: '#4d908e' },
  { name: 'Blue Grey', value: '#577590' },
  { name: 'Blue', value: '#277da1' },
];

function AppliancesList() {
  const { applianceColors, updateApplianceColor, getApplianceColor } = useApplianceColors();
  const [appliances, setAppliances] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [editingName, setEditingName] = useState('');
  const [colorMenuAnchor, setColorMenuAnchor] = useState(null);
  const [selectedApplianceId, setSelectedApplianceId] = useState(null);
  const [customColor, setCustomColor] = useState('');
  const [showColorPicker, setShowColorPicker] = useState(false);
  const [pickerAnchor, setPickerAnchor] = useState(null);

  const fetchAppliances = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await api.get('/api/appliances');
      const data = response.data;

      if (data && data.appliances && Array.isArray(data.appliances)) {
        setAppliances(data.appliances);
      } else {
        setAppliances([]);
      }
    } catch (err) {
      console.error('Error fetching appliances:', err);
      setError('Unable to load appliances');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAppliances();
  }, [fetchAppliances]);

  const handleEditClick = (appliance) => {
    setEditingId(appliance.id);
    setEditingName(appliance.name);
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditingName('');
  };

  const handleSaveEdit = async (applianceId) => {
    try {
      await api.patch(`/api/appliances/${applianceId}`, {
        name: editingName,
      });

      // Mettre à jour la liste locale
      setAppliances(
        appliances.map((a) =>
          a.id === applianceId ? { ...a, name: editingName } : a
        )
      );

      setEditingId(null);
      setEditingName('');
    } catch (err) {
      console.error('Error updating appliance:', err);
      setError('Unable to update appliance name');
    }
  };

  const handleColorClick = (event, applianceId) => {
    setColorMenuAnchor(event.currentTarget);
    setSelectedApplianceId(applianceId);
  };

  const handleColorClose = () => {
    setColorMenuAnchor(null);
    setSelectedApplianceId(null);
    setCustomColor('');
    setShowColorPicker(false);
    setPickerAnchor(null);
  };

  const handleColorSelect = (color) => {
    if (selectedApplianceId !== null) {
      updateApplianceColor(selectedApplianceId, color);
    }
    handleColorClose();
  };

  const handleCustomColorChange = (color) => {
    // color.hex contient la couleur au format #RRGGBB
    const hexColor = color.hex;
    setCustomColor(hexColor);
    
    if (selectedApplianceId !== null) {
      updateApplianceColor(selectedApplianceId, hexColor);
    }
  };

  const handlePickerClick = (event) => {
    setPickerAnchor(event.currentTarget);
    setShowColorPicker(true);
  };

  const handlePickerClose = () => {
    setShowColorPicker(false);
    setPickerAnchor(null);
  };

  if (loading) {
    return (
      <Card sx={{ display: 'flex', flexDirection: 'column', height: '100%', width: '100%' }}>
        <CardHeader 
          title="Mes appareils électriques"
          titleTypographyProps={{ variant: 'h5' }}
          avatar={<ElectricalServicesIcon />}
        />
        <CardContent sx={{ flexGrow: 1, overflow: 'auto' }}>
          <LinearProgress />
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card sx={{ display: 'flex', flexDirection: 'column', height: '100%', width: '100%' }}>
        <CardHeader 
          title="Mes appareils électriques"
          titleTypographyProps={{ variant: 'h5' }}
          avatar={<ElectricalServicesIcon />}
        />
        <CardContent sx={{ flexGrow: 1, overflow: 'auto' }}>
          <Alert severity="error">{error}</Alert>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card sx={{ display: 'flex', flexDirection: 'column', height: '100%', width: '100%' }}>
      <CardHeader
        title="Mes appareils électriques"
        titleTypographyProps={{ variant: 'h5' }}
        subheader={`${appliances.length} appareil${appliances.length !== 1 ? 's' : ''} disponibles`}
        avatar={<ElectricalServicesIcon />}
      />
      <CardContent sx={{ flexGrow: 1, overflow: 'auto', p: 0 }}>
        {appliances.length === 0 ? (
          <Box sx={{ p: 2 }}>
            <Typography variant="body2" color="text.secondary">
              No appliance configured yet
            </Typography>
          </Box>
        ) : (
          <TableContainer>
            <Table size="small" stickyHeader>
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 600 }}>Nom</TableCell>
                  <TableCell align="center" sx={{ fontWeight: 600 }}>
                    Signatures
                  </TableCell>
                  <TableCell align="center" sx={{ fontWeight: 600 }}>
                    Detections
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {appliances.map((appliance) => (
                  <TableRow
                    key={appliance.id}
                    hover
                    sx={{
                      '&:last-child td, &:last-child th': { border: 0 },
                    }}
                  >
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                        <Tooltip title="Change color">
                          <Box
                            onClick={(e) => handleColorClick(e, appliance.id)}
                            sx={{
                              width: 20,
                              height: 20,
                              borderRadius: '50%',
                              backgroundColor: getApplianceColor(appliance.id),
                              cursor: 'pointer',
                              flexShrink: 0,
                              transition: 'transform 0.2s',
                              '&:hover': {
                                transform: 'scale(1.2)',
                              },
                            }}
                          />
                        </Tooltip>
                        {editingId === appliance.id ? (
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexGrow: 1 }}>
                            <TextField
                              value={editingName}
                              onChange={(e) => setEditingName(e.target.value)}
                              size="small"
                              fullWidth
                              autoFocus
                              variant="standard"
                              onKeyPress={(e) => {
                                if (e.key === 'Enter') {
                                  handleSaveEdit(appliance.id);
                                } else if (e.key === 'Escape') {
                                  handleCancelEdit();
                                }
                              }}
                              onBlur={() => handleSaveEdit(appliance.id)}
                              sx={{
                                '& .MuiInput-underline:before': {
                                  borderBottomColor: 'primary.light',
                                },
                                '& .MuiInput-underline:after': {
                                  borderBottomColor: 'primary.main',
                                },
                              }}
                            />
                            <IconButton
                              size="small"
                              onClick={handleCancelEdit}
                              sx={{ 
                                opacity: 0.6,
                                '&:hover': { opacity: 1 }
                              }}
                            >
                              <Close fontSize="small" />
                            </IconButton>
                          </Box>
                        ) : (
                          <Box
                            sx={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 1,
                              cursor: 'pointer',
                              flexGrow: 1,
                              '&:hover .edit-icon': {
                                opacity: 1,
                              },
                            }}
                            onClick={() => handleEditClick(appliance)}
                          >
                            <Typography variant="body1" sx={{ fontWeight: 500, color: getApplianceColor(appliance.id) }}>
                              {appliance.name}
                            </Typography>
                            <Edit
                              className="edit-icon"
                              sx={{
                                fontSize: '1rem',
                                opacity: 0,
                                transition: 'opacity 0.2s',
                                color: 'text.secondary',
                              }}
                            />
                          </Box>
                        )}
                      </Box>
                    </TableCell>
                    <TableCell align="center">
                      <Chip
                        label={appliance.signature_count || 0}
                        size="small"
                        variant="outlined"
                      />
                    </TableCell>
                    <TableCell align="center">
                      <Chip
                        label={appliance.detection_count || 0}
                        size="small"
                        variant="outlined"
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </CardContent>

      {/* Menu de sélection de couleur */}
      <Menu
        anchorEl={colorMenuAnchor}
        open={Boolean(colorMenuAnchor)}
        onClose={handleColorClose}
        PaperProps={{
          sx: {
            mt: 1,
            minWidth: 240,
            borderRadius: 2,
          },
        }}
      >
        <Box sx={{ px: 2, py: 1.5 }}>
          <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
            PRESET COLORS
          </Typography>
        </Box>
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: 'repeat(5, 1fr)',
            gap: 1,
            px: 2,
            pb: 1.5,
          }}
        >
          {COLOR_PALETTE.map((color) => (
            <Tooltip key={color.value} title={color.name} placement="top">
              <Box
                onClick={() => handleColorSelect(color.value)}
                sx={{
                  width: 32,
                  height: 32,
                  borderRadius: '50%',
                  backgroundColor: color.value,
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  border: '2px solid',
                  borderColor:
                    applianceColors[selectedApplianceId] === color.value
                      ? 'primary.main'
                      : 'transparent',
                  boxShadow:
                    applianceColors[selectedApplianceId] === color.value
                      ? '0 0 0 2px rgba(189, 42, 46, 0.2)'
                      : 'none',
                  '&:hover': {
                    transform: 'scale(1.15)',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
                  },
                }}
              />
            </Tooltip>
          ))}
        </Box>
        <Divider sx={{ my: 1 }} />
        <Box sx={{ px: 2, py: 1.5 }}>
          <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600, mb: 1, display: 'block' }}>
            CUSTOM COLOR
          </Typography>
          <Box
            onClick={handlePickerClick}
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1.5,
              p: 1.5,
              borderRadius: 2,
              border: '1px solid',
              borderColor: 'divider',
              cursor: 'pointer',
              transition: 'all 0.2s',
              '&:hover': {
                borderColor: 'primary.main',
                backgroundColor: 'action.hover',
              },
            }}
          >
            <Box
              sx={{
                width: 28,
                height: 28,
                borderRadius: '50%',
                backgroundColor: customColor || applianceColors[selectedApplianceId] || '#e0e0e0',
                border: '2px solid',
                borderColor: 'divider',
                flexShrink: 0,
              }}
            />
            <Box sx={{ flexGrow: 1 }}>
              <Typography variant="body2" sx={{ fontWeight: 500 }}>
                Pick custom color
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {customColor || applianceColors[selectedApplianceId] || 'Click to select'}
              </Typography>
            </Box>
            <Palette sx={{ color: 'text.secondary' }} />
          </Box>
        </Box>
      </Menu>

      {/* Color Picker Popover */}
      <Popover
        open={showColorPicker}
        anchorEl={pickerAnchor}
        onClose={handlePickerClose}
        anchorOrigin={{
          vertical: 'center',
          horizontal: 'right',
        }}
        transformOrigin={{
          vertical: 'center',
          horizontal: 'left',
        }}
        PaperProps={{
          sx: {
            ml: 1,
            boxShadow: 3,
          },
        }}
      >
        <SketchPicker
          color={customColor || applianceColors[selectedApplianceId] || '#f94144'}
          onChange={handleCustomColorChange}
          disableAlpha={false}
          presetColors={COLOR_PALETTE.map(c => c.value)}
        />
      </Popover>
    </Card>
  );
}

export default AppliancesList;
