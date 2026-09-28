// Neural interface scene (/interface): pure, deterministic helpers shared by the WebGL scene, the
// record mode and test/interface.test.mjs. Every visual state is a function of time only (no
// accumulated animation state), so ?record=1 with window.__seek(t) renders the same frame every time.

/**
 * Illustrative Utah-style layout: a 10 x 10 grid without its four corners = 96 sites, row-major.
 * Electrode id k (1..96) sits at slot k - 1. The dataset has no array map, so this placement is
 * a drawing convention, not the real channel geometry. Coordinates are in pitch units, centred.
 * @returns {[number, number][]}
 */
export function gridSlots(side = 10) {
  const out = [];
  const c = (side - 1) / 2;
  for (let r = 0; r < side; r++)
    for (let q = 0; q < side; q++) {
      const corner = (r === 0 || r === side - 1) && (q === 0 || q === side - 1);
      if (!corner) out.push([q - c, r - c]);
    }
  return out;
}

/** Units recorded on each electrode id: Map(id -> unit indices). */
export function unitsByElectrode(unitElectrode) {
  const m = new Map();
  unitElectrode.forEach((e, u) => {
    if (!m.has(e)) m.set(e, []);
    m.get(e).push(u);
  });
  return m;
}

/** Index of the last spike at or before tMs in a sorted Int32Array (-1 if none). */
export function lastSpikeIndex(spikes, tMs) {
  let lo = 0;
  let hi = spikes.length - 1;
  let ans = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (spikes[mid] <= tMs) {
      ans = mid;
      lo = mid + 1;
    } else hi = mid - 1;
  }
  return ans;
}

/** Glow of a unit at tMs: 1 at a spike, decaying exponentially (decayMs), 0 before any spike. */
export function spikeGlow(spikes, tMs, decayMs = 60) {
  const i = lastSpikeIndex(spikes, tMs);
  if (i < 0) return 0;
  return Math.exp(-(tMs - spikes[i]) / decayMs);
}

/** Spikes in (tMs - windowMs, tMs], newest last: the pulses currently travelling up a lead. */
export function recentSpikes(spikes, tMs, windowMs) {
  const hi = lastSpikeIndex(spikes, tMs);
  const out = [];
  for (let i = hi; i >= 0 && spikes[i] > tMs - windowMs; i--) out.push(spikes[i]);
  return out.reverse();
}

/**
 * Replay timeline: the trials played one after another with a pause between them, looping.
 * @param {number[]} durationsMs trial durations
 * @returns {{ total: number, at: (tMs: number) => { trial: number, tMs: number } }}
 */
export function timeline(durationsMs, gapMs = 400) {
  const starts = [];
  let acc = 0;
  for (const d of durationsMs) {
    starts.push(acc);
    acc += d + gapMs;
  }
  const total = acc;
  return {
    total,
    at(t) {
      const x = ((t % total) + total) % total;
      let i = starts.length - 1;
      while (i > 0 && starts[i] > x) i--;
      return { trial: i, tMs: Math.min(x - starts[i], durationsMs[i]) };
    },
  };
}

const smooth = (a) => a * a * (3 - 2 * a);
const lerp = (a, b, f) => a + (b - a) * f;
const lerp3 = (a, b, f) => [lerp(a[0], b[0], f), lerp(a[1], b[1], f), lerp(a[2], b[2], f)];

/**
 * Guided tour / record camera path. Each key: time (s), camera position, look-at target, caption id.
 * Positions are in scene units (see interface-scene.ts: cortex slab ~ 12 wide, array at origin).
 */
export const TOUR = [
  { t: 0, pos: [17, 11, 27], target: [0, 2, -2.5], caption: 'overview' },
  { t: 5, pos: [6.5, 3.2, 9.5], target: [0, -1.2, -1.5], caption: 'array' },
  { t: 10, pos: [5, -0.4, 9.5], target: [0, -2.7, -1.8], caption: 'neurons' },
  { t: 15, pos: [1, 6.5, 13], target: [-4.5, 2.5, -3], caption: 'signal' },
  { t: 20, pos: [4, 10.5, 14], target: [2, 7.5, -5], caption: 'decoder' },
  { t: 26, pos: [17, 11, 27], target: [0, 2, -2.5], caption: 'overview' },
];
export const TOUR_SECONDS = TOUR[TOUR.length - 1].t;

