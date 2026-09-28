# Motor readout: data plan (metadata verified 2026-09-26; nothing downloaded)

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. No clinical claims.

Author: mathematician (motor-readout track), for Marius Carlsson. Every fact below was read from the DANDI REST API
(api.dandiarchive.org/api/dandisets/<id>/versions/<ver>/ and .../assets/), the PhysioNet page and HTTP HEAD, or GitHub READMEs,
in this session. No sign-up is needed for any of them: DANDI "OpenAccess" and PhysioNet open files download anonymously.

## 1. Candidates checked

| dandiset | name | version | licence | access | assets (bytes) | use |
|---|---|---|---|---|---|---|
| 000128 | MC_Maze (Churchland, Kaufman) | 0.220113.0400 | CC-BY-4.0 | OpenAccess, OPEN | train 690,612,247; test 3,392,688 | too large for the RAM plan; not used |
| 000138 | MC_Maze_Large | 0.220113.0407 | CC-BY-4.0 | OpenAccess, OPEN | **train `sub-Jenkins/sub-Jenkins_ses-large_desc-train_behavior+ecephys.nwb` 148,590,536** (asset e67b57b2-e9ad-4d95-b9e3-1262997360dc); test 802,352 | **D1 (primary within-session)** |
| 000139 | MC_Maze_Medium | 0.220113.0408 | CC-BY-4.0 | OpenAccess, OPEN | train 76,604,764; test 695,928 | fallback if RAM is exceeded |
| 000140 | MC_Maze_Small | 0.220113.0408 | CC-BY-4.0 | OpenAccess, OPEN | train 29,207,528; test 689,312 | dry run / tests only |
| 000129 | MC_RTT (O'Doherty) | 0.241017.1444 | CC-BY-4.0 | OpenAccess, OPEN | train 49,764,168; test 1,201,344 | **single session (one subject "Indy", one file), so it cannot measure across-day drift.** Not used. |
| 001201 | LINK (Temmar ... Chestek) | 0.251023.2336 | CC-BY-4.0 | OpenAccess, OPEN | 312 files, 12,563,287,466 total; about 35-57 MB each | **D2 (across-session drift)** |
| 000941 / 001209 / 000954 | FALCON M1-A / M1-B / H1 | 0.241029.1405 / draft / draft | CC-BY-4.0 | OpenAccess | 311.8 MB / 233.6 MB / 102.3 MB | Evaluation data are private [R41]; the held-out-calib files are few-shot only. Not used for a blind test. |
| 000688 | Long-term M1/PMd recordings during reaching | 0.250122.1735 | not checked | - | 13.2 GB, 111 files | alternative drift set; not needed |
| PhysioNet eegmmidb 1.0.0 | EEG Motor Movement/Imagery (Schalk) | 1.0.0 | **ODC-By 1.0** | open files, no login | 3.4 GB total; each 2-min run EDF = 2,596,896 B (HEAD on S001R04/R08/R12) | **D3 (optional EEG arm)** |

**The NLB test files hold no behaviour.** The NLB test NWBs are named `desc-test_ecephys` (no "behavior"), so they cannot score
decoding. D1 therefore uses **only the train file**, with our own locked chronological split (prereg §2). The NLB "val" labels
inside the train file are ignored.

## 2. Chosen downloads (total ≈ 0.70 GB <= 1.5 GB)

### D1: MC_Maze_Large train file (DANDI 000138)
- 1 file, 148,590,536 B.
- Content per DANDI: sorted units from M1 + PMd, and hand/cursor/eye position with hand velocity; delayed centre-out maze task.
  The exact neuron and trial counts must be read from the file by the coder (the NLB paper gives 182 neurons / 2,869 trials for
  the full MC_Maze only [R27]).
- NLB convention [R46]: trials aligned -250..+450 ms around movement onset; lag 120 ms for the scaled sets.

### D2: LINK (DANDI 001201): 9 sessions, chosen by a date-only rule fixed now (blind)
Rule:
- day 0 = the first session (2020-01-27);
- for each target lag L in {3, 7, 14, 30, 60, 120, 240, 365, 730} days, take the first session on or after day 0 + L;
- remove duplicates.

60 and 120 both map to 2020-06-26 because of the Mar-Jun 2020 recording gap. That leaves 9 unique files:

| lag target | actual lag (d) | session | bytes | asset_id |
|---|---|---|---|---|
| 0 | 0 | 20200127 | 45,005,026 | c002a9a1-664d-4a69-af02-ba810046c4fb |
| 3 | 3 | 20200130 | 43,863,496 | 9d1820f1-7583-4faf-bbd0-7e9fb7001ca4 |
| 7 | 8 | 20200204 | 43,052,898 | ea07a2e3-d5f4-4036-9b62-93d1f89cba64 |
| 14 | 15 | 20200211 | 44,035,784 | 9c0ac931-d97e-464b-a134-c366b7c84727 |
| 30 | 32 | 20200228 | 51,231,832 | b424f116-7827-4ab0-80ed-1e8951eea67a |
| 60/120 | 151 | 20200626 | 44,042,920 | 88039197-6170-4d06-ba3e-f58b68c6eb7f |
| 240 | 241 | 20200924 | 36,913,714 | b9868d49-f641-4b95-a8e3-6295111b958b |
| 365 | 393 | 20210223 | 45,577,090 | 9db3b62a-6fea-493b-98bf-2f6ded6eefec |
| 730 | 730 | 20220126 | 44,925,842 | 1a7aadf8-eb08-427b-93e3-8df11d71ae9e |
| **total** | | | **398,648,602** | |

- Paths: `sub-Monkey-N/sub-Monkey-N_ses-<YYYYMMDD>_ecephys.nwb`.
- Content per DANDI and README [R43]: 96-channel threshold crossings and SBP from Utah arrays in M1; index and MRP finger
  positions and velocities; 375 trials per target style; SBP and kinematics in 32 ms bins in the authors' pkl conversion.
- The NWB-internal layout (bin width, field names) must be checked by the coder on the day-0 file before any decoder code runs.
  Any mismatch with the prereg goes to DEVIATIONS.

### D3 (optional): EEGMMIDB, subjects S001-S020, runs 04, 08, 12
- Runs 04, 08 and 12 are motor imagery of the left vs right fist (run map from the MNE eegbci docstring [R45], **to be verified
  by the coder**: those runs must contain only T0/T1/T2 events, and their mapping must not be the hands-vs-feet runs 06/10/14).
- 60 EDF files x about 2,596,896 B = about 155.8 MB, plus 60 small .edf.event files.
- The coder HEADs each file first. Any file whose size differs goes to the manifest as-is.
- Hashes are checked against PhysioNet's SHA256SUMS.txt (3,058 lines, checked to exist).
- Subjects S001-S020 were chosen by ID order only (blind).
- The existing pure-numpy code\edf_reader.py can read them. EDF+ annotations: check that the reader handles the
  "EDF Annotations" channel, or use the .event file.

**Total: 148.6 + 398.6 + 155.8 ≈ 703 MB.** If D3 is dropped: 547 MB. Downloads go to research\neurobiology\data\raw\motor\ and
SHA-256 values go to data\manifests\motor_manifest.csv (HIVE rule 5). DANDI asset metadata carries `dandi:sha2-256`. Checked for
D1: `1188ddf5b822dd9ac49afb8916f4b42a85867613cf7f169d0b04a1d1aeecd700`, from api.dandiarchive.org/api/assets/<asset_id>/. The coder
must match every file against this digest.

## 3. Software needed (coder installs; HIVE rule 4)
- `h5py` to read the NWB/HDF5 files directly. pynwb is optional, and h5py alone is lighter.
- `torch` (CPU wheel) for the GRU. If it cannot be installed, the GRU arm is NOT TESTED (prereg A5). No hand-written numpy BPTT.
- numpy/scipy (present: numpy 2.5.3, scipy 1.18.1, Python 3.12.10 in C:\Users\mariu\neuro-company\.venv). Riemannian
  geometry in scipy (eigh), with no pyriemann dependency.
- RAM: read LINK one session at a time. Read D1 spike times per unit and bin them immediately (do not keep dense 1 ms arrays).

## 4. Licence obligations
- CC-BY-4.0 (DANDI): attribute with the DANDI citation strings (e.g. "Churchland, Mark; Kaufman, Matthew (2022) MC_Maze_Large
  ... DANDI archive. https://doi.org/10.48324/dandi.000138/0.220113.0407"; LINK: Temmar et al., DANDI 001201 version
  0.251023.2336).
- ODC-By 1.0 (PhysioNet): attribute Schalk G (2009) doi:10.13026/C28G6P, plus the Schalk 2004 BCI2000 paper and Goldberger
  2000, as the page requests.
- No redistribution of raw data; results only.
