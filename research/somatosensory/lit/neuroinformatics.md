# Neuroinformatics inventory: open datasets, models, tools for software checks of ICMS-feedback hypotheses
Role: neuroinformatics. Date: 2026-09-26. Target machine: Windows 11, ~3 GB free RAM, CPU only, venv
C:\Users\mariu\neuro-company\.venv (Python 3.12.10; numpy 2.5.3, scipy 1.18.1, matplotlib 3.11.2, pillow 12.3.0; checked with pip list).
Method: every item below was opened through its API (PyPI JSON, GitHub API/raw, DANDI REST API, Zenodo API, Dryad API,
PubMed E-utilities, Europe PMC full text). Sizes are copied from those APIs, not estimated. A wheel check was run with
`pip install --dry-run --only-binary=:all:` (nothing was installed; the report is in the scratchpad).
Grades: the evidence grade (A-D, HIVE rule 2) applies to the paper behind the item. "Fit" says how usable the item is on this PC.
Size flag: any single download over 500 MB is marked **TOO LARGE**.

---------------------------------------------------------------------------------------------------------------------
## 1. Peripheral touch model

### [B] TouchSim, Python port (Saal, Delhaye, Rayhaun, Bensmaia 2017), DOI 10.1073/pnas.1704856114, PMID 28652360
- Opened: https://api.github.com/repos/hsaal/touchsim, raw README.md, setup.py, environment.yml, touchsim/*.py;
  commit list; https://pypi.org/pypi/touchsim/json (returns **Not Found**: TouchSim is not on PyPI); PubMed abstract 28652360.
- URL: https://github.com/hsaal/touchsim (Python). The MATLAB original is https://github.com/BensmaiaLab/touchSim. Its readme says
  "A python version of this projet is maintained by Haanes Saal".
- License: **none declared**. The GitHub API gives license=null, LICENSE files return 404, and the MATLAB repo also has none.
  This means all rights are reserved. Internal research use and reading the code are fine, but we must not redistribute it
  or ship it in a product without the author's permission. **Blocker for commercial use.**
- Language / size: pure Python. The whole repo zip is 52 KB (downloaded to the scratchpad and listed: package, tests,
  surfaces/hand.png 17 KB, notebooks). Version 0.1.1 (setup.py). Last commits 2025-03/04: "Update impulse calculation for
  scipy compatibility", "Remove holoviews".
- Dependencies (setup.py): numpy, scipy, numba, matplotlib, scikit-image. It also imports PIL. Every one has a cp312 win_amd64
  wheel: numba 0.67.0 (2.8 MB, needs llvmlite 0.49.0 at 41.9 MB, and numpy<2.6, which our 2.5.3 satisfies) and
  scikit-image 0.26.0 (11.9 MB).
- Python 3.12 compatibility: likely, but UNVERIFIED until the tests run. What I checked in the source:
  - transduction.py:86 uses `np.bool`. That alias was removed in numpy 1.24 but came back in numpy 2.x, so it should work on 2.5.3.
  - Uses numba `@guvectorize(..., target='parallel')`.
  - `import touchsim` builds `hand_surface` from `<repo>/surfaces/hand.png` at import time (surface.py:362). setup.py installs
    that png as a data_file, so a normal `pip install` probably breaks the import path.
- Windows install route: unzip https://github.com/hsaal/touchsim/archive/refs/heads/master.zip and add the folder to sys.path
  (or `pip install -e <folder>`), then run `pytest tests/`. The test suite has 7 files.
- What it can verify: simulated SA1/RA/PC afferent spike trains for any indentation or vibration on the hand. These serve as
  the "natural" reference for biomimetic ICMS encoders: onset/offset transients, rate against depth, how many afferents
  are recruited. Afferent densities hard-coded in constants.py are SA1/RA/PC = 10/25/10 (palm), 30/40/10 (finger),
  70/140/25 (tip). The units are not stated in the code (probably per cm², UNVERIFIED). Internal sampling rate is 5000 Hz
  (classes.py:251).
- Fit: HIGH (small, CPU, pure Python + numba). Caveats: it is a peripheral model only and does not model cortex; the
  license is missing.

### [B] Tactile innervation densities across the whole body (Corniani & Saal 2020), DOI 10.1152/jn.00313.2020
- Opened: Zenodo API record 5594217 (metadata and file list only; PDF not read). License CC-BY-4.0, 1.71 MB PDF. Related
  data DOI 10.15131/shef.data.12753650 (not opened).
- Can verify: afferent-density parameters for body regions beyond the hand. Fit: HIGH (reference only).

### Other peripheral models (seen in the GitHub search, not evaluated)
- ouyangqq/model_tactile_pop_response (Python, no license, 42 MB)
- LClel/FootSim_insole_demonstration (Python, no license, 80 MB)
- leo-lopster/touchsimGUI (Jupyter GUI on TouchSim)

