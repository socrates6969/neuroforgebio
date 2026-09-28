// Decoder Arena client: runs a ridge / Kalman / GRU-reservoir decoder live in the visitor's own
// browser (Rust compiled to WebAssembly, tools/arena-core) against the same open MC_RTT/DANDI-000129
// asset the Neural Playground uses. No data leaves the browser: the asset is fetched once as a
// same-origin file, the WASM module runs entirely client-side, and the leaderboard lives only in
// this page's memory for the current load -- no cookies, no localStorage/sessionStorage/IndexedDB
// (the site's cookie statement says "none", and main's security.test.mjs enforces it). Nothing
// here fits or trains an offline model, no hardware or device API involved.
import assetUrl from '../assets/playground/mc-rtt-playground.json?url';
import { parsePlayground, formatR2 } from '../lib/playground-data.mjs';
// Resolved by astro.config.mjs to the real loader (apps/web/src/assets/arena/loader.mjs) when
// apps/web/src/assets/arena/pkg/ exists, or a zero-wasm stub otherwise. This page is only
// reachable when the astro frontmatter already found pkg/ present (see index.astro), so
// AVAILABLE should always be true here; it's still checked as a defense-in-depth safety net.
import { AVAILABLE, initArena, runMcRttEvaluation } from 'virtual:arena-loader';

type Model = ReturnType<typeof parsePlayground>;

// Mirrors tools/arena-core::eval::{EvaluationCard, PositionEvaluationCard} (serde field names).
interface EvaluationCard {
  decoder: string;
  n_train_trials: number;
  n_test_trials: number;
  r2: number | null;
  r2_ci_95: [number, number] | null;
  leak_check: { any_leak_detected: boolean; threshold: number; flagged_channels: number[] };
  shuffle_null: {
    observed_r2: number;
    null_mean: number;
    null_std: number;
    p_value: number;
    n_shuffles: number;
  } | null;
  scoring_convention: string;
}
interface PositionEvaluationCard {
  x: EvaluationCard;
  y: EvaluationCard;
  mean_r2: number | null;
}

interface LeaderboardEntry {
  ts: number;
  decoder: string;
  params: string;
  nUnits: number;
  noiseHz: number;
  meanR2: number | null;
  leak: boolean;
}

const LEADERBOARD_MAX = 20;

const root = document.querySelector<HTMLElement>('[data-arena]');
if (root) void init(root);

function q<T extends Element>(el: ParentNode, sel: string): T {
  const found = el.querySelector<T>(sel);
  if (!found) throw new Error(`arena: missing ${sel}`);
  return found;
}

