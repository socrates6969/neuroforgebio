# Channel estimator (`nf_channel_estimator`)

> **Research use only. Not a medical device. Computational analysis of projected-field maps; not a stimulation protocol. Clinical use requires an IRB/FDA-approved study.**

Status: research feature, version 0.1.0. Code: `services/workers/steps/channel_estimator/`.
It outputs channel counts and statistics only. It never outputs stimulation parameters of any kind
(tested: see "No-stimulation rule" below).

## What it computes

Input: one implant's per-electrode projected-field (PF) map, with each electrode's hand-segment labels.
A **channel** is a hand territory with at least `m` PF electrodes (default `m = 2`, for redundancy)
whose dominant PF lies in that territory. The estimator is a port of the research analysis P6
(`research/somatosensory/code/p6_empirical_channels.py`), which was pre-registered and independently
code-reviewed (`research/somatosensory/code/REVIEW_cycle4.md`). The maths was ported as-is, not
re-tuned.

| Output block | What it is |
|---|---|
| `channel_counts` | `k_digit` (digit territories D1..D5 with at least `m` electrodes) and `k_territory` (adds the pooled palm/dorsum-of-hand territory), under each labelling rule R1, R2, R3 and ray, plus the territory class sizes. Per array (R1) and the second-array gain. |
| `diversity` | N_eff = N² / Σ n_c² (inverse Simpson index / participation ratio) of the R1 digit-level and segment-level labels, the bias-corrected form, and the soft (Jaccard) variant. |
| `clustering` | Observed N_eff compared with spatially random nulls: Null A (segment chosen with probability proportional to its area), Null B (segments drawn from the pooled labels of the three published participants), and Null A without the wrist. For each: null median, ratio = observed / null median, one-sided p = P(null ≤ observed), at segment and digit level; plus the same for `k_digit`. Seed and number of draws are in the block. |
| `attrition` | P(K ≥ k) when each PF electrode survives independently with probability `survival` (default 0.62), for k = 1..5 (digit level) and 1..6 (territory level), computed exactly (Poisson-binomial dynamic programme over the disjoint territory classes). Sensitivity rows at 0.47, 0.54, 0.62, 0.64, 0.75 and 1.0. |
| `relabelling` (optional) | Robustness to digitisation errors: in each draw, round(x·N) PF electrodes get their dominant segment replaced by one of the 3 nearest same-surface segments; P(K ≥ k) for x = 0.05, 0.10, 0.20. |
| `limitations`, `notice` | Fixed text carried in every result. |
| `provenance` | Input hash, package version, code commit, every parameter and the seed, reference-data hashes. |

### Labelling rules

A segment tag starting with `Dk` maps to digit `Dk`; `W` maps to WRIST; other palm tags (for example
`P3-mcp`) map to PALM; other dorsum tags (for example `P-dr`) map to DORSUM_HAND.

| Rule | Territory of an electrode |
|---|---|
| R1 (primary, "palm first") | the palm tag's territory if the palm tag is set, else the dorsum tag's |
| R2 (liberal) | the first digit among (palm, dorsum); else as R1 |
| R3 (strict) | a digit only if every non-empty tag maps to that digit; palm/dorsum-of-hand only gives HAND; anything else is MIXED |
| ray | R1, but palm `P{2..5}-mcp` maps to digit `D{2..5}` |

Clustering, diversity and relabelling use R1 (as in the research). `--rule` selects the rule for the
attrition curve; counts are always reported for all four rules.

## Input schema (`nf.pf-map/v1`)

JSON Schema: `services/workers/steps/channel_estimator/schemas/pf-map.v1.schema.json`
(`python -m nf_channel_estimator schema input`).

```json
{
  "schema": "nf.pf-map/v1",
  "map_id": "example-1",
  "electrodes": [
    { "electrode_id": "33", "array_id": "LateralSensory", "has_pf": true,
      "palm_segment": "D2d-pu+D2d-pr", "dorsum_segment": "", "x_mm": 0.0, "y_mm": 0.0 },
    { "electrode_id": "34", "array_id": "LateralSensory", "has_pf": false }
  ]
}
```

| Field | Required | Meaning |
|---|---|---|
| `electrode_id`, `array_id` | yes | strings; the pair must be unique |
| `has_pf` | no (default `true`) | whether the electrode has a projected field; non-PF electrodes count only in the per-array totals |
| `palm_segment`, `dorsum_segment` | a PF electrode needs at least one | hand-segment tags (vocabulary of the digitised Greenspon 2025 Extended Data Fig. 1, for example `D2m-u+D2m-r`, `P3-mcp`, `P-dr`, `W`); empty for non-PF electrodes |
| `x_mm`, `y_mm` | no (both or neither) | electrode position on the array grid; carried and hashed, not used by the statistics (the nulls depend only on the labels, as in the research) |
| `dominant_segment` | no | optional check value `palm:<tag>` or `dors:<tag>`; must equal the palm-first derivation |

Unknown fields are rejected. The dominant segment is derived: the palm tag if set, else the dorsum
tag. Tags outside the reference segment table are accepted (the rules only read the prefix); they are
listed in `input_summary.dominant_segments_outside_reference` and switch off the relabelling check.

