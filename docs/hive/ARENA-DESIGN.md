# Decoder Arena — design (nfb-arena, 2026-09-27)

Route: `/arena`. New page only — the homepage, nav and every other route are untouched.

Moved here from `apps/web/src/pages/arena/DESIGN.md` (2026-09-27): Astro's file-based
routing treats *any* `.md`/`.astro` file under `src/pages/` as a route, so that location
was actually building a live `/arena/DESIGN/` page — found by running `pnpm build:clinical`
for real, not by inspection. `docs/hive/` is outside the pages tree and matches where the
website hive's other feature-design docs already live (`T3-ARENA-WASM-PLAN.md`,
`HOSTING-HEADERS.md`, etc.).

## What it is

A research demo, not a medical device and not a hardware-control surface. A visitor:

1. Picks a decoder — ridge regression, a linear Kalman filter, or a small GRU-style
   recurrent net — and its hyperparameters.
2. Runs it **live in their own browser** (Rust compiled to WebAssembly — no server round
   trip, no upload of any data) against the same open, CC-BY neural recording the Neural
   Playground uses (MC_RTT, DANDI 000129).
3. Gets back a signed **Evaluation Card**: R², a bootstrap confidence interval, the
   planted-leak check result, the scoring convention used, and the achieved statistical
   power (shuffle-null test), plus a local leaderboard of that visitor's own runs
   (browser-only storage, never sent anywhere).

Call to action, copy only, no accounts/payments/backend: *"Evaluate your own decoder
privately"*. Note: no playground page exists yet on this branch to match wording against
(see below), so this copy is new and should be reconciled with the playground's own CTA
wording once `feature/neural-playground` merges, rather than assumed consistent with it.

## Data dependency: WIRED (2026-09-27, after feature/neural-playground merged as 6a79900)

`tools/arena-core/src/mc_rtt.rs` parses `apps/web/src/assets/playground/mc-rtt-playground.json`
(schema `nf-playground/1`) directly — same asset `/playground` uses, no separate copy, no raw
NWB/DANDI data anywhere in this crate. It bins raw per-unit spike times into
`Trial`/`Dataset` (see `src/data.rs`), selects a population subset from the asset's fixed
`unitOrder`, and optionally adds the asset's precomputed noise spikes up to a requested
`noiseHz` tier. Provenance (dandiset, DOI, licence, citation, sha256) rides along on every
`PositionEvaluationCard` so the page can show exactly where the numbers came from.

**Important, deliberate limitation, stated plainly rather than glossed over**: the shipped
asset only carries the **12 representative test reaches** used for `/playground`'s own
visualizations (`method.shownTrials`), not the full 330 train / 100 test reaches its
headline R² numbers were computed from offline. A Decoder Arena run fits and scores on a
block-split of those same 12 trials — its R² is real and computed live in-browser, not
replayed from `/playground`, but it is necessarily noisier and **not comparable** to
`/playground`'s reported numbers. `tools/arena-core/tests/mc_rtt.rs` runs the full pipeline
end to end against the real asset (parses it, checks provenance, confirms noise levels
nest correctly, confirms the leak check never false-positives on real spike data) but does
not assert any particular R² value, for exactly this reason. The Evaluation Card's
`scoring_convention` string and this page's copy must keep saying so.

`x`/`y` cursor position are scored as two independent scalar decodes (this crate has no
vector-label decoder) and averaged into `mean_r2`, matching
`tools/playground/nf_playground/decoders.py::r2_score`'s convention.

## Crate: `tools/arena-core`

Pure Rust, no I/O, no network, no hardware — see `tools/arena-core/README` for the module
map. Evaluation always uses a **block-wise** (per-trial) train/test split, never a random
per-sample shuffle, because a per-sample split leaks temporal neighbours of test points
into training on any decoder with memory (Kalman, GRU) and inflates R² on the linear
decoder too via autocorrelated neural noise.

Evaluation Card fields (`src/eval.rs::EvaluationCard`):
- `decoder`, `hyperparameters`
- `r2` on held-out trial blocks
- `r2_ci_95` — percentile bootstrap over held-out trials (resample trials with
  replacement, not samples, to respect the same block structure)
- `leak_check` — pass/fail per input channel; a channel whose zero-lag correlation with
  the label exceeds a fixed threshold is flagged (see "Leak control")
- `shuffle_null` — mean/sd of R² under label-block permutation, the observed z-score and
  one-sided empirical p-value against that null (same convention as the BCI hive's 002
  harness: power comes from arithmetic against a shuffle-null, not an assumed formula)
- `scoring_convention` — a fixed string documenting exactly what's computed, so the card
  is self-describing

## Leak control

One fixture channel is defined as `label + tiny_noise` (a deliberate, known leak). The
harness's leak check flags any input channel whose zero-lag Pearson correlation with the
label exceeds a threshold; a cargo test asserts (a) the planted-leak channel is always
flagged and (b) a clean fixture with no such channel is never falsely flagged. This is the
control that must be caught before any evaluation is trusted, per the brief.

## Decoders

- **Ridge**: closed-form L2-regularized linear regression (`nalgebra`), one-shot fit.
- **Kalman**: standard linear-Gaussian state-space decoder (fixed A/H, C/W learned by
  least squares from training trials, matches the classic BCI kinematic-decode setup).
- **Small GRU-like net**: honesty note — this is a **fixed-gate GRU-style reservoir**
  (random, fixed recurrent gating dynamics) with a **trained linear readout** (ridge) on
  the hidden state trajectory, not a fully backprop-trained GRU. That's a real, working
  nonlinear-with-memory decoder and it's cheap enough to run in-browser at interactive
  latency, but the Evaluation Card must say so plainly (`decoder: "gru_reservoir"`) rather
  than implying full BPTT training happened — evidence rules apply to this page too.

## Build status

| Piece | Status |
|---|---|
| `tools/arena-core` (native, x86_64-pc-windows-msvc) | Written, 11 tests (6 original + 5 `mc_rtt`); pending a compile-slot run to confirm they pass (queued, see WEB-BOARD.md for live status) |
| `wasm32-unknown-unknown` bindings (`tools/arena-core/src/wasm.rs`) | `cargo check -p arena-core --features wasm --target wasm32-unknown-unknown` **passes**. `wasm-bindgen-cli 0.2.129` installed (lead-approved). Not yet run to produce the actual `.wasm`/JS bundle — that's an owner-approved CI job (Actions minutes), not done locally |
| `apps/web/src/assets/arena/{loader.mjs,loader-stub.mjs}` + `astro.config.mjs`'s `virtual:arena-loader` alias | Written: when `pkg/` (CI artifact, never committed) is present, Vite content-hashes the glue + `.wasm` normally; when absent, the build aliases to a zero-wasm stub instead. **NOT exercised with a real `pkg/` yet** — only the "absent" path has actually been build-tested |
| `/arena` Astro page (`apps/web/src/pages/arena/index.astro`) | Written: renders full interactive controls when `pkg/` exists, a plain "decoder loading unavailable" message (no script, no wasm reference) when it doesn't. Node/Astro were banned until 2026-09-27, now allowed — pending an actual `astro build` + `node --test` run to confirm both states render as designed |

Nothing here has been claimed as working beyond what actually ran. See
`docs/adr/0014-csp-wasm-exception-arena.md` for the CSP exception this page needs and its
approval conditions, and `tools/arena-core/README.md` for the wasm build recipe and its own
history of scheme changes on 2026-09-27.
