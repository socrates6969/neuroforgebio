// Neural Playground data loader: validates the precomputed asset written by tools/playground
// (schema nf-playground/2: the compact, lossless form of /1) and turns it into typed arrays. Pure functions only,
// shared by the browser bundle, the Astro page (build-time tables) and test/playground.test.mjs.
// Positions in the asset are integers in 1/posScale mm; everything returned here is in mm.

export const SCHEMA = 'nf-playground/1';
/** Compact form written by tools/playground/nf_playground/encode.py: integer series as differences. */
export const SCHEMA_COMPACT = 'nf-playground/2';

export class PlaygroundDataError extends Error {}

const fail = (msg) => {
  throw new PlaygroundDataError(`playground asset: ${msg}`);
};
const isInt = (v) => Number.isInteger(v);
const isNum = (v) => typeof v === 'number' && Number.isFinite(v);

function intArray(v, what) {
  if (!Array.isArray(v) || !v.every(isInt)) fail(`${what} must be an array of integers`);
  return v;
}

/**
 * @typedef {{ posR2: number, velR2: number, posR2Mean: number, posR2Min: number, posR2Max: number, subsets: number }} Result
 * @typedef {{ ms: Int32Array, level: Uint8Array }} NoiseSpikes
 * @typedef {{
 *   reach: number, durationMs: number, bins: number, target: [number, number],
 *   truePos: Float32Array, spikes: Int32Array[], noise: NoiseSpikes[],
 *   decoded: Record<string, Float32Array[][]>
 * }} Trial
 * @typedef {{
 *   dataset: Record<string, any>, method: Record<string, any>, neuronCounts: number[],
 *   noiseHz: number[], decoders: string[], unitOrder: number[], unitElectrode: number[], electrodes: number, units: number, binMs: number,
 *   bounds: { min: [number, number], max: [number, number] },
 *   results: Record<string, Result[][]>, trials: Trial[]
 * }} Playground
 */

/**
 * Validate a parsed asset and convert it. Throws PlaygroundDataError on any shape problem.
 * @param {any} raw
 * @returns {Playground}
 */
