> DRAFT – not legal advice. Must be reviewed by a Norwegian lawyer (advokat) before use.

# PLANNED – NOT OFFERED YET
# Business Associate Agreement (US HIPAA) – template

**Status: PLANNED – not offered yet.** NeuroForge Bio does not currently sign BAAs and customers must not upload Protected Health Information (PHI) (MSA § 10.6). Preconditions before this template may be used (architecture\BLUEPRINT.md §8.5): (1) NeuroForge has signed its cloud provider's BAA and restricts PHI tenants to BAA-covered services; (2) HIPAA Security Rule risk analysis, policies, incident response and workforce training are in place; (3) **US HIPAA counsel** (not only a Norwegian advokat) has reviewed this template. NeuroForge does not claim to be "HIPAA-compliant".
Prevailing language: English. Governing law: [US federal law (HIPAA) + [State] law for contract matters – US counsel to decide; the MSA's Norwegian-law clause does not displace HIPAA].

**Parties:** [Covered Entity or upstream Business Associate] ("**Covered Entity**") and [NeuroForge Bio AS / US affiliate] ("**Business Associate**"). Effective [date]. Supplements the MSA; prevails over it for PHI.

## 1. Definitions
Terms used but not defined (Breach, Designated Record Set, Individual, PHI, Required by Law, Secretary, Security Incident, Subcontractor, Unsecured PHI, etc.) have the meanings in 45 CFR Parts 160 and 164 (the HIPAA Rules).

## 2. Obligations of Business Associate (45 CFR 164.504(e)(2)(ii))
Business Associate shall:
(a) not use or disclose PHI other than as permitted or required by this Agreement or as Required by Law;
(b) use appropriate safeguards and comply with Subpart C of 45 CFR Part 164 (Security Rule) for electronic PHI, to prevent use or disclosure other than as provided here;
(c) report to Covered Entity any use or disclosure not provided for by this Agreement of which it becomes aware, including Breaches of Unsecured PHI as required by 45 CFR 164.410, and any Security Incident of which it becomes aware, within [5] business days of discovery [Breach of Unsecured PHI: without unreasonable delay and no later than [10] calendar days after discovery (proposal, well inside the regulatory outer limit, believed to be 60 calendar days under 164.410(b) – **UNVERIFIED**; US counsel to set); initial notice of a confirmed Security Incident within [24] hours, consistent with MSA Schedule 2 S7]; [unsuccessful attempts (pings, port scans) are hereby reported in aggregate and need no further notice];
(d) in accordance with 45 CFR 164.502(e)(1)(ii) and 164.308(b)(2), ensure that any Subcontractors that create, receive, maintain or transmit PHI on its behalf agree in writing to the same restrictions, conditions and requirements;
(e) make PHI in a Designated Record Set available to Covered Entity within [15] days as necessary to satisfy 45 CFR 164.524 (access);
(f) make amendments to PHI in a Designated Record Set as directed by Covered Entity under 45 CFR 164.526;
(g) maintain and make available the information required to provide an accounting of disclosures under 45 CFR 164.528;
(h) to the extent it carries out Covered Entity's obligations under Subpart E of 45 CFR Part 164 (Privacy Rule), comply with the requirements of Subpart E that apply to Covered Entity in performing them;
(i) make its internal practices, books and records available to the Secretary for determining compliance with the HIPAA Rules;
(j) request, use and disclose only the minimum necessary PHI.

## 3. Permitted uses and disclosures
3.1 Only to perform the Services in the MSA for Covered Entity.
3.2 [Optional:] for Business Associate's proper management and administration or legal responsibilities, as permitted by 45 CFR 164.504(e)(4).
3.3 **No de-identification for own use, no data aggregation, no sale of PHI, no model training** on PHI (consistent with MSA § 4.3) unless a separate written agreement permits it.
3.4 Business Associate shall not use or disclose PHI in a manner that would violate Subpart E if done by Covered Entity.

## 4. Obligations of Covered Entity
Notify Business Associate of limitations in its notice of privacy practices, changes in or revocation of an Individual's permission, and any agreed restriction under 45 CFR 164.522, to the extent they affect Business Associate's use or disclosure. Not request any use or disclosure impermissible under Subpart E.

## 5. Term and termination
5.1 Term: from Effective Date until the MSA ends and all PHI is returned or destroyed.
5.2 Covered Entity may terminate this Agreement [and the MSA] if Business Associate has violated a material term and has not cured it within [30] days (45 CFR 164.504(e)(2)(iii)).
5.3 **On termination**, Business Associate shall return or destroy all PHI it still maintains in any form and retain no copies; where return or destruction is infeasible, extend these protections to that PHI and limit further uses and disclosures to the purposes that make return or destruction infeasible. [Crypto-shredding of backups per MSA Schedule 2 S2 – US counsel to confirm it qualifies as destruction.] **Limitation:** PHI or Outputs already exported by Covered Entity outside the Service cannot be recalled by Business Associate; trained models are retrained, not "unlearned" (DPA § 11.2).

## 6. Miscellaneous
References to HIPAA Rules mean the section as in effect or amended. The Parties will amend this Agreement as needed to comply with changes in the HIPAA Rules. Ambiguity is resolved to permit compliance with the HIPAA Rules. Liability: MSA § 12 [US counsel to consider a separate cap].

## Hjemmel / Legal basis
- 45 CFR 164.504(e) (BAA content), 164.502(e), 164.308(b), 164.410, 164.522–164.528 – drafted from drafter knowledge of the HHS sample BAA provisions. **UNVERIFIED**: https://www.hhs.gov/hipaa/for-professionals/covered-entities/sample-business-associate-agreement-provisions/index.html returned **HTTP 403** (2026-09-26); eCFR (https://www.ecfr.gov/.../section-164.504) redirected to a bot-check page; web.archive.org blocked.
- HIPAA scope (covered entities + business associates only): market\regulation.md §3 (hhs.gov via Wayback, grade A, opened by the market team, not by this author).
- Product facts: architecture\BLUEPRINT.md §8.5 (BAA planned; preconditions), DECISIONS.md D4 (AWS BAA path).
