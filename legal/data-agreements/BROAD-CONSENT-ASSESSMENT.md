> DRAFT – not legal advice. Must be reviewed by a Norwegian lawyer (advokat) before use.

# Broad consent assessment: consent boxes (i)–(viii)

nfb-legal-privacy · 2026-09-26 · Owner: Marius Carlsson.
Covers the consent boxes in contributor-consent.{en,no}.md and the ledger scopes in CONSENT-SCOPES.{en,no}.md.
ASSUMPTION: NeuroForge Bio AS is not yet incorporated.

## 1. The rules (official texts opened)

**GDPR purpose limitation, Art. 5(1)(b).** Data must be "collected for specified, explicit and legitimate purposes and not further processed in a manner that is incompatible with those purposes". It adds: "further processing for … scientific or historical research purposes … shall, in accordance with Article 89(1), not be considered to be incompatible with the initial purposes".
- **Limit:** this helps the **same controller** re-use data for research. It gives **no Art. 9(2) condition**, and it does **not** make NeuroForge (a new controller) lawful. Commercial, non-research use is outside it.

**GDPR storage limitation, Art. 5(1)(e).** Data may be kept "for longer periods insofar as the personal data will be processed solely for … scientific … research purposes … in accordance with Article 89(1)", with safeguards.
- **Limit:** longer retention is allowed only while the data is used **solely** for research. Commercial scopes (vi)/(vii) cannot use this to extend retention.

**Legal bases, Art. 6 + Art. 9.**
- NeuroForge scopes rely on **explicit consent** "for one or more specified purposes" (Art. 9(2)(a); Norwegian text: "for ett eller flere spesifikke formål").
- The alternative is 9(2)(j) research with Art. 89(1) safeguards and personopplysningsloven § 9. That route requires necessity, that "samfunnets interesse … klart overstiger ulempene for den enkelte", and DPO consultation or a DPIA. For a company's commercial pool this balancing is weak, so consent is used.

**Research safeguards, Art. 89(1).** Research processing "shall be subject to appropriate safeguards … Those measures may include pseudonymisation". In our design the safeguards are:
- pseudonymisation with a pool-specific key;
- minimisation;
- the ledger;
- DPIA;
- access logging;
- the project records.

**Recital 33 (broad consent).** "It is often not possible to fully identify the purpose … at the time of data collection. Therefore, data subjects should be allowed to give their consent to **certain areas of scientific research** when in keeping with recognised ethical standards … Data subjects should have the opportunity to give their consent only to certain areas of research or parts of research projects".
- **Limit:** consent must name *areas*, and the person must be able to choose *parts*. It is **research only**.

**Recital 159.** Scientific research "should be interpreted in a broad manner including … applied research and privately funded research". NeuroForge's own research can qualify. Selling or licensing it does not become research because a company does it.

**Recital 42.** Consent is informed only if the person knows "at least … the identity of the controller and the purposes". Consent is not free if the person "is unable to refuse or withdraw consent without detriment".

**Helseforskningsloven (Norway).**
- § 14: broad consent to "nærmere bestemte, bredt definerte forskningsformål".
- REK "kan sette vilkår for bruk av bredt samtykke og kan pålegge prosjektleder å innhente nytt samtykke".
- Participants have "krav på jevnlig informasjon".
- § 9: REK prior approval of each *project*.
- § 13: consent must be "frivillig, spesifikk, informert og utvetydig".
- Datatilsynet: REK approval is no longer a legal basis for processing by itself.

**US states.**
- **Connecticut** (PA 25-113): consent is needed to process sensitive data, including neural data. The controller may "not sell the sensitive data … without the consumer's consent". Revocation must be "at least as easy" as giving consent, and processing must stop within 15 days.
- **California** (SB 1223; Civ. Code 1798.121): neural data is sensitive personal information. The person has a right to limit use to what is "necessary to perform the services … reasonably expected". The CCPA "sell" definition includes "making available … for … valuable consideration".
- **Colorado** (HB24-1058): biological and neural data used for identification is sensitive data. The CPA consent text is **UNVERIFIED**.
- **Montana** SB 163: **UNVERIFIED**.
- There is **no US equivalent of Recital 33 broad research consent** in the texts opened. Plan for **opt-in per purpose**.

## 2. Box by box: is the consent enough?

| Box | Enough as drafted? | Why / condition |
|---|---|---|
| (i) the customer's study | Yes, for the customer | The customer's own specific consent and approvals. NeuroForge is processor. |
| (ii) pool (+ internal R&D) | **Yes, if** it names NeuroForge as controller and the purpose is specific | Specific purpose: store a copy, study signals, test software. Needs the Research Pool Addendum, DPIA, and REK where health research. **Existing consents that name only the customer are NOT enough.** |
| (iii) internal model training | Yes | Specific. Honest withdrawal limits: retrain, no certified unlearning. |
| (iv) future research by NeuroForge | **Only as narrowed.** Not enough for project start by itself | Valid as broad consent to *named areas* (the allow-list in CONSENT-SCOPES § 2). **Each project still needs REK approval** where it is health research (§ 9). REK may require new consent (§ 14), and participants must get regular information. |
| (v) research partners | Yes | Specific recipient category and purpose; contract controls. Partners need their own legal basis. |
| (vi) models licensed to companies | Yes, as a **separate specific** tick | Commercial, so broad research consent cannot carry it. AI Act duties may apply if the model is a GPAI model (Art. 53). |
| (vii) data licensed to companies | Yes, as a **separate specific** tick | Commercial. A "sale" in CT/CA terms, so the US opt-in must name sale. |
| (viii) recontact | Yes | Simple. |

