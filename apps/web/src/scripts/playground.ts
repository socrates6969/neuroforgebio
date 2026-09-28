// Neural Playground client: fetches the precomputed asset (a content-hashed same-origin file) and
// draws the replay on four canvases. Nothing here decodes anything: every decoded path and score
// was computed offline by tools/playground on held-out test reaches. Graphics only; no device APIs.
import assetUrl from '../assets/playground/mc-rtt-playground.json?url';
import {
  activeUnits,
  armPoints,
  binsUpTo,
  formatR2,
  meanErrorMm,
  parsePlayground,
  sampleAt,
  solveArm,
} from '../lib/playground-data.mjs';
import { parseFlags, timeline } from '../lib/interface-model.mjs';

declare global {
  interface Window {
    __record?: { duration: number; fps: number; ready: boolean };
    __seek?: (tS: number) => void;
  }
}

/** ?record=1: every trial once at half speed, with a 0.9 s rest between trials. */
const RECORD_SPEED = 0.5;
const RECORD_GAP_MS = 450; // replay ms (0.9 s on screen at half speed)

type Model = ReturnType<typeof parsePlayground>;
type Ctx = CanvasRenderingContext2D;

const root = document.querySelector<HTMLElement>('[data-playground]');
if (root) void init(root);

function q<T extends Element>(el: ParentNode, sel: string): T {
  const found = el.querySelector<T>(sel);
  if (!found) throw new Error(`playground: missing ${sel}`);
  return found;
}

/** Theme colours and fonts come from the CSS tokens, so both themes paint correctly. */
function readTheme(el: HTMLElement) {
  const cs = getComputedStyle(el);
  const v = (name: string) => cs.getPropertyValue(name).trim();
  return {
    ink: v('--color-ink'),
    muted: v('--color-muted'),
    accent: v('--color-accent'),
    accentInk: v('--color-accent-ink'),
    secondary: v('--color-secondary'),
    line: v('--color-line'),
    mono: v('--font-mono'),
  };
}
type Theme = ReturnType<typeof readTheme>;

