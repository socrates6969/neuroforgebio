# Neurobiology research hive: shared protocol (queen = neuro-research-queen). Program owner: Marius Carlsson

Program: a leak-proof evaluation harness for seizure detection/forecasting and adaptive-DBS data analysis on OPEN data.
Base plan: C:\Users\mariu\research-lab\nevrobiologi-2\RAPPORT.md (Norwegian). The shared harness idea is in research-lab\neuroforge-kart\RAPPORT.md
and research-lab\matematikk\RAPPORT.md. Company rules: C:\Users\mariu\neuro-company\BRIEF.md.

## Status labels (every output)
RESEARCH USE ONLY. NOT A MEDICAL DEVICE. No clinical claims. Software intended for diagnosis, monitoring or treatment decisions
may be a medical device under EU MDR 2017/745 (e.g. Rule 11) or FDA SaMD rules. Any clinical use requires regulatory clearance
and clinical validation (IRB/ethics approval).

## Rules for every agent
1. Cite only sources you OPENED (DOI/PMID/URL), and say whether you read the abstract or the full text. Grades: A = replicated, B = single
   peer-reviewed study, C = preprint/theory, D = marketing. Never invent numbers, papers or results. Mark uncertain items UNVERIFIED.
2. WebSearch is unavailable. Use WebFetch on PubMed E-utilities, Europe PMC REST, Semantic Scholar, arXiv, PhysioNet, OpenNeuro and GitHub.
3. OPEN data only, with no registration. TUSZ, Epilepsyecosystem, IEEG.org, EPILEPSIAE and DABI are owner-gated: do not sign up.
4. Machine: Windows, about 3-4 GB RAM free. Total downloads for cycle 1 must stay UNDER 2 GB, so check sizes before downloading.
   Venv: C:\Users\mariu\neuro-company\.venv\Scripts\python.exe. Only coder agents install packages. Keep each run under 1.5 GB RAM.
5. Provenance: every downloaded file gets a SHA-256 in data\manifests\ (checked against PhysioNet's SHA256SUMS where it exists).
   Every result JSON records the input file hashes, a hash of the script, package versions and the seed (20261001).
6. Absolute paths, never cd, no git (the lead commits). Do not publish, push, sign up or contact anyone.
7. Blackboard: notes\BOARD.md (append-only, format `- [from -> to] message (path)`). Post your final report there, because the handback often
   fails. Numeric facts for preregs go in notes\facts.md, one section per role.
8. Pre-registration: PASS/FAIL thresholds are fixed in prereg\ BEFORE any code touches test data. Deviations are logged in code\DEVIATIONS.md.
   An independent reviewer checks the code, and nothing reaches a report without that review.

## Folders (root C:\Users\mariu\neuro-company\research\neurobiology\)
lit\, notes\, prereg\, code\ (code\review\ for reviewers), results\, figures\, data\raw\ (downloads), data\manifests\ (hashes),
STATUS.md, PLATFORM_FEATURES.md (queen).
