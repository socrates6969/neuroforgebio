# Data extraction, cycle 3b: per-electrode projected fields (PFs) for a within-array independence test (2026-09-26)

Role: data extractor. Scope: INPUTS ONLY. I did not read code\RESULTS_* or code\REVIEW_*. I used open sources only:
no sign-up, no login, and DABI was not touched. Every value is QUOTED, DIGITISED (read from a published figure, with
the method stated) or ARITHMETIC/ESTIMATE (derived by me, with the method stated).
Scripts and CSVs are in `notes\published-derived\`. Rerun them with `.venv\Scripts\python.exe <script> <scratch_dir>`. The
scripts download their own input images and code files.

## 1. Bottom line
- **Usable per-electrode PF data with known grid positions now exist from open sources: 318 electrodes across 11 arrays and
  5 participants, giving 4,508 within-array pairs.** All of it is DIGITISED from figures. No open numeric per-electrode PF table exists.
  | Source | Participants / arrays | Electrodes with PF | Within-array pairs | PF information per electrode | Pitch |
  |---|---|---|---|---|---|
  | Greenspon 2025 NBE, Ext. Data Fig 1 [B] | C1, P2, P3 / 6 | 186 of 192 wired | 2,791 | dominant hand **segment** (palm + dorsum, 48 + 24 segments) -> segment-centroid coordinates in mm | 400 um (stated) |
  | Fifer 2022 Neurology, Fig 1C [B] | JHU participant / 3 | 86 of 96 wired | 1,207 | set of **finger hue classes** (4 classes; finger identity not resolved) | 400 um (stated) |
  | Armenta Salas 2018 eLife, Fig 2B [B] | FG / 2 (7x7) | 46 of 96 (paper: 46/96) | 510 | set of **arm regions** (upper arm / forearm, anterior / posterior, hand) | NOT stated; 400 um ASSUMED |
- **PF location is spatially correlated within an array in all 6 Pitt/Chicago arrays and all 3 JHU arrays. It is not
  correlated in either Caltech arm-region array.** Section 4 has the numbers. None of this is modelled: it is the raw
  pairwise statistics plus a label-shuffle permutation test.
- **Still blocked:** per-electrode PF **area/shape** and true PF **centroids** (not segment centroids), pairwise pixel
  overlap (Jaccard of actual PFs), and per-electrode data for C2 and P4. The first three exist only in DABI (restricted).
  Downey 2024 Fig 3d shows C2 and P4 only at 709 px; see section 5.

## 2. Sources checked and what each gave (URL, figure, quote)

### 2.1 Greenspon et al. 2025 Nat Biomed Eng [B]: USED (main source)
PMID 39643730, PMC12176618, DOI 10.1038/s41551-024-01299-z.
- Figure: Extended Data Fig. 1, full resolution (1718 x 2423 px):
  https://media.springernature.com/full/springer-static/esm/art%3A10.1038%2Fs41551-024-01299-z/MediaObjects/41551_2024_1299_Fig8_ESM.jpg
  (the PMC/EPMC copy is only 687 x 969 px). Legend (quote): "The array diagrams show the dominant hand segment for each electrode.
  All array rotations are approximately aligned such that up is medial and anterior is left." Fig 1 legend: "The segment is assigned
  based on median reported sensation over time... White sections indicate unwired electrodes."
- How the figure was made. The authors' MIT code (https://github.com/CorticalBionics/StableAndPreciseICMS) draws it:
  - `GetSegmentLabels.m`, method 'DailyCentroid': the segment is the one containing the mean over sessions of the daily PF centroids.
    This is done separately for the palm and the dorsum. No 33% pixel threshold is applied here.
  - `PlotGridSegments.m` gives the cell geometry and grey [.6 .6 .6] = "no RF". `GetHandSegments.m` gives 48 palm and 24 dorsum
    segment tags with exact RGB colours. `PlotSegmentedHand.m` always draws the Medial array in the upper inset.
  - `LoadSubjectChannelMap.m` gives the grids and rotations: C1 = BCI02 (medial -105 deg, lateral 45 deg), P2 = CRS02 (lateral 60,
    medial 15), P3 = CRS07 (lateral 75, medial -10).
- Method (`extract_greenspon2025_pf_segments.py`):
  1. Fit each array blob with a rotated rectangle and regenerate the cell centres with the code's own geometry.
  2. Take the median RGB of a 7x7 px patch per cell and assign the nearest exact segment colour (or grey).
- Validation:
  - Wired/unwired pattern vs the code's chequerboard map: **60/60 cells agree on all 12 array drawings**.
  - Colour match: measured vs code RGB is at most 4.5 RGB units for every class, and the nearest-vs-second-nearest margin is >= 14.
    Correction: the published raster shows no-PF cells as (204,204,204), not the code's 0.6 grey (153); I used the measured value.
  - Hand-map scale: the filled palm silhouette minus the wrist is about 153 cm2 at 5 px/mm. The paper states a "palmar surface of
    165 cm2". So the code's 5 px/mm scale (Figure3_Somatotopy.m line 160, `./ 5`) is consistent to about 4% in length.
  - Cross-check against Shelchkova 2023 Nat Commun Fig 4c (PMC10638421; C1, thumb electrodes on the lateral array and ring-finger
    electrodes on the medial array). Our read-out gives 12 thumb (D1) electrodes clustered at one end of the lateral array's long
    axis, and 8 ring (D4) electrodes clustered at one end of the medial array. Their figure shows about 9 and about 8, with the same
    end-clustering. They agree qualitatively. Criteria differ, so an exact match is not expected.
- Segment centroids come from `BoundaryMapPalm.png` / `BoundaryMapDorsum.png` (4-connected regions of the 1050 x 1200 map, in the
  code's order). One ordering swap (D4p-u <-> D4d-dr) was corrected by finger-axis geometry. Tags that share a colour (the
  ulnar/radial halves of a phalanx) cannot be told apart in the figure, so they are merged.
- Note: distances are invariant to array rotation and mirroring, so the pairwise results do not depend on the orientation convention.
  Only the channel numbers do.

### 2.2 Fifer et al. 2022 Neurology [B]: USED (coarse)
PMID 34880087, PMC8865889. Fig 1C: https://cdn.ncbi.nlm.nih.gov/pmc/blobs/fa94/8865889/f3ebe80069bc/NEUROLOGY2021174458F1.jpg
(694 x 356 px, the largest copy reachable; the journal site is bot-walled). Legend (quote): "Hue denotes finger; saturation denotes
finger segment; and hatching denotes a dorsal hand percept ... For each electrode on the array, the set of colors present within the
square corresponds to a finger segment in panel A that was reported for that electrode. Gray squares are electrodes not wired for
stimulation, and white squares did not elicit any single percept multiple times." Data availability (quote): "Anonymized data not
published within this article will be made available by request".
- Method (`extract_fifer2022_fig1c.py`): rotated-rectangle fit, a 10x6 lattice, 25 samples per cell, and HSV hue classes
  red/orange/yellow/green.
- Validation: exactly **32 wired cells in each of the 3 arrays** (the paper reports 96 stimulating electrodes).
- Caveats:
  - Cells are about 14 px wide and multi-segment stripes are 2-4 px, so the hue sets are approximate.
  - Segment (saturation) and dorsal hatching are NOT used.
  - Finger identity per hue is not resolved (not needed for within-array identity).
  - The drawn cells are not square (aspect 1.96 vs 1.67); I used grid indices x 0.4 mm.

### 2.3 Armenta Salas et al. 2018 eLife [B]: USED (arm regions, not hand)
PMID 29633714, PMC5896877, CC BY 4.0. Fig 2B: https://cdn.elifesciences.org/articles/32904/elife-32904-fig2-v1.jpg (2004 x 1246).
Quotes: "Two 7 x 7 SIROF ... microelectrode arrays (with 48 physically-connected channels each) were implanted in S1"; Fig 2B "Left
side panels display the reported receptive fields at each electrode location"; "Stimulation through 46/96 electrodes (48%) prompted
at least one response".
- Result: our read-out gives **46 responsive electrodes (25 medial, 21 lateral), which matches the paper exactly**; 7 are multi-region.
- Pitch is not given in the paper or in 3 other Andersen-lab papers I opened (PMC7732821 says only "two 7x7 microelectrode arrays
  (48 channels per array...)"). I ASSUMED 400 um (Blackrock standard).
- The only source code is stimulation commands. There is no data file.

### 2.4 Checked, not usable for this purpose
| Source | What is open | Why it cannot be used |
|---|---|---|
| Flesher 2016 STM (PMID 27738096) | nothing | Not in PMC or Europe PMC (inEPMC = N); paywalled. BLOCKED. |
| Hughes 2021 JNE (PMID 34320481, PMC8500669) | legends read | Per-electrode maps show detection thresholds (Fig 4b), impedance and signal quality. No PF maps. |
| Valle 2025 Science (PMID 39818881, PMC11994950) | Fig 1B (c1 = C1), GitHub EdgesAndMotion (code only) | The Fig 1B array map is the same C1 map as Greenspon's. The fingertip PF outlines (d2, d3) are not tied to grid positions. Data are on DABI (S8Q532OTAXMS). |
| Greenspon decade preprint (PMID 40832410, PMC12363726) | Fig 1C schematic only; GitHub ICMS_Safety = code | No per-electrode PF data. DABI LVUPBGAXILJ6. |
| Hobbs 2025 (PMID 40106898, PMC13571258) | GitHub BiomimeticNaturalness = code plus one reference train | The statement "openly available" points to DABI 0SRDQG1CXCQ5; no PF data. |
| Verbaarschot 2025 Nat Commun (PMID 40312384, PMC12046030) | Source Data xlsx (22 MB; sheets Fig 2a-8b, S1-S11) | Only 3 electrodes per participant, with no grid positions. DABI JZITRHZ6X9WI. |
| Shelchkova 2023 Nat Commun (PMC10638421) | Source Data (.mat) for Figs 2b, 5b, 7, S3, S4, S6, S9 | Fig 4c (C1 thumb/ring electrodes) is not in the source data. Used only as a cross-check (2.1). GitHub ICMSconnectivity = code plus a Cerebus map file. |
| Bjanes 2025 (PMC12676579), Zenodo 15284113 | 4.6 GB of spikes, eye and RSA data | No electrode positions or PF data (per the WebFetch listing). |
| Downey 2024 HBM (PMID 39720868, PMC11669040) | Fig 3d (digit per electrode, 5 participants incl. **C2, P4**) and Fig 4 (proximal-distal shade) | Only 709 px (cells about 8 px, stripes of 3-5 digits). Blob segmentation merged arrays. Wiley and the PMC CDN full-size copy are bot-walled. NOT digitised (see 5). |
| CorticalBionics/SensorySurvey3D (GitHub) | hand meshes, Jaccard code, example log | No participant data. |

## 3. Files written (notes\published-derived\)
- `pf_per_electrode_greenspon2025.csv` (192 wired electrodes; 186 with a PF). Columns: participant, subject_code, array,
  electrode_channel (1-64 as in the code), channel_label (raw map value), grid_row (0-9), grid_col (0-5), x_mm, y_mm, has_PF,
  digits, palm_segment, palm_centroid_x_mm, palm_centroid_y_mm, palm_segment_area_mm2, dors_segment (+ the same three),
  colour distances, source, DIGITISED = yes.
  - **Coordinate system:** the authors' 1050 x 1200 px right-hand map (palm and dorsum are separate maps), origin top-left, x to the
    right, y down, 5 px = 1 mm. The PF centroid is the centroid of the dominant segment, so it is quantised to the segment.
  - **PF area is NOT available.** `*_segment_area_mm2` is the area of the segment, not of the PF.
- `pf_pairs_greenspon2025.csv` (2,791 pairs). Columns: cortical_mm, same_segment, jaccard (over each electrode's set {palm seg,
  dorsum seg}), same_digit, palm_centroid_dist_mm, dors_centroid_dist_mm.
- `pf_per_electrode_fifer2022.csv` and `pf_pairs_fifer2022.csv` (86 electrodes, 1,207 pairs).
- `pf_per_electrode_armentasalas2018.csv` and `pf_pairs_armentasalas2018.csv` (46 electrodes, 510 pairs).
- `pf_pairwise_summary.json`: all numbers in section 4.
- `greenspon2025_ed1_extraction.json`: the raw read-out (per-cell RGB, class, distance, margin), segment table and fit report.
- Scripts: `extract_greenspon2025_pf_segments.py`, `extract_fifer2022_fig1c.py`, `extract_armentasalas2018_fig2b.py`,
  `pf_pairwise_within_array.py` (permutations: 5,000, seed 20260926).

## 4. Results: the quantities the model needs, computed directly (DIGITISED inputs; ARITHMETIC outputs)

### 4.1 Greenspon 2025 (C1, P2, P3): pooled within-array pairs, binned by cortical distance
| cortical mm | n pairs | P(same dominant segment) | mean Jaccard (segment sets) | P(same digit) | mean palm-centroid distance mm (n) |
|---|---|---|---|---|---|
| 0.40 | 26 | 0.77 | 0.49 | 0.88 | 10.3 (25) |
| 0.57 (diag.) | 254 | 0.68 | 0.48 | 0.85 | 16.3 (241) |
| 0.6-0.9 | 274 | 0.59 | 0.38 | 0.82 | 20.9 (260) |
| 0.9-1.2 | 179 | 0.53 | 0.34 | 0.74 | 22.9 (169) |
| 1.2-1.5 | 400 | 0.51 | 0.32 | 0.73 | 23.9 (377) |
| 1.5-1.8 | 519 | 0.42 | 0.26 | 0.68 | 27.9 (476) |
| 1.8-2.2 | 258 | 0.37 | 0.21 | 0.67 | 30.4 (239) |
| 2.2-2.6 | 375 | 0.31 | 0.16 | 0.62 | 33.1 (344) |
| 2.6-3.0 | 185 | 0.15 | 0.07 | 0.50 | 39.8 (172) |
| 3.0-3.5 | 194 | 0.19 | 0.10 | 0.47 | 41.7 (174) |
| 3.5-4.7 | 127 | 0.18 | 0.11 | 0.40 | 47.3 (110) |
- The all-pairs baseline for P(same segment) is 0.418. The pooled curve reaches that baseline at about 1.5-1.8 mm of cortex and
  roughly halves again by 2.6 mm or more (ARITHMETIC from the table).
- Per array, P(same segment) for pairs <= 0.57 mm vs all pairs:
  | Array | Near | All |
  |---|---|---|
  | C1 medial | 0.64 | 0.31 |
  | C1 lateral | 0.79 | 0.47 |
  | P2 medial | 0.85 | 0.45 |
  | P2 lateral | 0.87 | 0.65 |
  | P3 medial | 0.41 | 0.30 |
  | P3 lateral | 0.59 | 0.33 |
- Spearman rho of cortical distance vs palm-centroid distance, with the label-shuffle permutation p (one-sided):
  | Array | rho | p |
  |---|---|---|
  | C1 medial | 0.33 | 0.0002 |
  | C1 lateral | 0.34 | 0.0002 |
  | P2 medial | 0.50 | 0.0002 |
  | P2 lateral | 0.38 | 0.0002 |
  | P3 medial | 0.17 | 0.0066 |
  | P3 lateral | 0.21 | 0.0028 |

  Jaccard vs distance gives rho -0.42, -0.42, -0.49, -0.36, -0.11 (p 0.038) and -0.18 (p 0.007) in the same array order.
  **Every array rejects spatial independence. P3 is the weakest.**
- Analogue of Fig 3e (same-digit pairs, palm; authors' 7 bins on [0,4] mm):
  | Bin centre (mm) | Mean PF-centroid distance (mm) |
  |---|---|
  | 0.29 | 11.8 |
  | 0.86 | 15.8 |
  | 1.43 | 16.6 |
  | 2.00 | 18.4 |
  | 2.57 | 21.3 |
  | 3.14 | 24.8 |
  | 3.71 | 26.1 |

  Pearson r = 0.17 (n = 1,806). The same-finger-only version runs 7.5 -> 26.9 mm, r = 0.20 (n = 724).
  Compare the DIGITISED Fig 3e curve: 3.1 -> 26.6 mm, with the paper's "r > 0.4 within each array".
  - The far end agrees. The near end is larger here, and r is lower.
  - Expected causes: segment quantisation (the fingertip segments are about 10-20 mm apart), no 33% threshold, and the mean
    rather than the thresholded PF.
  - **Use the Fig 3e curve for centroid distance and these tables for overlap/identity.**

### 4.2 Fifer 2022 (JHU, finger hue classes)
- P(share a finger class):
  | Array | Pairs <= 0.57 mm | All pairs |
  |---|---|---|
  | left A | 0.96 | 0.94 |
  | left B | 1.00 | 0.92 |
  | right | 0.97 | 0.70 |
- Pooled P(share a finger class): 0.97-0.98 at <= 0.9 mm, 0.82 at 1.8-2.2 mm, 0.63 at 2.6-3.0 mm, 0.57 at 3.0-3.5 mm.
- Jaccard vs distance: rho -0.18 (p 0.004), -0.43 (p 0.0002), -0.51 (p 0.0002).
- This is at finger level only, so it is much coarser than the Greenspon segments.

### 4.3 Armenta Salas 2018 (arm regions, 400 um ASSUMED)
- Medial: rho(Jaccard, distance) = 0.00 (p 0.46). Lateral: rho = -0.09 (p 0.14).
- P(share a region): near 0.43 vs all 0.42 (medial); near 0.52 vs all 0.45 (lateral).
- **No detectable within-array spatial structure** at this 5-category, arm-level resolution. This is consistent with the paper's
  "Coarse somatotopy was present between the medial and lateral arrays".

### 4.4 Inter-array distance (was "NOT FOUND" in cycle 3): ESTIMATE, not a measurement
Source: `ShowSubjectImplant.m` in the Greenspon code. It draws the arrays on each participant's MRI rendering at hard-coded
`array_positions` (px) with `array_scalar` "% Pixels per ch". Arrays are drawn as rows x cols x scalar, so 1 ch = 1 pitch = 0.4 mm.
Medial-to-lateral sensory array centre distance = |dpos| / scalar x 0.4 mm:
| Participant | Distance |
|---|---|
| C1 (BCI02) | 7.4 mm |
| P2 (CRS02) | 10.2 mm |
| P3 (CRS07) | 5.8 mm |
| BCI03 (likely C2, UNVERIFIED) | 11.3 mm |
| CRS08 (likely P4, UNVERIFIED) | 8.1 mm |
Caveat: the positions were placed by hand from intra-operative photos onto a 2-D rendering. Treat the error as about +/- 1-2 mm
(my guess, not measured).

## 5. Still blocked / not done
- Per-electrode PF **area**, true (unquantised) centroids, and pixel-level pairwise PF overlap: DABI only (GU5A5IO8LRXE etc.;
  restricted, login). Not requested.
- **C2 and P4** per-electrode maps: only Downey 2024 Fig 3d/4 at 709 px. Automated segmentation merged neighbouring arrays, and
  cells of about 8 px carry 3-5 digit stripes. It could be done by hand-placing corners, but the read-out would be low-confidence.
  I did not do it.
- Flesher 2016 STM: paywalled, and there is no PMC copy.
- Fifer 2022 at higher resolution: blocked by the publisher's bot wall.
- The Armenta Salas electrode pitch is not stated anywhere I could open.
- Any open numeric (non-figure) per-electrode PF table from any human S1 ICMS study: none found.
