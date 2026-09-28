// Pulls plot data out of a result JSON using the manifest's key paths. It only reads fields
// that exist; a missing or non-numeric field throws (the build fails instead of plotting a guess).
import type { HeatmapSpec, KeyPath, LineSpec, PlotSpec, ScatterSpec } from './manifest.ts';

export interface LineData {
  kind: 'line';
  xLabel: string;
  yLabel: string;
  x: number[];
  series: { label: string; y: number[] }[];
}
export interface HeatmapData {
  kind: 'heatmap';
  rowLabel: string;
  colLabel: string;
  valueLabel: string;
  rows: string[];
  cols: string[];
  values: number[][];
}
export interface ScatterData {
  kind: 'scatter';
  xLabel: string;
  yLabel: string;
  groupTitle: string;
  pointTitle: string;
  groups: { label: string; points: { label: string; x: number; y: number }[] }[];
}
export type PlotData = LineData | HeatmapData | ScatterData;

export class ExtractError extends Error {}

export function getPath(obj: unknown, path: KeyPath): unknown {
  let cur: unknown = obj;
  for (const k of path) {
    if (cur === null || typeof cur !== 'object' || !(k in (cur as Record<string, unknown>))) {
      throw new ExtractError(
        `missing field ${JSON.stringify(path)} (stopped at ${JSON.stringify(k)})`,
      );
    }
    cur = (cur as Record<string, unknown>)[k];
  }
  return cur;
}

function num(v: unknown, where: string): number {
  if (typeof v !== 'number' || !Number.isFinite(v))
    throw new ExtractError(`${where}: expected a finite number, got ${JSON.stringify(v)}`);
  return v;
}

function numArray(v: unknown, where: string): number[] {
  if (!Array.isArray(v)) throw new ExtractError(`${where}: expected an array`);
  return v.map((x, i) => num(x, `${where}[${i}]`));
}

function line(spec: LineSpec, json: unknown): LineData {
  const x = numArray(getPath(json, spec.x.path), JSON.stringify(spec.x.path));
  const series = spec.series.map((s) => {
    const y = numArray(getPath(json, s.path), JSON.stringify(s.path));
    if (y.length !== x.length)
      throw new ExtractError(
        `${JSON.stringify(s.path)}: length ${y.length} != x length ${x.length}`,
      );
    return { label: s.label, y };
  });
  return { kind: 'line', xLabel: spec.x.label, yLabel: spec.y.label, x, series };
}

function heatmap(spec: HeatmapSpec, json: unknown): HeatmapData {
  const base = getPath(json, spec.base);
  const values = spec.rows.values.map((r) =>
    spec.cols.values.map((c) => {
      const key = spec.key.replace('{row}', r).replace('{col}', c);
      return num(
        getPath(base, [key, spec.field]),
        `${JSON.stringify([...spec.base, key, spec.field])}`,
      );
    }),
  );
  return {
    kind: 'heatmap',
    rowLabel: spec.rows.label,
    colLabel: spec.cols.label,
    valueLabel: spec.value.label,
    rows: spec.rows.values,
    cols: spec.cols.values,
    values,
  };
}

function scatter(spec: ScatterSpec, json: unknown): ScatterData {
  const base = getPath(json, spec.base);
  const groups = spec.groups.map((g) => ({
    label: g,
    points: spec.keys.map((k) => ({
      label: spec.pointLabel.replace('{key}', k),
      x: num(getPath(base, [k, g, spec.x.field]), `${k}.${g}.${spec.x.field}`),
      y: num(getPath(base, [k, g, spec.y.field]), `${k}.${g}.${spec.y.field}`),
    })),
  }));
  return {
    kind: 'scatter',
    xLabel: spec.x.label,
    yLabel: spec.y.label,
    groupTitle: spec.groupTitle,
    pointTitle: spec.pointTitle,
    groups,
  };
}

export function extract(spec: PlotSpec, json: unknown): PlotData {
  switch (spec.kind) {
    case 'line':
      return line(spec, json);
    case 'heatmap':
      return heatmap(spec, json);
    case 'scatter':
      return scatter(spec, json);
  }
}
