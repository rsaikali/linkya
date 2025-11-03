import React, { useRef, useEffect, useMemo, useCallback, useState } from 'react';
import { Box } from '@mui/material';
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

const CombinedChart = ({ rawData, detections, signatures, onSignatureModalOpen }) => {
  const chartRef = useRef(null);
  const { zoomState, setZoomState, setVisibleTimeRange } = useChart();
  const { getApplianceColor } = useApplianceColors();
  const [isSelecting, setIsSelecting] = useState(false);
  const [selectionStart, setSelectionStart] = useState(null);
  const [selectionEnd, setSelectionEnd] = useState(null);
  const selectionRef = useRef({ isSelecting: false, startX: null, endX: null });
  const isUpdatingZoomRef = useRef(false);

  // Synchronize zoom from context
  useEffect(() => {
    if (!chartRef.current || isUpdatingZoomRef.current) return;
    if (zoomState.min === null || zoomState.max === null) return;
    
    const chart = chartRef.current;
    if (chart.options?.scales?.x) {
      chart.options.scales.x.min = zoomState.min;
      chart.options.scales.x.max = zoomState.max;
      chart.update('none');
    }
  }, [zoomState]);

  // Handle zoom/pan complete
  const handleZoomPanComplete = useCallback(() => {
    if (!chartRef.current || !rawData?.data) return;
    
    const chart = chartRef.current;
    if (chart.scales?.x) {
      const visibleMin = Math.max(0, Math.floor(chart.scales.x.min || 0));
      const visibleMax = Math.min(rawData.data.length - 1, Math.ceil(chart.scales.x.max || rawData.data.length - 1));
      
      if (rawData.data[visibleMin] && rawData.data[visibleMax]) {
        const startTime = new Date(rawData.data[visibleMin].time);
        const endTime = new Date(rawData.data[visibleMax].time);
        setVisibleTimeRange({ startTime, endTime });
      }
      
      isUpdatingZoomRef.current = true;
      setZoomState({
        min: chart.scales.x.min,
        max: chart.scales.x.max,
        dataLength: rawData.data.length,
      });
      setTimeout(() => {
        isUpdatingZoomRef.current = false;
      }, 50);
    }
  }, [rawData, setVisibleTimeRange, setZoomState]);

  // Prepare annotations
  const annotationsData = useMemo(() => {
    if (!rawData || !rawData.data) return {};

    const annotations = {};
    
    const assignRowLevels = (items) => {
      const sorted = [...items].sort((a, b) => a.startIndex - b.startIndex);
      const rowEndIndices = [];
      
      sorted.forEach(item => {
        let assignedRow = -1;
        for (let i = 0; i < rowEndIndices.length; i++) {
          if (rowEndIndices[i] < item.startIndex) {
            assignedRow = i;
            rowEndIndices[i] = item.endIndex;
            break;
          }
        }
        if (assignedRow === -1) {
          assignedRow = rowEndIndices.length;
          rowEndIndices.push(item.endIndex);
        }
        item.row = assignedRow;
      });
      
      return Math.max(1, rowEndIndices.length);
    };

    // Detections annotations (on yDetections scale, 0-1)
    if (detections && detections.length > 0) {
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

      const maxDetectionRows = assignRowLevels(detectionItems);
      
      detectionItems.forEach(d => {
        const color = getApplianceColor(d.appliance_id || d.name);
        const rowHeight = 1 / (maxDetectionRows + 1);
        
        annotations[`detection-${d.id}`] = {
          type: 'box',
          xMin: d.startIndex,
          xMax: d.endIndex,
          yMin: d.row * rowHeight + 0.05,
          yMax: (d.row + 1) * rowHeight - 0.05,
          yScaleID: 'yDetections',
          backgroundColor: `${color}`,
          borderColor: color,
          borderWidth: 5,
          drawTime: 'beforeDatasetsDraw',
        };
      });
    }

    // Signatures annotations (on ySignatures scale, 0-1)
    if (signatures && signatures.length > 0) {
      const signatureItems = signatures
        .filter(s => s.start_time && s.end_time && s.appliance_name)
        .map(s => {
          const startTime = new Date(s.start_time).getTime();
          const endTime = new Date(s.end_time).getTime();
          
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

      const maxSignatureRows = assignRowLevels(signatureItems);
      
      signatureItems.forEach(s => {
        const color = getApplianceColor(s.appliance_id || s.appliance_name);
        const isNegative = s.is_negative === true;
        const rowHeight = 1 / (maxSignatureRows + 1);
        
        annotations[`signature-${s.id}`] = {
          type: 'box',
          xMin: s.startIndex,
          xMax: s.endIndex,
          yMin: s.row * rowHeight + 0.05,
          yMax: (s.row + 1) * rowHeight - 0.05,
          yScaleID: 'ySignatures',
          backgroundColor: `${color}`,
          borderColor: isNegative ? 'rgba(255, 0, 0, 0.6)' : color,
          borderWidth: 5,
          drawTime: 'beforeDatasetsDraw',
        };
      });
    }

    return annotations;
  }, [rawData, detections, signatures, getApplianceColor]);

  // Handle right-click selection for signature creation
  useEffect(() => {
    const canvas = chartRef.current?.canvas;
    if (!canvas || !rawData?.data) return;

    const handleContextMenu = (e) => {
      e.preventDefault();
      return false;
    };

    const handleMouseDown = (e) => {
      if (e.button !== 2) return;
      
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
      
      if (Math.abs(endX - startX) < 10) {
        selectionRef.current.isSelecting = false;
        setIsSelecting(false);
        setSelectionStart(null);
        setSelectionEnd(null);
        return;
      }
      
      const chart = chartRef.current;
      if (!chart?.scales?.x) {
        selectionRef.current.isSelecting = false;
        setIsSelecting(false);
        return;
      }
      
      const xScale = chart.scales.x;
      const minX = Math.min(startX, endX);
      const maxX = Math.max(startX, endX);
      
      const startIndex = Math.round(xScale.getValueForPixel(minX));
      const endIndex = Math.round(xScale.getValueForPixel(maxX));
      
      if (startIndex >= 0 && endIndex >= 0 && 
          startIndex < rawData.data.length && endIndex < rawData.data.length) {
        
        const startTime = new Date(rawData.data[startIndex].time);
        const endTime = new Date(rawData.data[endIndex].time);
        
        setTimeout(() => {
          onSignatureModalOpen({ startTime, endTime });
        }, 0);
      }
      
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
  }, [rawData, onSignatureModalOpen]);

  // Update annotations
  useEffect(() => {
    if (!chartRef.current || !annotationsData) return;
    
    const chart = chartRef.current;
    if (chart.options?.plugins?.annotation) {
      chart.options.plugins.annotation.annotations = annotationsData;
      chart.update('none');
    }
  }, [annotationsData]);

  // Chart data with 3 datasets (one per Y axis)
  const chartData = useMemo(() => {
    if (!rawData || !rawData.data || rawData.data.length === 0) {
      return null;
    }

    const labels = rawData.data.map((d, index) => index);
    const powerData = rawData.data.map(d => d.avg_papp);

    return {
      labels,
      datasets: [
        // Signatures dataset (invisible, just for ySignatures scale) - Will be at bottom
        {
          label: 'Signatures',
          data: rawData.data.map(() => 0),
          yAxisID: 'ySignatures',
          borderColor: 'transparent',
          backgroundColor: 'transparent',
          pointRadius: 0,
          pointHoverRadius: 0,
        },
        // Consumption dataset (main) - Will be in middle
        {
          label: 'Puissance moyenne (W)',
          data: powerData,
          yAxisID: 'yConsumption',
          borderColor: '#0d6e00ff',
          backgroundColor: '#BD2A2E50',
          fill: true,
          borderWidth: 0,
          tension: 0.4,
          pointRadius: 0,
          pointHoverRadius: 0,
        },
        // Detections dataset (invisible, just for yDetections scale) - Will be at top
        {
          label: 'Detections',
          data: rawData.data.map(() => 0),
          yAxisID: 'yDetections',
          borderColor: 'transparent',
          backgroundColor: 'transparent',
          pointRadius: 0,
          pointHoverRadius: 0,
        },
      ],
    };
  }, [rawData]);

  // Chart options
  const options = useMemo(() => {
    if (!rawData || !rawData.data) return {};
    
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
      layout: {
        padding: {
          left: 0,
          right: 0,
          top: 0,
          bottom: 0,
        },
      },
      plugins: {
        annotation: {
          annotations: {},
        },
        legend: { display: false },
        title: { display: false },
        tooltip: { enabled: false },
        zoom: {
          zoom: {
            wheel: { enabled: true, speed: 0.1 },
            pinch: { enabled: true },
            mode: 'x',
            scaleMode: 'x',
            onZoomComplete: handleZoomPanComplete,
          },
          pan: {
            enabled: true,
            mode: 'x',
            scaleMode: 'x',
            modifierKey: null,
            onPanComplete: handleZoomPanComplete,
            threshold: 10,
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
        // Signatures Y axis (bottom, 15% height)
        ySignatures: {
          type: 'linear',
          position: 'left',
          min: 0,
          max: 1,
          display: true,
          title: { 
            display: true, 
            text: 'Signatures',
            font: { size: 11, weight: 600 },
            color: '#666',
          },
          stack: 'demo',
          stackWeight: 1,
          grid: { display: false },
          ticks: { display: false },
          border: { display: false },
        },
        // Consumption Y axis (middle, 70% height)
        yConsumption: {
          type: 'linear',
          position: 'left',
          beginAtZero: true,
          display: true,
          title: { 
            display: true, 
            text: 'Puissance (W)',
            font: { size: 12, weight: 600 },
          },
          stack: 'demo',
          stackWeight: 7,
          grid: { drawOnChartArea: true },
        },
        // Detections Y axis (top, 15% height)
        yDetections: {
          type: 'linear',
          position: 'left',
          min: 0,
          max: 1,
          display: true,
          title: { 
            display: true, 
            text: 'Detections',
            font: { size: 11, weight: 600 },
            color: '#666',
          },
          stack: 'demo',
          stackWeight: 1,
          grid: { display: false },
          ticks: { display: false },
          border: { display: false },
        },
        x: {
          min: initialMin,
          max: maxIndex48h,
          type: 'linear',
          title: { display: false },
          ticks: { 
            maxRotation: 0, 
            minRotation: 0,
            autoSkip: true,
            maxTicksLimit: 20,
            callback: (value) => {
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
  }, [handleZoomPanComplete, rawData]);

  if (!rawData || !chartData) return null;

  return (
    <Box 
      sx={{ height: 600, position: 'relative' }}
      onContextMenu={(e) => e.preventDefault()}
    >
      <Line ref={chartRef} data={chartData} options={options} />
      
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
  );
};

export default CombinedChart;