async function init(el: HTMLElement) {
  const status = q<HTMLElement>(el, '[data-arena-status]');
  status.hidden = false;

  let model: Model;
  let assetText: string;
  try {
    const res = await fetch(assetUrl, { credentials: 'same-origin' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    assetText = await res.text();
    model = parsePlayground(JSON.parse(assetText));
  } catch (err) {
    status.textContent = el.dataset.loadError ?? 'Could not load the dataset.';
    console.warn('arena: asset not loaded', err);
    return;
  }

  let runEvaluation: (
    assetJson: string,
    nUnits: number,
    noiseLevelIndex: number,
    choiceJson: string,
    seed: number,
  ) => string;
  if (!AVAILABLE) {
    // Shouldn't happen: index.astro only emits this script when pkg/ was present at build
    // time. Kept as a safety net rather than assuming that invariant always holds.
    status.textContent = el.dataset.wasmError ?? 'Could not load the evaluator.';
    console.warn('arena: evaluator unavailable (virtual:arena-loader resolved to the stub)');
    return;
  }
  try {
    await initArena();
    runEvaluation = runMcRttEvaluation;
  } catch (err) {
    status.textContent = el.dataset.wasmError ?? 'Could not load the evaluator.';
    console.warn('arena: wasm not loaded', err);
    return;
  }

  status.hidden = true;
  new Arena(el, model, assetText, runEvaluation).start();
}

class Arena {
  private el: HTMLElement;
  private m: Model;
  private assetText: string;
  private run: (a: string, n: number, l: number, c: string, s: number) => string;
  private ui: {
    decoder: HTMLSelectElement;
    ridgeLambda: HTMLInputElement;
    gruHidden: HTMLInputElement;
    units: HTMLInputElement;
    unitsOut: HTMLOutputElement;
    button: HTMLButtonElement;
    live: HTMLElement;
    card: HTMLElement;
    board: HTMLTableSectionElement;
  };
  private seedCounter = 1;

  constructor(
    el: HTMLElement,
    model: Model,
    assetText: string,
    run: (a: string, n: number, l: number, c: string, s: number) => string,
  ) {
    this.el = el;
    this.m = model;
    this.assetText = assetText;
    this.run = run;
    this.ui = {
      decoder: q(el, '[data-arena-decoder]'),
      ridgeLambda: q(el, '[data-arena-ridge-lambda]'),
      gruHidden: q(el, '[data-arena-gru-hidden]'),
      units: q(el, '[data-arena-units]'),
      unitsOut: q(el, '[data-arena-units-out]'),
      button: q(el, '[data-arena-run]'),
      live: q(el, '[data-arena-live]'),
      card: q(el, '[data-arena-card]'),
      board: q(el, '[data-arena-board]'),
    };
  }

  start() {
    const lastCount = this.m.neuronCounts.length - 1;
    this.ui.units.max = String(lastCount);
    this.ui.units.value = String(lastCount);
    this.ui.unitsOut.value = String(this.m.neuronCounts[lastCount]);
    for (const control of [
      this.ui.decoder,
      this.ui.ridgeLambda,
      this.ui.gruHidden,
      this.ui.units,
    ]) {
      control.disabled = false;
    }
    this.ui.button.disabled = false;

    const unitsUnit = this.el.dataset.unitsUnit ?? '';
    this.ui.units.addEventListener('input', () => {
      const i = Number(this.ui.units.value);
      const n = this.m.neuronCounts[i] ?? this.m.neuronCounts[lastCount];
      this.ui.unitsOut.value = String(n);
      // Mirrors /playground's pattern (settingsChanged() in playground.ts): the visible
      // <output> alone isn't announced to screen readers, so the slider needs its own
      // accessible value text too, not just the index a screen reader would otherwise read.
      this.ui.units.setAttribute('aria-valuetext', `${n} ${unitsUnit}`);
    });
    this.ui.decoder.addEventListener('change', () => this.syncParamVisibility());
    this.syncParamVisibility();

    this.ui.button.addEventListener('click', () => this.runOnce());
    this.renderLeaderboard();
  }

  private syncParamVisibility() {
    const kind = this.ui.decoder.value;
    this.ui.ridgeLambda.closest<HTMLElement>('.arena-param')!.hidden = kind === 'kalman';
    this.ui.gruHidden.closest<HTMLElement>('.arena-param')!.hidden = kind !== 'gru_reservoir';
  }

  private runOnce() {
    const noiseIndex = Number(
      (this.el.querySelector('input[name="arena-noise"]:checked') as HTMLInputElement | null)
        ?.value ?? '0',
    );
    const unitsIndex = Number(this.ui.units.value);
    const nUnits = this.m.neuronCounts[unitsIndex] ?? this.m.neuronCounts.at(-1)!;
    const kind = this.ui.decoder.value;
    const choice = {
      kind,
      ridge_lambda: Number(this.ui.ridgeLambda.value) || 1.0,
      gru_hidden_dim: Number(this.ui.gruHidden.value) || 32,
      gru_seed: 1,
    };
    const seed = this.seedCounter++;

    this.ui.live.textContent = 'Running...';
    this.ui.button.disabled = true;
    // Runs synchronously on the main thread (single decoder fit on <=12 small trials is a
    // few ms); a worker would only matter for a much larger in-browser dataset.
    try {
      const json = this.run(this.assetText, nUnits, noiseIndex, JSON.stringify(choice), seed);
      const card: PositionEvaluationCard = JSON.parse(json);
      this.renderCard(card, kind, nUnits, this.m.noiseHz[noiseIndex]);
      this.pushLeaderboard({
        ts: Date.now(),
        decoder: kind,
        params:
          kind === 'gru_reservoir'
            ? `hidden=${choice.gru_hidden_dim}`
            : `lambda=${choice.ridge_lambda}`,
        nUnits,
        noiseHz: this.m.noiseHz[noiseIndex],
        meanR2: card.mean_r2,
        leak: card.x.leak_check.any_leak_detected || card.y.leak_check.any_leak_detected,
      });
      this.renderLeaderboard();
      this.ui.live.textContent = `Run complete: mean R² ${formatR2(card.mean_r2 ?? NaN)}.`;
    } catch (err) {
      this.ui.live.textContent = 'That run failed; see the console.';
      console.warn('arena: evaluation failed', err);
    } finally {
      this.ui.button.disabled = false;
    }
  }

  private renderCard(
    card: PositionEvaluationCard,
    decoder: string,
    nUnits: number,
    noiseHz: number,
  ) {
    const ci =
      card.x.r2_ci_95 && card.y.r2_ci_95
        ? `[${formatR2((card.x.r2_ci_95[0] + card.y.r2_ci_95[0]) / 2)}, ${formatR2((card.x.r2_ci_95[1] + card.y.r2_ci_95[1]) / 2)}]`
        : '–';
    const leaked = card.x.leak_check.any_leak_detected || card.y.leak_check.any_leak_detected;
    const pValue =
      card.x.shuffle_null && card.y.shuffle_null
        ? Math.max(card.x.shuffle_null.p_value, card.y.shuffle_null.p_value)
        : null;
    const ds = this.m.dataset;

    this.ui.card.innerHTML = `
      <dl class="arena-nums">
        <div><dt>Decoder</dt><dd>${escapeHtml(decoder)}</dd></div>
        <div><dt>Mean R² (x, y)</dt><dd class="big">${formatR2(card.mean_r2 ?? NaN)}</dd></div>
        <div><dt>95% CI (mean)</dt><dd>${ci}</dd></div>
        <div><dt>Leak check</dt><dd class="${leaked ? 'bad' : 'ok'}">${leaked ? 'FLAGGED — do not trust this run' : 'passed'}</dd></div>
        <div><dt>Shuffle-null p</dt><dd>${pValue === null ? '–' : pValue.toFixed(3)}</dd></div>
        <div><dt>Train / test trials</dt><dd>${card.x.n_train_trials} / ${card.x.n_test_trials}</dd></div>
        <div><dt>Units used</dt><dd>${Number(nUnits)} of ${Number(this.m.units)}</dd></div>
        <div><dt>Added noise</dt><dd>${Number(noiseHz) === 0 ? 'none' : `+${Number(noiseHz)} Hz`}</dd></div>
      </dl>
      <p class="arena-convention">${escapeHtml(card.x.scoring_convention)}</p>
      <p class="arena-caveat">Only 12 held-out reaches ship in this asset (the same ones
        <a href="/playground/">/playground</a> visualises), far fewer than the 330/100 train/test
        reaches its own headline numbers use — so this R² is real and computed live, but
        noisier and not comparable to /playground's reported numbers.</p>
      <p class="arena-source">${escapeHtml(ds.shortName)}, DANDI ${escapeHtml(ds.dandiset)}, ${escapeHtml(ds.licence)}. sha256:${escapeHtml(ds.sha256.slice(0, 12))}…</p>
    `;
  }

  // In-memory only, for the current page load -- never persisted (no cookies, no
  // localStorage/sessionStorage/IndexedDB; see the file header comment and DESIGN doc).
  private leaderboard: LeaderboardEntry[] = [];

  private pushLeaderboard(entry: LeaderboardEntry) {
    this.leaderboard = [entry, ...this.leaderboard].slice(0, LEADERBOARD_MAX);
  }

  private renderLeaderboard() {
    this.ui.board.innerHTML = this.leaderboard
      .map(
        (e) => `
      <tr>
        <td>${new Date(e.ts).toLocaleTimeString()}</td>
        <td>${escapeHtml(e.decoder)}</td>
        <td>${escapeHtml(e.params)}</td>
        <td>${Number(e.nUnits)}</td>
        <td>${Number(e.noiseHz) === 0 ? '–' : `+${Number(e.noiseHz)}`}</td>
        <td>${formatR2(e.meanR2 ?? NaN)}</td>
        <td>${e.leak ? 'FLAGGED' : 'ok'}</td>
      </tr>`,
      )
      .join('');
  }
}

function escapeHtml(s: string): string {
  return s.replace(
    /[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!,
  );
}
