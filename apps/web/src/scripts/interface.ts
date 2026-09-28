// /interface entry: decides between the still image and the WebGL scene, loads the playground asset,
// then imports the three.js scene lazily (its chunk is fetched only here). Wires the HTML controls,
// the 3D labels, the tour captions, the electrode inspector and record mode (?record=1):
//   window.__record = { duration, fps }  and  window.__seek(t) renders exactly the frame at t seconds.
import assetUrl from '../assets/playground/mc-rtt-playground.json?url';
import { parsePlayground } from '../lib/playground-data.mjs';
import {
  lastSpikeIndex,
  orbitKey,
  placeLabels,
  parseFlags,
  TOUR_SECONDS,
  unitsByElectrode,
} from '../lib/interface-model.mjs';
import type { Layer, SceneApi } from './interface-scene.ts';

type Model = ReturnType<typeof parsePlayground>;
declare global {
  interface Window {
    __record?: { duration: number; fps: number; ready: boolean };
    __seek?: (tS: number) => void;
  }
}

const root = document.querySelector<HTMLElement>('[data-interface]');
if (root) void main(root);

function q<T extends Element>(sel: string, el: ParentNode = document): T {
  const found = el.querySelector<T>(sel);
  if (!found) throw new Error(`interface: missing ${sel}`);
  return found;
}

function webglAvailable() {
  try {
    const c = document.createElement('canvas');
    return Boolean(c.getContext('webgl2') || c.getContext('webgl'));
  } catch {
    return false;
  }
}

function themeColours(el: HTMLElement) {
  const cs = getComputedStyle(el);
  const v = (n: string) => cs.getPropertyValue(n).trim();
  return {
    bg: v('--color-bg'),
    ink: v('--color-ink'),
    muted: v('--color-muted'),
    accent: v('--color-accent'),
    accentInk: v('--color-accent-ink'),
    secondary: v('--color-secondary'),
    mono: v('--font-mono'),
  };
}

/** Show the still frame (no WebGL, reduced motion, load failure). Only then is the image fetched. */
function showStill(el: HTMLElement) {
  const stage = q<HTMLElement>('[data-ix-stage]', el);
  if (!stage.querySelector('[data-ix-still]')) {
    // <picture>: AVIF (built by sharp) for browsers that support it, the JPEG for the rest
    const d = stage.dataset;
    const pic = document.createElement('picture');
    pic.dataset.ixStill = '';
    if (d.stillAvif) {
      const source = document.createElement('source');
      source.type = 'image/avif';
      source.srcset = d.stillAvif;
      pic.append(source);
    }
    const img = document.createElement('img');
    img.className = 'still';
    img.src = d.stillSrc ?? '';
    img.alt = d.stillAlt ?? '';
    img.width = Number(d.stillWidth);
    img.height = Number(d.stillHeight);
    img.fetchPriority = 'high'; // when inserted, it is the page's main visual
    pic.append(img);
    stage.prepend(pic);
  }
  q<HTMLElement>('[data-ix-still-caption]', el).hidden = false;
}

async function main(el: HTMLElement) {
  const flags = parseFlags(location.search);
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!webglAvailable()) {
    showStill(el);
    q<HTMLElement>('[data-ix-nowebgl]', el).hidden = false;
    return;
  }
  if (reduce && !flags.record) {
    showStill(el);
    const box = q<HTMLElement>('[data-ix-reduced]', el);
    box.hidden = false;
    q<HTMLButtonElement>('[data-ix-show]', el).addEventListener(
      'click',
      () => {
        // Keep keyboard focus: hiding the focused button would drop focus to <body>, so move it to
        // the stage first (it becomes the focusable scene once start() finishes).
        const stage = q<HTMLElement>('[data-ix-stage]', el);
        stage.tabIndex = -1;
        stage.focus();
        box.hidden = true;
        void start(el, flags, true);
      },
      { once: true },
    );
    return;
  }
  await start(el, flags, reduce);
}

