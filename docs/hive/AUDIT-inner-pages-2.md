# Read-only claims audit 2: /research, /research/<slug>, /law-tracker, /sdks (EN)

By the H1-c worker (hive H1, queen hive-web), 2026-09-27, against main 4370f95. No files edited except this one. No runs made (no node, pnpm, python, build, test or lint). Same method as AUDIT-inner-pages.md: every number, date, named law/standard, version, count and status/capability claim checked against its repo source.

Verdicts: SOURCED-CORRECT / SOURCED-MISMATCH / UNSOURCED / STALE. Severity (findings only): HIGH = wrong or unsourced public claim; MED = claim/source mismatch or stale status; LOW = cite precision or wording.

Scope notes:
- `/research/<slug>` builds from `content.whitepapers` (`apps/web/src/pages/research/[slug].astro:14-16`). On main that map has exactly one entry, `somatosensory-closed-loop` (`packages/content/src/index.ts:73-75`). The parked web/papers drafts are not on main (WEB-BOARD.md:85), so only that slug is audited.
- `/law-tracker` renders `law-tracker.json` plus a table generated at build time from `rules/*.yaml` (`apps/web/src/pages/law-tracker.astro:16,53-94`). The generated rows are page claims too and are audited here (CLAIMS-AUDIT.md did not cover them).
- None of the four pages cites the research library (C:\Users\mariu\research-library), so it was not used.

## Totals (exact)

| Page | Claims | SOURCED-CORRECT | SOURCED-MISMATCH | UNSOURCED | STALE |
|---|---|---|---|---|---|
| /research | 6 | 4 | 1 | 1 | 0 |
| /research/somatosensory-closed-loop | 14 | 8 | 2 | 0 | 4 |
| /law-tracker | 24 | 21 | 3 | 0 | 0 |
| /sdks | 13 | 11 | 2 | 0 | 0 |
| **Total** | **57** | **44** | **8** | **1** | **4** |