---------------------------------------------------------------------------------------------------------------------
## 2. ICMS current-spread / recruitment: literature and open code

### [B] Stoney, Thompson, Asanuma 1968, "Excitation of pyramidal tract cells by ICMS: effective extent of stimulating current", DOI 10.1152/jn.1968.31.5.659, PMID 5711137
- Opened: PubMed record only. There is **no abstract** in PubMed and I did not read the full text. The I = K·r² constants are
  therefore **not** quoted from this paper. Use the Tehovnik numbers below.

### [B] Tehovnik 1996 review, "Electrical stimulation of neural tissue to evoke behavioral responses", DOI 10.1016/0165-0270(95)00131-x, PMID 8815302
- Opened: PubMed abstract.
- Key facts (abstract): current activates neurons "according to the square of the distance between the electrode and the
  neuron". Excitability "can vary between 100 and 4000 µA/mm² using a 0.2-ms cathodal pulse". "Currents as low as 10 µA
  ... activate from a few tenths to several thousands of cell bodies in the cat motor cortex directly". Tip size does not
  affect far-field current density.
- Can verify: the parameters for the analytic I = K·r² recruitment-radius model (a numpy-only model).
- Caveat: this is a review; the constants come from cat motor cortex.

### [B] Histed, Bonin, Reid 2009, "Direct activation of sparse, distributed populations of cortical neurons by electrical microstimulation", DOI 10.1016/j.neuron.2009.07.016, PMID 19709632
- Opened: PubMed abstract.
- Key facts: microstimulation "sparsely activates neurons around the electrode, sometimes as far as millimeters away, even
  at low currents". The pattern likely comes from "direct activation of axons in a volume tens of microns in diameter".
- Caveats: mouse/cat, two-photon imaging, abstract only.

### [B] Kumaravelu, Sombeck, Miller, Bensmaia, Grill 2022, "Stoney vs. Histed: quantifying the spatial effects of ICMS", DOI 10.1016/j.brs.2021.11.015, PMID 34861412, PMCID PMC8816873
- Opened: PubMed abstract. The Europe PMC full-text request failed (150-byte error).
- Key facts (model): somatic activation comes mainly from antidromic propagation after axonal activation, with no direct
  soma/dendrite activation. The volume where action potentials are initiated grows with amplitude (matches Stoney). The
  volume of activated somata stays roughly constant while their density rises (matches Histed).
- **Open code**: ModelDB 267691, mirrored at https://github.com/ModelDBRepository/267691 (6.1 MB; opened readme.txt and the
  file list). NEURON hoc/mod, 6410 neurons, 25 cell types. The readme says it "needs to be simulated on a compute cluster
  with many CPUs" (MPI, SLURM .q files). It includes the soma coordinates (realx/y/z.dat), cell_cnt.dat, and axon
  coordinates per cell type. Mod files were updated for NEURON 9+ (2023-06-01). License: not stated.
- Fit on this PC: running the full model is **NOT feasible** (cluster-scale). The coordinate files (~100 KB each) can be used
  without NEURON, e.g. for a geometric recruitment model that combines I = K·r² with axon positions.

### [B] Kumaravelu & Grill 2024, "Neural mechanisms of the temporal response of cortical neurons to ICMS", DOI 10.1016/j.brs.2024.03.012, PMID 38492885, PMC11090107
- Opened: PubMed abstract and Europe PMC full text (grep).
- Key facts: single-pulse ICMS gives short-latency excitation (0–25 ms) followed by inhibition (25–200 ms) (full text,
  intro). The model has 6410 neurons, was run on 50 processors, and uses a macaque column. The full text says code "will be
  available on ModelDB post-publication" (not located). Inhibition is prolonged at inter-pulse intervals under 50 ms. The
  excitatory response declines at higher train frequencies.
- Can verify: temporal-response templates for reduced (Brian2) models.

### [B] Overstreet, Klein, Helms Tillery 2013, computational modelling of direct neuronal recruitment during ICMS in S1, DOI 10.1088/1741-2560/10/6/066016, PMID 24280531
- Opened: PubMed abstract. Interneurons are recruited in a dense continuous region; pyramidal neurons are recruited
  sparsely, up to several millimetres away. Code: none found.