export function parsePlayground(raw) {
  if (!raw || typeof raw !== 'object') fail('not an object');
  if (raw.schema === SCHEMA_COMPACT) raw = expandCompact(raw);
  if (raw.schema !== SCHEMA) fail(`schema must be ${SCHEMA}, got ${raw.schema}`);
  const { dataset, method, neuronCounts, noiseHz, decoders, unitOrder, bounds, results } = raw;
  for (const k of ['dandiset', 'version', 'doi', 'licence', 'citation', 'sha256'])
    if (typeof dataset?.[k] !== 'string' || !dataset[k]) fail(`dataset.${k} missing`);
  if (!/^[0-9a-f]{64}$/.test(dataset.sha256)) fail('dataset.sha256 is not a sha256');
  const units = dataset.units;
  if (!isInt(units) || units < 1) fail('dataset.units must be a positive integer');
  const binMs = method?.binMs;
  if (!isInt(binMs) || binMs <= 0) fail('method.binMs must be a positive integer');
  const posScale = raw.posScale;
  if (!isNum(posScale) || posScale <= 0) fail('posScale must be positive');

  intArray(neuronCounts, 'neuronCounts');
  if (
    !neuronCounts.length ||
    neuronCounts.some((n, i) => n < 1 || n > units || (i && n <= neuronCounts[i - 1]))
  )
    fail('neuronCounts must be increasing and within 1..units');
  if (!Array.isArray(noiseHz) || !noiseHz.length || !noiseHz.every(isNum) || noiseHz[0] !== 0)
    fail('noiseHz must be numbers starting at 0');
  if (!Array.isArray(decoders) || !decoders.length || !decoders.every((d) => typeof d === 'string'))
    fail('decoders must be a list of names');
  intArray(unitOrder, 'unitOrder');
  if (
    unitOrder.length !== units ||
    new Set(unitOrder).size !== units ||
    unitOrder.some((u) => u < 0 || u >= units)
  )
    fail('unitOrder must be a permutation of the units');

  const electrodes = raw.electrodes;
  if (!isInt(electrodes) || electrodes < 1) fail('electrodes must be a positive integer');
  intArray(raw.unitElectrode, 'unitElectrode');
  if (raw.unitElectrode.length !== units || raw.unitElectrode.some((e) => e < 1 || e > electrodes))
    fail('unitElectrode must give an electrode id in 1..electrodes for every unit');

  const nc = neuronCounts.length;
  const nn = noiseHz.length;
  for (const d of decoders) {
    const grid = results?.[d];
    if (!Array.isArray(grid) || grid.length !== nc) fail(`results.${d} must have ${nc} rows`);
    grid.forEach((row, ci) => {
      if (!Array.isArray(row) || row.length !== nn)
        fail(`results.${d}[${ci}] must have ${nn} cells`);
      for (const cell of row)
        for (const k of ['posR2', 'velR2', 'posR2Mean', 'posR2Min', 'posR2Max'])
          if (!isNum(cell?.[k]) || cell[k] > 1)
            fail(`results.${d}[${ci}] ${k} must be a number <= 1`);
    });
  }

  const mm = (v) => v / posScale;
  const b = bounds ?? {};
  if (!Array.isArray(b.min) || !Array.isArray(b.max) || b.min.length !== 2 || b.max.length !== 2)
    fail('bounds must have min/max pairs');

  if (!Array.isArray(raw.trials) || !raw.trials.length) fail('trials missing');
  const trials = raw.trials.map((t, ti) => {
    const w = `trials[${ti}]`;
    if (!isInt(t.bins) || t.bins < 2) fail(`${w}.bins must be >= 2`);
    if (t.durationMs !== t.bins * binMs) fail(`${w}.durationMs must equal bins * binMs`);
    const truePos = intArray(t.truePos, `${w}.truePos`);
    if (truePos.length !== 2 * t.bins) fail(`${w}.truePos must hold 2 values per bin`);
    if (!Array.isArray(t.spikes) || t.spikes.length !== units)
      fail(`${w}.spikes must list every unit`);
    const spikes = t.spikes.map((s, u) => {
      intArray(s, `${w}.spikes[${u}]`);
      if (s.some((ms) => ms < 0 || ms > t.durationMs)) fail(`${w}.spikes[${u}] outside the trial`);
      return Int32Array.from(s);
    });
    if (!Array.isArray(t.noiseSpikes) || t.noiseSpikes.length !== units)
      fail(`${w}.noiseSpikes must list every unit`);
    const noise = t.noiseSpikes.map((pairs, u) => {
      intArray(pairs, `${w}.noiseSpikes[${u}]`);
      if (pairs.length % 2) fail(`${w}.noiseSpikes[${u}] must hold (ms, level) pairs`);
      const k = pairs.length / 2;
      const ms = new Int32Array(k);
      const level = new Uint8Array(k);
      for (let i = 0; i < k; i++) {
        ms[i] = pairs[2 * i];
        level[i] = pairs[2 * i + 1];
        if (level[i] < 1 || level[i] >= nn) fail(`${w}.noiseSpikes[${u}] level out of range`);
        if (ms[i] < 0 || ms[i] > t.durationMs) fail(`${w}.noiseSpikes[${u}] outside the trial`);
      }
      return { ms, level };
    });
    /** @type {Record<string, Float32Array[][]>} */
    const decoded = {};
    for (const d of decoders) {
      const grid = t.decoded?.[d];
      if (!Array.isArray(grid) || grid.length !== nc)
        fail(`${w}.decoded.${d} must have ${nc} rows`);
      decoded[d] = grid.map((row, ci) => {
        if (!Array.isArray(row) || row.length !== nn)
          fail(`${w}.decoded.${d}[${ci}] must have ${nn} cells`);
        return row.map((path, ni) => {
          intArray(path, `${w}.decoded.${d}[${ci}][${ni}]`);
          if (path.length !== 2 * t.bins)
            fail(`${w}.decoded.${d}[${ci}][${ni}] must hold 2 values per bin`);
          return Float32Array.from(path, mm);
        });
      });
    }
    return {
      reach: t.reach,
      durationMs: t.durationMs,
      bins: t.bins,
      target: [mm(t.target[0]), mm(t.target[1])],
      truePos: Float32Array.from(truePos, mm),
      spikes,
      noise,
      decoded,
    };
  });

  return {
    dataset,
    method,
    neuronCounts,
    noiseHz,
    decoders,
    unitOrder,
    unitElectrode: raw.unitElectrode,
    electrodes,
    units,
    binMs,
    bounds: { min: [mm(b.min[0]), mm(b.min[1])], max: [mm(b.max[0]), mm(b.max[1])] },
    results,
    trials,
  };
}

