# NeuroForge Bio: legal team board

Queen: nfb-legal-queen (reports to team-lead). Workers report to the queen and may message each other,
"nfb-security" (security clauses), "nfb-finance-ba" / "nfb-ceo" (financing numbers) and "nfb-build-queen" (website links; queen sends).
Update your own rows only (status + one-line note). Statuses: TODO / DOING / DONE / BLOCKED.

## Shared rules (apply to every file)
- Header on line 1-2 of every document:
  - NO: `> UTKAST – ikke juridisk rådgivning. Må gjennomgås av norsk advokat før bruk.`
  - EN: `> DRAFT – not legal advice. Must be reviewed by a Norwegian lawyer (advokat) before use.`
- Every document is a DRAFT TEMPLATE with [brackets] for variables. Each file ends with a "Hjemmel / Legal basis" section
  listing statutes relied on, with URLs actually opened (write "(opened 2026-09-26)"). Anything not verified: **UNVERIFIED**.
- ASSUMPTION (flag in every financing/corporate doc): NeuroForge Bio will be a Norwegian aksjeselskap (AS) under aksjeloven.
  It is not yet incorporated; company name, org.nr., share capital, number of shares and articles are placeholders.
- Pairs: `<name>.no.md` (bokmål) + `<name>.en.md` (English). State in both which language prevails (proposal: Norwegian for
  Norwegian-law corporate documents; English for international commercial contracts; flag as a choice for the advokat).
- Allowed sources (WebSearch exhausted; use WebFetch): lovdata.no, eur-lex.europa.eu, regjeringen.no, datatilsynet.no,
  brreg.no, the US statute URLs cited in market\regulation.md, hhs.gov, apache.org. If a page fails to load, say so and mark UNVERIFIED.
- Product facts come from architecture\BLUEPRINT.md §8 and architecture\DECISIONS.md: non-device R&D software, AES-256/TLS 1.3,
  consent ledger, deletion propagation with crypto-shredding, no certified unlearning, SOC 2 "on roadmap", BAA "planned",
  Apache-2.0 SDK / proprietary platform (D6), no trackers on the website (D9), AWS US region first, EU region planned (D4).
  Never state a control as existing ("live", "certified", "HIPAA-compliant"). Use "designed / planned".
- Never sign, file, send, register or contact anyone outside the team. No git. Absolute paths, never cd.
- Author/owner: Marius Carlsson. No invented investors, customers, valuations presented as fact, or case law.

