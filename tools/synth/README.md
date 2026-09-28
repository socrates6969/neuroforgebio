# tools/synth (nf-synth)

Small, deterministic generator of multichannel EEG-like signals with **known ground truth**, for tests and CI
(BUILD-GUIDE 0.6). Synthetic only: no real human data. Whether synthetic data has privacy value is a hypothesis
(`market/new-ideas.md` #7), not a claim.

What a recording contains (defaults: 8 channels of the 10-20 montage, 256 Hz, 20 s, microvolts):

| Component | Ground truth in `truth.json` |
|---|---|
| 1/f aperiodic background (FFT-shaped white noise) | `aperiodic.exponent`, `rms_uv` |
| Alpha peak (full amplitude on posterior channels, 30 % elsewhere) | `alpha.freq_hz`, `amp_uv`, channels |
| Line noise (common mode) | `line_noise.freq_hz` (50), `amp_uv` |
| Blinks (300 ms bumps on Fp/F7/F8) | `blinks[]` onset, duration, channels |
| Muscle burst (20–100 Hz on temporal channels) | `muscle[]` |
| One noisy bad channel (C3 by default) | `bad_channels[]` |
| Event markers every 2 s, codes 1/2 | `events[]` onset, sample, code, label |
| Determinism check | `data_sha256` (float64 LE bytes) |

```sh
.venv/Scripts/python.exe -m nf_synth --seed 1 --formats edf,bdf,vhdr,xdf --out .synth-out   # run with tools/synth on PYTHONPATH
.venv/Scripts/python.exe -m pytest tools/synth                                               # local tests
```

Output goes to `.synth-out/` by default, which is git-ignored; `tools/repo-guard` fails CI if any `.edf/.bdf/...`
file is tracked. Tests write to pytest's `tmp_path`.

## Writers

| Format | Writer | Local check | CI check |
|---|---|---|---|
| EDF+C (16-bit, annotations) | hand-written | header + data decode in `test_synth.py` | `mne.io.read_raw_edf` |
| BDF+C (24-bit) | hand-written | same | `mne.io.read_raw_bdf` |
| BrainVision (.vhdr/.vmrk/.eeg float32) | hand-written | data + marker decode | `mne.io.read_raw_brainvision` |
| XDF 1.0 (EEG + marker stream) | hand-written | chunk structure | `pyxdf.load_xdf` (also passed once locally in a throwaway uv env) |
| NWB | pynwb (CI-only dependency) | skipped | `pynwb.NWBHDF5IO` read |

Reader tests live in `tests/test_readers.py` and are skipped when MNE/pynwb/pyxdf are absent. CI installs them
with `uv sync --locked --group readers`; the dev PC does not (RAM).

## Acceptance tests (BUILD-GUIDE 0.6)

- Measured PSD peak within one frequency bin of the injected alpha (Welch, 0.25 Hz bins; 4 seeds × 3 frequencies).
- Deterministic for a fixed seed (same numpy version, pinned by `uv.lock`; other versions: compare within tolerance).
- Files open in MNE, pynwb and pyxdf: CI-only.
