# CHB-MIT subset for the cycle-1 seizure-DETECTION baseline (data agent)

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. No clinical claims.

Source: CHB-MIT Scalp EEG Database v1.0.0, PhysioNet, https://physionet.org/content/chbmit/1.0.0/ (ODC-By 1.0, open, no login).
Files opened by this agent: the directory listing of https://physionet.org/files/chbmit/1.0.0/ and of chb01/ to chb24/,
RECORDS, RECORDS-WITH-SEIZURES, SUBJECT-INFO, SHA256SUMS.txt, all 24 chbNN-summary.txt, and the EDF *header* of all 686 EDFs
(HTTP Range request, 256*(ns+1) bytes each, about 5 MB in total). Local copies: data\raw\chbmit\_meta\.
Full per-file inventory: notes\data\chbmit_inventory.csv (686 rows). Selection: notes\data\chbmit_selection.csv.
Scripts: code\chbmit_inventory.py -> code\chbmit_select.py -> code\chbmit_download.py.

Written 2026-09-26 BEFORE any EDF data was downloaded (only headers had been read).

## Inventory facts (from headers and summaries)
- All 686 EDFs: fs = 256 Hz on every signal, 1-s data records, 16-bit.
- An identical 23-channel bipolar montage (labels and order exactly as chb01, no dummy channels) in EVERY file: chb01, 02, 03, 05, 06, 07, 08, 10, 23, 24.
- chb04, 09, 11, 12, 13, 15, 16, 17, 18, 19 change channel sets between files. chb14, 20, 21, 22 are stable, but each has 28 signals
  (23 real channels plus 5 dummy "-" channels, in a different order), so they need a label-based channel map.
- Channel "T8-P8" appears twice in the standard 23-channel list (channels 15 and 23). The duplicates are identical by construction, so readers must de-duplicate by index, not by label.
- chb21 is the same patient as chb01, recorded 1.5 years later (PhysioNet description). They must never be split across train and test as different patients.
- chb24 was added later: its summary has no file start times, and 10 of its 22 EDFs are missing from the summary.
- Annotation inconsistency: RECORDS-WITH-SEIZURES lists chb07_18.edf and omits chb07_19.edf. The summary and the per-file .seizures file
  agree that the seizure (13688-13831 s) is in chb07_19. Treat the summary as authoritative. This does not affect the selected subjects.
- File-number order is not always chronological: chb03_24 starts after chb03_25 (per the summary and EDF header). The harness should sort
  by header start time, not by file name.

## Selection rule (fixed before download; implemented in code\chbmit_select.py)
Eligibility:
- E1: every file of the subject has exactly chb01's 23 labels in the same order, with no dummies, fs = 256 Hz.
- E2: at least 3 seizures.
- E3: summary start times are available.
- E4: not a repeat patient.

Eligible subjects: chb01 (7 seizures), chb02 (3), chb03 (7), chb05 (5), chb06 (10), chb07 (3), chb08 (5), chb10 (7), chb23 (7).

Per subject: take ALL seizure-containing files, then add seizure-free files in RECORDS order (earliest first). Stop as soon as the non-seizure time
reaches 10 h, counting both the seizure-free files and the interictal part of the seizure files.

Subject set: maximise the number of subjects (at most 4) with total bytes <= 1.8e9 (decimal GB). Break ties by more seizures, then more
seizure-containing files, then fewer bytes.

**The budget forces 3 subjects.** The cheapest possible 4-subject set (chb01+chb02+chb03+chb08) needs 1,819,473,920 bytes, which is more than 1.8e9.
It is within the HIVE's 2 GB hard cap, so the queen may approve it as a deviation. That would add chb08 and swap in chb02 by the same rule.
The chosen 3-subject set with the most seizures is chb01, chb03 and chb10: 21 seizures, all in separate files.

## Selected files: 29 EDFs, 1,512,087,040 bytes (1.512 GB), 35.66 h, 21 seizures
| subject | files | hours | non-seizure h | seizures (total s) | GB |
|---|---|---|---|---|---|
| chb01 (F, 11 y) | 11 (7 seizure + 4 seizure-free) | 10.65 | 10.52 | 7 (442 s) | 0.451 |
| chb03 (F, 14 y) | 11 (7 seizure + 4 seizure-free) | 11.00 | 10.89 | 7 (402 s) | 0.466 |
| chb10 (M, 3 y)  | 7 (7 seizure + 0 seizure-free) | 14.02 | 13.89 | 7 (447 s) | 0.594 |

In the table below, t0 is hours from the subject's FIRST file in the whole recording, using de-identified EDF header dates. Only within-subject differences are meaningful.