## 3. Where broad consent is NOT enough
1. **"Future biotech/neurobiology research" as originally proposed.** "Biotech" is not a "certain area". It could cover genetics, drugs or cell work. This fails Recital 33 and helseforskningsloven § 14's "nærmere bestemte". **It needs narrowing** (done: nervous system and neurological conditions only) **or specific re-consent** for other areas.
2. **Starting an actual health-research project.** Broad consent never replaces **REK approval of the project** (§ 9). REK can also order new consent (§ 14).
3. **Commercial use.** Selling or licensing data or models, including research "partnerships" that pay NeuroForge for data access, is outside "scientific research". It needs its own specific tick: boxes (vi) and (vii).
4. **A new controller.** NeuroForge cannot rely on the customer's study consent or on Art. 5(1)(b) compatibility. The person must know NeuroForge's identity and purposes (Recital 42).
5. **US residents.** No broad-consent concept was found in the opened texts. There must be **opt-in per purpose**, a **separate sale consent**, CA right-to-limit handling, and revocation within 15 days (CT).
6. **Vague purposes in general.** Wording such as "AI", "product development" or "any future use" is not specific. Each box names what, who and why.
7. **Linking to genetic, biobank or clinical records.** This needs new specific consent. Biobank rules also apply (helseforskningsloven chapter on research biobanks, **UNVERIFIED** details).
8. **Minors and people without capacity.** Not covered. Helseforskningsloven § 17 sets its own rules, so a separate process is needed.
9. **Payment conditional on boxes.** It would make consent not free (Recital 42). The same pay applies whatever is ticked.

## 4. Actions
- Ship boxes (i)–(viii) and the scope table **before the first design partner**.
- Advokat check points:
  - whether box (iv)'s allow-list is narrow enough for REK practice;
  - whether (ii) should be split from internal R&D;
  - the US wording for Colorado and Montana.
- Record REK's conditions in each project record.

## Sammendrag på norsk
- **Bredt samtykke** er tillatt for visse forskningsområder (fortalepunkt 33; helseforskningsloven § 14, «nærmere bestemte, bredt definerte forskningsformål»). REK kan sette vilkår og kreve nytt samtykke, og deltakerne har krav på jevnlig informasjon.
- **Bredt samtykke er ikke nok** i disse tilfellene:
  - a) «fremtidig biotek-/nevrobiologisk forskning» slik det først var formulert. Det er for vagt og er derfor snevret inn til nervesystemet og nevrologiske tilstander. Andre områder krever nytt samtykke;
  - b) oppstart av konkrete helseforskningsprosjekter, som alltid krever REK-godkjenning (§ 9);
  - c) kommersiell lisensiering av data eller modeller, som krever egne, spesifikke avkrysninger (vi og vii);
  - d) NeuroForge som ny behandlingsansvarlig. Personen må vite hvem vi er (fortalepunkt 42), og art. 5 nr. 1 bokstav b gir ikke et grunnlag etter art. 9;
  - e) personer i USA. Der kreves uttrykkelig samtykke (opt-in) per formål og eget samtykke til salg (Connecticut, California);
  - f) kobling mot gener, biobanker eller journaldata;
  - g) mindreårige;
  - h) betaling som avhenger av hvilke bokser som krysses av.
- **Lagring:** art. 5 nr. 1 bokstav e tillater lengre lagring bare for data som «utelukkende» brukes til forskning.

## Hjemmel / Legal basis
- **GDPR official English text**, Publications Office: http://publications.europa.eu/resource/celex/32016R0679 (content-negotiated XHTML; opened 2026-09-26). Used for Recitals 26, 33, 42, 159; Art. 5(1)(b), (e); Art. 89(1).
- **GDPR Norwegian text**, Lovdata (opened 2026-09-26): Art. 9 https://lovdata.no/lov/2018-06-15-38/gdpr/a9 and Art. 7 https://lovdata.no/lov/2018-06-15-38/gdpr/a7.
- **Personopplysningsloven § 9:** https://lovdata.no/lov/2018-06-15-38/§9 (opened 2026-09-26).
- **Helseforskningsloven** §§ 9, 13, 14, 16, 17: https://lovdata.no/lov/2008-06-20-44/§14 and https://lovdata.no/dokument/NL/lov/2008-06-20-44 (opened 2026-09-26). The research-biobank chapter details are **UNVERIFIED**.
- **Datatilsynet:** https://www.datatilsynet.no/personvern-pa-ulike-omrader/forskning-helse-og-velferd/helse-og-forskningsprosjekter/ (opened 2026-09-26).
- **Connecticut PA 25-113:** https://www.cga.ct.gov/2025/ACT/PA/PDF/2025PA-00113-R00SB-01295-PA.PDF (opened 2026-09-26).
- **California** (opened 2026-09-26): SB 1223 https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=202320240SB1223 and Civ. Code 1798.121 https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CIV&sectionNum=1798.121.
- **Colorado HB24-1058:** https://leg.colorado.gov/bills/hb24-1058 (opened 2026-09-26). CPA text **UNVERIFIED**.
- **Montana SB 163:** **UNVERIFIED**.
- **AI Act Art. 53** (official text, http://publications.europa.eu/resource/celex/32024R1689, opened 2026-09-26).