async function start(el: HTMLElement, flags: ReturnType<typeof parseFlags>, still: boolean) {
  const status = q<HTMLElement>('[data-ix-status]', el);
  status.hidden = false;
  let model: Model;
  let mod: typeof import('./interface-scene.ts');
  try {
    const [res, m] = await Promise.all([
      fetch(assetUrl, { credentials: 'same-origin' }),
      import('./interface-scene.ts'),
    ]);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    model = parsePlayground(await res.json());
    mod = m;
  } catch (err) {
    console.warn('interface: scene not loaded', err);
    showStill(el);
    q<HTMLElement>('[data-ix-nowebgl]', el).hidden = false;
    status.hidden = true;
    return;
  }
  status.hidden = true;
  if (flags.record) document.documentElement.classList.add('nf-rec');
  new Interface(el, model, mod, flags, still).run();
}

class Interface {
  private el: HTMLElement;
  private m: Model;
  private scene: SceneApi;
  private t: number;
  private playing: boolean;
  private tour: boolean;
  private record: boolean;
  private showCaptions: boolean;
  private last = 0;
  private raf = 0;
  private visible = true;
  private selected: number | null = null;
  private byElectrode: Map<number, number[]>;
  private labels: Map<string, HTMLElement> = new Map();
  private captions: Map<string, string> = new Map();
  private colours: ReturnType<typeof themeColours>;
  private ui: {
    play: HTMLButtonElement;
    tour: HTMLButtonElement;
    readout: HTMLOutputElement;
    inspect: HTMLSelectElement;
    caption: HTMLElement;
    trace: HTMLCanvasElement;
    raster: HTMLCanvasElement;
  };

  constructor(
    el: HTMLElement,
    model: Model,
    mod: typeof import('./interface-scene.ts'),
    flags: ReturnType<typeof parseFlags>,
    still: boolean,
  ) {
    this.el = el;
    this.m = model;
    this.record = flags.record;
    this.showCaptions = flags.captions;
    this.t = flags.t;
    this.playing = !still;
    this.tour = flags.record;
    this.colours = themeColours(el);
    this.byElectrode = unitsByElectrode(model.unitElectrode);
    const stage = q<HTMLElement>('[data-ix-stage]', el);
    // The scene is running: swap the static fallback (still, caption) for the live stage and controls.
    el.querySelector('[data-ix-still]')?.remove(); // present only after the reduced-motion opt-in
    q<HTMLElement>('[data-ix-still-caption]', el).hidden = true;
    q<HTMLElement>('[data-ix-overlay]', el).hidden = false;
    for (const n of el.querySelectorAll<HTMLElement>('[data-ix-needs-scene]')) n.hidden = false;
    for (const s of el.querySelectorAll<HTMLElement>('[data-ix-label]'))
      this.labels.set(s.dataset.ixLabel ?? '', s);
    for (const li of el.querySelectorAll<HTMLElement>('[data-ix-captions] li'))
      this.captions.set(li.dataset.key ?? '', li.textContent ?? '');
    this.ui = {
      play: q('[data-ix-play]', el),
      tour: q('[data-ix-tour]', el),
      readout: q('[data-ix-readout]', el),
      inspect: q('[data-ix-inspect]', el),
      caption: q('[data-ix-caption]', el),
      trace: q('[data-ix-trace]', el),
      raster: q('[data-ix-raster]', el),
    };
    this.scene = mod.createScene({
      host: stage,
      model,
      theme: this.colours,
      interactive: !flags.record,
      onPick: (e) => this.select(e),
    });
    this.scene.setTour(this.tour, 0);
  }

