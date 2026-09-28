# tools/playground (nf-playground)

Offline pipeline behind the website's **Neural Playground** (`apps/web/src/pages/playground.astro`). It reads one
open NWB file, fits two linear decoders, and writes one compact JSON asset
(`apps/web/src/assets/playground/mc-rtt-playground.json`). The browser only replays that asset: nothing is decoded
in the browser, nothing runs in real time, and no hardware is controlled.

Research demo on open monkey data. Not a medical device.

## Dataset (pinned)

| | |
|---|---|
| Dataset | MC_RTT, Neural Latents Benchmark: macaque motor cortex spiking activity during self-paced reaching (monkey Indy, Sabes lab) |
| Archive | DANDI `000129`, version `0.241017.1444`, <https://doi.org/10.48324/dandi.000129/0.241017.1444> |
| File | `sub-Indy/sub-Indy_desc-train_behavior+ecephys.nwb`, asset `2ae6bf3c-788b-4ece-8c01-4b4a5680b25b`, 49,764,168 bytes |
| SHA-256 | `2f78db62bd4d68b9bc737444f72bc2dfe475d7390dd7a54848aaf6a6a6ba8da5` (equals DANDI's `dandi:sha2-256`; checked on every run) |
| Licence | CC-BY-4.0 (DANDI metadata `spdx:CC-BY-4.0`) |
| Citation | O'Doherty, Joseph (2024) MC_RTT: macaque motor cortex spiking activity during self-paced reaching (Version 0.241017.1444) [Data set]. DANDI archive. https://doi.org/10.48324/dandi.000129/0.241017.1444 |
| Recording | 130 sorted units from a 96-channel Utah array in primary motor cortex (NWB electrode location `M1`); cursor position, finger velocity and target position at 1 kHz; 649 s |

Why this file: it is open (CC-BY-4.0, no sign-up), small, and **not** one of the files embargoed for the blind tests
of the motor-readout M1 track and the BCI hive (MC_Maze DANDI 000138/000140, LINK 001201, EEGMMIDB). The
motor-readout data plan (`research/neurobiology/motor-readout/notes/data_plan.md`) lists MC_RTT as "Not used". The
NLB test file of the same dandiset carries no behaviour and is not downloaded.

CC-BY-4.0 requires attribution and a note of changes. The page and the asset carry the citation, licence and DOI;
the changes are: spikes binned and decoded, a subset of test reaches excerpted, positions rounded to 0.1 mm, and
synthetic noise spikes added where stated. See `apps/web/src/assets/playground/THIRD_PARTY_NOTICE.md`.

## Method

- **Bins:** 50 ms, inside continuous stretches of the recording (NaN gaps split the session into segments;
  spike history never crosses a gap). Behaviour per bin = mean cursor position (mm) and finger velocity (mm/s).
- **Trials:** one trial = one reach, from a target change to the next one, kept if it lasts 0.3-3.0 s
  (539 reaches).
- **Split by trial:** reaches in chronological blocks of 10; every 5th block is **test**, the block before it is
  **validation**, the rest is **training** (330 / 109 / 100 reaches). Hyper-parameters are chosen on validation,
  decoders are refit on training + validation, and every reported number and every displayed trace comes from
  test reaches only.
- **Ridge (Wiener) filter:** counts from the current and 9 previous bins (500 ms causal history), z-scored;
  targets = position and velocity; L2 penalty chosen per setting from {1, 10, 100, 1000, 10000} on validation.
- **Kalman filter:** state = position and velocity with an offset, observation = spike counts, all matrices fit by
  least squares (Wu et al. 2003 style); spikes lead the state by a lag chosen once on validation (2 bins = 100 ms).
  Causal filtering; the state resets at each recording gap.
- **Neurons:** 8, 16, 32, 64 and all 130 units. Subsets are the first *k* units of a fixed random order (nested).
  Each setting is also refit on 4 further random subsets for the chart's min-max band.
- **Noise:** random extra spikes (Poisson) at 0, 5, 10 and 20 spikes per second per unit, added to training and
  test alike (the decoder is refit on noisy data). Levels are nested: every spike at 5/s is also present at 10/s.
  For scale, the recorded units fire 4.03 spikes/s on average.
- **Score:** R² = 1 - SSE/SST per axis, averaged over x and y, pooled over all test bins. Position R² is the headline
  (it is what the path shows); velocity R² is reported too.
- **Negative control:** the ridge filter refit on movements shifted by half the session scores test R² -0.050.
- **Shown trials:** 12 test reaches lasting 0.8-2.0 s, evenly spaced in time, chosen by that rule before decoding
  (not by score).
- Seed `20260927`; numpy only for the decoders (h5py to read the file). Deterministic: two runs produce a
  byte-identical asset.

## Results (test reaches, all 130 units, no added noise)

| Decoder | Position R² | Velocity R² |
|---|---|---|
| Ridge (Wiener) filter | 0.601 | 0.568 |
| Kalman filter | 0.657 | 0.454 |

With 8 units: position R² 0.092 (ridge) and 0.077 (Kalman). The full grid is in the asset and on the page.
These are within-session numbers on one monkey; they are not a benchmark claim.

## Run

Raw data stays outside the repo (default `~/playground-data`, override with `NF_PLAYGROUND_DATA` or `--nwb`).

```sh
# 1. download the pinned file (about 50 MB)
curl -L -o ~/playground-data/sub-Indy_desc-train_behavior+ecephys.nwb \
  https://api.dandiarchive.org/api/assets/2ae6bf3c-788b-4ece-8c01-4b4a5680b25b/download/

# 2. build the asset (needs numpy + h5py; about 4 minutes on 4 threads)
OMP_NUM_THREADS=4 PYTHONPATH=tools/playground python -m nf_playground

# 3. unit tests (numpy only, synthetic data; no download)
PYTHONPATH=tools/playground python -m pytest tools/playground/tests
```

The run fails if the file's SHA-256 differs from the pin. `apps/web/test/playground.test.mjs` checks that the asset,
this README and `nf_playground/dataset.py` carry the same hash.

## Asset format (`nf-playground/2`, the compact form of `nf-playground/1`)

`dataset` (ids, licence, citation, hash), `method` (bins, split, lags, chosen hyper-parameters, control),
`neuronCounts`, `noiseHz`, `decoders`, `unitOrder`, `bounds`, `posScale` (positions are integers in 0.1 mm),
`results[decoder][neuronIdx][noiseIdx]` = {posR2, velR2, posR2Mean, posR2Min, posR2Max, subsets}, and `trials[]`
with spike times (ms, per unit), noise spikes as (ms, first level) pairs, the true path and the decoded paths for
every setting. The web loader (`apps/web/src/lib/playground-data.mjs`) validates all of it.

The file is written as `nf-playground/2` (`nf_playground/encode.py`): the same integers, stored as first value
plus differences (paths per coordinate), with noise levels as one digit per spike. It is lossless:
`encode.py` refuses to write unless `expand(compact(v1)) == v1`, the loader expands it back to the `/1` arrays,
and `apps/web/test/playground.test.mjs` pins a digest of the decoded model. Transcoding the committed `/1` file
took it from 366,649 to 286,556 bytes (gzip 141,293 to 106,162, -25%).

## Neural interface in 3D (`/interface`)

`apps/web/src/pages/interface.astro` + `src/scripts/interface.ts` (entry) + `src/scripts/interface-scene.ts` (three.js
0.160.0, bundled, loaded only by a dynamic `import()` on that route; `apps/web/test/bundle.test.mjs` checks that no
other page loads three.js). The scene reuses this asset: spike times drive the neuron glow and the pulses up each
shank and the lead; the cursor screen and the arm follow the ridge-filter output (all units, no added noise) on the
same test reaches, replayed at half speed.

What is drawn, not measured: the tissue, the Utah-style array, lead, headstage and arm; the voltage trace in the
electrode inspector (its spikes sit at real spike times, the waveform and noise are illustrative); and where each
neuron sits. The NWB file gives each unit's electrode id (`unitElectrode` in the asset) but no array map, so
electrode *k* is drawn at slot *k* of a 10 x 10 grid without corners.

Without WebGL, or with reduced motion on, the page shows a still (`apps/web/src/assets/interface/`) and offers the
scene on request (it then stays still until Play).

## Record mode (video) and stills

Both pages take `?record=1`: page chrome is hidden, nothing autoplays, and every frame is a pure function of time.

| | `/playground/?record=1` | `/interface/?record=1` |
|---|---|---|
| Timeline | the 12 test reaches once, half speed, 0.9 s rest between them | the guided-tour camera path |
| Duration | `window.__record.duration` (39.3 s) | `window.__record.duration` (26 s, ends where it starts) |
| Seek | `window.__seek(t)` renders exactly the frame at *t* seconds | same |
| Extra flags | | `&captions=0` (no tour captions), `&t=<s>` (start time) |

Capture at 30 fps by calling `__seek(i / 30)` and screenshotting each frame. Serve a build with
`node apps/web/scripts/serve.mjs apps/web/dist/<clinical|cosmos> <port>` (Node 22).

Stills: `node tools/playground/render-stills.mjs http://127.0.0.1:<port> <theme>` writes
`marketing/stills/neural-interface/interface-<theme>-t<s>.jpg` (2560x1440; t = 0.5 overview, 6 array, 11 neurons,
21 decoder and outputs) and the page fallback stills. WebGL runs in SwiftShader, so no GPU is needed.