const cumsum = (d) => {
  const out = new Array(d.length);
  for (let i = 0; i < d.length; i++) out[i] = i ? out[i - 1] + d[i] : d[i];
  return out;
};
/** Interleaved (x, y) differences -> values; each coordinate has its own running sum. */
const cumsumXY = (d) => {
  const out = new Array(d.length);
  for (let i = 0; i < d.length; i++) out[i] = i < 2 ? d[i] : out[i - 2] + d[i];
  return out;
};

/**
 * nf-playground/2 -> nf-playground/1, exactly (the inverse of encode.py's compact()). Integer series
 * are stored as differences; noise spikes as {t: time differences, l: one level digit per spike}.
 */
export function expandCompact(raw) {
  const arr = (v, what) => {
    if (!Array.isArray(v) || !v.every(isInt)) fail(`${what} must be an array of integers`);
    return v;
  };
  const list = (v, what) => {
    if (!Array.isArray(v)) fail(`${what} must be an array`);
    return v;
  };
  if (!raw || typeof raw !== 'object') fail('not an object');
  list(raw.trials, 'trials');
  return {
    ...raw,
    schema: SCHEMA,
    trials: raw.trials.map((t, ti) => {
      const w = `trials[${ti}]`;
      if (!t || typeof t !== 'object') fail(`${w} must be an object`);
      const noise = list(t.noiseSpikes, `${w}.noiseSpikes`).map((n, u) => {
        if (!n || typeof n !== 'object') fail(`${w}.noiseSpikes[${u}] must be an object`);
        const ms = cumsum(arr(n.t, `${w}.noiseSpikes[${u}].t`));
        // levels are 1..9 (encode.py refuses anything else); level 0 would mean "no noise"
        if (typeof n.l !== 'string' || n.l.length !== ms.length || !/^[1-9]*$/.test(n.l))
          fail(`${w}.noiseSpikes[${u}].l must hold one level digit (1-9) per spike`);
        return ms.flatMap((m, i) => [m, Number(n.l[i])]);
      });
      if (!t.decoded || typeof t.decoded !== 'object') fail(`${w}.decoded must be an object`);
      const decoded = {};
      for (const [d, grid] of Object.entries(t.decoded))
        decoded[d] = list(grid, `${w}.decoded.${d}`).map((row, ci) =>
          list(row, `${w}.decoded.${d}[${ci}]`).map((path, ni) =>
            cumsumXY(arr(path, `${w}.decoded.${d}[${ci}][${ni}]`)),
          ),
        );
      return {
        ...t,
        truePos: cumsumXY(arr(t.truePos, `${w}.truePos`)),
        spikes: list(t.spikes, `${w}.spikes`).map((s, u) => cumsum(arr(s, `${w}.spikes[${u}]`))),
        noiseSpikes: noise,
        decoded,
      };
    }),
  };
}

/** Units used at a neuron count: the first `count` of the fixed random order. */
export function activeUnits(model, count) {
  return new Set(model.unitOrder.slice(0, count));
}

