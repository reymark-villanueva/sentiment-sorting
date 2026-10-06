/**
 * Isabela State University - Cauayan Campus Library
 * Renders the "Sentiment Trends Over Time" line chart from real,
 * server-computed bucketed data (see admin_dashboard() / trend_points).
 */

document.addEventListener('DOMContentLoaded', () => {
  const svg = document.getElementById('isuTrendChart');
  const dataEl = document.getElementById('isu-trend-data');
  if (!svg || !dataEl) return;

  let points;
  try {
    points = JSON.parse(dataEl.textContent);
  } catch (err) {
    return;
  }
  if (!points || !points.length) return;

  const NS = 'http://www.w3.org/2000/svg';
  const X_START = 70;
  const X_END = 500;
  const Y_TOP = 20;
  const Y_BOTTOM = 150;

  const stepX = points.length > 1 ? (X_END - X_START) / (points.length - 1) : 0;
  const xAt = (i) => X_START + stepX * i;
  const yAt = (pct) => Y_BOTTOM - (Math.max(0, Math.min(100, pct)) / 100) * (Y_BOTTOM - Y_TOP);

  function el(tag, attrs) {
    const node = document.createElementNS(NS, tag);
    Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, v));
    return node;
  }

  // Grid lines
  [0, 50, 100].forEach((pct) => {
    svg.appendChild(el('line', {
      x1: X_START, y1: yAt(pct), x2: X_END, y2: yAt(pct),
      stroke: pct === 0 ? '#e2ece7' : '#f0f4f2', 'stroke-width': pct === 0 ? 1.2 : 1,
    }));
    svg.appendChild(el('text', {
      x: X_START - 8, y: yAt(pct) + 4, 'font-size': 10, fill: '#849990', 'text-anchor': 'end',
    })).textContent = `${pct}%`;
  });

  // X axis labels
  points.forEach((p, i) => {
    svg.appendChild(el('text', {
      x: xAt(i), y: 170, 'font-size': 10, fill: '#849990', 'text-anchor': 'middle',
    })).textContent = p.label;
  });

  function drawSeries(key, color, width) {
    const path = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${xAt(i)} ${yAt(p[key])}`).join(' ');
    svg.appendChild(el('path', {
      d: path, fill: 'none', stroke: color, 'stroke-width': width, 'stroke-linecap': 'round',
    }));
    points.forEach((p, i) => {
      const isLast = i === points.length - 1;
      svg.appendChild(el('circle', {
        cx: xAt(i), cy: yAt(p[key]), r: isLast ? 4.5 : 3.5,
        fill: isLast ? color : '#ffffff', stroke: color, 'stroke-width': 2,
      }));
    });
  }

  drawSeries('positive', getComputedColor('--color-positive', '#3d8758'), 3);
  drawSeries('neutral', getComputedColor('--color-neutral-sentiment', '#ffcd09'), 2.5);
  drawSeries('negative', getComputedColor('--color-negative', '#ef4444'), 2.2);

  function getComputedColor(varName, fallback) {
    const value = getComputedStyle(document.documentElement).getPropertyValue(varName);
    return value ? value.trim() : fallback;
  }
});