| file | summary start-end | t0 (h) | dur (s) | seizures (s) |
|---|---|---|---|---|
| chb01_01 | 11:42:54-12:42:54 | 0.000 | 3600 | - |
| chb01_02 | 12:42:57-13:42:57 | 1.001 | 3600 | - |
| chb01_03 | 13:43:04-14:43:04 | 2.003 | 3600 | 2996-3036 |
| chb01_04 | 14:43:12-15:43:12 | 3.005 | 3600 | 1467-1494 |
| chb01_05 | 15:43:19-16:43:19 | 4.007 | 3600 | - |
| chb01_06 | 16:43:26-17:43:26 | 5.009 | 3600 | - |
| chb01_15 | 01:44:44-2:44:44 | 14.031 | 3600 | 1732-1772 |
| chb01_16 | 02:44:51-3:44:51 | 15.033 | 3600 | 1015-1066 |
| chb01_18 | 04:45:06-5:45:06 | 17.037 | 3600 | 1720-1810 |
| chb01_21 | 07:33:46-8:33:46 | 19.848 | 3600 | 327-420 |
| chb01_26 | 12:34:22-13:13:07 | 24.858 | 2325 | 1862-1963 |
| chb03_01 | 13:23:36-14:23:36 | 0.000 | 3600 | 362-414 |
| chb03_02 | 14:23:39-15:23:39 | 1.001 | 3600 | 731-796 |
| chb03_03 | 15:23:47-16:23:47 | 2.003 | 3600 | 432-501 |
| chb03_04 | 16:23:54-17:23:54 | 3.005 | 3600 | 2162-2214 |
| chb03_05 | 17:24:01-18:24:01 | 4.007 | 3600 | - |
| chb03_06 | 18:24:08-19:24:08 | 5.009 | 3600 | - |
| chb03_07 | 19:24:15-20:24:15 | 6.011 | 3600 | - |
| chb03_08 | 20:24:22-21:24:22 | 7.013 | 3600 | - |
| chb03_34 | 01:51:23-2:51:23 | 60.463 | 3600 | 1982-2029 |
| chb03_35 | 02:51:30-3:51:30 | 61.465 | 3600 | 2592-2656 |
| chb03_36 | 04:51:45-5:51:45 | 63.469 | 3600 | 1725-1778 |
| chb10_12 | 15:55:00-17:55:00 | 22.038 | 7200 | 6313-6348 |
| chb10_20 | 07:56:00-9:56:12 | 38.055 | 7212 | 6888-6958 |
| chb10_27 | 22:02:08-24:02:26 | 52.157 | 7218 | 2382-2447 |
| chb10_30 | 04:03:19-6:03:32 | 58.177 | 7213 | 3021-3079 |
| chb10_31 | 06:04:00-8:04:21 | 60.188 | 7221 | 3801-3877 |
| chb10_38 | 14:33:05-16:33:05 | 68.673 | 7200 | 4618-4707 |
| chb10_89 | 16:21:55-18:21:55 | 166.487 | 7200 | 1383-1437 |

## Caveats for the harness and mathematician
- chb10 has no seizure-free files in the subset: all of its 13.9 h of non-seizure EEG comes from seizure files, within about 2 h of a seizure.
  False alarms per hour there are measured on peri-ictal, not remote-interictal, data. Report FA/h per subject, and do not pool chb10 with the others without saying so.
- The "earliest seizure-free files" rule puts all of chb01's and chb03's seizure-free data at the start of the recording.
  A chronological split (train early, test late) therefore gives the test fold few or no seizure-free files. The prereg must state how this is handled
  (for example, leave-one-subject-out as the primary split, with the chronological split within-subject as secondary).
- Only 3 patients: leave-one-subject-out gives n = 3 folds. Any CI across patients is very wide, so the prereg thresholds should reflect that.

## Reader recommendation (nothing installed; the coder decides)
- code\edf_reader.py is a pure-numpy reader that needs no install. It reads the header, labels, fs and int16 data scaled to microvolts. It is enough for the baseline.
- If a library is wanted: **pyedflib 0.1.42** has a cp312-win_amd64 wheel on PyPI and depends only on numpy. It is the smallest safe choice.
  mne 1.13.2 is a py3-none-any wheel, but it pulls in pooch, tqdm, jinja2, lazy-loader and decorator. It is heavier than needed.
  edfio 0.4.17 is pure Python and depends only on numpy.
  (Checked on the PyPI JSON API on 2026-09-26.)

## Download status
See the "Download result" section below (appended after the download).

## Download result (2026-09-26, appended after download)
- 53 files were downloaded with code\chbmit_download.py: 29 EDFs, 21 .edf.seizures files and 3 summaries. That is 1,512,087,040 bytes of EDF (1.512 GB) plus a few kB of text.
  All 53 match PhysioNet SHA256SUMS.txt (verified = yes). Every EDF's listing size equalled its HTTP Content-Length before download.
- _meta files: RECORDS, RECORDS-WITH-SEIZURES, SUBJECT-INFO and the 24 summaries are also SHA-verified. SHA256SUMS.txt, the 24 listings and edf_headers.json have no reference hash.
  All are in data\manifests\chbmit_manifest.csv (106 rows).
- The total network use for the task was about 1.52 GB, including about 5 MB of EDF-header Range requests. This is under both the 1.8 GB target and the 2 GB cap.
- Readability: code\chbmit_check_headers.py read all 29 EDFs with code\edf_reader.py (header plus the first 60 s of data). Results are in notes\data\chbmit_selected_channels.csv:
  - All files have 23 signals at 256 Hz, in uV, with physical range -800..800 and digital range -2048..2047 (a 12-bit range, about 0.39 uV per step).
  - Labels are identical in all 29 files, so there are NO montage changes.
  - Durations match the inventory.
  - Channels 15 and 23 (both "T8-P8") are sample-identical in every file, so use 22 unique channels.
  - Labels: FP1-F7 F7-T7 T7-P7 P7-O1 FP1-F3 F3-C3 C3-P3 P3-O1 FP2-F4 F4-C4 C4-P4 P4-O2 FP2-F8 F8-T8 T8-P8 P8-O2 FZ-CZ CZ-PZ P7-T7 T7-FT9 FT9-FT10 FT10-T8 T8-P8
- A note on the PhysioNet content page: it still says "664 .edf files / 129 with seizures", from before chb24 was added. The current RECORDS file has 686 EDFs,
  141 of them with seizures and 198 seizures in total per the summaries (the inventory counts these).