### [B] Hickman, Hughes, Sahai, Miles, Denman 2026, "Neural population dynamics of direct electrical stimulation of neocortex", Cell Rep 45:117420, DOI 10.1016/j.celrep.2026.117420, PMID 42207642, PMC13404931
- Opened: PubMed abstract and Europe PMC full text (grep).
- Key facts:
  - Fewer than 5% of neurons are directly activated.
  - Raising amplitude raises the density, but not the spatial extent, of directly responsive neurons.
  - Fast-spiking interneurons are recruited nearer the source.
  - More than 50% of neurons are modulated at higher amplitudes.
  - Point-source reference model uses uniform cortical resistivity 5.8 Ω·m, at 5/25/50/100 µA.
  - Direct-response latency windows: 5 µA 0.68 ms, 25 µA 1.14 ms, 50 µA 1.22 ms, 100 µA 1.47 ms.
  - Mice weakly detect single pulses, and detection does not improve with amplitude.
- Caveats: mouse V1, not S1.
- Data: DANDI 000774 (below). Code: github.com/denmanlab/estim_populations (GPL-3.0, 88 MB, Jupyter).
  Related model: github.com/denmanlab/estim_model (GPL-3.0, 1.6 MB, NEURON).

---------------------------------------------------------------------------------------------------------------------
## 3. Datasets (DANDI searches were run for: somatosensory, microstimulation, touch, Utah array, area 2, Area2_Bump, proprioception, tactile, intracortical microstimulation, S1)

| DANDI / source | Name | License | Size (API) | Fit | What it can verify | Grade |
|---|---|---|---|---|---|---|
| **000127** v0.220113.0359 | Area2_Bump (NLB), Chowdhury & Miller | CC-BY-4.0 | 1823.4 MB total: train file 1822.9 MB (**TOO LARGE**), test file 0.5 MB | low (only HTTP streaming of parts) | area 2 proprioceptive encoding of reach and bump | B (eLife 10.7554/eLife.48198, PMID 31971510) |
| **001056** draft | NeuroTask "Center-Out with bump" (Filipe & Park), derived from Dryad 10.5061/dryad.nk98sf7q7 | CC-BY-4.0 on DANDI, but the NeuroTask README says **CC BY-NC 4.0** (conflict) | 54.5 MB (1 file) | HIGH | spike counts and hand kinematics during CO-bump. The README says "motor cortical regions", so **the recorded area must be confirmed from the NWB electrode table** | C (benchmark, not peer-reviewed as checked) |
| Dryad nk98sf7q7 / CRCNS ssc-12 | Chowdhury 2020 full area 2 data | CC0 | s1-kinematics.zip 4016.2 MB (**TOO LARGE**). CRCNS needs an account (blocked, no sign-up) | none | whole-arm kinematics in area 2 | B |
| **000774** v0.260520.1753 | Electrical stimulation spread in mouse V1, 3 Neuropixels probes (Denman lab) | CC-BY-4.0 | 1570.5 MB total, 10 sessions of 56.7–212.2 MB | MEDIUM-HIGH (one session) | Stoney-vs-Histed test: responsive-neuron density against distance and amplitude, polarity, latency | B (Cell Rep 2026) |
| **001868** v0.260715.2016 | Chronic ICMS in mouse S1 (trunk) with NET probes and 2-photon imaging, learning (Kim, Luan lab) | CC-BY-4.0 | 7504 MB total, 85 files. Passive-control files are **0.3–5.4 MB each** (sub-ICMS43/45/48/54/56/57, about 95 MB together). Task files 30–379 MB | HIGH | per-neuron activation against stimulation channel and current amplitude (passive controls); ICMS detection learning (task animals) | C (preprint DOI 10.64898/2026.06.05.730421v1; DANDI says it supports a 2026 Sci Adv paper, not opened) |
| Zenodo 21382755 | Kim 2026 figure source data | CC-BY-4.0 | data.zip 1638.9 MB (**TOO LARGE**) | none | same study | C |
| **000954** draft | FALCON H1: human 7-DoF reach/grasp motor BCI (Pitt; Ye, Collinger, Gaunt) | CC-BY-4.0 | 102.3 MB, 40 files of 1–7 MB | HIGH | motor-decoding side of the closed loop. Human data collected under FDA IDE / IRB (NCT01894802) | B |
| 000147 | PPC_Finger, human PPC Utah array (Andersen lab) | CC-BY-4.0 | 77.7 MB, 10 files of 5–11 MB | medium | BCI decoding; the array is at the postcentral–IPS junction, not S1 proper | B (eLife 10.7554/eLife.74478, not opened) |
| 000401 draft | touchExploration: human S1 area 1 Utah arrays (Rosenthal) | CC-BY-4.0 | **0 assets** (empty draft) | none | would be ideal, but it is empty | — |
| Zenodo 16887485 | StimContext_Timing: human S1 arrays, 2 participants (Rosenthal) | CC-BY-4.0 | 4633 MB total. Small files: *_SpksForRSA.mat 0.19/0.25 MB, RDMs about 0.5 MB, bootstrap results 49/65 MB. preprocessedSpks 397/792 MB (**TOO LARGE**) | low-medium | RSA-level analyses only | C (paper not opened) |
| 000880 draft | Haptics Lab vibrotactile mouse forepaw S1 | CC-BY-4.0 | 0 assets | none | — | — |
| 000013, 000226, 001341, 001788 | barrel cortex / Merkel afferent / Aβ synchrony | CC-BY-4.0 | 11.4 GB, 13.7 GB, 693 MB, 343 GB (**all TOO LARGE**) | none | — | — |