async function init(el: HTMLElement) {
  const status = q<HTMLElement>(el, '[data-pg-status]');
  status.hidden = false;
  let model: Model;
  try {
    const res = await fetch(assetUrl, { credentials: 'same-origin' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    model = parsePlayground(await res.json());
  } catch (err) {
    status.textContent = el.dataset.loadError ?? '';
    console.warn('playground: asset not loaded', err);
    return;
  }
  status.hidden = true;
  new Playground(el, model).start();
}

class Playground {
  private el: HTMLElement;
  private m: Model;
  private theme: Theme;
  private reduce: boolean;
  private trial = 0;
  private t = 0;
  private playing = false;
  private speed = 0.5;
  private ci: number;
  private ni = 0;
  private decoder: string;
  private hold = 0; // ms left to rest at the end of a trial before auto-advancing
  private last = 0;
  private raf = 0;
  private liveTimer = 0;
  private canvases: Record<string, HTMLCanvasElement> = {};
  private ui: {
    play: HTMLButtonElement;
    scrub: HTMLInputElement;
    time: HTMLOutputElement;
    trial: HTMLSelectElement;
    speed: HTMLSelectElement;
    advance: HTMLInputElement;
    neurons: HTMLInputElement;
    neuronsOut: HTMLOutputElement;
    r2Test: HTMLElement;
    r2Vel: HTMLElement;
    r2Trial: HTMLElement;
    live: HTMLElement;
  };
  private names: Record<string, string> = {};

  constructor(el: HTMLElement, model: Model) {
    this.el = el;
    this.m = model;
    this.theme = readTheme(el);
    this.reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
    this.ci = model.neuronCounts.length - 1;
    this.decoder = model.decoders[0];
    for (const c of el.querySelectorAll<HTMLCanvasElement>('[data-pg-canvas]'))
      this.canvases[c.dataset.pgCanvas ?? ''] = c;
    this.ui = {
      play: q(el, '[data-pg-play]'),
      scrub: q(el, '[data-pg-scrub]'),
      time: q(el, '[data-pg-time]'),
      trial: q(el, '[data-pg-trial]'),
      speed: q(el, '[data-pg-speed]'),
      advance: q(el, '[data-pg-advance]'),
      neurons: q(el, '[data-pg-neurons]'),
      neuronsOut: q(el, '[data-pg-neurons-out]'),
      r2Test: q(el, '[data-pg-r2="test"]'),
      r2Vel: q(el, '[data-pg-r2="vel"]'),
      r2Trial: q(el, '[data-pg-r2="trial"]'),
      live: q(el, '[data-pg-live]'),
    };
    for (const input of el.querySelectorAll<HTMLInputElement>('input[name="pg-decoder"]'))
      this.names[input.value] = input.parentElement?.textContent?.trim() ?? input.value;
  }

  start() {
    const { ui } = this;
    // The replay is ready: show the live panels, controls and chart (the still exists only in <noscript>).
    for (const n of this.el.querySelectorAll<HTMLElement>('[data-pg-needs-js]')) n.hidden = false;
    for (const c of this.el.querySelectorAll<
      HTMLInputElement | HTMLSelectElement | HTMLButtonElement
    >('[data-pg-controls] input, [data-pg-controls] select, [data-pg-controls] button'))
      c.disabled = false;
    q<HTMLFormElement>(this.el, '[data-pg-controls]').addEventListener('submit', (e) =>
      e.preventDefault(),
    );
    this.speed = Number(ui.speed.value) || 0.5;

    ui.play.addEventListener('click', () => this.setPlaying(!this.playing));
    ui.scrub.addEventListener('input', () => {
      this.setPlaying(false);
      this.t = Number(ui.scrub.value);
      this.draw();
    });
    ui.trial.addEventListener('change', () => this.selectTrial(Number(ui.trial.value), false));
    ui.speed.addEventListener('change', () => (this.speed = Number(ui.speed.value) || 0.5));
    ui.neurons.addEventListener('input', () => {
      this.ci = Number(ui.neurons.value);
      this.settingsChanged();
    });
    for (const r of this.el.querySelectorAll<HTMLInputElement>('input[name="pg-noise"]'))
      r.addEventListener('change', () => {
        this.ni = Number(r.value);
        this.settingsChanged();
      });
    for (const r of this.el.querySelectorAll<HTMLInputElement>('input[name="pg-decoder"]'))
      r.addEventListener('change', () => {
        this.decoder = r.value;
        this.settingsChanged();
      });

    // Reduced motion switched on while the page is open: stop at once (the user can press Play).
    matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change', (e) => {
      this.reduce = e.matches;
      if (e.matches) this.setPlaying(false);
    });

    const ro = new ResizeObserver(() => this.resize());
    for (const c of Object.values(this.canvases)) ro.observe(c);
    this.resize();
    this.selectTrial(0, false);
    this.updateScores(false);

    if (parseFlags(location.search).record) {
      // Record mode: fixed timeline, no autoplay; window.__seek(t) renders exactly the frame at t s.
      document.documentElement.classList.add('nf-rec');
      const tl = timeline(
        this.m.trials.map((t) => t.durationMs),
        RECORD_GAP_MS,
      );
      window.__seek = (tS: number) => {
        this.setPlaying(false);
        const { trial, tMs } = tl.at(Math.min(tS * 1000 * RECORD_SPEED, tl.total - 1));
        if (trial !== this.trial) this.selectTrial(trial, false);
        this.t = tMs;
        this.draw();
      };
      window.__seek(0);
      // ready only once the web fonts are in (canvas labels and readouts are text): stable frames
      void document.fonts.ready.then(() => {
        window.__seek?.(0);
        window.__record = { duration: tl.total / 1000 / RECORD_SPEED, fps: 30, ready: true };
      });
    } else if (this.reduce) {
      // No motion unless asked for: show the whole trial at once.
      this.t = this.m.trials[0].durationMs;
      this.draw();
    } else {
      // Start the replay the first time the demo scrolls into view.
      const io = new IntersectionObserver((entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          io.disconnect();
          this.setPlaying(true);
        }
      });
      io.observe(this.canvases.path);
    }
  }

  private resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    for (const c of Object.values(this.canvases)) {
      const w = Math.max(1, Math.round(c.clientWidth * dpr));
      const h = Math.max(1, Math.round(c.clientHeight * dpr));
      if (c.width !== w || c.height !== h) {
        c.width = w;
        c.height = h;
      }
    }
    this.draw();
  }

  private setPlaying(on: boolean) {
    if (on && this.t >= this.dur()) this.t = 0;
    this.playing = on;
    this.ui.play.textContent = on ? (this.el.dataset.pause ?? '') : (this.el.dataset.play ?? '');
    cancelAnimationFrame(this.raf);
    if (on) {
      this.last = performance.now();
      this.raf = requestAnimationFrame((now) => this.tick(now));
    }
  }

  private tick(now: number) {
    const dt = Math.min(now - this.last, 100);
    this.last = now;
    if (this.hold > 0) {
      this.hold -= dt;
      if (this.hold <= 0) this.selectTrial((this.trial + 1) % this.m.trials.length, true);
    } else {
      this.t += dt * this.speed;
      if (this.t >= this.dur()) {
        this.t = this.dur();
        if (this.ui.advance.checked) this.hold = 900;
        else {
          this.draw();
          this.setPlaying(false);
          return;
        }
      }
    }
    this.draw();
    if (this.playing) this.raf = requestAnimationFrame((n) => this.tick(n));
  }

  private dur() {
    return this.m.trials[this.trial].durationMs;
  }

  private selectTrial(i: number, keepPlaying: boolean) {
    this.trial = i;
    this.t = 0;
    this.hold = 0;
    this.ui.trial.value = String(i);
    this.ui.scrub.max = String(this.dur());
    if (!keepPlaying && this.playing) this.setPlaying(false);
    this.updateScores(false);
    this.draw();
  }

  private settingsChanged() {
    const n = this.m.neuronCounts[this.ci];
    // Always plural: the neuron counts are 8 to 130, never 1 (a singular word would be needed if
    // a count of 1 were ever added; web-a11y T12).
    const unit = this.el.dataset.neuronsUnit ?? '';
    this.ui.neuronsOut.textContent = String(n);
    this.ui.neurons.setAttribute('aria-valuetext', `${n} ${unit}`);
    this.updateScores(true);
    this.draw();
  }

  private path() {
    return this.m.trials[this.trial].decoded[this.decoder][this.ci][this.ni];
  }

  private updateScores(announce: boolean) {
    const res = this.m.results[this.decoder][this.ci][this.ni];
    const tr = this.m.trials[this.trial];
    const gapCm = meanErrorMm(tr.truePos, this.path()) / 10;
    const gap = Number.isFinite(gapCm)
      ? `${gapCm.toFixed(1)} ${this.ui.r2Trial.dataset.unit ?? ''}`
      : '–';
    this.ui.r2Test.textContent = formatR2(res.posR2);
    this.ui.r2Vel.textContent = formatR2(res.velR2);
    this.ui.r2Trial.textContent = gap;
    this.updateChartLabel();
    if (!announce) return;
    // One polite announcement after the user stops changing settings, not one per slider step.
    clearTimeout(this.liveTimer);
    this.liveTimer = window.setTimeout(() => {
      const dts = [...this.el.querySelectorAll('.nums dt')].map((d) => d.textContent ?? '');
      this.ui.live.textContent =
        `${this.names[this.decoder]}, ${this.m.neuronCounts[this.ci]} ${this.el.dataset.neuronsUnit}, ` +
        `+${this.m.noiseHz[this.ni]} ${this.el.dataset.noiseUnit}. ${dts[0]}: ${formatR2(res.posR2)}. ` +
        `${dts[2]}: ${gap}.`;
    }, 400);
  }

  private updateChartLabel() {
    const unit = this.el.dataset.neuronsUnit ?? '';
    const parts = this.m.decoders.map((d) => {
      const pts = this.m.neuronCounts.map(
        (n, ci) => `${n} ${unit} ${formatR2(this.m.results[d][ci][this.ni].posR2Mean)}`,
      );
      return `${this.names[d]}: ${pts.join(', ')}`;
    });
    this.canvases.chart.setAttribute(
      'aria-label',
      `${this.el.dataset.chartLabel} (+${this.m.noiseHz[this.ni]} ${this.el.dataset.noiseUnit}). ${parts.join('. ')}.`,
    );
  }

  private draw() {
    const tr = this.m.trials[this.trial];
    const t = Math.min(this.t, tr.durationMs);
    const secs = this.el.dataset.seconds ?? 's';
    this.ui.scrub.value = String(Math.round(t));
    this.ui.scrub.setAttribute(
      'aria-valuetext',
      `${(t / 1000).toFixed(2)} ${secs} / ${(tr.durationMs / 1000).toFixed(2)} ${secs}`,
    );
    this.ui.time.textContent = `${(t / 1000).toFixed(2)} / ${(tr.durationMs / 1000).toFixed(2)} ${secs}`;
    this.drawRaster(t);
    this.drawPath(t);
    this.drawArm(t);
    this.drawChart();
  }

  private ctx(name: string): [Ctx, number, number, number] | null {
    const c = this.canvases[name];
    const ctx = c?.getContext('2d');
    if (!c || !ctx) return null;
    const dpr = c.width / Math.max(1, c.clientWidth);
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, c.width, c.height);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return [ctx, c.width / dpr, c.height / dpr, dpr];
  }

  private label(ctx: Ctx, text: string, x: number, y: number, align: CanvasTextAlign = 'left') {
    ctx.fillStyle = this.theme.muted;
    ctx.font = `11px ${this.theme.mono}`;
    ctx.textAlign = align;
    ctx.fillText(text, x, y);
  }

  private drawRaster(t: number) {
    const got = this.ctx('raster');
    if (!got) return;
    const [ctx, w, h] = got;
    const th = this.theme;
    const tr = this.m.trials[this.trial];
    const pad = { l: 8, r: 8, t: 8, b: 20 };
    const pw = w - pad.l - pad.r;
    const ph = h - pad.t - pad.b;
    const rowH = ph / this.m.units;
    const used = this.m.neuronCounts[this.ci];
    const tick = Math.max(1, rowH * 0.8);
    const xOf = (ms: number) => pad.l + (ms / tr.durationMs) * pw;
    // Rows follow the fixed random unit order, so the units in use are always the top rows.
    this.m.unitOrder.forEach((u, rank) => {
      const y = pad.t + rank * rowH;
      const inUse = rank < used;
      const s = tr.spikes[u];
      for (let k = 0; k < s.length; k++) {
        const past = s[k] <= t;
        ctx.globalAlpha = (inUse ? 1 : 0.22) * (past ? 1 : 0.25);
        ctx.fillStyle = th.ink;
        ctx.fillRect(xOf(s[k]), y, 1.5, tick);
      }
      const nz = tr.noise[u];
      for (let k = 0; k < nz.ms.length; k++) {
        if (nz.level[k] > this.ni) continue;
        const past = nz.ms[k] <= t;
        ctx.globalAlpha = (inUse ? 0.9 : 0.2) * (past ? 1 : 0.25);
        ctx.fillStyle = th.secondary;
        ctx.fillRect(xOf(nz.ms[k]), y, 1.5, tick);
      }
    });
    ctx.globalAlpha = 1;
    if (used < this.m.units) {
      const y = pad.t + used * rowH;
      ctx.strokeStyle = th.accentInk;
      ctx.setLineDash([4, 3]);
      ctx.beginPath();
      ctx.moveTo(pad.l, y);
      ctx.lineTo(w - pad.r, y);
      ctx.stroke();
      ctx.setLineDash([]);
    }
    ctx.strokeStyle = th.accent;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(xOf(t), pad.t - 4);
    ctx.lineTo(xOf(t), h - pad.b + 2);
    ctx.stroke();
    ctx.lineWidth = 1;
    const secs = this.el.dataset.seconds ?? 's';
    this.label(ctx, `0 ${secs}`, pad.l, h - 5);
    this.label(ctx, `${(tr.durationMs / 1000).toFixed(2)} ${secs}`, w - pad.r, h - 5, 'right');
    this.label(ctx, `${used} / ${this.m.units}`, w / 2, h - 5, 'center');
  }

  /**
   * World (mm) -> canvas transform, equal scale on both axes, framed on this trial: the actual path,
   * the target and the decoded path, at least 6 cm across (the scale bar keeps sizes honest).
   */
  private world(w: number, h: number, pad: number) {
    const tr = this.m.trials[this.trial];
    const lo = [tr.target[0], tr.target[1]];
    const hi = [tr.target[0], tr.target[1]];
    for (const p of [tr.truePos, this.path()])
      for (let i = 0; i < p.length; i++) {
        lo[i % 2] = Math.min(lo[i % 2], p[i]);
        hi[i % 2] = Math.max(hi[i % 2], p[i]);
      }
    const min = [0, 1].map((k) => (lo[k] + hi[k]) / 2 - Math.max(30, (hi[k] - lo[k]) / 2 + 8));
    const max = [0, 1].map((k) => (lo[k] + hi[k]) / 2 + Math.max(30, (hi[k] - lo[k]) / 2 + 8));
    const spanX = max[0] - min[0];
    const spanY = max[1] - min[1];
    const s = Math.min((w - 2 * pad) / spanX, (h - 2 * pad) / spanY);
    const ox = (w - s * spanX) / 2;
    const oy = (h - s * spanY) / 2;
    return (x: number, y: number): [number, number] => [
      ox + (x - min[0]) * s,
      h - oy - (y - min[1]) * s,
    ];
  }

  private strokePath(
    ctx: Ctx,
    path: Float32Array,
    n: number,
    map: (x: number, y: number) => [number, number],
  ) {
    if (n < 1) return;
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      const [x, y] = map(path[2 * i], path[2 * i + 1]);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
  }

  private drawPath(t: number) {
    const got = this.ctx('path');
    if (!got) return;
    const [ctx, w, h] = got;
    const th = this.theme;
    const tr = this.m.trials[this.trial];
    const map = this.world(w, h, 14);
    const est = this.path();
    const n = binsUpTo(this.m.binMs, t, tr.bins);
    // target
    const [tx, ty] = map(tr.target[0], tr.target[1]);
    ctx.strokeStyle = th.secondary;
    ctx.lineWidth = 2;
    ctx.strokeRect(tx - 7, ty - 7, 14, 14);
    // whole actual path, faint, so the eye knows where the reach goes
    ctx.globalAlpha = 0.18;
    ctx.strokeStyle = th.ink;
    this.strokePath(ctx, tr.truePos, tr.bins, map);
    ctx.globalAlpha = 1;
    ctx.lineJoin = 'round';
    ctx.lineWidth = 2.5;
    ctx.strokeStyle = th.ink;
    this.strokePath(ctx, tr.truePos, n, map);
    ctx.setLineDash([6, 4]);
    ctx.strokeStyle = th.accentInk;
    this.strokePath(ctx, est, n, map);
    ctx.setLineDash([]);
    const [ax, ay] = map(...sampleAt(tr.truePos, this.m.binMs, t));
    const [dx, dy] = map(...sampleAt(est, this.m.binMs, t));
    ctx.fillStyle = th.ink;
    ctx.beginPath();
    ctx.arc(ax, ay, 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.lineWidth = 2.5;
    ctx.strokeStyle = th.accentInk;
    ctx.beginPath();
    ctx.arc(dx, dy, 7, 0, Math.PI * 2);
    ctx.stroke();
    ctx.lineWidth = 1;
    // scale bar: the largest of 1, 2, 5, 10 cm that fits in a third of the width
    const [s0] = map(0, 0);
    const perMm = Math.abs(map(1, 0)[0] - s0);
    const cm = [10, 5, 2, 1].find((c) => c * 10 * perMm <= w / 3) ?? 1;
    const s1 = s0 + cm * 10 * perMm;
    this.label(ctx, `${cm} cm`, 8, h - 6);
    ctx.strokeStyle = th.muted;
    ctx.beginPath();
    ctx.moveTo(8, h - 18);
    ctx.lineTo(8 + (s1 - s0), h - 18);
    ctx.stroke();
  }

  private drawArm(t: number) {
    const got = this.ctx('arm');
    if (!got) return;
    const [ctx, w, h] = got;
    const th = this.theme;
    const tr = this.m.trials[this.trial];
    const { min, max } = this.m.bounds;
    // Arm geometry in canvas units: shoulder at the bottom centre, equal link lengths.
    const reach = Math.min(w * 0.42, (h - 24) * 0.95);
    const l1 = reach * 0.52;
    const l2 = reach * 0.48;
    const sx = w / 2;
    const sy = h - 14;
    // Map the cursor workspace into a box the hand can reach above the shoulder.
    const box = { x0: -0.6 * reach, x1: 0.6 * reach, y0: 0.4 * reach, y1: 0.95 * reach };
    const toArm = (x: number, y: number): [number, number] => [
      box.x0 + ((x - min[0]) / (max[0] - min[0])) * (box.x1 - box.x0),
      box.y0 + ((y - min[1]) / (max[1] - min[1])) * (box.y1 - box.y0),
    ];
    const toCanvas = (x: number, y: number): [number, number] => [sx + x, sy - y];
    // workspace outline
    ctx.strokeStyle = th.line;
    ctx.setLineDash([3, 3]);
    const [bx0, by0] = toCanvas(box.x0, box.y1);
    ctx.strokeRect(bx0, by0, box.x1 - box.x0, box.y1 - box.y0);
    ctx.setLineDash([]);
    // target and actual hand position, faint
    const [gx, gy] = toCanvas(...toArm(tr.target[0], tr.target[1]));
    ctx.strokeStyle = th.secondary;
    ctx.lineWidth = 2;
    ctx.strokeRect(gx - 6, gy - 6, 12, 12);
    const [ax, ay] = toCanvas(...toArm(...sampleAt(tr.truePos, this.m.binMs, t)));
    ctx.globalAlpha = 0.5;
    ctx.fillStyle = th.ink;
    ctx.beginPath();
    ctx.arc(ax, ay, 4, 0, Math.PI * 2);
    ctx.fill();
    ctx.globalAlpha = 1;
    // arm following the decoded point
    const [hx, hy] = toArm(...sampleAt(this.path(), this.m.binMs, t));
    const sol = solveArm(hx, hy, l1, l2);
    const pts = armPoints(sol.shoulder, sol.elbow, l1, l2);
    const [ex, ey] = toCanvas(pts.elbow[0], pts.elbow[1]);
    const [px, py] = toCanvas(pts.hand[0], pts.hand[1]);
    ctx.lineCap = 'round';
    ctx.strokeStyle = th.muted;
    ctx.lineWidth = 12;
    ctx.beginPath();
    ctx.moveTo(sx, sy);
    ctx.lineTo(ex, ey);
    ctx.stroke();
    ctx.lineWidth = 9;
    ctx.beginPath();
    ctx.moveTo(ex, ey);
    ctx.lineTo(px, py);
    ctx.stroke();
    ctx.lineCap = 'butt';
    ctx.lineWidth = 1;
    ctx.fillStyle = th.ink;
    for (const [x, y, r] of [
      [sx, sy, 7],
      [ex, ey, 5],
    ] as const) {
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.lineWidth = 2.5;
    ctx.strokeStyle = th.accentInk;
    ctx.beginPath();
    ctx.arc(px, py, 7, 0, Math.PI * 2);
    ctx.stroke();
    ctx.lineWidth = 1;
  }

  private drawChart() {
    const got = this.ctx('chart');
    if (!got) return;
    const [ctx, w, h] = got;
    const th = this.theme;
    const counts = this.m.neuronCounts;
    const pad = { l: 40, r: 16, t: 12, b: 26 };
    const pw = w - pad.l - pad.r;
    const ph = h - pad.t - pad.b;
    let top = 0;
    for (const d of this.m.decoders)
      for (const row of this.m.results[d]) for (const c of row) top = Math.max(top, c.posR2Max);
    top = Math.min(1, Math.ceil(top * 5) / 5);
    const xOf = (ci: number) =>
      pad.l + (counts.length > 1 ? (ci / (counts.length - 1)) * pw : pw / 2);
    const yOf = (v: number) => pad.t + ph - (Math.max(0, Math.min(top, v)) / top) * ph;
    ctx.strokeStyle = th.line;
    for (let g = 0; g <= top + 1e-9; g += 0.2) {
      ctx.beginPath();
      ctx.moveTo(pad.l, yOf(g));
      ctx.lineTo(w - pad.r, yOf(g));
      ctx.stroke();
      this.label(ctx, g.toFixed(1), pad.l - 6, yOf(g) + 4, 'right');
    }
    counts.forEach((n, ci) => this.label(ctx, String(n), xOf(ci), h - 8, 'center'));
    const style: Record<string, { color: string; dash: number[] }> = {
      ridge: { color: th.accentInk, dash: [] },
      kalman: { color: th.secondary, dash: [6, 4] },
    };
    for (const d of this.m.decoders) {
      const s = style[d] ?? { color: th.ink, dash: [] };
      const cells = this.m.results[d].map((row) => row[this.ni]);
      ctx.globalAlpha = 0.16;
      ctx.fillStyle = s.color;
      ctx.beginPath();
      cells.forEach((c, ci) =>
        ci ? ctx.lineTo(xOf(ci), yOf(c.posR2Max)) : ctx.moveTo(xOf(ci), yOf(c.posR2Max)),
      );
      for (let ci = cells.length - 1; ci >= 0; ci--) ctx.lineTo(xOf(ci), yOf(cells[ci].posR2Min));
      ctx.closePath();
      ctx.fill();
      ctx.globalAlpha = 1;
      ctx.strokeStyle = s.color;
      ctx.lineWidth = 2.5;
      ctx.setLineDash(s.dash);
      ctx.beginPath();
      cells.forEach((c, ci) =>
        ci ? ctx.lineTo(xOf(ci), yOf(c.posR2Mean)) : ctx.moveTo(xOf(ci), yOf(c.posR2Mean)),
      );
      ctx.stroke();
      ctx.setLineDash([]);
      if (d === this.decoder) {
        ctx.fillStyle = s.color;
        ctx.beginPath();
        ctx.arc(xOf(this.ci), yOf(cells[this.ci].posR2), 6, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    ctx.lineWidth = 1;
  }
}
