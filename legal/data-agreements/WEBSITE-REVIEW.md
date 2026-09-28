> DRAFT – not legal advice. Must be reviewed by a Norwegian lawyer (advokat) before use.

# D2: Review of legal\website\ (privacy, terms, cookies; EN + NO)

Reviewer: nfb-legal-privacy · 2026-09-26.

**Verdict.** The pages are sound, consistent across the two languages, and match D9 (no trackers) and the pre-product status. I found no false control claims. I made small edits only, applied identically to EN and NO.

## Edits made
| # | File(s) | Problem | Edit |
|---|---|---|---|
| 1 | privacy-policy.en/.no § 2 (early-access row) | EN retention ran from "our last email you opened". Measuring opens needs a tracking pixel, which contradicts "no tracking" (D9) and would itself need ekomloven § 3-15 analysis. NO said only "siste aktivitet". | Both now say: "[24] months after your sign-up confirmation or your last reply to us; we do not track email opens or clicks". |
| 2 | privacy-policy.en/.no intro | Silent on NeuroForge-as-controller research data. Relevant now that data licensing is being considered. | Added: "We never sell or license data we hold for customers". A separate information/consent form would apply if NeuroForge ever collects research data itself. |
| 3 | privacy-policy.en/.no § 5 | The one-month answer time did not mention the possible extension. | Added the extension of up to two further months, with notice within the first month (Art. 12(3); verbatim **UNVERIFIED**, flagged in Hjemmel). |
| 4 | privacy-policy.en/.no § 8 | § 5 (13-year age limit) was marked UNVERIFIED. | Opened on Lovdata: 13 years confirmed. The placeholder is replaced by a plain statement and a source line in Hjemmel. |
| 5 | privacy-policy.en/.no Hjemmel | Said the GDPR text could not be verified anywhere. | Added: Norwegian GDPR text is available per article on Lovdata (listed articles opened). Articles not yet opened are listed as UNVERIFIED. |

## Findings not edited (for advokat / owner)
1. **Prevailing language.** All three pages say "English prevails". For a Norwegian controller whose notices reach Norwegian consumers, Norwegian prevailing is arguably safer. Choice for the advokat.
2. **Imprint (ehandelsloven).** The information duties (name, org.nr., address, email) are still UNVERIFIED, and the placeholders are unfilled. The site must not go live with [●].
3. **Transfers (§ 4).** The website host/CDN and email provider are not yet chosen. If the DPF is relied on, verify its status (still UNVERIFIED).
4. **Early-access form.** Keep it disabled until the controller placeholders are filled (the BOARD build note is correct).
5. **Terms § 10 venue vs consumers.** The wording is reasonable. The tvisteloven / Lugano rules are UNVERIFIED (already flagged).
6. **Cookie statement.** Correct under ekomloven § 3-15 as summarised by nfb-legal-commercial. Whether a user-set theme preference is "strictly necessary" remains open (only relevant if a runtime toggle is added; D3 says the theme is chosen at build time).
7. **Future consistency.** If a data-licensing line is ever started, the privacy policy's "we do not sell personal data" (§ 3, § 9) stays true for website data. The contributor programme needs its own notice (contributor-consent.*). Do not merge the two.

## Hjemmel / Legal basis
- Personopplysningsloven § 5: https://lovdata.no/lov/2018-06-15-38/§5 (opened 2026-09-26).
- GDPR Art. 7 (Norwegian text): https://lovdata.no/lov/2018-06-15-38/gdpr/a7 (opened 2026-09-26).
- GDPR Art. 12(3): **UNVERIFIED** verbatim.
- Ekomloven § 3-15 and Datatilsynet cookie guidance: as opened by nfb-legal-commercial (BOARD verified list).
