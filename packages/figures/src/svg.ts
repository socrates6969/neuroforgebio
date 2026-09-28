// Server-side SVG renderers (pure string builders, no DOM). The output works with JS off.
// Colours come only from CSS classes that the figure component maps to semantic tokens.
// Every data mark carries data-readout (text shown on hover/keyboard) and data-i (order).
import type { HeatmapData, LineData, PlotData, ScatterData } from './extract.ts';

const W = 640;
const H = 400;
const M = { top: 20, right: 20, bottom: 56, left: 64 };

export const fmt = (v: number, digits = 4): string => {
  if (v === 0) return '0';
  const a = Math.abs(v);
  if (a >= 1e5 || a < 1e-3) return v.toExponential(digits - 1);
  return String(Number(v.toPrecision(digits)));
};

const esc = (s: string) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

export function niceTicks(min: number, max: number, count = 5): number[] {
  if (min === max) {
    min -= 1;
    max += 1;
  }
  const span = max - min;
  const step0 = span / Math.max(1, count);
  const mag = 10 ** Math.floor(Math.log10(step0));
  const norm = step0 / mag;
  const step = (norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * mag;
  const start = Math.ceil(min / step) * step;
  const out: number[] = [];
  for (let v = start; v <= max + step * 1e-9; v += step) out.push(Number(v.toPrecision(12)));
  return out;
}

function extent(vals: number[], pad = 0.05): [number, number] {
  let lo = Math.min(...vals);
  let hi = Math.max(...vals);
  if (lo === hi) {
    lo -= 1;
    hi += 1;
  }
  const p = (hi - lo) * pad;
  return [lo - p, hi + p];
}

const scale = (d0: number, d1: number, r0: number, r1: number) => (v: number) =>
  r0 + ((v - d0) / (d1 - d0)) * (r1 - r0);

function axes(
  xs: (v: number) => number,
  ys: (v: number) => number,
  xd: [number, number],
  yd: [number, number],
  xLabel: string,
  yLabel: string,
): string {
  const x0 = M.left,
    x1 = W - M.right,
    y0 = H - M.bottom,
    y1 = M.top;
  const xt = niceTicks(xd[0], xd[1], 6)
    .map(
      (t) =>
        `<g class="tick"><line x1="${xs(t)}" x2="${xs(t)}" y1="${y0}" y2="${y1}" class="grid"/><text x="${xs(t)}" y="${y0 + 18}" text-anchor="middle">${esc(fmt(t, 3))}</text></g>`,
    )
    .join('');
  const yt = niceTicks(yd[0], yd[1], 5)
    .map(
      (t) =>
        `<g class="tick"><line x1="${x0}" x2="${x1}" y1="${ys(t)}" y2="${ys(t)}" class="grid"/><text x="${x0 - 8}" y="${ys(t) + 4}" text-anchor="end">${esc(fmt(t, 3))}</text></g>`,
    )
    .join('');
  return (
    `<g class="axes">${xt}${yt}<line class="axis" x1="${x0}" x2="${x1}" y1="${y0}" y2="${y0}"/><line class="axis" x1="${x0}" x2="${x0}" y1="${y0}" y2="${y1}"/>` +
    `<text class="alabel" x="${(x0 + x1) / 2}" y="${H - 12}" text-anchor="middle">${esc(xLabel)}</text>` +
    `<text class="alabel" transform="translate(16 ${(y0 + y1) / 2}) rotate(-90)" text-anchor="middle">${esc(yLabel)}</text></g>`
  );
}

const MARKERS = ['circle', 'square', 'diamond'] as const;
function marker(kind: number, x: number, y: number, attrs: string): string {
  const m = MARKERS[kind % MARKERS.length];
  if (m === 'circle') return `<circle cx="${x}" cy="${y}" r="4.5" ${attrs}/>`;
  if (m === 'square') return `<rect x="${x - 4}" y="${y - 4}" width="8" height="8" ${attrs}/>`;
  return `<path d="M${x} ${y - 5.5}L${x + 5.5} ${y}L${x} ${y + 5.5}L${x - 5.5} ${y}Z" ${attrs}/>`;
}

function legend(labels: string[], kind: 'line' | 'point'): string {
  const items = labels
    .map((l, i) => {
      const x = M.left + 8 + i * 150;
      const sw =
        kind === 'line'
          ? `<line x1="${x}" x2="${x + 22}" y1="${M.top + 8}" y2="${M.top + 8}" class="ln s${i}"/>`
          : '';
      return `<g class="lg">${sw}${marker(i, x + 11, M.top + 8, `class="mk s${i}"`)}<text x="${x + 30}" y="${M.top + 12}">${esc(l)}</text></g>`;
    })
    .join('');
  return `<g class="legend" aria-hidden="true">${items}</g>`;
}

function renderLine(d: LineData): string {
  const all = d.series.flatMap((s) => s.y);
  const xd = extent(d.x, 0.03),
    yd = extent(all, 0.12);
  const xs = scale(xd[0], xd[1], M.left, W - M.right),
    ys = scale(yd[0], yd[1], H - M.bottom, M.top + 22);
  let i = 0;
  const body = d.series
    .map((s, si) => {
      const pts = d.x.map((x, k) => `${xs(x).toFixed(1)},${ys(s.y[k]).toFixed(1)}`).join(' ');
      const marks = d.x
        .map((x, k) =>
          marker(
            si,
            +xs(x).toFixed(1),
            +ys(s.y[k]).toFixed(1),
            `class="mk s${si}" data-i="${i++}" data-readout="${esc(`${s.label}: ${d.xLabel} = ${fmt(x)}, ${d.yLabel} = ${fmt(s.y[k])}`)}"`,
          ),
        )
        .join('');
      return `<g class="series"><polyline class="ln s${si}" points="${pts}"/>${marks}</g>`;
    })
    .join('');
  return (
    axes(xs, ys, xd, yd, d.xLabel, d.yLabel) +
    body +
    legend(
      d.series.map((s) => s.label),
      'line',
    )
  );
}

function renderScatter(d: ScatterData): string {
  const xsAll = d.groups.flatMap((g) => g.points.map((p) => p.x));
  const ysAll = d.groups.flatMap((g) => g.points.map((p) => p.y));
  const xd = extent(xsAll, 0.1),
    yd = extent(ysAll, 0.14);
  const xs = scale(xd[0], xd[1], M.left, W - M.right),
    ys = scale(yd[0], yd[1], H - M.bottom, M.top + 22);
  let i = 0;
  const body = d.groups
    .map(
      (g, gi) =>
        `<g class="group">${g.points
          .map((p) =>
            marker(
              gi,
              +xs(p.x).toFixed(1),
              +ys(p.y).toFixed(1),
              `class="mk s${gi}" data-i="${i++}" data-readout="${esc(`${g.label}, ${p.label}: ${d.xLabel} = ${fmt(p.x)}, ${d.yLabel} = ${fmt(p.y)}`)}"`,
            ),
          )
          .join('')}</g>`,
    )
    .join('');
  return (
    axes(xs, ys, xd, yd, d.xLabel, d.yLabel) +
    body +
    legend(
      d.groups.map((g) => g.label),
      'point',
    )
  );
}

function renderHeatmap(d: HeatmapData): string {
  const flat = d.values.flat();
  const lo = Math.min(...flat),
    hi = Math.max(...flat);
  const x0 = M.left + 10,
    x1 = W - M.right,
    y0 = M.top,
    y1 = H - M.bottom;
  const cw = (x1 - x0) / d.cols.length,
    ch = (y1 - y0) / d.rows.length;
  let i = 0;
  const cells = d.rows
    .map((r, ri) =>
      d.cols
        .map((c, ci) => {
          const v = d.values[ri][ci];
          const t = hi === lo ? 1 : (v - lo) / (hi - lo);
          const x = x0 + ci * cw,
            y = y0 + ri * ch;
          const label = `${d.rowLabel} = ${r}, ${d.colLabel} = ${c}: ${d.valueLabel} = ${fmt(v)}`;
          return (
            `<g class="cell"><rect class="hm mk" x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${(cw - 2).toFixed(1)}" height="${(ch - 2).toFixed(1)}" fill-opacity="${(0.08 + 0.92 * t).toFixed(3)}" data-i="${i++}" data-readout="${esc(label)}"/>` +
            `<text class="${t > 0.55 ? 'cv on' : 'cv'}" x="${(x + cw / 2 - 1).toFixed(1)}" y="${(y + ch / 2 + 4).toFixed(1)}" text-anchor="middle">${esc(fmt(v, 3))}</text></g>`
          );
        })
        .join(''),
    )
    .join('');
  const colT = d.cols
    .map(
      (c, ci) =>
        `<text x="${(x0 + ci * cw + cw / 2).toFixed(1)}" y="${y1 + 18}" text-anchor="middle">${esc(c)}</text>`,
    )
    .join('');
  const rowT = d.rows
    .map(
      (r, ri) =>
        `<text x="${x0 - 8}" y="${(y0 + ri * ch + ch / 2 + 4).toFixed(1)}" text-anchor="end">${esc(r)}</text>`,
    )
    .join('');
  return (
    `<g class="axes">${colT}${rowT}<text class="alabel" x="${(x0 + x1) / 2}" y="${H - 12}" text-anchor="middle">${esc(d.colLabel)}</text>` +
    `<text class="alabel" transform="translate(16 ${(y0 + y1) / 2}) rotate(-90)" text-anchor="middle">${esc(d.rowLabel)}</text></g>${cells}`
  );
}

/** Full <svg> markup. `labelId` points at the element holding the accessible name. */
export function renderSvg(d: PlotData, opts: { ariaLabel: string }): string {
  const inner =
    d.kind === 'line' ? renderLine(d) : d.kind === 'scatter' ? renderScatter(d) : renderHeatmap(d);
  return `<svg class="nf-plot-svg nf-plot-${d.kind}" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(opts.ariaLabel)}" preserveAspectRatio="xMidYMid meet">${inner}</svg>`;
}

/** Rows for the accessible data table that accompanies every figure. */
export function tableRows(d: PlotData): { head: string[]; rows: string[][] } {
  if (d.kind === 'line')
    return {
      head: [d.xLabel, ...d.series.map((s) => s.label)],
      rows: d.x.map((x, k) => [fmt(x), ...d.series.map((s) => fmt(s.y[k]))]),
    };
  if (d.kind === 'scatter')
    return {
      head: [d.groupTitle, d.pointTitle, d.xLabel, d.yLabel],
      rows: d.groups.flatMap((g) => g.points.map((p) => [g.label, p.label, fmt(p.x), fmt(p.y)])),
    };
  return {
    head: [`${d.rowLabel} \\ ${d.colLabel}`, ...d.cols],
    rows: d.rows.map((r, ri) => [r, ...d.values[ri].map((v) => fmt(v))]),
  };
}
