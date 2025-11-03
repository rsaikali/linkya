import React, { useRef, useEffect, useMemo, useCallback, useState } from 'react';
import { Box, Typography } from '@mui/material';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
} from 'chart.js';
import annotationPlugin from 'chartjs-plugin-annotation';
import zoomPlugin from 'chartjs-plugin-zoom';
import { Bar } from 'react-chartjs-2';
import { useChart } from '../context/ChartContext';
import { useApplianceColors } from '../context/ApplianceColorsContext';

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  annotationPlugin,
  zoomPlugin
);

const DetectionsTimeline = ({ rawData, detections }) => {
  const chartRef = useRef(null);
  const { zoomState, setZoomState } = useChart();
  const { getApplianceColor } = useApplianceColors();
  const [customTooltip, setCustomTooltip] = useState({ visible: false, x: 0, y: 0, content: null });
  const isUpdatingZoomRef = useRef(false);
  const initializedRef = useRef(false);

  // Synchronize zoom from context
  useEffect(() => {
    if (!chartRef.current || isUpdatingZoomRef.current) return;
    if (zoomState.min === null || zoomState.max === null) return;
    
    const chart = chartRef.current;
    if (chart.options?.scales?.x) {
      chart.options.scales.x.min = zoomState.min;
      chart.options.scales.x.max = zoomState.max;
      chart.update('none');
      initializedRef.current = true;
    }
  }, [zoomState]);

  // Handle zoom/pan complete
  const handleZoomPanComplete = useCallback(() => {
    if (!chartRef.current || !rawData?.data) return;
    
    const chart = chartRef.current;
    if (chart.scales?.x) {
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
  }, [rawData, setZoomState]);

  // Prepare annotations for detections
  const annotationsData = useMemo(() => {
    if (!rawData || !detections || detections.length === 0) {
      return {};
    }

    const annotations = {};
    
    // Assign row levels to avoid overlapping
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

    const maxRows = assignRowLevels(detectionItems);
    
    detectionItems.forEach(d => {
      const color = getApplianceColor(d.appliance_id || d.name);
      const rowHeight = 1 / (maxRows + 1);
      
      annotations[`detection-${d.id}`] = {
        type: 'box',
        xMin: d.startIndex,
        xMax: d.endIndex,
        yMin: d.row * rowHeight,
        yMax: (d.row + 1) * rowHeight - 0.05,
        backgroundColor: `${color}99`,
        borderColor: `${color}`,
        borderWidth: 1,
        drawTime: 'beforeDatasetsDraw',
      };
    });

    return annotations;
  }, [rawData, detections, getApplianceColor]);

  // Chart options
  const options = useMemo(() => {
    if (!rawData?.data) return {};

    const now = new Date();
    const fortyEightHoursAgo = new Date(now.getTime() - 48 * 60 * 60 * 1000);
    const minIndex48h = rawData.data.findIndex(d => new Date(d.time) >= fortyEightHoursAgo);
    const initialMin = minIndex48h !== -1 ? minIndex48h : 0;
    const maxIndex48h = rawData.data.length - 1;

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
            onZoomComplete: handleZoomPanComplete,
          },
          pan: {
            enabled: true,
            mode: 'x',
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
      },
      scales: {
        y: {
          display: false,
          min: 0,
          max: 1,
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
            color: 'transparent',
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
          grid: {
            display: false,
          },
        },
      },
    };
  }, [rawData, handleZoomPanComplete]);

  // Update annotations
  useEffect(() => {
    if (!chartRef.current || !annotationsData) return;
    
    const chart = chartRef.current;
    if (chart.options?.plugins?.annotation) {
      chart.options.plugins.annotation.annotations = annotationsData;
      chart.update('none');
    }
  }, [annotationsData]);

  // Custom tooltip handling
  useEffect(() => {
    const canvas = chartRef.current?.canvas;
    if (!canvas || !rawData?.data) return;

    const handleTooltipMove = (e) => {
      const rect = canvas.getBoundingClientRect();
      const x = e.clientX - rect.left;
      
      const chart = chartRef.current;
      if (!chart?.scales?.x) return;

      const xScale = chart.scales.x;
      const dataIndex = Math.round(xScale.getValueForPixel(x));
      
      if (dataIndex >= 0 && dataIndex < rawData.data.length) {
        const dataPoint = rawData.data[dataIndex];
        const currentTime = new Date(dataPoint.time).getTime();
        
        const hoveredDetection = detections.find(d => {
          const startTime = new Date(d.start_time).getTime();
          const endTime = new Date(d.end_time).getTime();
          return currentTime >= startTime && currentTime <= endTime;
        });
        
        if (hoveredDetection) {
          const startDate = new Date(hoveredDetection.start_time);
          const endDate = new Date(hoveredDetection.end_time);
          const duration = (endDate - startDate) / 1000 / 60;
          
          setCustomTooltip({
            visible: true,
            x: e.clientX,
            y: e.clientY - 10,
            content: {
              name: hoveredDetection.name,
              startTime: startDate.toLocaleString('fr-FR'),
              endTime: endDate.toLocaleString('fr-FR'),
              duration: duration.toFixed(1),
              energy: hoveredDetection.energy_consumed?.toFixed(2) || 'N/A',
              validated: hoveredDetection.validated,
            },
          });
        } else {
          setCustomTooltip({ visible: false, x: 0, y: 0, content: null });
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
  }, [rawData, detections]);

  const chartData = useMemo(() => {
    if (!rawData?.data) return null;

    return {
      labels: rawData.data.map((d, index) => index),
      datasets: [{
        data: rawData.data.map(() => 0),
        backgroundColor: 'transparent',
      }],
    };
  }, [rawData]);

  if (!rawData || !chartData) return null;

  return (
    <>
      <Box sx={{ height: 100, position: 'relative', borderBottom: '1px solid rgba(0,0,0,0.1)' }}>
        <Typography 
          variant="caption" 
          sx={{ 
            position: 'absolute', 
            top: 4, 
            left: 8, 
            zIndex: 1, 
            fontWeight: 600,
            color: 'text.secondary',
          }}
        >
          Detections
        </Typography>
        <Bar ref={chartRef} data={chartData} options={options} />
      </Box>

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
          }}
        >
          <Typography variant="body2" sx={{ fontWeight: 600, mb: 0.5 }}>
            {customTooltip.content.name}
          </Typography>
          <Typography variant="caption" color="text.secondary" display="block">
            Debut: {customTooltip.content.startTime}
          </Typography>
          <Typography variant="caption" color="text.secondary" display="block">
            Fin: {customTooltip.content.endTime}
          </Typography>
          <Typography variant="caption" color="text.secondary" display="block">
            Duree: {customTooltip.content.duration} min
          </Typography>
          <Typography variant="caption" color="text.secondary" display="block">
            Energie: {customTooltip.content.energy} Wh
          </Typography>
          {customTooltip.content.validated !== undefined && (
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
                display: 'block',
              }}
            >
              {customTooltip.content.validated === true
                ? 'Valide'
                : customTooltip.content.validated === false
                ? 'Rejete'
                : 'En attente'}
            </Typography>
          )}
        </Box>
      )}
    </>
  );
};

export default DetectionsTimeline;
