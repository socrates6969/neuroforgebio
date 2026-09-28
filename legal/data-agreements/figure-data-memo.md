> DRAFT – not legal advice. Must be reviewed by a Norwegian lawyer (advokat) before use.

# Memo: data digitised from Greenspon et al. 2025, in the private repo and in an Apache-2.0 release

Prepared by nfb-legal, 2026-09-26, for team-lead. ASSUMPTION: NeuroForge Bio is a Norwegian AS (not yet incorporated), which makes it a commercial actor.

## Bottom line
1. **Private repo: yes, keep it**, as internal test data with attribution. Risk is **low**, but see caveat A. Tidy the participant fields as in step 4.
2. **Open-source redistribution under Apache-2.0: not as-is.** Remove the Greenspon-derived files from any public package, including the package-data files in `nf_channel_estimator/reference_data/`, which would ship inside the wheel. Replace them with (a) a fetch-and-digitise script that users run against the open-access article themselves, or (b) synthetic fixtures with the same shape. Or (c) get written permission from the authors or rights holder; contacting them is an owner action. Reason: the article's licence is **CC BY-NC-ND 4.0**, and Apache-2.0 permits commercial use and modification. If any part of the extracted material is protected, the two licences are incompatible.

## What was checked
- **Article:** Greenspon et al., *Nat Biomed Eng* 9:935 (2025), doi:10.1038/s41551-024-01299-z, PMC12176618.
- **Licence (verified).** Europe PMC metadata says `license: cc by-nc-nd`. The full-text XML licence statement reads: "licensed under a Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International License … You do not have permission under this licence to share adapted material derived from this article or parts of it."
- **The paper's own data (verified).** "The de-identified data … are available from the data archive BRAIN Initiative [DABI, project GU5A5IO8LRXE] … Owing to participant privacy, the data are available under restricted access."
- **What we vendor.** I inspected `services/workers/steps/channel_estimator/`:
  - `tests/golden/*`: the digitisation report and a per-electrode projected-field CSV;
  - `nf_channel_estimator/reference_data/*.json`: **shipped as package data**; holds segment geometry (centroids in figure pixels, areas) plus per-electrode dominant segments;
  - `examples/greenspon2025_{C1,P2,P3}.pf-map.json`.
  All of them carry the participant codes C1/P2/P3.

## Analysis
**A. Copyright in the figure vs facts extracted from it.** Measured values (which hand segment an electrode's projected field covers) are facts, and facts as such are not protected by copyright (general principle; Norwegian case law not checked, **UNVERIFIED**). The figure's drawing *is* protected. Our `reference_data` holds hand-segment geometry in figure pixel coordinates (`cx`, `cy`, `area_mm2`), so that part is closer to a copy of the drawing than to bare facts. This is the weakest spot for an open release.

**B. Database right.** Under åndsverkloven § 24, the maker of a database whose gathering, verification or presentation involved a "vesentlig investering" (substantial investment) controls extraction and reuse of the whole or "vesentlige deler" (substantial parts), for 15 years. The EU sui generis right is similar (Directive 96/9/EC, not opened: **UNVERIFIED**). Whether one figure's per-electrode labels form a protected database, and whether we took a substantial part (we took essentially all of Extended Data Fig. 1), is **UNVERIFIED**; it is arguable either way. CC BY-NC-ND 4.0 §4 expressly covers database rights: extraction is licensed "for NonCommercial purposes only and provided You do not Share Adapted Material".

**C. How the CC licence applies.** It binds us only where a right exists. §2(a)(2) says: "Where Exceptions and Limitations apply to Your use, this Public License does not apply." If the extracted values are unprotected facts, the licence does not restrict them. If A or B applies, then:
- NonCommercial ("not primarily intended for or directed towards commercial advantage") rules out use in a commercial product. Internal tests at a commercial company are a grey zone.
- NoDerivatives blocks sharing a transformed version, and our re-projected segment tables are arguably adapted material.
Apache-2.0 cannot sublicense rights we do not hold, so a public package would pass users rights we cannot give.

**D. Participant privacy (GDPR).** The participants are coded (C1, P2, P3). The paper also publishes sex, age at implant and injury level, and names the trial (NCT01894802). Participants in this trial may have been named in the press (**UNVERIFIED**). Electrode-level sensation maps linked to a coded person are arguably **pseudonymised health-related data about identifiable people**, not anonymous data (GDPR Recital 26: identifiability depends on the means reasonably likely to be used). Holding them internally with a research/test purpose and minimal fields is low risk. Republishing them in a package, keyed to the same codes, adds exposure for no engineering benefit. It also sits badly next to the authors' own choice to keep the underlying data under restricted access "owing to participant privacy". For a neural-data governance company that is a reputational risk, even if lawful.

## Actions
1. **Now (private repo):** keep the files. Add a `LICENSE-THIRD-PARTY` / README note: source, DOI, "CC BY-NC-ND 4.0, used for internal testing, not for redistribution". Keep the hash pins.
2. **Before any public release or open-sourcing (D6):**
   - move `reference_data/greenspon2025_*` out of the package;
   - exclude `tests/golden/greenspon2025_*` and `examples/greenspon2025_*` from the public repo, and check git history (a history rewrite is a lead/owner decision);
   - add a CI check that fails the release if `greenspon2025` appears in the sdist or wheel.
3. **Replace with:** a `fetch_reference()` script that downloads the open-access figure, runs our digitiser locally and verifies against published hash pins (hashes of our own outputs are fine to publish), plus synthetic fixtures for unit tests.
4. **Minimise now:** replace C1/P2/P3 with neutral labels (S1–S3) in the vendored files, and keep the mapping in one internal file, except where tests need the paper's labels.
5. **If the owner wants to ship the real data:** ask the corresponding author or Springer Nature for written permission. This is an owner-gated contact; agents must not do it.

## Hjemmel / Legal basis
- Åndsverkloven (LOV-2018-06-15-40) § 24, database right: https://lovdata.no/lov/2018-06-15-40/§24 (opened 2026-09-26).
- CC BY-NC-ND 4.0 legal code, definitions of NonCommercial and Adapted Material, §2(a)(2), §4: https://creativecommons.org/licenses/by-nc-nd/4.0/legalcode.en (opened 2026-09-26).
- Article licence and data-availability statement: Europe PMC REST, PMID 39643730 core metadata, and https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12176618/fullTextXML (opened 2026-09-26).
- Apache-2.0, already verified by nfb-legal-commercial (see BOARD source list).
- GDPR Recital 26 / Art. 4(1), (5): text not re-opened for this memo; the privacy worker verified it via publications.europa.eu (see BOARD). The application here is **UNVERIFIED**.
- UNVERIFIED: Norwegian or EU case law on facts extracted from figures; whether a single figure qualifies for § 24 protection; EU Directive 96/9/EC text; press identification of participants.