Human ICMS psychophysics (Pitt / Chicago "CorticalBionics" org). Code repos opened, all MATLAB and mostly MIT:
StableAndPreciseICMS, ICMS_Safety, BiomimeticNaturalness, EdgesAndMotion, ICMSOrderEffects. ICMSconnectivity is GPL-3.0.
Their data sit on **DABI** (e.g. https://dabi.loni.usc.edu/dsi/GU5A5IO8LRXE, /IB30CTQCJ6OP, /0SRDQG1CXCQ5, /S8Q532OTAXMS).
The DABI pages are a JavaScript app with "Login". The banner reads "This repository is under review for potential
modification in compliance with Administration directives". Access and sizes are **UNVERIFIED/blocked** (no sign-up allowed).
- pitt-rnel org (Gaunt/Collinger lab): tools only, no datasets found. Examples: perceptmapper (MIT), br_stimpy (CereStim
  wrapper), rtma, pyrtma (MIT).
- Miller lab: data is in 000127 / Dryad / CRCNS ssc-12 above.
- CRCNS ssc-1..12: all need a free account (https://crcns.org/download). Blocked.

---------------------------------------------------------------------------------------------------------------------
## 4. Simulation frameworks (checked on PyPI JSON and conda-forge API)

| Tool | Version | Windows cp312 route | License | Fit | Notes |
|---|---|---|---|---|---|
| **Brian2** (Stimberg et al. 2019, eLife 10.7554/eLife.47314, PMID 31429824, grade B) | 2.10.1 | **brian2-2.10.1-cp312-cp312-win_amd64.whl** (1.08 MB); conda-forge also has win-64 | CECILL-2.1 | HIGH | Requires Python >=3.12, numpy>=2, Cython<3.1.4. The Cython runtime target on Windows needs MS Visual C++ Build Tools (Brian2 install docs, opened). Without MSVC, use `prefs.codegen.target='numpy'` (slower, works) |
| NEST | 3.10.0 | **no** Windows wheel on PyPI (only macOS/linux/musl); conda-forge has linux/osx only | GPL-2.0 | NONE | WSL/Docker would be needed, which is too heavy for 3 GB RAM |
| NEURON | 9.0.2 | **no** win wheel on PyPI and no conda-forge win-64. A GitHub release has a Windows installer `nrn-9.0.2.w64-mingw-py-310-311-312-313-314-setup.exe` (56.0 MB) | proprietary-style BSD-like ("Copyright (c) 2018, Michael Hines") | LOW | The installer supports py3.12 but is outside the venv. Only single-cell / small ModelDB models would fit this PC. Kumaravelu 2022 is too big |
| numba | 0.67.0 | cp312 win wheel 2.8 MB (+ llvmlite 41.9 MB) | BSD | HIGH | needed by TouchSim |
| scikit-image | 0.26.0 | cp312 win wheel 11.9 MB | BSD | HIGH | needed by TouchSim |

## 5. Data-access tools

| Tool | Version | Wheel | License | Fit | Notes |
|---|---|---|---|---|---|
| **pynwb** | 4.2.0 | py3-none-any (1.4 MB) | BSD-3 | HIGH | pulls in hdmf 6.2.0, h5py 3.16.0 (cp312 win wheel 3.2 MB), pandas 3.0.6 |
| **remfile** | 0.1.15 | py3-none-any (0.02 MB) | not stated | HIGH | lazy HTTP range reads of remote NWB/HDF5. This lets us read spike times from the 1.8 GB Area2_Bump file without downloading all of it (ESTIMATE: only the touched chunks move) |
| dandi CLI | 0.80.1 | py3-none-any | Apache-2.0 | LOW | The dry-run closure is heavy: deno, tensorstore, zarr, pydantic, aiohttp, bids-validator-deno. **Not recommended**: direct `https://api.dandiarchive.org/api/assets/<id>/download/` with curl is enough |
| nlb_tools | 0.0.4 | py3-none-any | MIT | **BROKEN on py3.12** | requires pandas<=1.3.4, which has no cp312 wheel (last win wheel is cp310). Read the NLB NWB files with pynwb directly |
| Neural Latents Benchmark paper (Pei et al. 2021) | arXiv 2109.04463 (opened, abstract) | — | — | — | grade C (preprint): "four datasets of neural spiking activity from cognitive, sensory, and motor areas" |
