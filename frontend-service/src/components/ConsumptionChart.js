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
import { ZoomOutMap } from '@mui/icons-material';
import QueryStatsIcon from '@mui/icons-material/QueryStats';
import { apiService } from '../services/api';
import { detectionsWS } from '../services/websocket';
import SignatureModal from './SignatureModal';
import { useChart } from '../context/ChartContext';
import { useApplianceColors } from '../context/ApplianceColorsContext';

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
  const { getApplianceColor: getApplianceColorFromContext, applianceColors } = useApplianceColors();
  
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

  // Tooltip personnalisé
  const [customTooltip, setCustomTooltip] = useState({
    visible: false,
    x: 0,
    y: 0,
    content: null,
  });

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

  // Gestion du tooltip personnalisé
  useEffect(() => {
    const canvas = chartRef.current?.canvas;
    if (!canvas || !rawData?.data) return;

    const handleTooltipMove = (e) => {
      // Ne pas afficher le tooltip pendant la sélection
      if (selectionRef.current.isSelecting) {
        setCustomTooltip({ visible: false, x: 0, y: 0, content: null });
        return;
      }

      const rect = canvas.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      
      const chart = chartRef.current;
      if (!chart?.scales?.x || !chart?.scales?.y) return;

      const xScale = chart.scales.x;
      const yScale = chart.scales.y;
      
      // Convertir pixel → index de données
      const dataIndex = Math.round(xScale.getValueForPixel(x));
      
      if (dataIndex >= 0 && dataIndex < rawData.data.length) {
        const dataPoint = rawData.data[dataIndex];
        
        // Vérifier si on survole une annotation
        let hoveredAnnotation = null;
        const items = annotationMode === 'detections' ? detections : signatures;
        
        for (const item of items) {
          const itemName = item.name || item.appliance_name;
          if (!itemName) continue;
          
          const startTime = new Date(item.start_time).getTime();
          const endTime = new Date(item.end_time).getTime();
          const currentTime = new Date(dataPoint.time).getTime();
          
          if (currentTime >= startTime && currentTime <= endTime) {
            // Vérifier si on est dans la zone verticale de l'annotation
            const pixelY = yScale.getPixelForValue(0);
            const range = yScale.max - yScale.min;
            const annotationHeight = range * 0.045;
            
            // Trouver le niveau (row) de cette annotation
            const annotationYMax = yScale.max;
            const annotationYMin = yScale.max - annotationHeight;
            
            // Si la souris est dans la zone de l'annotation verticalement
            const mouseValue = yScale.getValueForPixel(y);
            if (mouseValue <= annotationYMax && mouseValue >= annotationYMin - (annotationHeight * 5)) {
              hoveredAnnotation = item;
              break;
            }
          }
        }
        
        if (hoveredAnnotation) {
          // Tooltip pour annotation
          const isDetection = annotationMode === 'detections';
          const itemName = hoveredAnnotation.name || hoveredAnnotation.appliance_name;
          const startDate = new Date(hoveredAnnotation.start_time);
          const endDate = new Date(hoveredAnnotation.end_time);
          const duration = (endDate - startDate) / 1000 / 60; // en minutes
          
          setCustomTooltip({
            visible: true,
            x: e.clientX,
            y: e.clientY - 10,
            content: {
              type: isDetection ? 'detection' : 'signature',
              name: itemName,
              startTime: startDate.toLocaleString('fr-FR'),
              endTime: endDate.toLocaleString('fr-FR'),
              duration: duration.toFixed(1),
              energy: hoveredAnnotation.energy_consumed?.toFixed(2) || 'N/A',
              isNegative: hoveredAnnotation.is_negative === true,
              validated: hoveredAnnotation.validated,
            },
          });
        } else {
          // Tooltip pour données normales
          const date = new Date(dataPoint.time);
          const power = dataPoint.avg_papp;
          
          setCustomTooltip({
            visible: true,
            x: e.clientX,
            y: e.clientY - 10,
            content: {
              type: 'data',
              time: date.toLocaleString('fr-FR', {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                day: '2-digit',
                month: '2-digit',
                year: '2-digit'
              }),
              power: power.toFixed(0),
            },
          });
        }
      }
    };

    const handleTooltipLeave = () => {
      setCustomTooltip({ visible: false, x: 0, y: 0, content: null });
    };

    canvas.addEventListener('mousemove', handleTooltipMove);
    canvas.addEventListener('mouseleave', handleTooltipLeave);

    return () => {
      canvas.removeEventListener('mousemove', handleTooltipMove);
      canvas.removeEventListener('mouseleave', handleTooltipLeave);
    };
  }, [rawData, detections, signatures, annotationMode]);

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
      
      // Mettre à jour la période visible dans le contexte
      if (rawData.data[visibleMin] && rawData.data[visibleMax]) {
        const startTime = new Date(rawData.data[visibleMin].time);
        const endTime = new Date(rawData.data[visibleMax].time);
        setVisibleTimeRange({ startTime, endTime });
      }
    }
  }, [rawData, setVisibleTimeRange]);

  // Fonction pour obtenir la couleur d'un appareil en utilisant le Context
  // On cherche l'appliance_id ou on utilise le nom si l'ID n'est pas disponible
  const getApplianceColor = useCallback((applianceNameOrId, applianceId = null) => {
    // Si on a un ID d'appareil, l'utiliser directement
    const id = applianceId || applianceNameOrId;
    
    // Récupérer la couleur depuis le Context
    const baseColor = getApplianceColorFromContext(id);
    
    return {
      bg: `${baseColor}99`,      // 60% d'opacité pour le fond
      border: `${baseColor}99`,   // 60% d'opacité pour la bordure
      solid: baseColor,           // Couleur pleine
      dark: baseColor,            // Couleur foncée (même que solid)
    };
  }, [getApplianceColorFromContext, applianceColors]); // eslint-disable-line react-hooks/exhaustive-deps

  // Légende des appareils (détections ou signatures selon le mode)
  const getLegendItems = useCallback(() => {
    const items = annotationMode === 'detections' ? detections : signatures;
    if (!items || items.length === 0) return [];
    
    const applianceMap = new Map();
    items.forEach(item => {
      // Pour les détections: item.name, pour les signatures: item.appliance_name
      const itemName = item.name || item.appliance_name;
      const itemId = item.appliance_id;
      if (!itemName) return;
      
      if (!applianceMap.has(itemName)) {
        applianceMap.set(itemName, {
          name: itemName,
          color: getApplianceColor(itemName, itemId).solid,
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
          label: 'Puissance moyenne (W)',
          data: powerData,
          borderColor: '#0d6e00ff',
          backgroundColor: '#BD2A2E50',
          fill: true,
          borderWidth: 0,
          tension: 0.4,
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
    
    // Fonction pour détecter les chevauchements et assigner des niveaux (rows)
    const assignRowLevels = (items) => {
      // Trier par heure de début
      const sorted = [...items].sort((a, b) => a.startIndex - b.startIndex);
      
      // Tableau pour garder trace de la fin de chaque niveau (row)
      const rowEndIndices = [];
      
      sorted.forEach(item => {
        // Trouver le premier niveau disponible (en commençant par 0)
        let assignedRow = -1;
        
        for (let i = 0; i < rowEndIndices.length; i++) {
          // Si ce niveau est libre (la fin précédente < début actuel)
          if (rowEndIndices[i] < item.startIndex) {
            assignedRow = i;
            rowEndIndices[i] = item.endIndex;
            break;
          }
        }
        
        // Si aucun niveau existant n'est disponible, créer un nouveau niveau
        if (assignedRow === -1) {
          assignedRow = rowEndIndices.length;
          rowEndIndices.push(item.endIndex);
        }
        
        item.row = assignedRow;
      });
      
      return Math.max(1, rowEndIndices.length);
    };
    
    if (annotationMode === 'detections') {
      // Préparer les données avec indices
      const detectionItems = detections
        .filter(d => d.start_time && d.end_time && d.name)
        .map(d => {
          const startTime = new Date(d.start_time).getTime();
          const endTime = new Date(d.end_time).getTime();
          const startIndex = rawData.data.findIndex(dt => new Date(dt.time).getTime() >= startTime);
          const endIndex = rawData.data.findIndex(dt => new Date(dt.time).getTime() >= endTime);
          
          if (startIndex !== -1) {
            return {
              ...d,
              startIndex,
              endIndex: endIndex !== -1 ? endIndex : rawData.data.length - 1,
            };
          }
          return null;
        })
        .filter(Boolean);
      
      // Assigner les niveaux pour éviter les chevauchements
      assignRowLevels(detectionItems);
      
      // Créer les annotations avec décalage vertical
      detectionItems.forEach(d => {
        const colors = getApplianceColor(d.name, d.appliance_id);
        const rowHeight = 0.045; // 4.5% de la hauteur par niveau (3% + 50%)
        
        annotations[`detection-${d.id}`] = {
          type: 'box',
          xMin: d.startIndex,
          xMax: d.endIndex,
          yMin: (ctx) => {
            const yScale = ctx.chart.scales.y;
            const range = yScale.max - yScale.min;
            // Le niveau 0 est tout en haut, niveau 1 juste en dessous, etc.
            const rowOffset = (d.row + 1) * rowHeight;
            return yScale.max - (range * rowOffset);
          },
          yMax: (ctx) => {
            const yScale = ctx.chart.scales.y;
            const range = yScale.max - yScale.min;
            // Haut de la barre = max - (niveau * hauteur)
            const rowOffset = d.row * rowHeight;
            return yScale.max - (range * rowOffset);
          },
          backgroundColor: colors.bg,
          borderColor: colors.border,
          borderWidth: 1,
          drawTime: 'beforeDatasetsDraw',
          clip: true,
        };
      });
    } else if (annotationMode === 'signatures') {
      // Préparer les données avec indices
      const signatureItems = signatures
        .filter(s => s.start_time && s.end_time && s.appliance_name)
        .map(s => {
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
            return {
              ...s,
              startIndex: Math.min(startIndex, endIndex),
              endIndex: Math.max(startIndex, endIndex),
            };
          }
          return null;
        })
        .filter(Boolean);
      
      // Assigner les niveaux pour éviter les chevauchements
      assignRowLevels(signatureItems);
      
      // Créer les annotations avec décalage vertical
      signatureItems.forEach(s => {
        const colors = getApplianceColor(s.appliance_name, s.appliance_id);
        const isNegative = s.is_negative === true;
        const rowHeight = 0.045; // 4.5% de la hauteur par niveau (3% + 50%)
        
        // Zone colorée pour la signature
        annotations[`signature-box-${s.id}`] = {
          type: 'box',
          xMin: s.startIndex,
          xMax: s.endIndex,
          yMin: (ctx) => {
            const yScale = ctx.chart.scales.y;
            const range = yScale.max - yScale.min;
            // Le niveau 0 est tout en haut, niveau 1 juste en dessous, etc.
            const rowOffset = (s.row + 1) * rowHeight;
            return yScale.max - (range * rowOffset);
          },
          yMax: (ctx) => {
            const yScale = ctx.chart.scales.y;
            const range = yScale.max - yScale.min;
            // Haut de la barre = max - (niveau * hauteur)
            const rowOffset = s.row * rowHeight;
            return yScale.max - (range * rowOffset);
          },
          backgroundColor: colors.bg,
          borderColor: isNegative ? 'rgba(255, 0, 0, 0.6)' : colors.border,
          borderWidth: 1,
          borderDash: isNegative ? [10, 5] : undefined,
          drawTime: 'beforeDatasetsDraw',
          clip: true,
        };
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
          enabled: false, // Désactiver le tooltip par défaut
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
          title: { display: true, text: 'Puissance (W)' },
        },
        x: {
          min: initialMin,  // Zoom initial sur 48h
          max: maxIndex48h,
          type: 'linear',  // Utiliser échelle linéaire pour les indices
          title: { display: false },
          ticks: { 
            maxRotation: 0, 
            minRotation: 0,
            autoSkip: true,
            maxTicksLimit: 20,
            callback: (value, index) => {
              // Formater uniquement les ticks visibles sur deux lignes: Jour DD.MM et HH:mm
              if (rawData?.data && rawData.data[value]) {
                const date = new Date(rawData.data[value].time);
                const dayName = date.toLocaleDateString('fr-FR', { weekday: 'long' });
                const day = String(date.getDate()).padStart(2, '0');
                const month = String(date.getMonth() + 1).padStart(2, '0');
                const hours = String(date.getHours()).padStart(2, '0');
                const minutes = String(date.getMinutes()).padStart(2, '0');
                return [`${dayName} ${day}.${month}`, `${hours}:${minutes}`];
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
          avatar={<QueryStatsIcon />}
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
                    fontSize: '1rem',
                    color: annotationMode === 'signatures' ? 'primary.main' : 'text.secondary',
                    fontWeight: annotationMode === 'signatures' ? 700 : 400,
                  }}
                >
                  Signatures
                </Typography>
                <Switch
                  checked={annotationMode === 'detections'}
                  onChange={(e) => setAnnotationMode(e.target.checked ? 'detections' : 'signatures')}
                  size="medium"
                  color="primary"
                  disabled={loading}
                />
                <Typography 
                  variant="caption" 
                  sx={{ 
                    fontSize: '1rem',
                    color: annotationMode === 'detections' ? 'primary.main' : 'text.secondary',
                    fontWeight: annotationMode === 'detections' ? 700 : 400,
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
        </CardContent>
      </Card>

      {/* Tooltip personnalisé */}
      {customTooltip.visible && customTooltip.content && (
        <Box
          sx={{
            position: 'fixed',
            left: customTooltip.x,
            top: customTooltip.y,
            transform: 'translate(-50%, -100%)',
            backgroundColor: 'rgba(255, 255, 255, 0.98)',
            border: '1px solid rgba(0, 0, 0, 0.12)',
            borderRadius: 2,
            boxShadow: '0px 4px 12px rgba(0, 0, 0, 0.15)',
            padding: 1.5,
            pointerEvents: 'none',
            zIndex: 10000,
            minWidth: 200,
            maxWidth: 350,
          }}
        >
          {customTooltip.content.type === 'data' ? (
            // Tooltip pour données normales
            <Box>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                {customTooltip.content.time}
              </Typography>
              <Typography variant="body1" sx={{ fontWeight: 600, color: 'primary.main' }}>
                {customTooltip.content.power} W
              </Typography>
            </Box>
          ) : (
            // Tooltip pour annotation (détection ou signature)
            <Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <Box
                  sx={{
                    width: 12,
                    height: 12,
                    borderRadius: 0.5,
                    backgroundColor: getApplianceColor(
                      customTooltip.content.name,
                      null
                    ).solid,
                  }}
                />
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  {customTooltip.content.name}
                </Typography>
                {customTooltip.content.isNegative && (
                  <Typography
                    variant="caption"
                    sx={{
                      backgroundColor: 'error.main',
                      color: 'white',
                      px: 0.5,
                      borderRadius: 0.5,
                      fontWeight: 600,
                    }}
                  >
                    NÉGATIF
                  </Typography>
                )}
              </Box>
              
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                <Typography variant="caption" color="text.secondary">
                  Début: {customTooltip.content.startTime}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Fin: {customTooltip.content.endTime}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Durée: {customTooltip.content.duration} min
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Énergie: {customTooltip.content.energy} Wh
                </Typography>
                
                {customTooltip.content.type === 'detection' && customTooltip.content.validated !== undefined && (
                  <Typography
                    variant="caption"
                    sx={{
                      color: customTooltip.content.validated === true
                        ? 'success.main'
                        : customTooltip.content.validated === false
                        ? 'error.main'
                        : 'warning.main',
                      fontWeight: 600,
                      mt: 0.5,
                    }}
                  >
                    {customTooltip.content.validated === true
                      ? '✓ Validé'
                      : customTooltip.content.validated === false
                      ? '✗ Rejeté'
                      : '⏳ En attente'}
                  </Typography>
                )}
              </Box>
            </Box>
          )}
        </Box>
      )}

      {selectedRange && (
        <SignatureModal
          open={showSignatureModal}
          onClose={() => {
            setShowSignatureModal(false);
            setSelectedRange(null);
          }}
          selectedRange={selectedRange}
          onSignatureSaved={async () => {
            setShowSignatureModal(false);
            setSelectedRange(null);
            
            // Switch to signatures mode to show the newly created signature
            setAnnotationMode('signatures');
            
            // Refresh signatures list in this component
            try {
              const result = await apiService.getSignatures();
              setSignatures(result.signatures || []);
              console.log('✅ Signatures refreshed after creation:', result.signatures?.length);
              
              // Force chart update after a small delay to ensure state is updated
              setTimeout(() => {
                if (chartRef.current) {
                  chartRef.current.update('none');
                  console.log('✅ Chart annotations updated');
                }
              }, 100);
            } catch (err) {
              console.error('Failed to refresh signatures:', err);
            }
            // Emit custom event for other components to refresh
            window.dispatchEvent(new CustomEvent('signature-created'));
          }}
        />
      )}
    </>
  );
};

export default ConsumptionChart;
