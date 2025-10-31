import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  Typography,
  Box,
  CircularProgress,
  Alert,
  Switch,
  IconButton,
  Tooltip as MuiTooltip,
  LinearProgress,
} from '@mui/material';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
  Decimation,
} from 'chart.js';
import annotationPlugin from 'chartjs-plugin-annotation';
import zoomPlugin from 'chartjs-plugin-zoom';
import { Line } from 'react-chartjs-2';
import { ShowChart, ZoomOutMap } from '@mui/icons-material';
import { apiService } from '../services/api';
import { detectionsWS } from '../services/websocket';
import SignatureModal from './SignatureModal';
import { useChart } from '../context/ChartContext';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
  Decimation,
  annotationPlugin,
  zoomPlugin
);

const ConsumptionChart = () => {
  // Context pour partager la période visible
  const { setVisibleTimeRange } = useChart();
  
  // Données brutes complètes (chargées une seule fois)
  const [rawData, setRawData] = useState(null);
  // Détections
  const [detections, setDetections] = useState([]);
  // Signatures
  const [signatures, setSignatures] = useState([]);
  // États de chargement et erreur
  const [loading, setLoading] = useState(true);
  const [loadingProgress, setLoadingProgress] = useState(0);
  const [error, setError] = useState(null);
  // Modal de signature
  const [showSignatureModal, setShowSignatureModal] = useState(false);
  const [selectedRange, setSelectedRange] = useState(null);
  // Affichage des annotations: 'detections' ou 'signatures'
  const [annotationMode, setAnnotationMode] = useState('detections');
  // Référence au graphique
  const chartRef = useRef(null);
  const isInteractingRef = useRef(false);
  const interactionTimeoutRef = useRef(null);
  // Sélection par clic droit + drag
  const [isSelecting, setIsSelecting] = useState(false);
  const [selectionStart, setSelectionStart] = useState(null);
  const [selectionEnd, setSelectionEnd] = useState(null);
  const selectionRef = useRef({ isSelecting: false, startX: null, endX: null });

  // Charger TOUTES les données disponibles au montage
  useEffect(() => {
    const loadAllData = async () => {
      try {
        setLoading(true);
        setLoadingProgress(10);
        
        // Charger toutes les données avec intervalle de 10 secondes
        // Bon compromis : ~36k points pour 360k points bruts (1/10)
        // Chart.js peut gérer cela + decimation LTTB pour affichage fluide
        setLoadingProgress(30);
        
        const result = await apiService.getConsumptionHistory(null, null, '30 seconds');
        setLoadingProgress(70);
        
        setRawData(result);
        
        // Initialiser la période visible pour les 48 dernières heures
        if (result?.data && result.data.length > 0) {
          const now = new Date();
          const fortyEightHoursAgo = new Date(now.getTime() - 48 * 60 * 60 * 1000);
          const minIndex48h = result.data.findIndex(d => new Date(d.time) >= fortyEightHoursAgo);
          const visibleMin = minIndex48h !== -1 ? minIndex48h : 0;
          const visibleMax = result.data.length - 1;
          
          if (result.data[visibleMin] && result.data[visibleMax]) {
            const startTime = new Date(result.data[visibleMin].time);
            const endTime = new Date(result.data[visibleMax].time);
            setVisibleTimeRange({ startTime, endTime });
          }
        }
        
        setLoadingProgress(100);
        
        setError(null);
      } catch (err) {
        setError('Impossible de récupérer les données');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    loadAllData();

    // Charger les détections
    const fetchDetections = async () => {
      try {
        const result = await apiService.getDetections(0); // 0 = all detections
        setDetections(result.detections || []);
      } catch (err) {
        console.error('Failed to fetch detections:', err);
      }
    };
    fetchDetections();

    // Charger les signatures
    const fetchSignatures = async () => {
      try {
        const result = await apiService.getSignatures();
        setSignatures(result.signatures || []);
      } catch (err) {
        console.error('❌ Failed to fetch signatures:', err);
      }
    };
    fetchSignatures();    // Setup WebSocket pour les mises à jour en temps réel
    const handleNewDetection = (detection) => {
      setDetections(prev => [...prev, detection]);
    };

    const handleDetectionComplete = async (data) => {
      try {
        const result = await apiService.getDetections(0);
        setDetections(result.detections || []);
      } catch (err) {
        console.error('Failed to refresh detections:', err);
      }
    };

    const handleDetectionsCleared = (data) => {
      setDetections([]);
    };

    // Enregistrer les handlers
    detectionsWS.on('new_detection', handleNewDetection);
    detectionsWS.on('detection_complete', handleDetectionComplete);
    detectionsWS.on('detections_cleared', handleDetectionsCleared);
    detectionsWS.connect();

    // Cleanup
    return () => {
      detectionsWS.off('new_detection', handleNewDetection);
      detectionsWS.off('detection_complete', handleDetectionComplete);
      detectionsWS.off('detections_cleared', handleDetectionsCleared);
      
      // Nettoyer le timeout d'interaction
      if (interactionTimeoutRef.current) {
        clearTimeout(interactionTimeoutRef.current);
      }
    };
  }, [setVisibleTimeRange]);

  // Plus de useEffect pour le zoom initial - on le fait directement dans les scales

  // Gestion de la sélection par clic droit + drag
  useEffect(() => {
    const canvas = chartRef.current?.canvas;
    if (!canvas || !rawData?.data) return;

    const handleContextMenu = (e) => {
      e.preventDefault();
      return false;
    };

    const handleMouseDown = (e) => {
      if (e.button !== 2) return; // Seulement clic droit
      
      const rect = canvas.getBoundingClientRect();
      const x = e.clientX - rect.left;
      
      selectionRef.current = {
        isSelecting: true,
        startX: x,
        endX: x,
      };
      setIsSelecting(true);
      setSelectionStart(x);
      setSelectionEnd(x);
    };

    const handleMouseMove = (e) => {
      if (!selectionRef.current.isSelecting) return;
      
      const rect = canvas.getBoundingClientRect();
      const x = e.clientX - rect.left;
      
      selectionRef.current.endX = x;
      setSelectionEnd(x);
    };

    const handleMouseUp = (e) => {
      // Toujours bloquer le clic droit, même si pas en sélection
      if (e.button === 2) {
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
      }
      
      if (!selectionRef.current.isSelecting || e.button !== 2) {
        selectionRef.current.isSelecting = false;
        setIsSelecting(false);
        return;
      }
      
      const rect = canvas.getBoundingClientRect();
      const endX = e.clientX - rect.left;
      const startX = selectionRef.current.startX;
      
      // Annuler si la sélection est trop petite (< 10px)
      if (Math.abs(endX - startX) < 10) {
        selectionRef.current.isSelecting = false;
        setIsSelecting(false);
        setSelectionStart(null);
        setSelectionEnd(null);
        return;
      }
      
      // Convertir les positions pixel en indices de données
      const chart = chartRef.current;
      if (!chart?.scales?.x) {
        selectionRef.current.isSelecting = false;
        setIsSelecting(false);
        return;
      }
      
      const xScale = chart.scales.x;
      const minX = Math.min(startX, endX);
      const maxX = Math.max(startX, endX);
      
      // Convertir pixel → valeur d'échelle (index)
      const startIndex = Math.round(xScale.getValueForPixel(minX));
      const endIndex = Math.round(xScale.getValueForPixel(maxX));
      
      // Vérifier les indices valides
      if (startIndex >= 0 && endIndex >= 0 && 
          startIndex < rawData.data.length && endIndex < rawData.data.length) {
        
        const startTime = new Date(rawData.data[startIndex].time);
        const endTime = new Date(rawData.data[endIndex].time);
        
        // Utiliser setTimeout pour ouvrir la modal après que tous les events soient traités
        setTimeout(() => {
          setSelectedRange({ startTime, endTime });
          setShowSignatureModal(true);
        }, 0);
      }
      
      // Reset de la sélection
      selectionRef.current.isSelecting = false;
      setIsSelecting(false);
      setSelectionStart(null);
      setSelectionEnd(null);
    };

    const handleMouseLeave = () => {
      if (selectionRef.current.isSelecting) {
        selectionRef.current.isSelecting = false;
        setIsSelecting(false);
        setSelectionStart(null);
        setSelectionEnd(null);
      }
    };

    canvas.addEventListener('contextmenu', handleContextMenu);
    canvas.addEventListener('mousedown', handleMouseDown);
    canvas.addEventListener('mousemove', handleMouseMove);
    canvas.addEventListener('mouseup', handleMouseUp);
    canvas.addEventListener('mouseleave', handleMouseLeave);

    return () => {
      canvas.removeEventListener('contextmenu', handleContextMenu);
      canvas.removeEventListener('mousedown', handleMouseDown);
      canvas.removeEventListener('mousemove', handleMouseMove);
      canvas.removeEventListener('mouseup', handleMouseUp);
      canvas.removeEventListener('mouseleave', handleMouseLeave);
    };
  }, [rawData]);

  // Plus de useEffect pour le zoom initial - on le fait directement dans les scales

  // Réinitialiser le zoom
  const handleResetZoom = useCallback(() => {
    if (chartRef.current) {
      chartRef.current.resetZoom();
      // Pas besoin de réinitialiser initialZoomApplied car on veut garder la vue complète
    }
  }, []);

  // Callback après zoom/pan - juste pour logger
  const handleZoomPanComplete = useCallback(() => {
    // Annuler le timeout précédent si existant
    if (interactionTimeoutRef.current) {
      clearTimeout(interactionTimeoutRef.current);
    }
    
    // Attendre 200ms après la fin du zoom/pan avant de marquer comme terminé
    // Cela évite les mises à jour d'annotations pendant le pan
    interactionTimeoutRef.current = setTimeout(() => {
      isInteractingRef.current = false;
      interactionTimeoutRef.current = null;
    }, 200);
    
    if (chartRef.current?.scales?.x && rawData?.data) {
      const xScale = chartRef.current.scales.x;
      const visibleMin = Math.max(0, Math.floor(xScale.min || 0));
      const visibleMax = Math.min(rawData.data.length - 1, Math.ceil(xScale.max || rawData.data.length - 1));
      
      const visibleCount = visibleMax - visibleMin + 1;
      
      // Mettre à jour la période visible dans le contexte
      if (rawData.data[visibleMin] && rawData.data[visibleMax]) {
        const startTime = new Date(rawData.data[visibleMin].time);
        const endTime = new Date(rawData.data[visibleMax].time);
        setVisibleTimeRange({ startTime, endTime });
      }
    }
  }, [rawData, setVisibleTimeRange]);

  // Palette de couleurs pour les annotations des appareils
  const APPLIANCE_COLORS = [
    "#f94144",
    "#f3722c",
    "#f8961e",
    "#f9844a",
    "#f9c74f",
    "#90be6d",
    "#43aa8b",
    "#4d908e",
    "#577590",
    "#277da1"
  ];

  // Obtenir la liste unique des noms d'appareils
  const uniqueApplianceNames = useMemo(() => {
    const items = annotationMode === 'detections' ? detections : signatures;
    if (!items || items.length === 0) return [];
    
    const names = new Set();
    items.forEach(item => {
      const itemName = item.name || item.appliance_name;
      if (itemName) names.add(itemName);
    });
    
    return Array.from(names).sort();
  }, [annotationMode, detections, signatures]);

  const getApplianceColor = useCallback((applianceName) => {
    const name = applianceName || 'Unknown';
    const totalAppliances = uniqueApplianceNames.length;
    
    if (totalAppliances === 0) {
      return {
        bg: `${APPLIANCE_COLORS[0]}26`,
        border: `${APPLIANCE_COLORS[0]}99`,
        solid: APPLIANCE_COLORS[0],
        dark: APPLIANCE_COLORS[0],
      };
    }
    
    const applianceIndex = uniqueApplianceNames.indexOf(name);
    let colorIndex;
    
    if (totalAppliances === 1) {
      colorIndex = 0;
    } else {
      // Répartir uniformément sur toute la palette
      const position = applianceIndex / (totalAppliances - 1);
      colorIndex = Math.round(position * (APPLIANCE_COLORS.length - 1));
    }
    
    const baseColor = APPLIANCE_COLORS[colorIndex];
    
    return {
      bg: `${baseColor}26`,
      border: `${baseColor}99`,
      solid: baseColor,
      dark: baseColor,
    };
  }, [uniqueApplianceNames]);

  // Légende des appareils (détections ou signatures selon le mode)
  const getLegendItems = useCallback(() => {
    const items = annotationMode === 'detections' ? detections : signatures;
    if (!items || items.length === 0) return [];
    
    const applianceMap = new Map();
    items.forEach(item => {
      // Pour les détections: item.name, pour les signatures: item.appliance_name
      const itemName = item.name || item.appliance_name;
      if (!itemName) return;
      
      if (!applianceMap.has(itemName)) {
        applianceMap.set(itemName, {
          name: itemName,
          color: getApplianceColor(itemName).solid,
          count: 1,
          totalEnergy: item.energy_consumed || 0,
        });
      } else {
        const mapItem = applianceMap.get(itemName);
        mapItem.count += 1;
        mapItem.totalEnergy += item.energy_consumed || 0;
      }
    });
    
    return Array.from(applianceMap.values());
  }, [annotationMode, detections, signatures, getApplianceColor]);

  // Préparer les données du graphique (useMemo pour éviter recalcul)
  const chartData = useMemo(() => {
    if (!rawData || !rawData.data || rawData.data.length === 0) {
      return null;
    }

    // Utiliser les timestamps bruts comme labels (plus performant)
    // Le formatage sera fait uniquement dans les tooltips
    const labels = rawData.data.map((d, index) => index);
    const powerData = rawData.data.map(d => d.avg_papp);

    return {
      labels,
      datasets: [
        {
          label: 'Puissance moyenne (VA)',
          data: powerData,
          borderColor: '#0d6e00ff',
          backgroundColor: 'rgba(72, 105, 102, 0.1)',
          fill: true,
          borderWidth: 1,
          tension: 0,
          pointRadius: 0,
          pointHoverRadius: 0,
        },
      ],
    };
  }, [rawData]);

  // Créer les annotations (useMemo) - calculer directement sans passer par createDetectionAnnotations
  const annotationsData = useMemo(() => {
    if (annotationMode === 'none' || !rawData) {
      return { annotations: {}, maxRows: 0 };
    }

    const annotations = {};
    
    if (annotationMode === 'detections') {
      // Créer les annotations pour chaque détection (zones colorées uniquement)
      detections
        .filter(d => d.start_time && d.end_time && d.name)
        .forEach(d => {
          const startTime = new Date(d.start_time).getTime();
          const endTime = new Date(d.end_time).getTime();
          const startIndex = rawData.data.findIndex(dt => new Date(dt.time).getTime() >= startTime);
          const endIndex = rawData.data.findIndex(dt => new Date(dt.time).getTime() >= endTime);
          
          if (startIndex !== -1) {
            const colors = getApplianceColor(d.name);
            const finalEndIndex = endIndex !== -1 ? endIndex : rawData.data.length - 1;
            
            annotations[`detection-${d.id}`] = {
              type: 'box',
              xMin: startIndex,
              xMax: finalEndIndex,
              yMin: 'min',  // Du bas du graphique
              yMax: 'max',  // Au haut du graphique
              backgroundColor: colors.bg,
              borderColor: colors.border,
              borderWidth: 1,
              drawTime: 'beforeDatasetsDraw',
              clip: true,  // Clipper l'annotation dans la zone du graphique
            };
          }
        });
    } else if (annotationMode === 'signatures') {
      // Créer les annotations pour chaque signature (lignes verticales avec labels)
      const filteredSignatures = signatures.filter(s => s.start_time && s.end_time && s.appliance_name);
      
      filteredSignatures.forEach(s => {
          const startTime = new Date(s.start_time).getTime();
          const endTime = new Date(s.end_time).getTime();
          
          // Trouver l'index le plus proche pour le début et la fin
          let startIndex = -1;
          let endIndex = -1;
          let minStartDiff = Infinity;
          let minEndDiff = Infinity;
          
          rawData.data.forEach((dt, idx) => {
            const dtTime = new Date(dt.time).getTime();
            const startDiff = Math.abs(dtTime - startTime);
            const endDiff = Math.abs(dtTime - endTime);
            
            if (startDiff < minStartDiff) {
              minStartDiff = startDiff;
              startIndex = idx;
            }
            if (endDiff < minEndDiff) {
              minEndDiff = endDiff;
              endIndex = idx;
            }
          });
          
          
          if (startIndex !== -1 && endIndex !== -1) {
            const colors = getApplianceColor(s.appliance_name);
            const finalStartIndex = Math.min(startIndex, endIndex);
            const finalEndIndex = Math.max(startIndex, endIndex);
            
            // Pour les signatures négatives : bordure rouge, fond plus transparent, et bordure plus épaisse
            const isNegative = s.is_negative === true;
            
            // Zone colorée pour la signature
            annotations[`signature-box-${s.id}`] = {
              type: 'box',
              xMin: finalStartIndex,
              xMax: finalEndIndex,
              yMin: 'min',
              yMax: 'max',
              backgroundColor: colors.bg,
              borderColor: isNegative ? 'rgba(255, 0, 0, 0.6)' : colors.border,
              borderWidth: 1,
              borderDash: isNegative ? [10, 5] : undefined,  // Ligne pointillée seulement pour les négatives
              drawTime: 'beforeDatasetsDraw',
              clip: true,
            };
            
          } 
        });
    }

    return { annotations, maxRows: 0 };
  }, [annotationMode, detections, signatures, rawData, getApplianceColor]);

  // Options TOTALEMENT stables - ne dépendent QUE de rawData et handleZoomPanComplete
  const options = useMemo(() => {
    if (!rawData || !rawData.data) return {};
    
    // Calculer les indices pour les 48 dernières heures (pour affichage initial)
    const now = new Date();
    const fortyEightHoursAgo = new Date(now.getTime() - 48 * 60 * 60 * 1000);
    const minIndex48h = rawData.data.findIndex(d => new Date(d.time) >= fortyEightHoursAgo);
    const maxIndex48h = rawData.data.length - 1;
    const initialMin = minIndex48h !== -1 ? minIndex48h : 0;
    
    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: {
        mode: 'index',
        intersect: false,
      },
      plugins: {
        annotation: {
          clip: true,  // Clipper les annotations dans la zone du graphique
          annotations: {}, // VIDE - sera rempli par useEffect
        },
        legend: { display: false },
        title: { display: false },
        tooltip: {
          callbacks: {
            title: (context) => {
              // Formater le timestamp uniquement dans le tooltip
              if (context[0] && rawData?.data) {
                const index = context[0].parsed.x;
                const dataPoint = rawData.data[index];
                if (dataPoint) {
                  const date = new Date(dataPoint.time);
                  return date.toLocaleString('fr-FR', {
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit',
                    day: '2-digit',
                    month: '2-digit',
                    year: '2-digit'
                  });
                }
              }
              return '';
            },
            label: (context) => `${context.dataset.label}: ${context.parsed.y.toFixed(0)} VA`,
          },
        },
        zoom: {
          zoom: {
            wheel: { enabled: true, speed: 0.1 },
            pinch: { enabled: true },
            mode: 'x',
            scaleMode: 'x',
            onZoomStart: () => { isInteractingRef.current = true; },
            onZoomComplete: handleZoomPanComplete,
          },
          pan: {
            enabled: true,
            mode: 'x',
            scaleMode: 'x',
            modifierKey: null,
            onPanStart: () => { isInteractingRef.current = true; },
            onPanComplete: handleZoomPanComplete,
            threshold: 10, // Seuil minimum de déplacement en pixels (augmenté pour plus de stabilité)
          },
          limits: {
            x: { 
              min: 0, 
              max: rawData.data.length - 1,
              minRange: 10,
            },
          },
        },
        decimation: {
          enabled: true,
          algorithm: 'lttb',
          samples: 1000,
        },
      },
      scales: {
        y: {
          beginAtZero: true,
          title: { display: true, text: 'Puissance (VA)' },
        },
        x: {
          min: initialMin,  // Zoom initial sur 48h
          max: maxIndex48h,
          type: 'linear',  // Utiliser échelle linéaire pour les indices
          title: { display: false },
          ticks: { 
            maxRotation: 45, 
            minRotation: 45,
            autoSkip: true,
            maxTicksLimit: 20,
            callback: (value, index) => {
              // Formater uniquement les ticks visibles
              if (rawData?.data && rawData.data[value]) {
                const date = new Date(rawData.data[value].time);
                return date.toLocaleString('fr-FR', {
                  hour: '2-digit',
                  minute: '2-digit',
                  day: '2-digit',
                  month: '2-digit',
                });
              }
              return '';
            },
          },
        },
      },
    };
  }, [handleZoomPanComplete, rawData]); // NE DÉPEND PAS de annotationsData !

  // Mettre à jour les annotations après création du chart, sans changer les options
  useEffect(() => {
    if (!chartRef.current || !annotationsData) return;
    
    // Ne pas update pendant une interaction utilisateur (zoom/pan)
    if (isInteractingRef.current) {
      return;
    }
    
    const chart = chartRef.current;
    if (chart.options?.plugins?.annotation) {
      chart.options.plugins.annotation.annotations = annotationsData.annotations;
      // update('none') = mise à jour sans animation ni reset du zoom
      chart.update('none');
    }
  }, [annotationsData]);

  // Rendu conditionnel APRÈS tous les hooks
  if (loading) {
    return (
      <Card>
        <CardContent sx={{ textAlign: 'center', py: 4 }}>
          <CircularProgress />
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            Chargement des données...
          </Typography>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent>
          <Alert severity="error">{error}</Alert>
        </CardContent>
      </Card>
    );
  }

  if (!rawData || !rawData.data || rawData.data.length === 0 || !chartData) {
    return (
      <Card>
        <CardContent>
          <Alert severity="info">Aucune donnée disponible</Alert>
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <Card>
        <CardHeader
          title="Historique de consommation"
          titleTypographyProps={{ variant: 'h5' }}
          subheader={
            loading 
              ? `Chargement des données (${loadingProgress}%)...`
              : `Molette: zoom • Glisser: naviguer • Clic droit + glisser: créer signature`
          }
          avatar={<ShowChart />}
          action={
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
              <MuiTooltip title="Réinitialiser le zoom">
                <span>
                  <IconButton
                    color="primary"
                    onClick={handleResetZoom}
                    disabled={loading}
                  >
                    <ZoomOutMap />
                  </IconButton>
                </span>
              </MuiTooltip>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <Typography 
                  variant="caption" 
                  sx={{ 
                    fontSize: '0.75rem',
                    color: annotationMode === 'signatures' ? 'primary.main' : 'text.secondary',
                    fontWeight: annotationMode === 'signatures' ? 600 : 400,
                  }}
                >
                  Signatures
                </Typography>
                <Switch
                  checked={annotationMode === 'detections'}
                  onChange={(e) => setAnnotationMode(e.target.checked ? 'detections' : 'signatures')}
                  size="small"
                  color="primary"
                  disabled={loading}
                />
                <Typography 
                  variant="caption" 
                  sx={{ 
                    fontSize: '0.75rem',
                    color: annotationMode === 'detections' ? 'primary.main' : 'text.secondary',
                    fontWeight: annotationMode === 'detections' ? 600 : 400,
                  }}
                >
                  Détections
                </Typography>
              </Box>
            </Box>
          }
        />
        {loading && (
          <LinearProgress 
            variant="determinate" 
            value={loadingProgress} 
            sx={{ 
              height: 2,
              backgroundColor: 'rgba(0, 0, 0, 0.05)',
            }} 
          />
        )}
        <CardContent>
          <Box 
            sx={{ height: 400, mb: 3, position: 'relative' }}
            onContextMenu={(e) => e.preventDefault()}
          >
            <Line 
              ref={chartRef} 
              data={chartData} 
              options={options}
            />
            {/* Overlay de sélection */}
            {isSelecting && selectionStart !== null && selectionEnd !== null && (
              <Box
                sx={{
                  position: 'absolute',
                  top: 0,
                  left: Math.min(selectionStart, selectionEnd),
                  width: Math.abs(selectionEnd - selectionStart),
                  height: '100%',
                  backgroundColor: 'rgba(33, 150, 243, 0.2)',
                  border: '2px solid rgba(33, 150, 243, 0.6)',
                  pointerEvents: 'none',
                  zIndex: 1000,
                }}
              />
            )}
          </Box>

          {getLegendItems().length > 0 && (
            <Box>
              <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1.5, fontWeight: 600 }}>
                Légende des appareils {annotationMode === 'detections' ? 'détectés' : 'en signatures'}
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
                {getLegendItems().map((item) => (
                  <Box
                    key={item.name}
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 1,
                      px: 1.5,
                      py: 0.75,
                      borderRadius: 1,
                      backgroundColor: 'background.paper',
                      border: '1px solid',
                      borderColor: 'divider',
                    }}
                  >
                    <Box
                      sx={{
                        width: 16,
                        height: 16,
                        borderRadius: 0.5,
                        backgroundColor: item.color,
                      }}
                    />
                    <Typography variant="body2" sx={{ fontWeight: 500 }}>
                      {item.name}
                    </Typography>
                    
                  </Box>
                ))}
              </Box>
            </Box>
          )}
        </CardContent>
      </Card>

      {selectedRange && (
        <SignatureModal
          open={showSignatureModal}
          onClose={() => {
            setShowSignatureModal(false);
            setSelectedRange(null);
          }}
          selectedRange={selectedRange}
          onSignatureSaved={() => {
            setShowSignatureModal(false);
            setSelectedRange(null);
          }}
        />
      )}
    </>
  );
};

export default ConsumptionChart;
