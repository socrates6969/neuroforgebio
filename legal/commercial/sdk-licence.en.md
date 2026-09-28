> DRAFT – not legal advice. Must be reviewed by a Norwegian lawyer (advokat) before use.

# SDK licensing – open-core split and Platform/Client Licence

Version [0.1] · [DATE] · Prevailing language: English [advokat choice].

## Part A – How NeuroForge software is licensed (design decision D6)
| Component | Licence | Where the terms are |
|---|---|---|
| `nf-core` (Rust core), Python/C++/Unity/Unreal SDKs, format converters, validators, synthetic-data tool, pipeline step library ("**Open SDK**") | **Apache License 2.0** | https://www.apache.org/licenses/LICENSE-2.0 – the licence text is included **unmodified** as `LICENSE` in each repository/package; we do not rewrite or add terms to it |
| Hosted platform (consent & deletion ledger, model registry, evidence kit, web console), and any closed client components (e.g. [platform connectors, enterprise plugins, proprietary rule sets]) ("**Platform Components**") | **Proprietary** – Part C below (Platform/Client Licence) + MSA | This document + the MSA |
| Third-party open-source dependencies | Their own licences | `THIRD_PARTY_NOTICES` / SBOM per release |

Notes:
- **Status:** per D6, repositories stay all-rights-reserved until SDK code exists; Apache-2.0 applies from the first public release of each Open SDK component. [Owner action: publishing is owner-gated.]
- Apache-2.0 includes an express patent licence (Sect. 3) that terminates for a licensee who brings patent litigation over the Work, and requires keeping NOTICE attributions in redistributions (Sect. 4(d)).
- The Apache-2.0 licence has no field-of-use limits. The **AUP applies only when the Open SDK is used with the hosted Service** – we cannot and do not add use restrictions to Apache-licensed code.
- **Trademarks:** Apache-2.0 does not grant trademark rights (Sect. 6). "NeuroForge Bio" and logos may be used only to truthfully refer to the project [trademark policy – to be written; trademark not yet registered].
- **Contributions:** inbound contributions under Apache-2.0 Sect. 5 (inbound = outbound) [+ Developer Certificate of Origin sign-off – recommendation]; no CLA assigning copyright [owner choice; a CLA would be needed if relicensing is ever planned].
- **Export:** cryptographic code in the Open SDK may require an export-control assessment before publication [**UNVERIFIED**].

## Part B – Templates to place in each Open SDK repository

**`LICENSE`**: exact copy of https://www.apache.org/licenses/LICENSE-2.0.txt (do not edit).

**`NOTICE`** (template):
```
NeuroForge [component name]
Copyright [yyyy] [NeuroForge Bio AS]

This product includes software developed by [NeuroForge Bio AS] ([https://neuroforge.bio]).

[This product includes software developed by third parties; see THIRD_PARTY_NOTICES
for their copyright and licence notices, including any NOTICE files they require.]
```
Keep NOTICE short: attributions only, no licence terms (Apache-2.0 Sect. 4(d)).

**Per-file header** (from the Apache-2.0 appendix):
```
Copyright [yyyy] [NeuroForge Bio AS]

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```
SPDX alternative: `// SPDX-License-Identifier: Apache-2.0` plus the copyright line.

**README "Not a medical device" notice** (recommended, informational – not a licence term):
> Research software. Not a medical device. Not for diagnosis, treatment or clinical decision-making. If you build a regulated product with it, you are responsible for its regulatory compliance.

## Part C – NeuroForge Platform/Client Licence (proprietary)
1. **Scope.** Applies to Platform Components delivered for installation or use on Customer's systems (e.g. closed connectors, CLI/agent binaries, on-prem/edge packages – [roadmap]) and to their documentation. Hosted use is governed by the MSA.
2. **Grant.** Subject to a valid MSA/Order Form and payment, NeuroForge grants Customer a non-exclusive, non-transferable, non-sublicensable licence during the Subscription Term to install and use the Platform Components, in object code, solely to access and use the Service for Customer's internal R&D, within Order Form limits. [Enterprise on-prem: number of nodes/instances – ●.]
3. **Restrictions.** No copying except for backup and installation; no modification, reverse engineering, decompiling or disassembly except to the extent mandatory law permits despite this restriction [åndsverkloven interoperability exception – **UNVERIFIED**]; no distribution, rental, or use to provide services to third parties; no removal of notices; no circumvention of licence keys or usage metering; compliance with the AUP and MSA § 10–11.
4. **Open-source inside.** Platform Components may include open-source components licensed under their own terms, listed in `THIRD_PARTY_NOTICES`/SBOM; nothing here limits rights under those licences.
5. **Ownership.** NeuroForge and its licensors keep all rights. Customer Data and Outputs remain Customer's (MSA § 4).
6. **Updates and telemetry.** Components may check licence validity and send Aggregated Service Metrics as defined in the MSA § 4.4 – **never Customer Data** [designed]; Customer may disable non-essential telemetry [planned].
7. **Warranty, liability, confidentiality, export, law and venue:** as in the MSA (§§ 6, 9, 11, 12, 16). If no MSA is in force (e.g. evaluation), the components are provided "as is" for [30] days of evaluation, NeuroForge's liability is limited to [EUR 1,000] except where mandatory law prevents it, and Norwegian law and Oslo tingrett apply.
8. **Termination.** Ends with the Subscription Term or on breach; Customer shall uninstall and destroy copies and certify on request.

## Hjemmel / Legal basis
- Apache License 2.0 – Sect. 3 (patent licence), 4(d) (NOTICE), 5 (contributions), 6 (trademarks), appendix header: https://www.apache.org/licenses/LICENSE-2.0 (opened 2026-09-26; Sect. 5 and 6 content from drafter knowledge of the same text – cross-check).
- Avtaleloven § 36: https://lovdata.no/dokument/NL/lov/1918-05-31-4/KAPITTEL_3 (opened 2026-09-26).
- Åndsverkloven (computer program exceptions) – **UNVERIFIED** (not opened). Export control for cryptography – eksportkontrolloven (https://lovdata.no/dokument/NL/lov/1987-12-18-93, opened 2026-09-26); classification **UNVERIFIED**.
- Product facts: architecture\DECISIONS.md D6 (Apache-2.0 open core; proprietary platform; repo all-rights-reserved until SDK code exists), D7 (Rust core); BLUEPRINT.md §5.
