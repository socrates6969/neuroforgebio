# Toolchain plan for coder-verifier (from neuroinformatics, 2026-09-26)
Full inventory with sources: ..\lit\neuroinformatics.md. Nothing has been installed. Every wheel below was confirmed on
PyPI JSON as a cp312-win_amd64 build or as pure Python, and the dependency closure was resolved with
`pip install --dry-run --only-binary=:all:` against this venv (Python 3.12.10, numpy 2.5.3, scipy 1.18.1).

## 1. pip installs (run in C:\Users\mariu\neuro-company\.venv; tiers are independent)
Tier 1 covers the TouchSim afferent model and NWB reading. It is needed for all three datasets.
```
python -m pip install numba==0.67.0 llvmlite==0.49.0 scikit-image==0.26.0 pynwb==4.2.0 hdmf==6.2.0 h5py==3.16.0 remfile==0.1.15 pytest
```
- Wheels:
  - numba-0.67.0-cp312-cp312-win_amd64 (2.8 MB)
  - llvmlite-0.49.0-cp312-cp312-win_amd64 (41.9 MB)
  - scikit_image-0.26.0-cp312-cp312-win_amd64 (11.9 MB)
  - h5py-3.16.0-cp312-cp312-win_amd64 (3.2 MB)
  - pynwb-4.2.0 / hdmf-6.2.0 / remfile-0.1.15: py3-none-any
- The resolver also pulls in pandas 3.0.6 (cp312 win wheel), networkx 3.7, imageio 2.37.4, tifffile, lazy-loader,
  jsonschema, ruamel.yaml, platformdirs and requests.
- numba 0.67 needs numpy<2.6. The installed 2.5.3 satisfies this, so **do not upgrade numpy past 2.5.x**.

Tier 2 covers reduced network models of ICMS (Brian2).
```
python -m pip install brian2==2.10.1
```
- Wheel: brian2-2.10.1-cp312-cp312-win_amd64 (1.08 MB). It pulls in Cython 3.1.3 (cp312 win wheel), sympy 1.14.0,
  jinja2 and py-cpuinfo.
- There is no MSVC Build Tools on this PC (assumed; check with `where cl`). Without them, set
  `prefs.codegen.target = 'numpy'`. The Cython target needs MSVC (Brian2 install docs).

Do NOT install:
- nest-simulator: no Windows wheel on PyPI and no win-64 build on conda-forge.
- NEURON: no Windows wheel; the only Windows route is a 56 MB .exe installer outside the venv.
- dandi CLI: its dependency closure is heavy (deno, tensorstore, zarr, aiohttp). Use curl on the asset URLs instead.
- nlb_tools: it pins pandas<=1.3.4, which has no cp312 wheel, so it cannot be installed here.

TouchSim is not on PyPI and has no license (internal use only). Get it as a 52 KB zip:
```
curl -L -o C:\Users\mariu\neuro-company\research\somatosensory\code\vendor\touchsim-master.zip https://github.com/hsaal/touchsim/archive/refs/heads/master.zip
```
Unzip it, add `...\vendor\touchsim-master` to sys.path (a plain `pip install` misplaces surfaces/hand.png, which is loaded
at import), then run `python -m pytest tests` inside that folder. It is uses `np.bool` (transduction.py:86), which is valid again
in numpy 2.x. py3.12 compatibility is **UNVERIFIED until pytest passes**. A copy of the zip is already in the scratchpad:
C:\Users\mariu\AppData\Local\Temp\claude\C--Users-mariu\2dcc3945-43e6-45fb-9a6f-2985750d27b3\scratchpad\touchsim-master.zip

## 2. Datasets (< 300 MB each; all CC-BY-4.0 on DANDI; download with curl -L -o <file> <url>)
Suggested folder: C:\Users\mariu\neuro-company\research\somatosensory\code\data\ . Open files lazily
(`NWBHDF5IO(path,'r')`, slice arrays) and never load full arrays, because RAM is about 3 GB.

### D1. DANDI 001868 (v0.260715.2016): chronic ICMS in mouse S1 with 2-photon imaging, passive-control animals (about 95 MB for all; start with 3 files, 12.7 MB)
- sub-ICMS43_ses-2022-01-11_ophys.nwb, 4.61 MB:
  https://api.dandiarchive.org/api/assets/86908791-392b-4f26-b6fa-e3bdea8de6c1/download/