Findings (non-correct rows): 13 = HIGH 1, MED 8, LOW 4. (RI6 regraded LOW -> HIGH by hive-web after vote V2, per this audit's own rubric: UNSOURCED = HIGH.)
CLAIMS-AUDIT.md re-verification: 10 earlier rows (8 law-tracker, 2 sdks). AGREE 8, DISAGREE 2.

Paths: `research.json` = packages/content/content/pages/research.json; `wp.json` = packages/content/content/research/somatosensory-closed-loop.json; `law-tracker.json` and `sdks.json` = packages/content/content/pages/*.json; `reg.md` = market/regulation.md; `STATUS.md` = research/somatosensory/STATUS.md.

## Findings (fix list)

| # | Sev | Page | Claim (file:line) | Source checked (file:line) | Verdict | Owner |
|---|---|---|---|---|---|---|
| S1 | MED | /research/somatosensory-closed-loop | Meta "No results are reported yet; research is ongoing" (wp.json:5); statusNote "Research is ongoing and no results are reported on this page yet" (wp.json:11) | STATUS.md:1,10-24 (4 cycles, 10 preregistered tests, all with verdicts); STATUS.md:30 (work waits for an owner/lead choice); research/somatosensory/whitepaper/whitepaper_draft.md:2,13,17 (draft v0.2 with results, "we report those failures"); the page itself shows the P4 result figure (wp.json:42-47) | STALE. Results exist and the program is paused for a decision. "No results are reported on this page yet" is literally true only if the P4 figure is not counted as a result. | unassigned in WEB-BOARD.md:12-24 (copy from M1, nfb-build-queen, M1-REPORT.md:3); science status: research-queen (research/somatosensory/HIVE.md:1) |
| S7 | MED | /research/somatosensory-closed-loop | "Latency budget": how much feedback delay a simulated grip tolerates, shown as an open question; source P1b prereg (wp.json:19-21) | STATUS.md:13 (P1 UNTESTED), :17 (P1b ABANDONED), :23 (H3 latency RETIRED) | STALE. The line is closed with no verdict, and the page presents it as pending. | same as S1 |
| S8 | MED | /research/somatosensory-closed-loop | "Encoding": whether biomimetic beats linear encoding at matched charge; source P2b prereg (wp.json:24-26) | STATUS.md:14 (P2 INCONCLUSIVE), :18 (P2b FAIL/ABANDONED), :22 (P2c FAIL, robust 10/10) | STALE. It was answered negatively, and the page cites P2b, not the final P2c test. | same as S1 |
| S9 | MED | /research/somatosensory-closed-loop | "Calibration": whether psi needs fewer trials than a staircase; source P3 prereg (wp.json:29-31) | STATUS.md:15 (P3 FAIL 2/48), :19 (P3b FAIL, line closed) | STALE. The line is closed after two failed tests. | same as S1 |
| S4 | MED | /research/somatosensory-closed-loop | Intro: the study models how stimulation "could encode touch, pressure and proprioception" (wp.json:13) | research/somatosensory/theories.md:15 (H5 proprioception "THEORY, deprioritised"); STATUS.md:33 (proprioception is a future option that "need[s] open data"); no prereg in research/somatosensory/prereg/ covers it | SOURCED-MISMATCH. Proprioception is in the program scope (HIVE.md:4) but was never modelled. | same as S1 |
| RI4 | MED | /research | Card summary: "…could encode touch, pressure and proprioception" (research.json:16) | same as S4 | SOURCED-MISMATCH (same claim as S4, on the index card). | unassigned (copy origin nfb-build-queen) |
| E2 | MED | /sdks | "planned as open source (Apache-2.0 proposed), pending the owner's decision" (sdks.json:64); meta "Licence pending the owner's decision" (sdks.json:4) | docs/adr/0006-licensing.md:3-5,10 (Status **Accepted**, 2026-09-26, owner decided at GATE B: Apache-2.0 for SDK/core; repo stays all-rights-reserved until SDK code ships); commit c1b2f5a message ("Per lead ruling: licence choice is an open owner decision") | SOURCED-MISMATCH. The page and ADR 0006 disagree. Unsure which is current: the lead ruling in c1b2f5a is not recorded in any repo doc I found, and ADR 0006 was not superseded. Either the ADR status or the page must change. | web-copy |
| E10 | MED | /sdks | "Unity and Unreal: Planned, on the same C interface" (sdks.json:48-50, status `roadmap`); meta "A C interface for C++ and game engines is planned" (sdks.json:4) | architecture/BLUEPRINT.md:437 ("Unity/Unreal only on customer pull, because market/validation.md #10 found no evidence of Unity/Unreal demand"); sdk/README.md:3; market/validation.md:16 | SOURCED-MISMATCH. The sources make engines conditional on customer pull, not planned. The `roadmap` pill is closer than the body text. | web-copy |
| RI6 | HIGH | /research | "A reference architecture for HIPAA-aligned neural data pipelines", status `planned` (research.json:36-40) | Only design/CONTENT-SPEC.md:52 and the design/option-*.html mockups. No plan, BUILD-GUIDE step, research folder or ADR found (git grep "reference architecture") | UNSOURCED. The status comes from the design copy spec, not from any work plan. | unassigned (copy origin nfb-build-queen) |
| S11 | LOW | /research/somatosensory-closed-loop | Evidence legend "A = peer-reviewed or primary legal text; B = reputable secondary; C = preprint or theory; D = company marketing" (wp.json:40) | market/landscape.md:5 (matches this scale); research/somatosensory/whitepaper/whitepaper_draft.md:23 (the paper's own scale: "A = replicated across groups; B = single study…"); architecture/BLUEPRINT.md:176 ("evidence grades per claim") | SOURCED-MISMATCH. The legend uses the market scale, not the paper's, and no claim on the page carries a grade, so the legend explains nothing shown. | same as S1 |
| L21 | LOW | /law-tracker | Generated row EU/GDPR: "Neural data is personal data… Art. 9 special categories", cited to EMBO Rep 2025 [A], marked verified ✓ (rules/eu.yaml:10-21, rendered via law-tracker.astro:64-90) | reg.md:52 | SOURCED-MISMATCH (unsure). In reg.md:52 the EMBO citation follows a separate quote ("already offer[s] stronger safeguards…"). The Art. 9 sentences before it may be our own reading. The GDPR text itself is not cited. The row renders the note text in quotation marks as if it were quoted. | unassigned (rules from M5 5.2, nfb-build-queen, M5-REPORT.md:3) |
| L23 | LOW | /law-tracker | sourceNote: "Every row cites the section of our research notes…, plus the primary or peer-reviewed source named there" (law-tracker.json:144) | law-tracker.json:89-98 (HIPAA row: no sourceUrl; the primary hhs.gov source is named only in reg.md:31); law-tracker.json:112-115 (EU AI Act row: the source is a secondary site, grade B, reg.md:53) | SOURCED-MISMATCH. Two rows do not show a primary or peer-reviewed source. | unassigned (copy origin nfb-build-queen, M1) |
| L24 | LOW | /law-tracker | Meta: "A draft of US state, US federal and EU rules…, generated from the platform rule files" (law-tracker.json:4) | rules/ruleset.yaml:7-12 (only CO, CA, CT, MT, EU); law-tracker.json:144 ("the context rows are maintained by hand") | SOURCED-MISMATCH. The US federal rows (and Chile) are hand-maintained, not generated from rule files. | same as L23 |

## CLAIMS-AUDIT.md rows re-verified (independently, against main 4370f95)

| # | Earlier row | Claim (file:line now) | Source checked (file:line) | My verdict | AGREE / DISAGREE |
|---|---|---|---|---|---|
| L1 | CLAIMS-AUDIT.md:72 | "MIND Act of 2025 (Management of Individuals' Neural Data)" (law-tracker.json:68) | reg.md:25 | SOURCED-CORRECT | AGREE |
| L2 | CLAIMS-AUDIT.md:73 | "Introduced September 2025; bill number, sponsors and current status not verified" (law-tracker.json:69) | reg.md:25-26 | SOURCED-CORRECT | AGREE |
| L3 | CLAIMS-AUDIT.md:74 | "EU AI Act, Art. 5(1)(f)" (law-tracker.json:108) | reg.md:53-54 | SOURCED-CORRECT | AGREE |
| L4 | CLAIMS-AUDIT.md:75 | "Applicable from 2 Feb 2025" (law-tracker.json:109), grade B (:115) | reg.md:53 (artificialintelligenceact.eu, B) | SOURCED-CORRECT | AGREE |
| L5 | CLAIMS-AUDIT.md:76 | Chile "2021 constitutional amendment" (law-tracker.json:126) | reg.md:59 | SOURCED-CORRECT | AGREE |
| L6 | CLAIMS-AUDIT.md:77 | "Amended 2021; court ruling 2023" (law-tracker.json:127) | reg.md:59 | SOURCED-CORRECT | AGREE |
| L7 | CLAIMS-AUDIT.md:78 | "Protects cerebral activity and the information drawn from it; in 2023 the Supreme Court ordered neural-data deletion" (law-tracker.json:128); EMBO doi, A (:131-132) | reg.md:59 | SOURCED-CORRECT | AGREE |
| L8 | CLAIMS-AUDIT.md:79 | asOf "2026-09-26" (law-tracker.json:12) | reg.md:4 ("Prepared 2026-09-26") | SOURCED-CORRECT | DISAGREE with the earlier row's reasoning. It cites "law-tracker.json (generated)", which is circular, and the file is hand-maintained (only the rules table is generated, law-tracker.json:144). The date is right against reg.md:4. |
| E1 | CLAIMS-AUDIT.md:55 | "MNE-Python had about 308,000 PyPI downloads in the month to 26 September 2026" (sdks.json:55; the wording changed since 7355277) | market/landscape.md:51 (pypistats "recent", last month, on 2026-09-26), :57 (308,276/month) | SOURCED-CORRECT | AGREE |
| E2 | CLAIMS-AUDIT.md:32 | Apache-2.0 licence (sdks.json:64, then :63) | docs/adr/0006-licensing.md:3,10 | SOURCED-MISMATCH (see Findings E2) | DISAGREE. The earlier row called it MISSING because "naming requires no source". The status of the licence decision is a sourced claim (ADR 0006). At 7355277 the text "under the Apache-2.0 licence" matched the ADR. The current "pending the owner's decision" conflicts with it. |

Earlier-audit consistency notes: CLAIMS-AUDIT.md:15 gives /sdks 3 claims (2 sourced, 1 missing), but only 2 /sdks rows are listed (:55 and :32). Its law-tracker section also omits the whole generated rules table (5 rows) and 8 hand-written claims.

## Rows the earlier audit missed, and the /research pages (all SOURCED-CORRECT unless listed above)

| # | Page | Claim (file:line) | Source checked (file:line) | Verdict |
|---|---|---|---|---|
| L9 | /law-tracker | MIND Act "defined neural data and directed the Federal Trade Commission to study how to regulate it"; doi 10.1212/wnl.0000000000214942, A (law-tracker.json:70,74-75) | reg.md:25 | SOURCED-CORRECT |
| L10 | /law-tracker | Bills in Alabama, Massachusetts, Minnesota, Illinois, Vermont; unverified; EMBO doi, A (law-tracker.json:52-57) | reg.md:15 | SOURCED-CORRECT |
| L11 | /law-tracker | "No federal statute regulates neural data; … mostly soft policy"; doi 10.1111/bioe.70062, A (law-tracker.json:80-86) | reg.md:27 | SOURCED-CORRECT |
| L12 | /law-tracker | HIPAA applies to covered entities and business associates; many consumer, wellness and research-only neurotech firms are not covered (law-tracker.json:93) | reg.md:31-32 | SOURCED-CORRECT |
| L13 | /law-tracker | AI Act row text: bans emotion inference in workplace and education except medical/safety; "secondary site… (grade B)" (law-tracker.json:110,112) | reg.md:53-54 | SOURCED-CORRECT |
| L14 | /law-tracker | Open questions: Montana SB 163 text; MIND Act number/sponsors/status; MA/MN/IL/VT/AL bill status; Colorado controller-size thresholds (law-tracker.json:139-142) | reg.md:69-73 | SOURCED-CORRECT |
| L15 | /law-tracker | "Every rule is a draft until counsel reviews it, and counsel review is still pending" (law-tracker.json:19) | rules/ruleset.yaml:1-2; review_status draft/unverified in rules/{co,ca,ct,eu}.yaml, rules/mt.yaml:25; M5-REPORT.md:3 ("nothing sent to counsel") | SOURCED-CORRECT |
| L16 | /law-tracker | "The table is generated from the same rule files the platform uses to classify channels" (law-tracker.json:9) | apps/web/src/pages/law-tracker.astro:16; services/platform/nf_platform/governance/rules.py:134; M5-REPORT.md:18 (5.6 pass) | SOURCED-CORRECT |
| L17 | /law-tracker | Generated CO row: HB24-1058, signed 17 Apr 2024, effective 2024-08-07, CNS-or-PNS definition, sensitive data + opt-in consent, controller-size note (rules/co.yaml:8-35) | reg.md:10, :73 | SOURCED-CORRECT |
| L18 | /law-tracker | Generated CA row: SB 1223 Ch. 887, chaptered 28 Sep 2024, effective date "Not stated in our research notes", definition, SPI + right to limit use (rules/ca.yaml:8-32; law-tracker.json:35) | reg.md:11, :64 | SOURCED-CORRECT |
| L19 | /law-tracker | Generated CT row: SB 1295 / PA 25-113, signed 24 Jun 2025, effective 2026-07-01, CNS-only definition, item (G) (rules/ct.yaml:8-30) | reg.md:13, :20 | SOURCED-CORRECT |
| L20 | /law-tracker | Generated MT row: SB 163 adopted May 2025, grade "A (secondary to the statute)", unverified, not evaluated (rules/mt.yaml:8-26) | reg.md:12 | SOURCED-CORRECT |
| L22 | /law-tracker | "Generated at build time from RuleSet v1 · Content hash 010f3375cde1" (law-tracker.astro:38-39) | rules/ruleset.yaml:6,13 | SOURCED-CORRECT for the displayed value. Unsure whether the hash still matches the five files: rules.mjs:80 passes it through without checking, and I could not recompute it (no runs). The Python loader refuses a mismatch (ruleset.yaml:2-4), and commit 946acf8 says the hash was unchanged after reformatting. |
| E3 | /sdks | Meta "A Python SDK first, built and tested internally, on one shared core" (sdks.json:4) | docs/hive/M4-REPORT.md:3,16-17; architecture/BLUEPRINT.md:412,437 | SOURCED-CORRECT |
| E4 | /sdks | "Every SDK records provenance the same way because every SDK uses the same core" (sdks.json:9) | architecture/BLUEPRINT.md:412,429 | SOURCED-CORRECT (design statement; only the Python SDK exists) |
| E5 | /sdks | "Signal processing stays in the Python tools your lab already trusts" (sdks.json:9) | architecture/BLUEPRINT.md:435 | SOURCED-CORRECT |
| E6 | /sdks | A run gives a provenance handle recording every parameter, version and input hash (sdks.json:16) | bindings/python/tests/test_sdk_platform.py:62-80; M4-REPORT.md:17 | SOURCED-CORRECT |
| E7 | /sdks | Snippet: `nf.open`, `nf.pipelines.get("eeg-basic@1.0.0").run(rec)`, `run.provenance.id` (sdks.json:21-24) | M4-REPORT.md:17 (snippet pinned to the real eeg-basic@1.0.0); test_sdk_platform.py:54 (home and /sdks snippets must be equal and are executed), :62-68; bindings/python/python/neuroforge/pipelines.py:1 | SOURCED-CORRECT (labelled "illustrative" but it is the tested API) |
| E8 | /sdks | Python: works alongside MNE-Python, BIDS and NWB tooling; "Not published yet"; built-internal, M4 4.2-4.3 (sdks.json:38-40) | bindings/python/README.md:18,26 (to_mne, [mne] extra); M2-REPORT.md:19 (BIDS), :28 (NWB round-trip CI-only); M4-REPORT.md:3,16-17; docs/adr/0006-licensing.md:14 | SOURCED-CORRECT |
| E9 | /sdks | C and C++ planned: a C interface on the shared core, interop through LSL and BrainFlow (sdks.json:43-45) | architecture/BLUEPRINT.md:421,423,437; sdk/README.md:3,5; market/validation.md:16 ("C/C++ via LSL/BrainFlow interop") | SOURCED-CORRECT |
| E11 | /sdks | "We build for the languages our users already work in, in the order they ask for them" (sdks.json:33) | architecture/BLUEPRINT.md:437; market/validation.md:16 (Python demand from download stats) | SOURCED-CORRECT |
| E12 | /sdks | Open-source scope: SDKs, shared core, converters, step library; hosted platform with consent ledger and model registry proprietary (sdks.json:64) | docs/adr/0006-licensing.md:10 | SOURCED-CORRECT (scope only; licence status is E2) |
| E13 | /sdks | "No SDK code is published yet" (sdks.json:65) | docs/adr/0006-licensing.md:10,14; M4-REPORT.md:3 ("no package uploaded") | SOURCED-CORRECT |
| RI1 | /research | "Figures stay labelled preliminary until they pass our verification gate" (research.json:9) | architecture/BUILD-GUIDE.md:214; docs/hive/M1-REPORT.md:37; packages/figures/manifests/somatosensory-closed-loop.figures.json:7; apps/web/test/builds.test.mjs:188 | SOURCED-CORRECT |
| RI2 | /research | Banner "Computational/theoretical work; any clinical application requires IRB/FDA oversight" (research.json:11) | architecture/BLUEPRINT.md:176; BRIEF.md:31; reg.md:49 | SOURCED-CORRECT |
| RI3 | /research | Somatosensory card status `in-preparation` (research.json:17) | research/somatosensory/whitepaper/whitepaper_draft.md:2-3 (internal draft v0.2) | SOURCED-CORRECT |
| RI5 | /research | Multiverse study: preprocessing grid on open EEG datasets, status `planned` (research.json:29-33) | research/multiverse/study.json (`"status": "planned"`); research/multiverse/README.md:3-5 | SOURCED-CORRECT |
| S2 | /research/somatosensory-closed-loop | Status `in-preparation`, "Whitepaper · computational study" (wp.json:8-9) | whitepaper_draft.md:2-3 | SOURCED-CORRECT |
| S3 | /research/somatosensory-closed-loop | IRB/FDA banner (wp.json:10) | same as RI2 | SOURCED-CORRECT |
| S5 | /research/somatosensory-closed-loop | Simulation only; published data and models; no stimulation settings; no human or animal experiments (wp.json:13-14) | prereg P1b:3-4, P2b:3-4, P3:3-4, P4:2; whitepaper_draft.md:3-4 | SOURCED-CORRECT |
| S6 | /research/somatosensory-closed-loop | "Each question below has a written analysis plan in our repository" (wp.json:16) | the four cited files exist: research/somatosensory/prereg/{P1b_grip_latency_budget_v2, P2b_biomimetic_dprime_difference, P3_psi_vs_staircase_calibration, P4_pooling_capacity}.md (git ls-files) | SOURCED-CORRECT |
| S10 | /research/somatosensory-closed-loop | "Capacity": how much pooling can raise distinguishable intensity levels, in theory (wp.json:34-36) | prereg/P4_pooling_capacity.md:1-2,7-12; STATUS.md:16 (PASS) | SOURCED-CORRECT |
| S12 | /research/somatosensory-closed-loop | Figure caption: C in bits/symbol by Weber fraction w (rows) and pooled electrodes M (columns) at kappa = 0 (wp.json:45) | manifest :24-35 (key `0\|{row}\|{col}`, rows 0.128/0.162/0.225/0.268, cols 1-1024); research/somatosensory/code/p4_pooling_capacity.py:302,304 (table key = (kappa, w, M)); prereg P4:20-21 (w values) | SOURCED-CORRECT |
| S13 | /research/somatosensory-closed-loop | Figure note "Theory computed from published psychophysical summary numbers. Preliminary." (wp.json:46) | prereg P4:2; manifest :7 (`preliminary`) | SOURCED-CORRECT |
| S14 | /research/somatosensory-closed-loop | Each figure "traceable to the code and result file that produced it" (wp.json:11) | manifest :8-20 (result, SVG and script SHA-256 plus script commit 455986f); apps/web/src/lib/figures.ts:1-2,22 (the build fails on a hash mismatch); [slug].astro:73-83 (rendered) | SOURCED-CORRECT |

## Owners (labels only; nobody contacted)

- /sdks: **web-copy** (WEB-BOARD.md:23 owns pages/sdks.json). Findings: E2, E10.
- /law-tracker: law-tracker.json and rules/*.yaml have **no row in the WEB-BOARD.md:12-24 ownership table**. Origin: M1 content (nfb-build-queen, M1-REPORT.md:3); 5.6 table and rules (nfb-build-queen, M5-REPORT.md:3,18). web-a11y made the last edit, but only to headings (2bb50ee). Queen to route. Findings: L21, L23, L24.
- /research and /research/somatosensory-closed-loop: **no row in the ownership table**. Copy origin: nfb-build-queen (M1, d751a30). Science status: research-queen (research/somatosensory/HIVE.md:1). Unsure which live agent holds that role now. Findings: RI4, RI6, S1, S4, S7, S8, S9, S11.

## Queen spot-check (3 quick rows)

1. **S7**: wp.json:19-21 presents "Latency budget" as open, citing the P1b prereg. STATUS.md:17 says "P1b latency v2 | ABANDONED", and :23 says "H3 latency | RETIRED".
2. **E2**: sdks.json:64 says "Apache-2.0 proposed, pending the owner's decision". docs/adr/0006-licensing.md:3 says "Status: **Accepted**", and :10 says Apache-2.0 for nf-core/SDKs.
3. **L19**: rules/ct.yaml:12 has `effective_date: '2026-07-01'` and :9-11 "Signed by the Governor 24 Jun 2025". Compare reg.md:13 (same date and signing).