**CSV form**: one row per electrode, header with `electrode_id,array_id` and any of
`has_pf,palm_segment,dorsum_segment,x_mm,y_mm` (same meaning; `has_pf` is `1/0/true/false`, empty =
true). A CSV map and the equivalent JSON map give the same input hash and the same result.

## Output schema (`nf.channel-estimate/v1`)

JSON Schema: `services/workers/steps/channel_estimator/schemas/channel-estimate.v1.schema.json`
(`python -m nf_channel_estimator schema output`). Every object is closed
(`additionalProperties: false`). Top-level keys, in this fixed order: `schema`, `notice`, `map_id`,
`input_summary`, `channel_counts`, `diversity`, `clustering`, `attrition`, `relabelling`,
`limitations`, `provenance`.

## CLI

```sh
# from the repo root, with the project venv
PYTHONPATH=services/workers/steps/channel_estimator \
  .venv/Scripts/python -m nf_channel_estimator estimate \
  services/workers/steps/channel_estimator/examples/greenspon2025_C1.pf-map.json \
  --m 2 --survival 0.62 --rule R1 --seed 20260926 --null-draws 10000 [--relabel] [--compact]
```

Result JSON goes to stdout; errors go to stderr as `error: <message>`.

| Exit code | Meaning |
|---|---|
| 0 | success |
| 1 | unexpected internal error |
| 2 | usage error or parameter out of range (for example `--survival 2`) |
| 3 | input cannot be read or parsed (missing file, invalid JSON or CSV syntax, duplicate JSON keys) |
| 4 | input parsed but fails validation (schema, labels, duplicate electrodes) |

Trimmed output for the C1 example map:

```json
{
  "schema": "nf.channel-estimate/v1",
  "channel_counts": { "m": 2, "by_rule": { "R1": { "k_digit": 4, "k_territory": 4 } } },
  "diversity": { "n_eff_digit": 2.6731571627260085, "n_eff_segment": 5.152815013404826 },
  "clustering": { "seed": 20260926, "draws": 10000,
    "null_b_pooled": { "segment_level": { "null_median": 9.562189054726367,
      "ratio": 0.5388739946380697, "p_value": 0.0002 } } },
  "attrition": { "survival": 0.62,
    "digit_level": { "p_k_at_least": [ { "k": 4, "probability": 0.9796904516165368 } ] } }
}
```

## Python API

```python
from nf_channel_estimator import EstimateParams, estimate, load_map

pf_map = load_map("map.json")            # or .csv; raises PFMapError with a clear message
result = estimate(pf_map, EstimateParams(m=2, survival=0.62, rule="R1", seed=20260926))
result.k_digit("R1")                     # 4 for the C1 example
result.p_k_at_least(4)                   # P(K_digit >= 4) at the requested survival
doc = result.to_dict()                   # the JSON document
```

## Parameters and their sources

| Parameter | Default | Source |
|---|---|---|
| `m` (electrodes per channel) | 2 | P6 prereg §4a: two electrodes per channel give redundancy against electrode loss |
| `survival` | 0.62 | published long-term functional fraction of electrodes, 62 ± 15 % (Greenspon 2026 preprint; published value 64 ± 13 %), P6 prereg §4c |
| sensitivity survivals | 0.47, 0.54, 0.62, 0.64, 0.75, 1.0 | P6 prereg §4c (0.47 = 62 − 15; 0.54 = a 10-year single-person value) |
| `rule` | R1 | P6 prereg §3 (primary rule) |
| `seed` | 20260926 | the research seed; streams follow the research layout, `SeedSequence(seed).spawn(10)` with Null A = stream 3, Null B = stream 4, relabelling = stream 1 |
| `null_draws` | 10,000 | P6 prereg §7 (C4) |
| relabel fractions / draws | 0.05, 0.10, 0.20 / 5,000 | P6 prereg §5 (0.10 is the stated guess, not a measurement) |

Reference tables (`nf_channel_estimator/reference_data/`, **not shipped in the package**): the
hand-segment table (48 segments with centroid and area) and the 186 pooled R1 dominant segments of
participants C1, P2 and P3, both derived from the digitised Greenspon 2025 Extended Data Fig. 1
(grade B source). The article is licensed CC BY-NC-ND 4.0, so these files, the golden inputs in
`tests/golden/` and the `examples/` maps stay in the private repository for internal testing only
(`THIRD_PARTY_NOTICE.md` in each folder; `legal/data-agreements/figure-data-memo.md`). The wheel and
sdist exclude them, and `tests/test_ce_release_guard.py` builds both and fails if any
`greenspon2025_*` file is inside.

Without the tables (an installed package), channel counts, diversity and attrition are computed
as usual; `clustering` and `relabelling` report `skipped` with the reason, and
`provenance.reference_data` is `{"status": "not_installed"}`. To run the nulls, point
`--reference-dir` (CLI), `reference_dir=` (API) or `NF_CHANNELS_REFERENCE_DIR` at a local copy.