/** R² of an interleaved (x, y) path against the truth, averaged over x and y. */
export function r2(truth, est) {
  if (truth.length !== est.length || truth.length < 4 || truth.length % 2) return NaN;
  let total = 0;
  for (const c of [0, 1]) {
    let mean = 0;
    const n = truth.length / 2;
    for (let i = c; i < truth.length; i += 2) mean += truth[i];
    mean /= n;
    let res = 0;
    let tot = 0;
    for (let i = c; i < truth.length; i += 2) {
      res += (truth[i] - est[i]) ** 2;
      tot += (truth[i] - mean) ** 2;
    }
    total += tot > 0 ? 1 - res / tot : NaN;
  }
  return total / 2;
}

/** Mean Euclidean distance (mm) between two interleaved (x, y) paths of equal length. */
export function meanErrorMm(truth, est) {
  if (truth.length !== est.length || truth.length < 2 || truth.length % 2) return NaN;
  let sum = 0;
  for (let i = 0; i < truth.length; i += 2)
    sum += Math.hypot(truth[i] - est[i], truth[i + 1] - est[i + 1]);
  return sum / (truth.length / 2);
}

/**
 * Point on a binned path at time tMs from the trial start. Each bin's value sits at the bin centre;
 * between centres it is linearly interpolated, outside them it is clamped.
 * @returns {[number, number]}
 */
export function sampleAt(path, binMs, tMs) {
  const n = path.length / 2;
  const f = Math.min(Math.max(tMs / binMs - 0.5, 0), n - 1);
  const i = Math.min(Math.floor(f), n - 2);
  const a = Math.max(0, f - i);
  return [
    path[2 * i] + a * (path[2 * i + 2] - path[2 * i]),
    path[2 * i + 1] + a * (path[2 * i + 3] - path[2 * i + 1]),
  ];
}

/** Number of whole bins whose centre is at or before tMs (how much of a path to draw). */
export function binsUpTo(binMs, tMs, bins) {
  return Math.max(0, Math.min(bins, Math.floor(tMs / binMs + 0.5)));
}

/**
 * Two-link planar arm, inverse kinematics (elbow bent to one fixed side). The target is pulled onto
 * the reachable annulus first, so the arm never flips or jumps. Angles in radians.
 * @returns {{ shoulder: number, elbow: number, x: number, y: number }}
 */
export function solveArm(x, y, l1, l2) {
  const eps = 1e-6;
  const rMax = l1 + l2 - eps;
  const rMin = Math.abs(l1 - l2) + eps;
  let r = Math.hypot(x, y);
  if (r < eps) {
    x = rMin;
    y = 0;
    r = rMin;
  }
  const rc = Math.min(Math.max(r, rMin), rMax);
  const tx = (x / r) * rc;
  const ty = (y / r) * rc;
  const cosE = (rc * rc - l1 * l1 - l2 * l2) / (2 * l1 * l2);
  const elbow = Math.acos(Math.min(1, Math.max(-1, cosE)));
  const shoulder = Math.atan2(ty, tx) - Math.atan2(l2 * Math.sin(elbow), l1 + l2 * Math.cos(elbow));
  return { shoulder, elbow, x: tx, y: ty };
}

/** Forward kinematics for solveArm's angles: elbow and hand positions. */
export function armPoints(shoulder, elbow, l1, l2) {
  const ex = l1 * Math.cos(shoulder);
  const ey = l1 * Math.sin(shoulder);
  return {
    elbow: [ex, ey],
    hand: [ex + l2 * Math.cos(shoulder + elbow), ey + l2 * Math.sin(shoulder + elbow)],
  };
}

/** Two decimals, with a true minus sign for negative values. */
export function formatR2(v) {
  if (!Number.isFinite(v)) return '–';
  const s = Math.abs(v).toFixed(2);
  return v < 0 ? `−${s}` : s;
}
