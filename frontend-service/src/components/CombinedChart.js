import { Box } from "@mui/material";
import { useTheme } from "@mui/material/styles";
import {
  CategoryScale,
  Chart as ChartJS,
  Decimation,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  TimeScale,
  Title,
  Tooltip,
} from "chart.js";
import "chartjs-adapter-date-fns";
import annotationPlugin from "chartjs-plugin-annotation";
import zoomPlugin from "chartjs-plugin-zoom";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Line } from "react-chartjs-2";
import { useApplianceColors } from "../context/ApplianceColorsContext";
import { useData } from "../context/DataContext";
import {
  formatDateFull,
  formatDateTime,
  formatDayName,
  formatDurationMinutes,
  formatHumanizedDate,
  formatTimeOnly,
} from "../utils/dateUtils";

ChartJS.register(
  CategoryScale,
  LinearScale,
  TimeScale,
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

const CombinedChart = ({
  rawData,
  detections,
  signatures,
  onSignatureModalOpen,
  isModalOpen,
}) => {
  const theme = useTheme();
  const chartRef = useRef(null);
  const { zoomState, setZoomState, setVisibleTimeRange } = useData();
  const { getApplianceColor, getApplianceIcon } = useApplianceColors();
  const [isSelecting, setIsSelecting] = useState(false);
  const [selectionStart, setSelectionStart] = useState(null);
  const [selectionEnd, setSelectionEnd] = useState(null);
  const selectionRef = useRef({ isSelecting: false, startX: null, endX: null });
  const isUpdatingZoomRef = useRef(false);
  const tooltipRef = useRef(null);

  // Custom plugin to draw horizontal Y-axis labels
  const horizontalYLabelsPlugin = useMemo(
    () => ({
      id: "horizontalYLabels",
      afterDraw: (chart) => {
        const ctx = chart.ctx;
        const chartArea = chart.chartArea;

        // Draw "Signatures" label
        const ySignaturesScale = chart.scales.ySignatures;
        if (ySignaturesScale) {
          const yPos = (ySignaturesScale.top + ySignaturesScale.bottom) / 2;
          ctx.save();
          ctx.font = "400 11px sans-serif";
          ctx.fillStyle = theme.palette.text.tertiary;
          ctx.textAlign = "right";
          ctx.textBaseline = "middle";
          ctx.fillText("Signatures", chartArea.left - 10, yPos);
          ctx.restore();
        }

        // Draw "Detections" label
        const yDetectionsScale = chart.scales.yDetections;
        if (yDetectionsScale) {
          const yPos = (yDetectionsScale.top + yDetectionsScale.bottom) / 2;
          ctx.save();
          ctx.font = "400 11px sans-serif";
          ctx.fillStyle = theme.palette.text.tertiary;
          ctx.textAlign = "right";
          ctx.textBaseline = "middle";
          ctx.fillText("Detections", chartArea.left - 10, yPos);
          ctx.restore();
        }
      },
    }),
    [theme]
  );

  // Custom tooltip handler for annotations
  useEffect(() => {
    const canvas = chartRef.current?.canvas;
    if (!canvas || !rawData?.data) return;

    // Create tooltip element if it doesn't exist
    if (!tooltipRef.current) {
      const tooltip = document.createElement("div");
      tooltip.style.position = "absolute";
      tooltip.style.pointerEvents = "none";
      tooltip.style.opacity = "0";
      tooltip.style.transition = "opacity 0.2s ease";
      tooltip.style.zIndex = "10000";
      tooltip.style.padding = "12px";
      tooltip.style.backgroundColor = theme.palette.overlay.white[95];
      tooltip.style.borderRadius = "6px";
      tooltip.style.boxShadow = theme.palette.utility.tooltip.shadow;
      tooltip.style.fontSize = "14px";
      tooltip.style.lineHeight = "1.6";
      tooltip.style.minWidth = "250px";
      document.body.appendChild(tooltip);
      tooltipRef.current = tooltip;
    }

    const handleMouseMove = (e) => {
      const chart = chartRef.current;
      if (!chart) return;

      const rect = canvas.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      // Get the annotations
      const annotations =
        chart.config?.options?.plugins?.annotation?.annotations;
      if (!annotations) return;

      let foundTooltipData = null;

      // Check if mouse is over any annotation
      for (const key in annotations) {
        const annotation = annotations[key];
        if (annotation.type === "box" && annotation.tooltipData) {
          const xScale = chart.scales.x;
          const yScale = chart.scales[annotation.yScaleID];

          if (xScale && yScale) {
            const xMin = xScale.getPixelForValue(annotation.xMin);
            const xMax = xScale.getPixelForValue(annotation.xMax);
            const yMin = yScale.getPixelForValue(annotation.yMax); // Inverted for canvas
            const yMax = yScale.getPixelForValue(annotation.yMin); // Inverted for canvas

            if (x >= xMin && x <= xMax && y >= yMin && y <= yMax) {
              foundTooltipData = annotation.tooltipData;
              break;
            }
          }
        }
      }

      // If not over an annotation, check if over the chart data
      if (!foundTooltipData) {
        const xScale = chart.scales.x;
        const yScale = chart.scales.yConsumption;

        if (xScale && yScale) {
          const dataIndex = Math.round(xScale.getValueForPixel(x));

          if (dataIndex >= 0 && dataIndex < rawData.data.length) {
            const dataPoint = rawData.data[dataIndex];

            // Check if mouse is near the data point (within chart area)
            const chartArea = chart.chartArea;
            if (
              x >= chartArea.left &&
              x <= chartArea.right &&
              y >= chartArea.top &&
              y <= chartArea.bottom
            ) {
              foundTooltipData = {
                type: "consumption",
                time: new Date(dataPoint.time),
                power: dataPoint.avg_papp,
              };
            }
          }
        }
      }

      const tooltip = tooltipRef.current;
      if (foundTooltipData) {
        // Build tooltip HTML based on type
        let html = "";

        if (foundTooltipData.type === "detection") {
          html = `
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 10px;">
              <span class="material-symbols-outlined" style="font-size: 36px; color: ${
                foundTooltipData.color
              }; flex-shrink: 0;">
                ${foundTooltipData.icon || "power"}
              </span>
              <strong style="color: ${
                foundTooltipData.color
              }; font-size: 16px;">${foundTooltipData.name}</strong>
              <div style="font-size: 14px;">
              à <strong>${formatTimeOnly(
                foundTooltipData.startTime
              )}</strong> pendant <strong>${formatDurationMinutes(
            foundTooltipData.durationSeconds
          )}min</strong>
            </div>
            </div>
            
            <div style="color: ${
              theme.palette.text.tertiary
            }; font-size: 12px; font-weight: 300;">
              ${formatHumanizedDate(
                foundTooltipData.startTime
              )} (${formatDateTime(
            foundTooltipData.startTime
          )} - ${formatTimeOnly(foundTooltipData.endTime)})
            </div>
            <div style="color: ${
              theme.palette.text.tertiary
            }; font-size: 12px; margin-top: 6px;">
              Confiance: ${Math.round(foundTooltipData.confidenceScore * 100)}%
            </div>
          `;
          tooltip.style.borderLeft = `4px solid ${foundTooltipData.color}`;
        } else if (foundTooltipData.type === "signature") {
          html = `
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 10px;">
              <span class="material-symbols-outlined" style="font-size: 36px; color: ${
                foundTooltipData.isNegative
                  ? theme.palette.chart.negativeSignature.main
                  : foundTooltipData.color
              }; flex-shrink: 0;">
                ${foundTooltipData.icon || "power"}
              </span>
              <strong style="color: ${
                foundTooltipData.isNegative
                  ? theme.palette.chart.negativeSignature.main
                  : foundTooltipData.color
              }; font-size: 16px;">${foundTooltipData.name}</strong>
              <div style="font-size: 14px;">
              à <strong>${formatTimeOnly(
                foundTooltipData.startTime
              )}</strong> pendant <strong>${formatDurationMinutes(
            foundTooltipData.durationSeconds
          )}min</strong>
            </div>
            </div>
            <div style="color: ${
              theme.palette.text.tertiary
            }; font-size: 12px; font-weight: 300;">
              ${formatHumanizedDate(
                foundTooltipData.startTime
              )} (${formatDateTime(
            foundTooltipData.startTime
          )} - ${formatTimeOnly(foundTooltipData.endTime)})
            </div>
            ${
              foundTooltipData.isNegative
                ? `<div style="color: ${theme.palette.chart.negativeSignature.main}; font-size: 12px; margin-top: 6px; font-style: italic;">Issue d'une détection déclarée comme incorrecte par l'utilisateur.<br/>Elle aide le modèle IA à apprendre de ses erreurs.</div>`
                : ""
            }
          `;
          tooltip.style.borderLeft = `4px solid ${
            foundTooltipData.isNegative
              ? theme.palette.chart.negativeSignature.main
              : foundTooltipData.color
          }`;
        } else if (foundTooltipData.type === "consumption") {
          const dayName = formatDayName(foundTooltipData.time);
          const formattedDate = formatDateFull(foundTooltipData.time);
          const formattedTime = formatTimeOnly(foundTooltipData.time);
          const powerW = Math.round(foundTooltipData.power);

          html = `
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 10px;">
              <strong style="color: ${theme.palette.chart.consumption.main}; font-size: 16px;">Consommation</strong><strong style="color: ${theme.palette.text.tertiary}; font-size: 16px;"> ${powerW} W</strong>
            </div>
            <div style="color: ${theme.palette.text.tertiary}; font-size: 12px; font-weight: 300; text-transform: capitalize;">
              ${dayName} ${formattedDate} à ${formattedTime}
            </div>
          `;
          tooltip.style.borderLeft = `4px solid ${theme.palette.chart.consumption.main}`;
        }

        tooltip.innerHTML = html;
        tooltip.style.left = `${e.pageX + 15}px`;
        tooltip.style.top = `${e.pageY - 10}px`;
        tooltip.style.opacity = "1";
      } else {
        tooltip.style.opacity = "0";
      }
    };

    const handleMouseLeave = () => {
      const tooltip = tooltipRef.current;
      if (tooltip) {
        tooltip.style.opacity = "0";
      }
    };

    canvas.addEventListener("mousemove", handleMouseMove);
    canvas.addEventListener("mouseleave", handleMouseLeave);

    return () => {
      canvas.removeEventListener("mousemove", handleMouseMove);
      canvas.removeEventListener("mouseleave", handleMouseLeave);
      if (tooltipRef.current) {
        document.body.removeChild(tooltipRef.current);
        tooltipRef.current = null;
      }
    };
  }, [rawData]); // eslint-disable-line react-hooks/exhaustive-deps

  // Hide tooltip when modal is open
  useEffect(() => {
    if (isModalOpen && tooltipRef.current) {
      tooltipRef.current.style.opacity = "0";
    }
  }, [isModalOpen]);

  // Synchronize zoom from context
  useEffect(() => {
    if (!chartRef.current || isUpdatingZoomRef.current) return;
    if (zoomState.min === null || zoomState.max === null) return;

    const chart = chartRef.current;
    if (chart.options?.scales?.x) {
      chart.options.scales.x.min = zoomState.min;
      chart.options.scales.x.max = zoomState.max;
      chart.update("none");
    }
  }, [zoomState]);

  // Handle zoom/pan complete
  const handleZoomPanComplete = useCallback(() => {
    if (!chartRef.current || !rawData?.data) return;

    const chart = chartRef.current;
    if (chart.scales?.x) {
      const visibleMin = Math.max(0, Math.floor(chart.scales.x.min || 0));
      const visibleMax = Math.min(
        rawData.data.length - 1,
        Math.ceil(chart.scales.x.max || rawData.data.length - 1)
      );

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

      sorted.forEach((item) => {
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
        .filter((d) => d.start_time && d.end_time && d.name)
        .map((d) => {
          const startTime = new Date(d.start_time).getTime();
          const endTime = new Date(d.end_time).getTime();
          const startIndex = rawData.data.findIndex(
            (dt) => new Date(dt.time).getTime() >= startTime
          );
          const endIndex = rawData.data.findIndex(
            (dt) => new Date(dt.time).getTime() >= endTime
          );

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

      detectionItems.forEach((d) => {
        const color = getApplianceColor(d.appliance_id || d.name);
        const icon = getApplianceIcon(d.appliance_id || d.name);
        const rowHeight = 1 / maxDetectionRows;

        const startTime = new Date(d.start_time);
        const endTime = new Date(d.end_time);
        const durationSeconds = Math.round((endTime - startTime) / 1000);
        const confidenceScore = d.confidence_score || 0;

        annotations[`detection-${d.id}`] = {
          type: "box",
          xMin: d.startIndex,
          xMax: d.endIndex,
          yMin: d.row * rowHeight + 0.05,
          yMax: (d.row + 1) * rowHeight - 0.05,
          yScaleID: "yDetections",
          backgroundColor: `${color}`,
          borderColor: color,
          borderWidth: 5,
          borderRadius: 10,
          drawTime: "beforeDatasetsDraw",
          // Store tooltip data
          tooltipData: {
            type: "detection",
            name: d.name || "Inconnu",
            startTime,
            endTime,
            durationSeconds,
            confidenceScore,
            color,
            icon,
          },
        };
      });
    }

    // Signatures annotations (on ySignatures scale, 0-1)
    if (signatures && signatures.length > 0) {
      const signatureItems = signatures
        .filter((s) => s.start_time && s.end_time && s.appliance_name)
        .map((s) => {
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

      signatureItems.forEach((s) => {
        const color = getApplianceColor(s.appliance_id || s.appliance_name);
        const icon = getApplianceIcon(s.appliance_id || s.appliance_name);
        const isNegative = s.is_negative === true;
        const rowHeight = 1 / maxSignatureRows;

        const startTime = new Date(s.start_time);
        const endTime = new Date(s.end_time);
        const durationSeconds =
          s.duration_seconds || Math.round((endTime - startTime) / 1000);

        annotations[`signature-${s.id}`] = {
          type: "box",
          xMin: s.startIndex,
          xMax: s.endIndex,
          yMin: s.row * rowHeight + 0.05,
          yMax: (s.row + 1) * rowHeight - 0.05,
          yScaleID: "ySignatures",
          backgroundColor: `${color}`,
          borderColor: isNegative
            ? theme.palette.chart.negativeSignature.border
            : color,
          borderWidth: isNegative ? 3 : 5,
          borderRadius: 10,
          drawTime: "beforeDatasetsDraw",
          // Store tooltip data
          tooltipData: {
            type: "signature",
            name: s.appliance_name,
            startTime,
            endTime,
            durationSeconds,
            color,
            isNegative,
            icon,
          },
        };
      });
    }

    return annotations;
  }, [
    rawData,
    detections,
    signatures,
    getApplianceColor,
    getApplianceIcon,
    theme,
  ]);

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

      if (
        startIndex >= 0 &&
        endIndex >= 0 &&
        startIndex < rawData.data.length &&
        endIndex < rawData.data.length
      ) {
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

    canvas.addEventListener("contextmenu", handleContextMenu);
    canvas.addEventListener("mousedown", handleMouseDown);
    canvas.addEventListener("mousemove", handleMouseMove);
    canvas.addEventListener("mouseup", handleMouseUp);
    canvas.addEventListener("mouseleave", handleMouseLeave);

    return () => {
      canvas.removeEventListener("contextmenu", handleContextMenu);
      canvas.removeEventListener("mousedown", handleMouseDown);
      canvas.removeEventListener("mousemove", handleMouseMove);
      canvas.removeEventListener("mouseup", handleMouseUp);
      canvas.removeEventListener("mouseleave", handleMouseLeave);
    };
  }, [rawData, onSignatureModalOpen]);

  // Update annotations
  useEffect(() => {
    if (!chartRef.current || !annotationsData) return;

    const chart = chartRef.current;
    if (chart.options?.plugins?.annotation) {
      chart.options.plugins.annotation.annotations = annotationsData;
      chart.update("none");
    }
  }, [annotationsData]);

  // Chart data with 3 datasets (one per Y axis)
  const chartData = useMemo(() => {
    if (!rawData || !rawData.data || rawData.data.length === 0) {
      return null;
    }

    const labels = rawData.data.map((d, index) => index);
    const powerData = rawData.data.map((d) => d.avg_papp);

    return {
      labels,
      datasets: [
        // Signatures dataset (invisible, just for ySignatures scale) - Will be at bottom
        {
          label: "Signatures",
          data: rawData.data.map(() => 0),
          yAxisID: "ySignatures",
          borderColor: "transparent",
          backgroundColor: "transparent",
          pointRadius: 0,
          pointHoverRadius: 0,
        },
        // Consumption dataset (main) - Will be in middle
        {
          label: "Puissance moyenne (W)",
          data: powerData,
          yAxisID: "yConsumption",
          borderColor: theme.palette.chart.consumption.main,
          backgroundColor: theme.palette.chart.consumption.background,
          fill: true,
          borderWidth: 0,
          tension: 0.4,
          pointRadius: 0,
          pointHoverRadius: 0,
        },
        // Detections dataset (invisible, just for yDetections scale) - Will be at top
        {
          label: "Detections",
          data: rawData.data.map(() => 0),
          yAxisID: "yDetections",
          borderColor: "transparent",
          backgroundColor: "transparent",
          pointRadius: 0,
          pointHoverRadius: 0,
        },
      ],
    };
  }, [rawData, theme]);

  // Chart options
  const options = useMemo(() => {
    if (!rawData || !rawData.data) return {};

    const now = new Date();
    const fortyEightHoursAgo = new Date(now.getTime() - 48 * 60 * 60 * 1000);
    const minIndex48h = rawData.data.findIndex(
      (d) => new Date(d.time) >= fortyEightHoursAgo
    );
    const maxIndex48h = rawData.data.length - 1;
    const initialMin = minIndex48h !== -1 ? minIndex48h : 0;

    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: {
        mode: "index",
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
          drawTime: "beforeDatasetsDraw",
        },
        legend: { display: false },
        title: { display: false },
        tooltip: { enabled: false },
        zoom: {
          zoom: {
            wheel: { enabled: true, speed: 0.1 },
            pinch: { enabled: true },
            mode: "x",
            scaleMode: "x",
            onZoomComplete: handleZoomPanComplete,
          },
          pan: {
            enabled: true,
            mode: "x",
            scaleMode: "x",
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
          algorithm: "lttb",
          samples: 1000,
        },
      },
      scales: {
        // Signatures Y axis (bottom, 15% height)
        ySignatures: {
          type: "linear",
          position: "left",
          min: 0,
          max: 1,
          display: true,
          title: {
            display: false,
          },
          stack: "demo",
          stackWeight: 1,
          grid: { display: false },
          ticks: { display: false },
          border: { display: false },
        },
        // Consumption Y axis (middle, 70% height)
        yConsumption: {
          type: "linear",
          position: "left",
          beginAtZero: true,
          display: true,
          title: {
            display: true,
            text: "Puissance (W)",
            font: { size: 12, weight: 600 },
          },
          stack: "demo",
          stackWeight: 7,
          grid: { drawOnChartArea: true },
        },
        // Detections Y axis (top, 15% height)
        yDetections: {
          type: "linear",
          position: "left",
          min: 0,
          max: 1,
          display: true,
          title: {
            display: false,
          },
          stack: "demo",
          stackWeight: 1,
          grid: { display: false },
          ticks: { display: false },
          border: { display: false },
        },
        x: {
          min: initialMin,
          max: maxIndex48h,
          type: "linear",
          title: { display: false },
          ticks: {
            maxRotation: 0,
            minRotation: 0,
            autoSkip: true,
            maxTicksLimit: 20,
            callback: (value) => {
              if (rawData?.data && rawData.data[Math.floor(value)]) {
                const date = new Date(rawData.data[Math.floor(value)].time);

                // Round to nearest appropriate time unit based on zoom level
                const totalPoints = rawData.data.length;
                const visiblePoints =
                  (chartRef.current?.scales?.x?.max || maxIndex48h) -
                  (chartRef.current?.scales?.x?.min || initialMin);
                const zoomRatio = visiblePoints / totalPoints;

                let roundedDate = new Date(date);

                // If zoomed out (>50% of data visible), round to hours
                if (zoomRatio > 0.5) {
                  roundedDate.setMinutes(0, 0, 0);
                }
                // If medium zoom (10-50% visible), round to 15 minutes
                else if (zoomRatio > 0.1) {
                  const minutes =
                    Math.round(roundedDate.getMinutes() / 15) * 15;
                  roundedDate.setMinutes(minutes, 0, 0);
                }
                // If zoomed in (<10% visible), round to 5 minutes
                else {
                  const minutes = Math.round(roundedDate.getMinutes() / 5) * 5;
                  roundedDate.setMinutes(minutes, 0, 0);
                }

                const dayName = formatDayName(roundedDate);
                const day = String(roundedDate.getDate()).padStart(2, "0");
                const month = String(roundedDate.getMonth() + 1).padStart(
                  2,
                  "0"
                );
                const hours = String(roundedDate.getHours()).padStart(2, "0");
                const minutes = String(roundedDate.getMinutes()).padStart(
                  2,
                  "0"
                );

                return [`${dayName} ${day}.${month}`, `${hours}:${minutes}`];
              }
              return "";
            },
          },
        },
      },
    };
  }, [handleZoomPanComplete, rawData]);

  if (!rawData || !chartData) return null;

  return (
    <Box
      sx={{ height: 600, position: "relative" }}
      onContextMenu={(e) => e.preventDefault()}
    >
      <Line
        ref={chartRef}
        data={chartData}
        options={options}
        plugins={[horizontalYLabelsPlugin]}
      />

      {isSelecting && selectionStart !== null && selectionEnd !== null && (
        <Box
          sx={{
            position: "absolute",
            top: 0,
            left: Math.min(selectionStart, selectionEnd),
            width: Math.abs(selectionEnd - selectionStart),
            height: "100%",
            backgroundColor: (theme) =>
              theme.palette.chart.selection.background,
            border: (theme) =>
              `2px solid ${theme.palette.chart.selection.border}`,
            pointerEvents: "none",
            zIndex: 1000,
          }}
        />
      )}
    </Box>
  );
};

export default CombinedChart;