- sub-ICMS45_ses-2022-02-12_ecephys+ophys.nwb, 2.63 MB:
  https://api.dandiarchive.org/api/assets/8c8eabdf-b479-4e5e-b476-76a5c69481e8/download/
- sub-ICMS54_ses-2022-06-01_ecephys+ophys.nwb, 5.43 MB:
  https://api.dandiarchive.org/api/assets/1b152ad8-263c-4a70-b7b5-43c0616a65ec/download/
- The remaining passive files (0.3–5.4 MB each) are listed via
  https://api.dandiarchive.org/api/dandisets/001868/versions/0.260715.2016/assets/?page_size=100
- DANDI description: "per-neuron activation measurements across stimulation channels and current amplitudes for passive
  controls".
- Supports test T1 (Stoney vs Histed in S1): as ICMS amplitude rises, does the **number or density** of activated neurons
  rise while their **spatial extent** plateaus? Fit I = K·r² (Stoney/Tehovnik) against a fixed-volume density model
  (Histed/Kumaravelu 2022) and compare them by AIC or cross-validated likelihood.
- Caveats: mouse trunk S1, GCaMP (not spikes), preprint-level source (grade C).

### D2. DANDI 000774 (v0.260520.1753): 3-probe Neuropixels around a single-pulse electrical stimulation site, mouse V1 (one session, 56.7 MB)
- sub-jlh33_ses-jlh33-2023-02-22-15-24-35_ecephys.nwb, 56.7 MB:
  https://api.dandiarchive.org/api/assets/9ecf6b0a-11ab-480b-bac3-60b7f16050cc/download/
- Next smallest: sub-jlh39, 76.2 MB:
  https://api.dandiarchive.org/api/assets/7928a4b8-71ab-47d5-9b0b-98152e48219e/download/
- Supports test T2 (current-spread geometry): compare the evoked potential against distance with the point-source
  prediction V = ρI/(4πr), using ρ = 5.8 Ω·m (the value the authors use).
- Supports test T3: the fraction of direct responders (latency within 2 ms) against amplitude (5/25/50/100 µA) and
  distance. The published summary to reproduce is "<5% directly activated; density but not extent increases" (Hickman
  et al. 2026 Cell Rep, PMID 42207642).
- Reference analysis code: github.com/denmanlab/estim_populations (GPL-3.0).
- Caveat: V1, not S1.

### D3. DANDI 001056 (draft): NeuroTask "Center-Out with bump" (54.5 MB, 1 file)
- sub-Animal-1-&-2.nwb, 54.5 MB:
  https://api.dandiarchive.org/api/assets/64b856dd-97ad-4829-a971-95933297dc63/download/
- Supports test T4 (proprioceptive encoding target for ICMS): decode bump/reach direction and hand velocity from binned
  spike counts (linear/Poisson GLM). This gives the "natural" area 2 code that a biomimetic proprioceptive ICMS encoder
  should imitate.
- **Before use, confirm from the NWB electrodes/metadata that the units are area 2.** The NeuroTask README says "motor
  cortical regions", while the source Dryad dataset (10.5061/dryad.nk98sf7q7) is Chowdhury 2020 area 2.
- License conflict: DANDI says CC-BY-4.0 and the NeuroTask README says CC BY-NC 4.0. Treat it as non-commercial.
- Fallback: stream Area2_Bump (DANDI 000127). The train file is 1822.9 MB and **must not be downloaded**. It can be read
  with remfile+h5py from https://api.dandiarchive.org/api/assets/ded26b6c-418d-43f5-8a37-dfd072c2dbd4/download/
- Motor-side fallback: FALCON H1 (DANDI 000954; 1–7 MB files, e.g.
  https://api.dandiarchive.org/api/assets/dd1bdcf3-5430-4037-ad4a-1727004d38d2/download/ at 5.2 MB).

Model-only (no data): **TouchSim** gives the afferent reference (test T5: do biomimetic ICMS trains built from simulated
SA1/RA/PC population rates reproduce onset/offset transients?).

## 3. Blockers
- No human S1 ICMS psychophysics data is downloadable. The CorticalBionics data is on DABI (login, and "under review").
  DANDI 000401 is empty. CRCNS needs an account.
- TouchSim has no license.
- The Kumaravelu 2022 NEURON column model is cluster-scale.
- NEST and NEURON have no Windows wheels.
