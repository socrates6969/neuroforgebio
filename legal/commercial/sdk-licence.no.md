> UTKAST – ikke juridisk rådgivning. Må gjennomgås av norsk advokat før bruk.

# SDK-lisensiering – åpen kjerne og plattform-/klientlisens

Versjon [0.1] · [DATO] · Gjeldende språk: engelsk (sdk-licence.en.md) [valg for advokat]. Apache-2.0 finnes bare på engelsk og brukes uendret.

## Del A – Slik lisensieres NeuroForge-programvaren (beslutning D6)
| Komponent | Lisens | Vilkår |
|---|---|---|
| `nf-core` (Rust), SDK-er for Python/C++/Unity/Unreal, konverterere, validatorer, syntetiske data-verktøy, pipeline-stegbibliotek («**Åpen SDK**») | **Apache License 2.0** | https://www.apache.org/licenses/LICENSE-2.0 – teksten legges **uendret** som `LICENSE`; vi skriver den ikke om og legger ikke til vilkår |
| Driftet plattform (samtykke- og slettelogg, modellregister, evidence kit, konsoll) og lukkede klientkomponenter («**Plattformkomponenter**») | **Proprietær** – Del C + MSA | Dette dokumentet + MSA |
| Tredjeparts åpen kildekode | Egne lisenser | `THIRD_PARTY_NOTICES` / SBOM per versjon |

Merknader:
- **Status:** etter D6 er kodelagrene «all rights reserved» til SDK-kode finnes; Apache-2.0 gjelder fra første offentlige utgivelse. [Publisering er eierbeslutning.]
- Apache-2.0 gir uttrykkelig patentlisens (pkt. 3), som faller bort for den som saksøker for patentinngrep, og krever at NOTICE-attribusjoner beholdes (pkt. 4(d)).
- Apache-2.0 har ingen bruksbegrensninger. **AUP gjelder bare når Åpen SDK brukes sammen med Tjenesten** – vi legger ikke bruksbegrensninger på Apache-lisensiert kode.
- **Varemerker:** Apache-2.0 gir ikke varemerkerett (pkt. 6). [Varemerkepolicy skrives; varemerket er ikke registrert.]
- **Bidrag:** inn = ut etter Apache-2.0 pkt. 5 [+ DCO-signering anbefales]; ingen CLA med overdragelse [eiervalg].
- **Eksport:** kryptografisk kode kan kreve eksportkontrollvurdering før publisering [**UVERIFISERT**].

## Del B – Maler for hvert åpent kodelager
**`LICENSE`**: nøyaktig kopi av https://www.apache.org/licenses/LICENSE-2.0.txt.

**`NOTICE`** (mal, på engelsk):
```
NeuroForge [component name]
Copyright [yyyy] [NeuroForge Bio AS]

This product includes software developed by [NeuroForge Bio AS] ([https://neuroforge.bio]).

[This product includes software developed by third parties; see THIRD_PARTY_NOTICES
for their copyright and licence notices, including any NOTICE files they require.]
```

**Filhode**: standardteksten fra Apache-2.0-vedlegget (se sdk-licence.en.md, Del B), eller `SPDX-License-Identifier: Apache-2.0` + opphavsrettslinje.

**README-merknad** (informasjon, ikke lisensvilkår): «Forskningsprogramvare. Ikke medisinsk utstyr. Ikke for diagnose, behandling eller kliniske beslutninger. Bygger du et regulert produkt, er du ansvarlig for regelverksetterlevelsen.»

## Del C – NeuroForge plattform-/klientlisens (proprietær)
1. **Omfang.** Plattformkomponenter levert for installasjon hos Kunden (lukkede koblinger, CLI/agent, on-prem/edge – [veikart]) og dokumentasjon. Driftet bruk reguleres av MSA.
2. **Lisens.** Mot gyldig MSA/bestillingsskjema og betaling: ikke-eksklusiv, ikke-overdragbar rett uten underlisens i Abonnementsperioden til å installere og bruke komponentene i objektkode, bare for å bruke Tjenesten til intern FoU, innenfor avtalte grenser.
3. **Begrensninger.** Ingen kopiering utover sikkerhetskopi/installasjon; ingen endring, dekompilering eller omvendt utvikling utover det ufravikelig lov tillater [åndsverkloven – **UVERIFISERT**]; ingen distribusjon, utleie eller tjenesteyting til tredjepart; merknader skal ikke fjernes; lisensnøkler/måling skal ikke omgås; AUP og MSA pkt. 10–11 gjelder.
4. **Åpen kildekode inni** reguleres av egne lisenser (`THIRD_PARTY_NOTICES`/SBOM).
5. **Eierskap.** NeuroForge beholder alle rettigheter. Kundedata og Resultater tilhører Kunden (MSA pkt. 4).
6. **Oppdateringer og telemetri.** Kan sjekke lisens og sende aggregerte tjenestemålinger (MSA pkt. 4.4) – **aldri Kundedata** [utformet]; ikke-nødvendig telemetri kan slås av [planlagt].
7. **Garanti, ansvar, konfidensialitet, eksport, lovvalg og verneting:** som i MSA (pkt. 6, 9, 11, 12, 16). Uten MSA (evaluering): «som den er» i [30] dager, ansvar begrenset til [EUR 1 000] med forbehold for ufravikelig lov, norsk rett og Oslo tingrett.
8. **Opphør.** Med Abonnementsperioden eller ved mislighold; Kunden avinstallerer, destruerer kopier og bekrefter på forespørsel.

## Hjemmel / Legal basis
- Apache License 2.0 pkt. 3, 4(d), 5, 6 og vedlegg: https://www.apache.org/licenses/LICENSE-2.0 (åpnet 2026-09-26; pkt. 5 og 6 etter forfatterens kunnskap om samme tekst – kontrolleres).
- Avtaleloven § 36: https://lovdata.no/dokument/NL/lov/1918-05-31-4/KAPITTEL_3 (åpnet 2026-09-26).
- Åndsverkloven – **UVERIFISERT**. Eksportkontrolloven: https://lovdata.no/dokument/NL/lov/1987-12-18-93 (åpnet 2026-09-26); klassifisering **UVERIFISERT**.
- Produktfakta: architecture\DECISIONS.md D6, D7; BLUEPRINT.md §5.