### Before an open-source release (TODO, decision D6)

Open item; nothing here is done yet. Before any public repository or package release:

1. Replace the `greenspon2025_*` files with **synthetic fixtures** of the same shape for unit tests.
2. Add a **fetch-and-digitise script** that users run on their own machine against the
   open-access article, verified against hash pins of our own outputs.
3. Remove the files from the public repository and decide about git history (a history rewrite is
   a lead/owner decision).
4. Consider neutral participant labels (S1–S3) in any remaining internal files (legal memo, action 4).
5. Keep `tests/test_ce_release_guard.py` in the release pipeline.

Contacting the authors or publisher for permission is an owner action.

## Provenance

Every result carries `provenance`:

- `input_sha256`: SHA-256 of the NF-CJSON v1 canonical JSON (docs/spec/hashing.md §3) of the
  normalised input map (defaults written out). It does not depend on key order or on JSON vs CSV.
  The canonicaliser is a copy of `spec/reference/python/nf_canonical.py`, checked against the frozen
  vectors in `spec/test-vectors/`.
- `version`, `code_commit` (git `HEAD`, or `NF_CODE_COMMIT`; `null` if unknown), `parameters` (all of
  them, including the seed), `reference_data` hashes (or `{"status": "not_installed"}`), and the
  Python and numpy versions.

For a fixed input, parameters and seed the result is identical run to run.

## Validation against the research

Golden tests (`tests/test_ce_golden_p6.py`) rebuild the three published maps from the digitised data
(input files pinned by SHA-256) and compare with the reviewed `p6_empirical_channels.json`:

- K_digit(m = 2, R1) = 4 / 2 / 4 for C1 / P2 / P3; K_terr = 4 / 3 / 5; all rules and m = 1, 2, 3.
- Exact attrition to 1e-12 at every sensitivity survival, for example P(K ≥ 4; 0.62) = 0.980 (C1) and
  0.782 (P3), P(K ≥ 2; 0.62) = 0.383 (P2).
- N_eff (2.67 / 1.43 / 3.70; segment level 5.15 / 4.12 / 6.24) exactly; clustering ratios vs Null B
  (segment 0.54 / 0.43 / 0.65, digit 0.72 / 0.38 / 0.99) and Null A (0.29 / 0.23 / 0.35) bit for bit;
  relabelling probabilities bit for bit.

The public API gives the research numbers for C1 directly. The research drew C1, P2 and P3 from one
shared random stream in sequence, so P2's and P3's research nulls depend on C1's draws having come
first; the tests replay that order through the same functions. A single-map call for P2 or P3 uses a
fresh stream and gives statistically equivalent, not identical, null values.

## No-stimulation rule

`tests/test_ce_no_stimulation.py` walks every key of real outputs (all golden maps, every rule, with
relabelling, and the empty map) and every property of the output JSON Schema, and fails on any
stimulation-like name (`stim*`, `pulse*`, `amplitude*`, `current*`, `charge*`, `frequency*`, `freq*`,
`waveform*`, `train*`, `duty*`, `phase_width*`, `microamp*`, `uA`, `electrode_setting*`, `trigger*`,
`command*`). Inputs with unknown fields are rejected.

## Verified vs open

From `research/somatosensory/DESIGN_RECOMMENDATION.md` (cycle 4). Data: 3 participants, all labels
digitised from published figures, grade-B sources.

| Status | Claim |
|---|---|
| Verified (P6, reviewed) | One channel per digit (K ≥ 5) is not supported by any open-data 2 × 32 implant, under every labelling rule. |
| Verified (P6, reviewed) | The channel count is limited by somatotopic clustering, not by electrode count: segment-level N_eff is 0.43-0.65 of the pooled random null in 3 of 3 participants (p ≤ 0.007). |
| Verified (P6, reviewed) | The count depends on placement: observed digit channels are 4 / 2 / 4; P2's arrays map mostly to the palm (51 of 62 electrodes). |
| Verified (P6, reviewed) | At 62 % survival, 4 channels survive with P = 0.98 (C1) and 0.78 (P3); P2's 2 channels survive with P = 0.38. |
| **Open** | **No guaranteed per-implant minimum is verified.** No level, not even 2, holds in 3 of 3 implants after attrition, so "every implant gives at least K channels" is not verified for any K. The ray-rule fallback of 3 is rule-conditional. |
| **Open** | **Perceptual independence.** A distinct dominant territory is not proof that channels feel distinct. PF areas and overlaps exist only in restricted data. |
| **Open** | **Model-based counts** (research P5 about 14, P5b about 8-14) failed their validation gates; they are not design values. |
| Condition | Independent electrode loss is assumed; clustered loss lowers C1's P(K ≥ 4) to 0.75 and P3's to 0.49. |
| Condition | Results hold for 2 × 32 wired electrodes in the S1 hand area at 400 µm pitch, placed with fMRI targeting as in the Pitt/Chicago trials. |

What would turn this into a verified positive number: per-electrode PF areas and overlaps from more
implants, or perceptual discrimination data between channels; then the same analysis is rerun
unchanged.
