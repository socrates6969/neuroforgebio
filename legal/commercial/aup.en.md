> DRAFT – not legal advice. Must be reviewed by a Norwegian lawyer (advokat) before use.

# Acceptable Use Policy (AUP)

Version [0.1] · [DATE] · Applies to the NeuroForge Bio platform, APIs, console, model registry and the proprietary Platform/Client components ("Service"), and is incorporated into the MSA. [The open-source SDK is governed by Apache-2.0, which has no use restrictions; this AUP applies to it only when used with the Service.] Prevailing language: English [advokat choice].

Breach of this AUP may lead to removal of content, suspension (MSA § 14.3) or termination, and is excluded from the liability cap (MSA § 12.4(d) for § 10.7/§ 11 breaches). Report suspected misuse to [abuse@neuroforge.bio].

## You must not use the Service to:

### 1. Re-identify people
1.1 Attempt to re-identify, or link to an identified person, any data subject whose data is pseudonymised or de-identified, including by combining neural data with other datasets, unless the data controller has a lawful basis, the relevant ethics approval covers it, and the data subject has been informed as required.
1.2 Use neural data to uniquely identify a person (biometric identification) without an explicit lawful basis and Art. 9(2) GDPR condition (where GDPR applies) and any required opt-in under US state law.

### 2. Engage in prohibited AI practices (EU AI Act Art. 5)
Including, where Regulation (EU) 2024/1689 applies:
2.1 **inferring emotions of a natural person in the workplace or in education institutions**, except where intended for medical or safety reasons;
2.2 deploying subliminal, purposefully manipulative or deceptive techniques that materially distort behaviour and cause or are likely to cause significant harm;
2.3 biometric categorisation that infers race, political opinions, trade-union membership, religious or philosophical beliefs, sex life or sexual orientation;
2.4 any other practice listed in Art. 5 (e.g. exploiting vulnerabilities due to age, disability or social/economic situation; social scoring).
Respect use-restriction flags on registry models. [Full list per Art. 5 – verify against official text; **UNVERIFIED**.]

### 3. Process data without required consent or approvals
3.1 Upload or process personal data (especially neural or health data) without a valid lawful basis, required consent (including opt-in consent for neural data as sensitive data under US state laws such as Colorado, California, Connecticut, Montana), and required ethics/IRB/REK approval.
3.2 Process data outside the scopes recorded in the consent ledger, or disable or circumvent consent-scope checks.
3.3 Upload HIPAA PHI (no BAA is offered – PLANNED).

### 4. Sell or exploit identifiable neural data
4.1 Sell, rent or trade identifiable (including pseudonymised) neural data, or share it for advertising, profiling for marketing, credit, insurance or employment decisions.
4.2 Use neural data to make decisions about individuals' employment, education admission, insurance, credit or law-enforcement status.

### 5. Make clinical decisions
5.1 Use the Service, Outputs or registry models to diagnose, treat, monitor or make any clinical decision about an individual patient, or to control stimulation or any device in closed loop (MSA § 10.1).
5.2 Market Outputs as clinically validated when they are not.

### 6. Break the law or others' rights
6.1 Violate export control or sanctions laws, or give access to sanctioned persons or embargoed destinations (MSA § 11).
6.2 Infringe intellectual property or confidentiality rights; upload data you have no right to.
6.3 Develop weapons, surveillance of individuals without lawful authority, or interrogation/"lie-detection" uses of neural data [policy choice – advokat/owner].
6.4 Harass, discriminate or harm individuals.

### 7. Attack or abuse the Service
7.1 Probe, scan or test vulnerabilities (except under our responsible-disclosure policy), bypass authentication, rate limits or tenant isolation, or access other customers' data.
7.2 Upload malware, run crypto-mining, or place unreasonable load.
7.3 Share credentials or API keys, or give access to people who are not Authorised Users.

## Research exception
Security and privacy research on **your own tenant and data** (e.g. re-identification risk testing on your own datasets under ethics approval) is permitted if it does not affect others, and findings about the Service are reported to [security@neuroforge.bio] first.

## Changes
NeuroForge may update this AUP with [30] days' notice; material changes that reduce Customer's rights allow termination under the MSA.

## Hjemmel / Legal basis
- EU AI Act (EU) 2024/1689 Art. 5 – EUR-Lex failed to load (2026-09-26) – **UNVERIFIED**; items 2.1–2.3 as summarised in market\regulation.md §5 (artificialintelligenceact.eu, grade B, applicable from 2 Feb 2025).
- GDPR Art. 9 – via personopplysningsloven § 1 (https://lovdata.no/dokument/NL/lov/2018-06-15-38, opened 2026-09-26); Art. 9 wording **UNVERIFIED** verbatim.
- Colorado HB24-1058 (https://leg.colorado.gov/bills/hb24-1058, opened 2026-09-26): neural data = sensitive data under the Colorado Privacy Act. CA SB 1223, CT PA 25-113, MT SB 163 – per market\regulation.md, **UNVERIFIED** by this author.
- Eksportkontrolloven (https://lovdata.no/dokument/NL/lov/1987-12-18-93, opened 2026-09-26).
- Product facts: architecture\BLUEPRINT.md §8.2 (EU AI Act flag in registry), §8.3 (consent-scope enforcement), §1 out-of-scope (no diagnosis/closed-loop control).