/** Camera at tour time tS (clamped): eased interpolation between keys. */
export function cameraAt(tS, keys = TOUR) {
  const t = Math.min(Math.max(tS, keys[0].t), keys[keys.length - 1].t);
  let i = 0;
  while (i < keys.length - 2 && keys[i + 1].t <= t) i++;
  const a = keys[i];
  const b = keys[i + 1];
  const f = smooth((t - a.t) / (b.t - a.t));
  return {
    pos: lerp3(a.pos, b.pos, f),
    target: lerp3(a.target, b.target, f),
    caption: f < 0.5 ? a.caption : b.caption,
  };
}

/** Label priority, most important first; lower ones give way when labels would collide. */
export const LABEL_PRIORITY = [
  'array',
  'neurons',
  'decoder',
  'screen',
  'arm',
  'headstage',
  'cortex',
];
/** Below this stage width only the primary labels are drawn (captions stay). */
export const NARROW_STAGE_PX = 500;
const PRIMARY_LABELS = new Set(['array', 'neurons', 'decoder', 'arm']);

/**
 * Which 3D labels to show. Each label is anchored above its point (box = [x - w/2, y - h] to
 * [x + w/2, y]). A label is dropped when its anchor is hidden, when its box would leave the stage
 * (clipped), or when it would overlap a higher-priority label. Narrow stages keep primary labels only.
 * @param {{ key: string, x: number, y: number, w: number, h: number, visible: boolean }[]} labels
 * @returns {Set<string>} keys to show
 */
export function placeLabels(labels, stageW, stageH, gap = 4) {
  const byKey = new Map(labels.map((l) => [l.key, l]));
  const order = [
    ...LABEL_PRIORITY,
    ...labels.map((l) => l.key).filter((k) => !LABEL_PRIORITY.includes(k)),
  ];
  const placed = [];
  const shown = new Set();
  for (const key of order) {
    const l = byKey.get(key);
    if (!l || !l.visible) continue;
    if (stageW < NARROW_STAGE_PX && !PRIMARY_LABELS.has(key)) continue;
    const box = { x0: l.x - l.w / 2, y0: l.y - l.h, x1: l.x + l.w / 2, y1: l.y };
    if (box.x0 < 0 || box.y0 < 0 || box.x1 > stageW || box.y1 > stageH) continue;
    const hit = placed.some(
      (b) =>
        box.x0 < b.x1 + gap && box.x1 + gap > b.x0 && box.y0 < b.y1 + gap && box.y1 + gap > b.y0,
    );
    if (hit) continue;
    placed.push(box);
    shown.add(key);
  }
  return shown;
}

/** Radians per arrow-key press when the 3D scene has keyboard focus. */
export const ORBIT_STEP = Math.PI / 16;

/**
 * Keyboard control of the focused scene (the keyboard equivalent of drag/scroll):
 * arrows orbit, + / - and PageUp / PageDown zoom, Home resets the view. Unknown keys: null.
 * @returns {{ rotate?: [number, number], zoom?: number, reset?: boolean } | null}
 */
export function orbitKey(key) {
  switch (key) {
    case 'ArrowLeft':
      return { rotate: [-ORBIT_STEP, 0] };
    case 'ArrowRight':
      return { rotate: [ORBIT_STEP, 0] };
    case 'ArrowUp':
      return { rotate: [0, -ORBIT_STEP] };
    case 'ArrowDown':
      return { rotate: [0, ORBIT_STEP] };
    case '+':
    case '=':
    case 'PageUp':
      return { zoom: 0.85 };
    case '-':
    case '_':
    case 'PageDown':
      return { zoom: 1 / 0.85 };
    case 'Home':
      return { reset: true };
    default:
      return null;
  }
}

/**
 * Query flags: ?record=1 (deterministic video mode), ?t=<seconds> (start frame),
 * ?captions=0 (no tour captions, for clean stills).
 */
export function parseFlags(search) {
  const p = new URLSearchParams(search);
  const t = Number(p.get('t'));
  return {
    record: p.get('record') === '1',
    t: Number.isFinite(t) && t > 0 ? t : 0,
    captions: p.get('captions') !== '0',
  };
}