  run() {
    const { ui } = this;
    for (const c of this.el.querySelectorAll<
      HTMLInputElement | HTMLButtonElement | HTMLSelectElement
    >('[data-ix-controls] button, [data-ix-controls] input, [data-ix-controls] select'))
      c.disabled = false;
    q<HTMLFormElement>('[data-ix-controls]', this.el).addEventListener('submit', (e) =>
      e.preventDefault(),
    );
    ui.play.addEventListener('click', () => this.setPlaying(!this.playing));
    ui.tour.addEventListener('click', () => this.setTour(!this.tour));
    q<HTMLButtonElement>('[data-ix-reset]', this.el).addEventListener('click', () => {
      this.setTour(false);
      this.scene.resetView();
      this.frame();
    });
    for (const b of this.el.querySelectorAll<HTMLButtonElement>('[data-ix-zoom]'))
      b.addEventListener('click', () => {
        this.setTour(false);
        this.scene.zoom(Number(b.dataset.ixZoom));
        this.frame();
      });
    for (const cb of this.el.querySelectorAll<HTMLInputElement>('[data-ix-layer]'))
      cb.addEventListener('change', () => {
        this.scene.setLayer(cb.dataset.ixLayer as Layer, cb.checked);
        this.frame();
      });
    ui.inspect.addEventListener('change', () =>
      this.select(ui.inspect.value ? Number(ui.inspect.value) : null),
    );

    const stage = q<HTMLElement>('[data-ix-stage]', this.el);
    if (!this.record) {
      // The live scene is operable: keyboard focus, arrows orbit, +/- zoom, Home resets (hint text).
      stage.setAttribute('role', 'group');
      stage.setAttribute('aria-describedby', 'ix-hint');
      stage.tabIndex = 0;
      stage.addEventListener('keydown', (e) => {
        const k = orbitKey(e.key);
        if (!k) return;
        e.preventDefault();
        this.setTour(false);
        if (k.rotate) this.scene.rotate(k.rotate[0], k.rotate[1]);
        if (k.zoom) this.scene.zoom(k.zoom);
        if (k.reset) this.scene.resetView();
        this.frame();
      });
    }
    // Reduced motion switched on while the page is open: stop the replay and the tour at once.
    matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change', (e) => {
      if (!e.matches || this.record) return;
      this.setTour(false);
      this.setPlaying(false);
    });
    new ResizeObserver(() => {
      this.scene.resize();
      this.frame();
    }).observe(stage);
    new IntersectionObserver((es) => {
      this.visible = es.some((e) => e.isIntersecting);
      if (this.visible && this.playing) this.loop();
    }).observe(stage);
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden && this.playing) this.loop();
    });

    if (this.record) {
      window.__seek = (tS: number) => {
        this.setPlaying(false);
        this.t = tS;
        this.frame();
      };
      // Deterministic frames need the web fonts (the 3D labels and captions are HTML text):
      // announce readiness only after they have loaded, so frame t never changes on a later seek.
      void document.fonts.ready.then(() => {
        this.frame();
        window.__record = { duration: TOUR_SECONDS, fps: 30, ready: true };
      });
    }
    this.setPlaying(this.playing);
    this.frame();
  }

  private setPlaying(on: boolean) {
    this.playing = on;
    this.ui.play.textContent = (on ? this.el.dataset.pause : this.el.dataset.play) ?? '';
    if (on) this.loop();
    else cancelAnimationFrame(this.raf);
  }

  private setTour(on: boolean) {
    this.tour = on;
    this.ui.tour.setAttribute('aria-pressed', String(on));
    this.scene.setTour(on, this.t);
    if (on && !this.playing) this.setPlaying(true);
    if (!on) this.ui.caption.textContent = '';
  }

  /** Polite screen-reader message for discrete changes (tour step, inspected electrode). */
  private announce(text: string) {
    q<HTMLElement>('[data-ix-live]', this.el).textContent = text;
  }

  private loop() {
    cancelAnimationFrame(this.raf);
    this.last = performance.now();
    const step = (now: number) => {
      if (!this.playing || !this.visible || document.hidden) return;
      this.t += Math.min(now - this.last, 100) / 1000;
      this.last = now;
      if (this.record && this.t > TOUR_SECONDS) this.t = TOUR_SECONDS;
      this.frame();
      this.raf = requestAnimationFrame(step);
    };
    this.raf = requestAnimationFrame(step);
  }

  private select(e: number | null) {
    this.selected = e;
    this.ui.inspect.value = e === null ? '' : String(e);
    this.scene.select(e);
    const units = e === null ? [] : (this.byElectrode.get(e) ?? []);
    q<HTMLElement>('[data-ix-inspect-title]', this.el).textContent =
      e === null ? '' : `· ${this.el.dataset.electrode} ${e}`;
    q<HTMLElement>('[data-ix-inspect-empty]', this.el).hidden = e !== null;
    q<HTMLElement>('[data-ix-inspect-nounits]', this.el).hidden = e === null || units.length > 0;
    q<HTMLElement>('[data-ix-inspect-body]', this.el).hidden = units.length === 0;
    if (e !== null)
      this.announce(
        `${this.el.dataset.electrode} ${e}, ${units.length} ${units.length === 1 ? this.el.dataset.unitWord : this.el.dataset.unitsWord}`,
      );
    this.frame();
  }

  private frame() {
    this.scene.renderAt(this.t);
    const { trial, tMs } = this.scene.replay(this.t);
    const d = this.el.dataset;
    this.ui.readout.textContent = `${d.trial} ${trial + 1} ${d.of} ${this.m.trials.length} · ${(tMs / 1000).toFixed(2)} s`;
    // 3D labels: no overlaps and no clipping at any stage width (mobile keeps primary labels only)
    const stage = q<HTMLElement>('[data-ix-stage]', this.el);
    const anchors = this.scene.labelAnchors().map((a) => {
      const s = this.labels.get(a.key);
      return { ...a, w: s?.offsetWidth ?? 0, h: s?.offsetHeight ?? 0 };
    });
    const shown = placeLabels(anchors, stage.clientWidth, stage.clientHeight);
    for (const a of anchors) {
      const s = this.labels.get(a.key);
      if (!s) continue;
      // visibility (not display) keeps each label measurable for the next frame
      s.classList.toggle('is-off', !shown.has(a.key));
      // left/top on whole pixels, not transform: a per-frame transform promoted labels to their own
      // compositor layers, and a label's antialiased corners then depended on whether it had been
      // shown in the previous frame (record-mode flake: frame t differed after a re-seek)
      s.style.left = `${Math.round(a.x - a.w / 2)}px`;
      s.style.top = `${Math.round(a.y - a.h)}px`;
    }
    if (this.tour && this.showCaptions) {
      const text = this.captions.get(this.scene.caption()) ?? '';
      if (text !== this.ui.caption.textContent) {
        this.ui.caption.textContent = text;
        this.announce(text); // once per tour step, not per frame
      }
    }
    if (this.selected !== null) this.drawInspect(trial, tMs);
  }

  /** Drawn trace (real spike times, illustrative waveform and noise) and the real raster. */
  private drawInspect(trial: number, tMs: number) {
    const units = this.byElectrode.get(this.selected ?? -1) ?? [];
    if (!units.length) return;
    const col = this.colours;
    const tr = this.m.trials[trial];
    const prep = (c: HTMLCanvasElement) => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const w = c.clientWidth;
      const h = c.clientHeight;
      if (c.width !== Math.round(w * dpr)) c.width = Math.round(w * dpr);
      if (c.height !== Math.round(h * dpr)) c.height = Math.round(h * dpr);
      const ctx = c.getContext('2d')!;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);
      return { ctx, w, h };
    };
    // trace: the last 300 ms up to now
    {
      const { ctx, w, h } = prep(this.ui.trace);
      const span = 300;
      const mid = h / 2;
      ctx.strokeStyle = col.ink;
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      for (let px = 0; px <= w; px++) {
        const ms = tMs - span + (px / w) * span;
        let y = Math.sin(ms * 1.7) * 1.3 + Math.sin(ms * 0.61 + 1) * 1.8; // drawn background
        units.forEach((u, k) => {
          const s = tr.spikes[u];
          const i = lastSpikeIndex(s, ms);
          if (i < 0) return;
          const dt = ms - s[i];
          if (dt < 1.6) {
            const amp = (h * 0.34) / (1 + k * 0.45);
            y +=
              dt < 0.4
                ? -amp * (dt / 0.4)
                : -amp +
                  amp * 1.35 * Math.min(1, (dt - 0.4) / 0.5) -
                  amp * 0.35 * Math.max(0, (dt - 0.9) / 0.7);
          }
        });
        if (px === 0) ctx.moveTo(px, mid + y);
        else ctx.lineTo(px, mid + y);
      }
      ctx.stroke();
    }
    // raster: the whole reach, playhead at now
    {
      const { ctx, w, h } = prep(this.ui.raster);
      const rowH = Math.min(22, (h - 8) / units.length);
      units.forEach((u, k) => {
        ctx.fillStyle = k % 2 ? col.secondary : col.accentInk;
        for (const s of tr.spikes[u]) {
          ctx.globalAlpha = s <= tMs ? 1 : 0.3;
          ctx.fillRect((s / tr.durationMs) * w, 4 + k * rowH, 2, rowH - 4);
        }
      });
      ctx.globalAlpha = 1;
      ctx.strokeStyle = col.accent;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo((tMs / tr.durationMs) * w, 0);
      ctx.lineTo((tMs / tr.durationMs) * w, h);
      ctx.stroke();
    }
  }
}
