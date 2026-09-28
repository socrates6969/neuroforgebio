# Multiverse study: how preprocessing choices change decoding results

**Status: Planned / in preparation.** No data has been downloaded, no study run has happened, and
there are no results. Nothing here is published; publication needs the owner's explicit approval
after the claims are graded (BUILD-GUIDE 3.9).

## Question

How much does cross-validated decoding accuracy on public EEG data move when only the
preprocessing pipeline changes (high-pass cutoff, low-pass cutoff, line-noise notch), with the
classifier, features, data and seed held fixed? Motivation (from `market/landscape.md` §3):
Kessler et al. 2025 (_Commun Biol_) found that artifact-correction steps reduced decoding
performance while higher high-pass cutoffs increased it; Huang et al. 2025 (_Psychophysiology_)
tested 43 pipelines and found "no single best pipeline".

## Files

| File                    | What                                                                                                                                                                                    |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `study.json`            | Study definition: question, base pipeline, grid, metric, dataset-specific TODOs, publication gate.                                                                                      |
| `datasets.json`         | Dataset manifest with licence fields (SPDX id, URL, who verified it, when). Entries are **TODO placeholders**: no EEG decoding accession appears in the repo's docs, and none is invented. |
| `pipelines/base.json`   | Base PipelineVersion (notch, filter, re-reference, epochs, band power, `nf_steps.decode_lda@1`), every parameter explicit. Draft until a dataset is chosen.                              |
| `run_study.py`          | Runner: `validate` (local), `fetch` (CI only), `ingest` (not built yet), `sweep` (CI only), `render` (local).                                                                            |
| `.github/workflows/multiverse-study.yml` | Dispatch-only workflow, SHA-pinned actions, `uv sync --locked`, outputs as a 14-day artifact.                                                                          |

## How it runs (CI only)

1. `validate`: the study, the manifest and the base pipeline. A dataset entry that is not a TODO
   must carry a well-formed accession (OpenNeuro `ds` + 6 digits, DANDI 6 digits), a pinned
   version, a citation and a recorded licence.
2. `fetch`: downloads the selected datasets from the public OpenNeuro S3 bucket or the DANDI API
   and writes `files.json` (path, size, SHA-256 per file). Refuses outside CI and refuses TODO
   entries. Never run locally.
3. `ingest`: **not built yet**. Mapping the chosen dataset's files onto the M2 upload/convert API
   (and its events onto epoch labels) is decided when the dataset is chosen.
4. `sweep`: publishes the base pipeline and posts the grid to `POST /v1/sweeps` of a CI platform
   instance; every grid point is its own content-addressed PipelineVersion, every cell a run on the
   3.3 queue with provenance. Saves the report (`GET /v1/sweeps/{id}/report`).
5. `render`: writes `results.json` (heatmap table; each cell lists its run IDs and provenance node
   IDs) and a `packages/figures`-style manifest (pinned SHA-256, heatmap plot spec, status
   `preliminary`) into the artifact directory. It refuses to write into `packages/`.

## Gates before anything is published

- A scientist selects the dataset(s) and fills `datasets.json` from the repository pages (never
  from memory), including the licence and who verified it.
- An independent re-run from the provenance IDs reproduces every figure (BUILD-GUIDE 3.9).
- Claims are graded; the owner approves publication explicitly.

The method itself is tested on synthetic data with a planted effect
(`services/platform/tests/sweeps/test_sweeps_planted.py`); that test says nothing about real data.
