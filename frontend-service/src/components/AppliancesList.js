import React, { useState } from 'react';
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
  Chip,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Divider,
  Grid,
  Skeleton,
} from '@mui/material';
import { Edit, Close } from '@mui/icons-material';
import ElectricalServicesIcon from '@mui/icons-material/ElectricalServices';
import api from '../services/api';
import { useData } from '../context/DataContext';
import { useApplianceColors } from '../context/ApplianceColorsContext';

// Custom Material Symbols Icon component
const MaterialIcon = ({ children, sx = {} }) => (
  <span 
    className="material-symbols-outlined" 
    style={{
      fontSize: sx.fontSize || 'inherit',
      color: sx.color || 'inherit',
      ...sx,
    }}
  >
    {children}
  </span>
);

// French Palette from flatuicolors.com
const COLOR_PALETTE = [
  { name: 'Flat Flesh', value: '#fdcb6e' },
  { name: 'Melon Melody', value: '#e17055' },
  { name: 'Prunus Avium', value: '#d63031' },
  { name: 'Carmine Pink', value: '#e84393' },
  { name: 'Exodus Fruit', value: '#6c5ce7' },
  { name: 'Shy Moment', value: '#a29bfe' },
  { name: 'Pico-8 Pink', value: '#74b9ff' },
  { name: 'Electron Blue', value: '#0984e3' },
  { name: 'Mint Leaf', value: '#00b894' },
  { name: 'Robin\'s Egg Blue', value: '#00cec9' },
  { name: 'Light Greenish Blue', value: '#55efc4' },
  { name: 'Faded Poster', value: '#81ecec' },
  { name: 'Orange Ville', value: '#fab1a0' },
  { name: 'Chi-Gong', value: '#ff7675' },
  { name: 'Bloom', value: '#fd79a8' },
  { name: 'Sour Lemon', value: '#ffeaa7' },
  { name: 'City Lights', value: '#dfe6e9' },
  { name: 'Amour', value: '#b2bec3' },
  { name: 'Grisaille', value: '#636e72' },
  { name: 'Dark Slate', value: '#2d3436' },
];