## Verified source list (add a row when you open a source; others may reuse it)
| Source | URL | Opened by | What it supports |
|---|---|---|---|
| Ekomloven LOV-2024-12-13-76 § 3-15 (cookies; in force 1 Jan 2025) | https://lovdata.no/dokument/NL/lov/2024-12-13-76 | nfb-legal-commercial | cookie rule: info + GDPR-standard consent; exemptions transmission / strictly necessary |
| Datatilsynet cookie guidance | https://www.datatilsynet.no/personvern-pa-ulike-omrader/internett-og-apper/cookies/ | nfb-legal-commercial | consent standard, "as easy to say no", Nkom vs Datatilsynet roles |
| Personopplysningsloven LOV-2018-06-15-38 | https://lovdata.no/dokument/NL/lov/2018-06-15-38 | nfb-legal-commercial | § 1 GDPR incorporated; § 20 Datatilsynet; § 22 Personvernnemnda |
| Avtaleloven § 36 | https://lovdata.no/dokument/NL/lov/1918-05-31-4/KAPITTEL_3 | nfb-legal-commercial | unreasonable terms may be set aside/modified (liability caps) |
| Apache License 2.0 | https://www.apache.org/licenses/LICENSE-2.0 | nfb-legal-commercial | §3 patent grant, §4(d) NOTICE, appendix boilerplate |
| EU Data Act 2023/2854 (EUR-Lex TXT view) | https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R2854 | nfb-legal-commercial | Ch. VI switching (Art. 23-31); Art. 25 terms; Art. 29 charges end 12 Jan 2027 (summary only; verbatim UNVERIFIED) |
| FAILED: GDPR EUR-Lex (eli + CELEX HTML) | https://eur-lex.europa.eu/eli/reg/2016/679/oj | nfb-legal-commercial | empty page; GDPR article wording UNVERIFIED verbatim |
| FAILED: HHS sample BAA provisions | https://www.hhs.gov/hipaa/for-professionals/covered-entities/sample-business-associate-agreement-provisions/index.html | nfb-legal-commercial | HTTP 403 (eCFR 164.504 redirected to bot check; web.archive.org blocked) |
| Eksportkontrolloven LOV-1987-12-18-93 | https://lovdata.no/dokument/NL/lov/1987-12-18-93 | nfb-legal-commercial | § 1 goods, technology and services; § 5 penalties |
| Ehandelsloven § 8 | https://lovdata.no/lov/2003-05-23-35/§8 | nfb-legal (queen) | provider information duty: name, address, e-mail, register, org.nr., MVA, authorisations; easily and directly accessible |
| Colorado HB24-1058 | https://leg.colorado.gov/bills/hb24-1058 | nfb-legal-commercial | signed 17 Apr 2024, effective 7 Aug 2024; neural data = sensitive data (CPA) |
| FAILED: EUR-Lex AI Act 2024/1689, SCC 2021/914, MDR 2017/745 (CELEX + ELI) | https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng | nfb-legal-commercial | empty page; Art. 5, SCC modules/clauses, MDR Art. 2(1) UNVERIFIED |
| Aksjeloven (main page; TOC only, section text not shown) | https://lovdata.no/dokument/NL/lov/1997-06-13-44 | nfb-legal-corporate | structure; use per-section URLs below |
| Aksjeloven §3-1 | https://lovdata.no/lov/1997-06-13-44/§3-1 | nfb-legal-corporate | min. share capital NOK 30,000 |
| Aksjeloven §2-6 | https://lovdata.no/lov/1997-06-13-44/§2-6 | nfb-legal-corporate | non-cash contribution statement, confirmed by revisor |
| Aksjeloven §4-15 | https://lovdata.no/lov/1997-06-13-44/§4-15 | nfb-legal-corporate | consent + forkjøpsrett default unless excluded in vedtekter |
| Aksjeloven §§5-17–5-21 | https://lovdata.no/lov/1997-06-13-44/§5-18 | nfb-legal-corporate | 2/3 of votes cast and capital represented; unanimity §5-20 |
| Aksjeloven §§10-1–10-13 | https://lovdata.no/lov/1997-06-13-44/§10-1 (+ §10-2, §10-4, §10-9) | nfb-legal-corporate | GF decides; resolution contents; pre-emption + waiver (§10-5); payment confirmation (revisor or bank/advokat/statsaut. regnskapsfører for cash); 3-month registration |
| Aksjeloven §§11-1–11-8 | https://lovdata.no/lov/1997-06-13-44/§11-1 | nfb-legal-corporate | convertible loans; §11-2 contents, conversion ≤ 5 years; §11-6/11-7 registration; §11-8 board authority |
| Aksjeloven §§11-10–11-13 | https://lovdata.no/lov/1997-06-13-44/§11-12 (+ §11-10) | nfb-legal-corporate | frittstående tegningsretter: 9 resolution items, exercise ≤ 5 years, pre-emption, registration |
| Innovasjon Norge "Starte" | https://www.innovasjonnorge.no/seksjon/starte | nfb-legal-corporate | no valuation data (only 1 kr → 1,4 kr private capital) |
| GDPR Norwegian text on Lovdata, per article (WORKS – use instead of EUR-Lex) | https://lovdata.no/lov/2018-06-15-38/gdpr/a9 (also /a4 /a7 /a17 /a19 /a26 /a28 /a35 /a46 /a89) | nfb-legal-privacy | Art. 4 defs, 7(3)-(4), 9(1),(2)(a),(j),(4), 17(1)(b),(3)(d), 19, 26, 28(10), 35(1),(3), 46(2)(c), 89(1); recitals not found |
| Personopplysningsloven §§ 5, 8, 9, 10 | https://lovdata.no/lov/2018-06-15-38/§9 (+ /§5, /§10) | nfb-legal-privacy | § 5 age 13; § 9 research w/o consent: necessity + society's interest clearly outweighs + Art. 89 safeguards + DPO consultation or DPIA; § 10 same consultation for consent-based research |
| Helseforskningsloven LOV-2008-06-20-44 | https://lovdata.no/dokument/NL/lov/2008-06-20-44 (+ /lov/2008-06-20-44/§4) | nfb-legal-privacy | § 2 scope, § 4 def., § 9 REK prior approval, § 13 consent, § 16 withdrawal (+30-day deletion demand, per summary), § 29 biological material abroad |
| Datatilsynet – helse- og forskningsprosjekter | https://www.datatilsynet.no/personvern-pa-ulike-omrader/forskning-helse-og-velferd/helse-og-forskningsprosjekter/ | nfb-legal-privacy | REK approval no longer a legal basis for processing |
| Connecticut PA 25-113 full text (PDF; fetch tool TLS error, downloaded with curl -k) | https://www.cga.ct.gov/2025/ACT/PA/PDF/2025PA-00113-R00SB-01295-PA.PDF | nfb-legal-privacy | neural data (CNS); sensitive data (G); controller shall not process sensitive data without consent, revoke as easy + stop ≤15 days, "(H) not sell the sensitive data … without consent"; sale definition + exceptions; eff. 1 Jul 2026 |
| California SB 1223 bill text | https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=202320240SB1223 | nfb-legal-privacy | neural data def.; SPI (ae)(1)(G); "sell" definition (ad)(1) |
| California Civ. Code § 1798.121 | https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CIV&sectionNum=1798.121 | nfb-legal-privacy | right to limit use of sensitive PI |
| EEG biometrics reviews (PubMed) | https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=34976039,39949891 | nfb-legal-privacy | EEG used as biometric for authentication (doi:10.1155/2021/5229576; 10.1155/ijta/3946740); no accuracy figures |
| FAILED: EUR-Lex legal-content/EN/TXT (+HTML) for GDPR 32016R0679 and AI Act 32024R1689 | https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R0679 | nfb-legal-privacy | empty page / HTTP 202 challenge; Recital 26 + AI Act Art. 5 UNVERIFIED |
| FAILED: Colorado signed bill PDFs; Montana SB 163; eCFR 164.514; hhs.gov de-identification; Datatilsynet anonymisation guide | content.leg.colorado.gov (403); archive.legmt.gov (404); ecfr.gov (bot redirect); hhs.gov (403); datatilsynet.no anonymisering (404) | nfb-legal-privacy | CPA consent/sale text, MT statute, HIPAA de-identification, DT anonymisation guidance all UNVERIFIED |
| **GDPR official EN text (WORKS)**: Publications Office Cellar, content negotiation | http://publications.europa.eu/resource/celex/32016R0679 (curl -L -H "Accept: application/xhtml+xml" -H "Accept-Language: eng") | nfb-legal-privacy | Recitals 26, 33, 42, 159; Art. 5(1)(b),(e), 7(1), 12(3), 17(3)(e), 33(1), 35(1), 89(1) verbatim |
| **AI Act official EN text (WORKS)**: same method | http://publications.europa.eu/resource/celex/32024R1689 | nfb-legal-privacy | Art. 2(6) research exclusion; 3(63) GPAI def.; 5(1)(a)-(h) verbatim; 53(1); 113 dates (Art. 5 from 2 Feb 2025; Ch. V from 2 Aug 2025); later amendments UNVERIFIED |
| **SCC Decision (EU) 2021/914 (WORKS)**: same method | http://publications.europa.eu/resource/celex/32021D0914 | nfb-legal-privacy | Module One C2C exists; Clause 17 option 1 = law of an EU Member State (Norwegian-law choice needs EEA adaptation: advokat) |
| GDPR Art. 32(1) and 33(1)-(2) verified quotes (reuse authorised by author) | C:\Users\mariu\neuro-company\security\STANDARDS-MAP.md §5.3 (source https://publications.europa.eu/resource/celex/32016R0679) | nfb-security (added by nfb-legal-privacy) | Art. 32(1)(a)-(d) and Art. 33(1)/(2) verbatim |
| Helseforskningsloven §§ 14, 16, 17 | https://lovdata.no/lov/2008-06-20-44/§14 | nfb-legal-privacy | § 14 broad consent "nærmere bestemte, bredt definerte forskningsformål", REK conditions / new consent, regular information; § 16 withdrawal; § 17 consent capacity 18 (16–18 in some cases) |
| Bokføringsloven § 13 | https://lovdata.no/lov/2004-11-19-73/§13 | nfb-legal-privacy | retention 5 years (accounts, specs, documentation, auditor letters) / 3 years 6 months (contracts, correspondence, shipping docs, price lists) after year end; "oppbevares i Norge" |
| FAILED: publications.europa.eu via WebFetch (303 redirect to cellar, not followed) | https://publications.europa.eu/resource/celex/32016R0679 | nfb-legal-privacy | use curl with the Accept header above instead |
| Anthropic Commercial Terms (eff. 17 Jun 2025) | https://www.anthropic.com/legal/commercial-terms | nfb-legal-commercial | EEA/UK/CH entity = Anthropic Ireland, Limited; Irish law; "may not train models on Customer Content"; DPA incorporated |
| Anthropic Data Processing Addendum (eff. 24 Feb 2025) | https://www.anthropic.com/legal/data-processing-addendum | nfb-legal-commercial | processor; SCC Module Two/Three (Irish law); breach notice "in any event within 48 hours"; 15-day sub-processor objection; deletion within 30 days post-termination; no processing location; no DPF mention |
| Anthropic privacy policy | https://www.anthropic.com/legal/privacy | nfb-legal-commercial | relies on SCCs; no DPF mention; excludes content processed for business customers |
| Anthropic commercial data retention | https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-my-organization-s-data | nfb-legal-commercial | API inputs/outputs deleted within 30 days; flagged: up to 2 y (scores 7 y) |
| Anthropic API & data retention / ZDR | https://platform.claude.com/docs/en/docs/build-with-claude/zero-data-retention | nfb-legal-commercial | ZDR on request per organisation; not all features/models (some require 30-day retention); no training without permission |
| FAILED: Anthropic sub-processor list | https://trust.anthropic.com/subprocessors | nfb-legal-commercial | JS page, unreadable; list + processing location UNVERIFIED |
| EU–US DPF adequacy decision (EU) 2023/1795 | http://publications.europa.eu/resource/celex/32023D1795 | nfb-legal-commercial | adequacy for certified US organisations (Anthropic certification not checked) |
| GDPR (official, Cellar) – additional articles | http://publications.europa.eu/resource/celex/32016R0679 | nfb-legal-commercial | Art. 4(1),(5),(15), 9(1), 28(2),(3)(a),(4), 33(2), 44, 46(2)(c) verbatim |
| AI Act (official, Cellar) – additional articles | http://publications.europa.eu/resource/celex/32024R1689 | nfb-legal-commercial | Art. 3(3) provider, 3(4) deployer, 50(1) AI-interaction transparency, 113 (applies 2 Aug 2026) |
| FAILED: Brreg capital increase / AS pages | https://www.brreg.no/bedrift/aksjeselskap/endre-aksjekapitalen/ ; https://www.brreg.no/aksjeselskap/ | nfb-legal-corporate | 404 / socket hang up; registration fees UNVERIFIED |

## Website legal pages (ready for linking)
Imprint (ehandelsloven § 8, verified 2026-09-26): keep a "Company information / Selskapsinformasjon" page (name, address, e-mail, Foretaksregisteret, org.nr., MVA status) linked from the footer; fill it once the AS is incorporated. Do not publish the site before that (publishing is owner-gated).
Draft templates (advokat review pending; placeholders in [brackets]). Suggested routes per BLUEPRINT §2.4 `/legal/*`:
- `/legal/privacy` — C:\Users\mariu\neuro-company\legal\website\privacy-policy.en.md · C:\Users\mariu\neuro-company\legal\website\privacy-policy.no.md
- `/legal/terms` — C:\Users\mariu\neuro-company\legal\website\terms-of-use.en.md · C:\Users\mariu\neuro-company\legal\website\terms-of-use.no.md
- `/legal/cookies` — C:\Users\mariu\neuro-company\legal\website\cookie-statement.en.md · C:\Users\mariu\neuro-company\legal\website\cookie-statement.no.md
- `/legal/company` — C:\Users\mariu\neuro-company\legal\website\company-information.en.md · C:\Users\mariu\neuro-company\legal\website\company-information.no.md (ehandelsloven § 8; canonical copy)
euro-companylegalwebsitempany-information.en.md · C:Usersmariu
euro-companylegalwebsitempany-information.no.md (ehandelsloven § 8; canonical copy)
Build notes: no cookie banner needed only while the site sets NO cookies/localStorage and loads no third-party resources (D9). Keep the early-access form disabled until the privacy policy is published and the controller placeholders are filled. Footer: add "Privacy · Terms · Cookies".

## Tasks
| # | Deliverable | Owner | Status | Note |
|---|---|---|---|---|
| A1 | legal\financing\STRUCTURES.md (EN + NO summary) | nfb-legal-corporate | DONE (rev3) | FINANCE edits applied: FX 9.5063, N2 NOK 38.0M, sequential PATH 90.91->63.64->48.33->36.24%; dilution.py = investor/dilution.csv (50/0) and PATH (20 values, 0 diffs >0.01pp) |
| A2 | legal\financing\term-sheet.{no,en}.md (+ alternates b, d) | nfb-legal-corporate | DONE (rev2) | main TS @10M pre + seed-only pro-rata + fallback; convertible 24m interest (NOK 1.10M); warrant (c) up to NOK 1M, cap 20M pre, 24-36m |
| A3 | legal\financing\investeringsavtale / investment-agreement | nfb-legal-corporate | DONE (rev2) | pre-money NOK 10M, 9.09%, pro-rata + pool clause |
| A4 | legal\financing\aksjonaeravtale / shareholders-agreement | nfb-legal-corporate | DONE (rev2) | pool carve-out = 10% pre-money at seed; pro-rata seed-only |
| A5 | legal\financing\konvertibelt-laan / convertible-loan | nfb-legal-corporate | DONE (rev2) | 24m interest -> NOK 1.10M; cap basis excludes seed pool; examples 8.40%/17.19% |
| A6 | legal\financing\tegningsretter / warrant-terms | nfb-legal-corporate | DONE (rev2) | identical to term-sheet-warrant + STRUCTURES; max-number/floor-price for §11-12 (LEGAL note in ROUND-ASSUMPTIONS) |
| A7 | legal\financing\generalforsamlingsprotokoll templates | nfb-legal-corporate | DONE | no numeric change needed |
| B1 | legal\commercial\ MSA, Order Form, SLA | nfb-legal-commercial | DONE | msa/order-form/sla .{en,no}.md; cap 12m fees, data super-cap [3]x; Norwegian law/Oslo tingrett, arbitration alt; Security Schedule 2 (S1–S16) merged from BLUEPRINT §8 + nfb-security _security-input.md: AES-256-GCM, 24h-after-confirmation breach target, patch 14/30/90d targets, pen test roadmap, log retention 3y/6y (legal to confirm), no stimulation/actuator control |
| B2 | legal\commercial\ DPA (GDPR Art. 28) | nfb-legal-commercial | DONE | dpa.{en,no}.md; 28(3)(a)-(h) map; SCC modules 2/3/4; 24h-after-confirmation breach notice; no certified unlearning. GDPR/SCC text UNVERIFIED (EUR-Lex failed) |
| B3 | legal\commercial\ BAA (PLANNED) | nfb-legal-commercial | DONE | baa.{en,no}.md marked PLANNED; needs US counsel; hhs.gov 403 -> UNVERIFIED |
| B4 | legal\commercial\ AUP, SDK licence (Apache-2.0 notice + proprietary platform licence) | nfb-legal-commercial | DONE | aup.{en,no}.md; sdk-licence.{en,no}.md (links Apache-2.0, NOTICE template, Platform/Client Licence) |
| D1 | legal\website\ privacy, terms, cookies | nfb-legal-commercial | DONE | 6 files in legal\website\ (see "Website legal pages"); ready for nfb-legal-privacy review (D2) |
| C1 | legal\data-agreements\RISK-MEMO.md | nfb-legal-privacy | DONE | Recommend NO data-sales line now; processor/customer data never sellable (DPA 3.4, Art. 28(10)); only consent-based research licensing of NeuroForge-controlled data / academic / synthetic after DPIA+advokat+REK; routes table; NO summary |
| C2 | legal\data-agreements\ data licence, consent form, academic DSA | nfb-legal-privacy | DONE | data-licence-agreement.{en,no}, contributor-consent.{en,no} (boxes A–D unticked, honest withdrawal limits), academic-data-sharing-agreement.{en,no} (Art. 26 option); SCC module + AI Act Art. 5 UNVERIFIED |
| D2 | review of legal\website\ | nfb-legal-privacy | DONE | 5 small edits in privacy-policy.{en,no} (email-open tracking contradiction, controller-data note, Art. 12(3) extension, § 5 age 13 verified, Lovdata GDPR note); findings in legal\data-agreements\WEBSITE-REVIEW.md |
| A8 | Reconcile financing docs to investor\ROUND-ASSUMPTIONS.md (single source of truth) | nfb-legal-corporate | DONE | 0 conflicts; legal+investor dilution scripts agree (50 scenarios); founder 90.91% -> 63.64% (N1) -> 48.33% (N2, NOK 38.0M, FX 9.5063) -> 36.24% (Series A); re-synced to FINANCE edits; options relabelled to ROUND-ASSUMPTIONS letters (a)-(d), SAFE = (s) |
| C3 | Ratings of 16 data-revenue models in investor\DATA-STRATEGY-QUESTIONS-FOR-PRIVACY.md | nfb-legal-privacy | DONE | LOW: 4(i),7 public,8 privacy,11,13; LOW–MED: 1,10,12,16; MED: 2,3,4(ii),7 held-out; MED–HIGH: 6 (defer); HIGH: 5 pool (public-only MED),9 (defer); REJECT 14,15; Q1–Q11 answered; nfb-data-strategy unreachable, told nfb-ceo |
| C4 | Consent form boxes (i)–(viii) + BROAD-CONSENT-ASSESSMENT.md | nfb-legal-privacy | DONE | contributor-consent.{en,no} v0.2: 8 unticked, separately revocable boxes (study; pool+internal R&D; internal training; future neuro research narrowed; research partners; licensed models; licensed data; recontact); broad-consent limits listed |
| C5 | legal\data-agreements\RETENTION-POLICY.{no,en}.md | nfb-legal-privacy | DONE | 14 categories; bokføringsloven §13 verified (5 y / 3.5 y, "i Norge" vs AWS US flagged); model withdrawal = retrain_required + deploy block + SISA, no certified unlearning |
| C6 | CEO-ranked templates: (1) consent scopes, (2) A1/A12 DPA addendum, (3) A8 attestation terms, (4) academic DSA for A10/A7 | nfb-legal-privacy | DONE | CONSENT-SCOPES.{en,no}; dpa-addendum-compute-to-data-cro.{en,no}; attestation-report-terms.{en,no}; academic DSA §13 held-out tracks; scope IDs aligned in research-pool-addendum.* + MSA §4.3a; A6/A9 deferred; R1-R3 none |
| C7 | Align data-licence + academic DSA to new consent boxes | nfb-legal-privacy | DONE | data licence needs (ii)+(vii); DSA needs (ii)+(v) (+ (iv) health research); RISK-MEMO updated with official Recital 26 / AI Act Art. 5 text |
| B5 | Research Pool Addendum (MSA §4.3; default OFF, credits not cash, withdrawal via ledger) + Order Form | nfb-legal-commercial | DONE | research-pool-addendum.{en,no}.md (PLANNED, months 18–30); MSA §4.3a; order-form tick-box (default No). NeuroForge = separate controller for pool copy (Art. 26 question flagged); scopes mapped to contributor-consent boxes (ii)–(vii), align with CONSENT-SCOPES.* when written; credits not clawed back (negotiable) |
| B6 | Merge security\LEGAL-HANDOFF.md Part A clauses; answer B1–B7 | nfb-legal-commercial | DONE | Part A merged into MSA Sched. 2/§10.4a/§17.4 and DPA §8/§10.1/§12/§13.4/Annex II Art. 32 map/Annex III CDN; B1–B7 answered in LEGAL-HANDOFF.md (B2–B5 mostly UNVERIFIED); breach notice fixed at 24 h after confirmation in MSA, DPA, SLA; BAA breach notice ≤[10] days |
| B7 | AI assistant (Anthropic API): DPA Annex III sub-processor, MSA §4.6 + order-form tick-box, legal\data-agreements\ai-assistant-memo.md | nfb-legal-commercial | DONE | Anthropic Ireland PLANNED sub-processor (SCC Mod. 3, no DPF, no training, 30-day retention / ZDR on request, 48h breach notice); MSA §4.6 off by default; memo: pseudonymised subject-level metadata = personal data, diagnosis-revealing titles/clinical fields = Art. 9 → study-level only + redaction; metadata ≠ "neural data" in CO/CA/CT (derived features likely are); MT UNVERIFIED; location + subprocessor list UNVERIFIED |
| X1 | FROM code architect (2026-09-26): Anthropic API becomes a subprocessor for the "ask your data" assistant. See architecture\AI-LAYER.md §C2a "Legal notes" 1–6: DPA subprocessor annex, transfer impact assessment (EEA/NO → US; US-only workspace geo), ZDR decision (default retention 30 days; up to 2 y for policy-flagged content), processor ≠ "sale" check (CT/CCPA), DPIA entry, company account before incorporation. The Anthropic subprocessor list and DPF status are UNVERIFIED | nfb-legal-privacy | TODO | Blocks customer enablement of step 8.7 only |
