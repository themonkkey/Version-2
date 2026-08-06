/* Swarna Andhra — MUI X Charts, bundled into one static file.
 *
 * The landing page is deliberately buildless: a folder of static assets, eleven
 * plain <script> tags, deployed by copying files. MUI is React, so instead of
 * migrating the whole page we mount React ONLY where a chart goes -- "islands".
 * The vanilla templates keep emitting HTML; they just leave a placeholder div
 * where a chart belongs, and this file fills it.
 *
 * Bundled rather than loaded from a CDN so the page keeps working with no
 * external dependency, no extra DNS/TLS round trip, and no version drift.
 *
 * Rebuild after changing this file:
 *     npm --prefix charts-src run build
 * and commit the built landing/assets/dash/mui-charts.js.
 */
import * as React from 'react';
import { createRoot } from 'react-dom/client';
import { BarChart } from '@mui/x-charts/BarChart';
import { LineChart } from '@mui/x-charts/LineChart';
import { PieChart } from '@mui/x-charts/PieChart';
import { SparkLineChart } from '@mui/x-charts/SparkLineChart';

const REGISTRY = { bar: BarChart, line: LineChart, pie: PieChart, spark: SparkLineChart };

/* The page is a dark glass surface, so MUI's light defaults would be invisible.
 * These are passed per-chart rather than via a ThemeProvider to keep the bundle
 * free of @mui/material's theming layer. */
const INK = 'rgba(255,255,255,.92)';
const INK_2 = 'rgba(255,255,255,.62)';
const INK_3 = 'rgba(255,255,255,.42)';
const HAIR = 'rgba(255,255,255,.14)';

const DARK_SX = {
  '& .MuiChartsAxis-line': { stroke: HAIR },
  '& .MuiChartsAxis-tick': { stroke: HAIR },
  '& .MuiChartsAxis-tickLabel': { fill: INK_3, fontSize: 11 },
  '& .MuiChartsAxis-label': { fill: INK_2 },
  '& .MuiChartsGrid-line': { stroke: HAIR, strokeDasharray: '0' },
  '& .MuiChartsLegend-series text': { fill: `${INK_2} !important`, fontSize: '12px !important' },
  '& .MuiChartsTooltip-root': { color: INK },
};

function mount(el) {
  if (el.dataset.muiMounted) return;
  let spec;
  try {
    spec = JSON.parse(el.getAttribute('data-mui-chart') || '{}');
  } catch (e) {
    return;                       // malformed spec: leave the placeholder empty
  }
  const Chart = REGISTRY[spec.type];
  if (!Chart) return;

  el.dataset.muiMounted = '1';
  const props = Object.assign({}, spec.props, {
    sx: Object.assign({}, DARK_SX, spec.props && spec.props.sx),
  });
  createRoot(el).render(React.createElement(Chart, props));
}

/* Called after every panel render, because the dashboard replaces innerHTML
 * wholesale and any previously mounted root goes with it. */
function mountAll(root) {
  const scope = root || document;
  scope.querySelectorAll('[data-mui-chart]').forEach(mount);
}

window.MUICharts = { mountAll, registry: Object.keys(REGISTRY) };

/* Anything already in the DOM at load time (the page renders a panel before this
 * script finishes parsing on a warm cache). */
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => mountAll());
} else {
  mountAll();
}