function AppliancesList() {
  const { 
    updateApplianceColor, 
    updateApplianceIcon,
    getApplianceColor,
    getApplianceIcon,
    availableIcons,
  } = useApplianceColors();
  const { appliances, loading, errors, refreshAppliances } = useData();
  
  const [editingId, setEditingId] = useState(null);
  const [editingName, setEditingName] = useState('');
  
  // Menu state
  const [styleMenuAnchor, setStyleMenuAnchor] = useState(null);
  const [selectedApplianceId, setSelectedApplianceId] = useState(null);
  const [menuView, setMenuView] = useState('main'); // 'main', 'icon', 'color'

  // Use data from context
  const isLoading = loading.appliances;
  const error = errors.appliances;

  // No need to fetch appliances - DataContext handles it all

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

      // Refresh the list from context
      await refreshAppliances();

      setEditingId(null);
      setEditingName('');
    } catch (err) {
      console.error('Error updating appliance:', err);
      // Error is already in context, no need to set it locally
    }
  };

  const handleStyleClick = (event, applianceId) => {
    setStyleMenuAnchor(event.currentTarget);
    setSelectedApplianceId(applianceId);
    setMenuView('main');
  };

  const handleStyleMenuClose = () => {
    setStyleMenuAnchor(null);
    setSelectedApplianceId(null);
    setMenuView('main');
  };

  const handleIconSelect = (iconName) => {
    if (selectedApplianceId !== null) {
      updateApplianceIcon(selectedApplianceId, iconName);
    }
    handleStyleMenuClose();
  };

  const handleColorSelect = (color) => {
    if (selectedApplianceId !== null) {
      updateApplianceColor(selectedApplianceId, color);
    }
    handleStyleMenuClose();
  };

  return (
    <Card sx={{ display: 'flex', flexDirection: 'column', height: '100%', width: '100%' }}>
      <CardHeader
        title="Mes appareils électriques"
        titleTypographyProps={{ variant: 'h5' }}
        subheader={
          isLoading 
            ? 'Chargement...' 
            : `${appliances.length} appareil${appliances.length !== 1 ? 's' : ''} disponibles`
        }
        avatar={<ElectricalServicesIcon />}
      />
      
      {isLoading && <LinearProgress sx={{ height: 2 }} />}
      
      <CardContent sx={{ flexGrow: 1, overflow: 'auto', p: 0 }}>
        {error && (
          <Box sx={{ p: 2 }}>
            <Alert severity="error">{error}</Alert>
          </Box>
        )}

        {isLoading && (
          <Box sx={{ p: 2 }}>
            <Skeleton variant="rectangular" height={60} sx={{ mb: 1, borderRadius: 1 }} />
            <Skeleton variant="rectangular" height={60} sx={{ mb: 1, borderRadius: 1 }} />
            <Skeleton variant="rectangular" height={60} sx={{ borderRadius: 1 }} />
          </Box>
        )}

        {!isLoading && appliances.length === 0 && !error && (
          <Box sx={{ p: 2 }}>
            <Typography variant="body2" color="text.secondary">
              No appliance configured yet
            </Typography>
          </Box>
        )}

        {!isLoading && appliances.length > 0 && (
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
                        <Tooltip title="Customize style">
                          <Box
                            onClick={(e) => handleStyleClick(e, appliance.id)}
                            sx={{
                              display: 'flex',
                              alignItems: 'center',
                              cursor: 'pointer',
                              transition: 'transform 0.2s',
                              '&:hover': {
                                transform: 'scale(1.15)',
                              },
                            }}
                          >
                            <MaterialIcon sx={{ fontSize: '2rem', color: getApplianceColor(appliance.id) }}>
                              {getApplianceIcon(appliance.id)}
                            </MaterialIcon>
                          </Box>
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

      {/* Style Customization Menu */}
      <Menu
        anchorEl={styleMenuAnchor}
        open={Boolean(styleMenuAnchor)}
        onClose={handleStyleMenuClose}
        PaperProps={{
          sx: {
            mt: 1,
            maxWidth: 400,
            maxHeight: 500,
            borderRadius: 2,
          },
        }}
      >
        {menuView === 'main' && (
          <>
            <MenuItem onClick={() => setMenuView('icon')}>
              <ListItemIcon>
                <MaterialIcon sx={{ fontSize: '1.7rem' }}>
                  {getApplianceIcon(selectedApplianceId)}
                </MaterialIcon>
              </ListItemIcon>
              <ListItemText primary="Modifier l'icône" />
            </MenuItem>
            <MenuItem onClick={() => setMenuView('color')}>
              <ListItemIcon>
                <Box
                  sx={{
                    width: 26,
                    height: 26,
                    borderRadius: '50%',
                    backgroundColor: getApplianceColor(selectedApplianceId),
                    border: '2px solid',
                    borderColor: 'divider',
                  }}
                />
              </ListItemIcon>
              <ListItemText primary="Modifier la couleur" />
            </MenuItem>
          </>
        )}

        {menuView === 'icon' && (
          <>
            <MenuItem onClick={() => setMenuView('main')}>
              <ListItemText primary="← Back" />
            </MenuItem>
            <Divider />
            <Box sx={{ px: 2, pb: 2 }}>
              <Grid container spacing={1}>
                {availableIcons.map((icon) => (
                  <Grid item xs={2} key={icon.name}>
                    <Tooltip title={icon.label} placement="top">
                      <Box
                        onClick={() => handleIconSelect(icon.name)}
                        sx={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          p: 1.5,
                          cursor: 'pointer',
                          borderRadius: 2,
                          border: '2px solid',
                          borderColor: getApplianceIcon(selectedApplianceId) === icon.name 
                            ? getApplianceColor(selectedApplianceId) 
                            : 'transparent',
                          backgroundColor: getApplianceIcon(selectedApplianceId) === icon.name 
                            ? 'action.selected' 
                            : 'transparent',
                          transition: 'all 0.2s',
                          '&:hover': {
                            backgroundColor: 'action.hover',
                            borderColor: 'divider',
                          },
                        }}
                      >
                        <MaterialIcon
                          sx={{
                            fontSize: '2rem',
                            color: getApplianceIcon(selectedApplianceId) === icon.name 
                              ? getApplianceColor(selectedApplianceId) 
                              : 'text.secondary',
                          }}
                        >
                          {icon.name}
                        </MaterialIcon>
                      </Box>
                    </Tooltip>
                  </Grid>
                ))}
              </Grid>
            </Box>
          </>
        )}

        {menuView === 'color' && (
          <>
            <MenuItem onClick={() => setMenuView('main')}>
              <ListItemText primary="← Back" />
            </MenuItem>
            <Divider />
            <Box sx={{ px: 2, pb: 2 }}>
              <Grid container spacing={1.5}>
                {COLOR_PALETTE.map((color) => (
                  <Grid item xs={2} key={color.value}>
                    <Tooltip title={color.name} placement="top">
                      <Box
                        onClick={() => handleColorSelect(color.value)}
                        sx={{
                          aspectRatio: '1',
                          cursor: 'pointer',
                          borderRadius: 20,
                          backgroundColor: color.value,
                          border: '3px solid',
                          borderColor: getApplianceColor(selectedApplianceId) === color.value 
                            ? 'background.paper' 
                            : color.value,
                          boxShadow: getApplianceColor(selectedApplianceId) === color.value 
                            ? 3 
                            : 0,
                          transition: 'all 0.2s',
                          '&:hover': {
                            transform: 'scale(1.1)',
                            boxShadow: 2,
                          },
                        }}
                      />
                    </Tooltip>
                  </Grid>
                ))}
              </Grid>
            </Box>
          </>
        )}
      </Menu>
    </Card>
  );
}

export default AppliancesList;
