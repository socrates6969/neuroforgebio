# Neuro-data company — master brief (owner: Marius Carlsson, started 2026-09-26)

## Owner's plan (follow in order; STOP at every GATE for owner input)
Company: B2B Neuro-Data Analytics Platform ("picks and shovels" for BCI hardware makers): hardware-agnostic
ingest (BIDS, LSL, EEG/ECoG/microelectrode), low-latency time-series storage, automated neuro-cleaning
(ICA, filtering, artifact rejection, normalization), Neuro-AI model marketplace (motor intent, cognitive state),
SDKs (Python, C++, Unity/Unreal), compliance moat (HIPAA/BAA, AES-256, RBAC, neural-data privacy laws:
Colorado, Connecticut, Montana...), GTM: free academic tier -> seed-stage BCI hardware startups.
Audience: scientists, entrepreneurs, companies in neurology/neurotech. Focus: SOFTWARE (team strength: code + math).

STEP 1 (now): Business analyst + marketing: market research, validate/extend the blueprint, NEW ideas.
STEP 2 (now): Design/UI agent researches competitor + similar sites; 3D graphics agent makes graphics;
        deliver 6 UNIQUE website design options that still resemble the sector.  -> GATE A: owner picks a design.
STEP R (now, parallel): Research swarm on "Bidirectional closed-loop somatosensory feedback" (ICMS of
        postcentral gyrus / S1 to evoke realistic touch, pressure, temperature, proprioception). Neurologist,
        neurobiologist, mathematician, neuroinformatics expert, coder-verifier. Read papers, theorize,
        verify in software (own code or existing validated tools), iterate until a workable, verified
        solution; produce whitepaper(s) for the website's Whitepaper page (interactive visuals).
STEP 3 (after GATE A): Code architect: complete enterprise architecture + step-by-step build guide
        (website, platform, API, SDKs, DBs, infra, compliance).          -> GATE B: owner approves.
STEP 4 (after GATE B): Build org as agent swarms under a hive-mind queen (hybrid: everyone reports to the
        queen and can also message each other), CEO role, team lead, architects, frontend, backend,
        designers/3D artists, marketing team, scientists (mathematician, neurologist, neurobiologist,
        neuroinformatics). Plus investor pitch, marketing plan + templates, pricing, 10-15y scaling plan.

## Rules
- Evidence: every factual/market/scientific claim cites a source actually opened (DOI/PMID/arXiv/URL).
  Grades: A peer-reviewed/replicated, B single study/reputable press, C preprint/theory, D marketing.
  Estimates labeled ESTIMATE with method. Never invent numbers, papers, customers or results.
- Science safety: research is computational/theoretical (models, published datasets, simulation).
  No protocols for self-experimentation or human stimulation; flag that clinical work needs IRB/FDA.
  No medical claims in marketing copy.
- WebSearch budget of this session is exhausted: use WebFetch on known URLs and search APIs:
  PubMed E-utilities (https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=...),
  Europe PMC REST, arXiv API (http://export.arxiv.org/api/query?search_query=...),
  Semantic Scholar API (https://api.semanticscholar.org/graph/v1/paper/search?query=...), GitHub.
- Never publish, push, sign up, buy, or contact anyone. Machine: Windows, ~3 GB free RAM ->
  no heavy builds; Python scripts OK (C:\Users\mariu\AppData\Local\Programs\Python\Python312\python.exe);
  create a venv under neuro-company\.venv for science code; CARGO_BUILD_JOBS=1 if Rust.
- Folders: market\, design\, research\somatosensory\, (later) architecture\, build\, investor\.

## GATE A decision (owner, 2026-09-26)
Owner picked BOTH option 3 (Neural cosmos, 3D) and option 1 (Clinical precision): "create 1 for each without
writing software twice". So: ONE codebase (shared content, components, logic, API, SDK), TWO visual themes
("clinical" = option 1, "cosmos" = option 3). The three.js brain is an optional hero module loaded only by the
cosmos theme. Company name still undecided: keep "NeuroForge (working name)".
Copy fixes to apply in both: status labels say "designed/planned/roadmap", never "built-in"/"live";
replace "automated neuro-cleaning" with reproducible, comparable pipelines (Kessler 2025, Huang 2025).

## Name decision (owner, 2026-09-26)
Company name: NeuroForge (owner chose "the English one" over Nordlyd/Nordlys). Pending the naming agent's clash
check (market\names.md); until then write "NeuroForge" without "(working name)" only in internal docs.

## GATE B decision (owner, 2026-09-26)
Name: **NeuroForge Bio** (owner). Blueprint: owner accepted all architect recommendations
("take whatever blueprint you want"), i.e. D1 yes (reposition to reproducible/comparable pipelines +
neural-data governance), D3 clinical canonical + cosmos secondary (build-time theme), D4 AWS + static host,
D5 ledger in parallel, D6 Apache-2.0 SDK/core later + proprietary platform (repo stays all-rights-reserved
until SDK code exists), D7 Rust core, D8 one heading set, D9 self-hosted fonts / no trackers, D10 experts
as recommended. Owner-gated (never done by agents): domains, cloud accounts, spending, publishing site or
packages, contacting counsel/anyone.
STEP 4 starts: build M0+M1 (website, both themes), business pack (pitch, marketing, pricing, 10-15y plan),
research continues.
