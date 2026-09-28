# Somatosensory research hive: shared protocol (queen = "research-queen")

Program: bidirectional closed-loop somatosensory feedback. Intracortical microstimulation (ICMS) of S1
(areas 3b/1/2/3a) to evoke touch, pressure, texture, temperature and limb position, closed-loop with motor BCI decoding.
Binding rules: C:\Users\mariu\neuro-company\BRIEF.md (read it).

## Rules for every agent
1. Every scientific claim cites a source you actually OPENED (DOI or PMID, plus the URL you fetched). Record what you
   read: abstract only, or full text (PMC). Never invent papers, numbers or results. If unsure, write UNVERIFIED.
2. Grades: A = peer-reviewed and replicated/independently confirmed; B = single peer-reviewed study; C = preprint/theory;
   D = marketing/press.
3. WebSearch is exhausted. Use WebFetch on:
   - PubMed search: https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&retmode=json&retmax=20&term=...
   - PubMed abstracts: https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&rettype=abstract&retmode=text&id=PMID1,PMID2
   - Europe PMC: https://www.ebi.ac.uk/europepmc/webservices/rest/search?format=json&resultType=core&query=...
     (full text for OA papers: https://www.ebi.ac.uk/europepmc/webservices/rest/PMCxxxxxxx/fullTextXML)
   - Semantic Scholar: https://api.semanticscholar.org/graph/v1/paper/search?query=...&fields=title,year,externalIds,abstract
   - arXiv: http://export.arxiv.org/api/query?search_query=...
   - GitHub (repos, READMEs, raw files).
4. Computational/theoretical work only. NO protocols for human stimulation or self-experimentation. Where a result
   would need clinical testing, say "requires IRB/FDA-approved clinical study" and stop there.
   Stimulation parameters may be QUOTED from published trials as facts, never proposed as settings to apply to a person.
5. Machine: Windows, ~3 GB RAM free. Small CPU jobs only. Venv: C:\Users\mariu\neuro-company\.venv
   (python: C:\Users\mariu\neuro-company\.venv\Scripts\python.exe; numpy/scipy/matplotlib installed).
   Only agent "coder-verifier" installs packages into it and runs verification code (others may run tiny snippets).
6. Use absolute paths. Never `cd` in shared shells. Do not publish, push, sign up or contact anyone.
7. Communication (blackboard; direct agent-to-agent messaging is not available in this session):
   peers are neurologist, neurobiologist, mathematician, neuroinformatics, coder-verifier (spawned later).
   - notes\BOARD.md: append-only message board. Entry format: `- [role -> role|all] message (path if any)`.
     Re-read BOARD.md at the start and a few times during your task; answer requests addressed to you.
   - notes\facts_for_models.md: numeric facts (with citations) for models, one section per role.
   - Your FINAL ANSWER goes to the queen automatically; mid-task notes for the queen go on BOARD.md (-> queen).
   Append with Edit/small writes; never overwrite another role's content. Long handoffs: write a file under notes\ and send its path;
   ask for a one-line receipt. Keep messages short.
8. Final answer of every agent (to the queen) <= 25 lines: files written, key findings with grades, open questions.

## Folders (root C:\Users\mariu\neuro-company\research\somatosensory\)
- lit\        annotated bibliographies, one file per role (lit\<role>.md) + lit\INDEX.md (queen merges)
- notes\      handoffs, working notes
- prereg\     pre-registered verification specs (one file per test: hypothesis, model, metric, PASS/FAIL threshold,
              fixed BEFORE running code)
- code\       verification code; code\results\ (json/csv), code\figures\ (png/svg)
- theories.md, STATUS.md, whitepaper\ (queen owns these; others propose via notes\)

## Bibliography entry format
### [Grade] Short title (First author, year) - DOI / PMID
- Opened: URL fetched; abstract | full text
- Key facts (with numbers, exactly as reported):
- Relevance to program / open problem it addresses:
- Caveats (n subjects, blinding, species, replication):
