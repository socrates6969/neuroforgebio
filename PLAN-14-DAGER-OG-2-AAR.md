# NeuroForge Bio: plan for de neste 14 dagene og 2 årene

Eier: Marius Carlsson. Laget 2026-09-26.

Planen bygger på det teamene har levert: `investor\FUNDING-ROUND.md`, `investor\financial-model.py`, `legal\` og `architecture\BUILD-GUIDE.md`.

Grunnregler:
- Alle beløp er ESTIMATER.
- Sjekk gebyrer, frister og tilskudd på de offisielle nettsidene før du handler. Der står det "sjekk".
- Planen følger den **nøkterne (lean) veien**: deg selv pluss AI-verktøy, NOK 1M fra en første investor, og tilskudd. Den gir omtrent 18–22 måneder driftstid uten inntekter.

---

## De første 14 dagene

Målet er et selskap som finnes lovlig, med en rådgiver og en bankkonto. Ingenting publiseres ennå.

| Dag | Hva du gjør | Hvorfor | Hvor |
|---|---|---|---|
| 1 | **Hvil.** Les denne planen og `IDEAS-PARKING.md`. Snakk med en du stoler på om planene | Store beslutninger blir bedre uthvilt og med noen å drøfte dem med | — |
| 2 | Bestill en gratis samtale med en rådgiver i Innovasjon Norge (region Trøndelag) | De kan gründerløpet, tilskuddene og lokale nettverk | innovasjonnorge.no → kontakt |
| 3 | Finn 2–3 regnskapsførere som jobber med oppstartsselskaper, og be om tilbud | Du trenger en til stiftelse, MVA og årsregnskap | Regnskap Norge sitt medlemsregister (sjekk), eller anbefaling fra Innovasjon Norge |
| 4 | Finn 2–3 advokatfirmaer med startup-avdeling i Trondheim eller Oslo, og be om fastpristilbud på: (a) gjennomgang av kontraktutkastene i `legal\`, og (b) varemerkeundersøkelse for "NeuroForge Bio" | Kontraktene er AI-utkast som *må* gjennomgås. Navnet har en mulig konflikt med Neuroforge GmbH | Advokatforeningens advokatsøk (sjekk) |
| 5 | Les `legal\financing\STRUCTURES.md` (norsk sammendrag) og `investor\FUNDING-ROUND.md` §7a | Du må forstå tilbudet før du snakker med investorer | Repoet |
| 6–7 | Helg: fri | — | — |
| 8 | Møte med Innovasjon Norge-rådgiveren. Spør om oppstartstilskudd 1 og om SkatteFUNN passer | Penger du ikke gir bort aksjer for | — |
| 9 | Velg regnskapsfører. Forbered stiftelse av AS: stiftelsesdokument og vedtekter (regnskapsfører eller advokat hjelper), aksjekapital på minst NOK 30 000 | Investorer kan bare gå inn i et aksjeselskap | Altinn: samordnet registermelding (sjekk) |
| 10 | Opprett bankkonto for aksjekapitalen. Sammenlign bankenes bedriftspakker | Kapitalen må settes inn før registrering | Banker med startup-tilbud (sjekk) |
| 11 | Send registreringen til Foretaksregisteret | Da finnes selskapet | Brønnøysundregistrene (sjekk gebyr) |
| 12 | Velg advokat og send kontraktutkastene til gjennomgang. Start varemerkesøket | Beskytter deg før noe blir offentlig | — |
| 13 | Skriv en liste over 30 mulige kunder: BCI-oppstartsselskaper, universitetslaber, nevro-forskningsmiljøer, med offentlig kontaktinformasjon (nettsider og LinkedIn) | Grunnlag for kundeintervjuene, som er risiko nr. 1 | `market\landscape.md` har navnene |
| 14 | Fri. Oppsummer uken for deg selv | — | — |

**Ikke gjør i disse 14 dagene:**
- publisere nettsiden;
- kontakte investorer;
- ansette noen;
- kjøpe domene eller skytjenester før advokaten har sjekket navnet.

---

## Uke 3–12: kundeintervjuer og første investor (måned 1–3)

| Uke | Hovedoppgave |
|---|---|
| 3 | Selskapet registrert. Fast ukerytme: mandag planlegging, tirsdag–torsdag arbeid, fredag oppsummering |
| 4 | Send de første 10 intervjuforespørslene. Malene ligger i `marketing\templates\` og tilpasses etter at advokaten har sett dem |
| 5–8 | **15–20 kundeintervjuer**, 3–5 per uke. Spør hva de sliter med i dag, hva de betaler for, og om de ville betalt for sporbarhet og samtykke. Skriv notater fra hvert intervju |
| 6 | Søk oppstartstilskudd hos Innovasjon Norge, hvis rådgiveren anbefaler det |
| 8 | Advokaten er ferdig med gjennomgangen. Varemerkesvar. **Beslutning:** beholde navnet, eller bytte til en av reservene i `market\names.md` |
| 9 | Kjøp domene. Gi byggeteamet klarsignal til å publisere nettsiden (et eierbeslutningspunkt i BUILD-GUIDE 1.10) |
| 10 | Oppdater pitch og priser med det intervjuene faktisk sa. Fjern det ingen ville betale for |
| 11–12 | Snakk med 5–10 aktuelle første investorer (engler/angels). Gode steder å finne dem: Innovasjon Norges nettverk, lokale investornettverk og inkubatorer i Trondheim (NTNU-miljøet), og investormøter. Bruk term sheet-utkastet (NOK 1M, NOK 10M pre-money) *etter* advokatens gjennomgang |

---

## Måned 4–9: første produkt og designpartnere

Ukerytmen er den samme hver uke: 1 dag kunder, 3 dager produkt, 1 dag administrasjon og økonomi.

| Måned | Milepæl |
|---|---|
| 4 | NOK 1M-runden lukkes: emisjon vedtatt på generalforsamling, aksjer registrert. Søk SkatteFUNN for utviklingsprosjektet |
| 4–6 | Bygg det åpne kjernen: SDK plus sporbarhet (BUILD-GUIDE M2–M3, begrenset versjon). AI-agentene gjør mye av kodingen; du styrer og tester |
| 5 | Signer 3–5 **designpartnere** med rabatt (se `investor\PRICING.md`) |
| 6 | Kvartalsrapport til investoren: tall, fremgang, risiko |
| 7–8 | Samtykkeloggen, første versjon (M5, den kommersielle kjernen) |
| 9 | **Beslutning:** er det nok bevis (partnere som bruker produktet, noen som vil betale) til å hente seed (NOK 10M)? Hvis ja, start seed-prosessen. Hvis nei, forleng den nøkterne veien og selg mindre revisjonsoppdrag |

---

## Måned 10–24: seed, første ansatte, første inntekter

| Periode | Milepæl | Ansettelser (bare hvis seed er lukket) |
|---|---|---|
| Mnd 10–12 | Seed lukkes. Betalt lansering forberedes | Første ansatte: **CTO eller erfaren backend-utvikler**, deretter **en person med salg og kundeansvar** |
| Mnd 13–18 | Betalt lansering. De første betalende kundene | **Deltids CFO** eller regnskapsfører med CFO-tjeneste. Juridisk bistand kjøpes fortsatt som tjeneste |
| Mnd 18–24 | Styre med 1–2 uavhengige medlemmer fra bransjen: helse/medtech og finans/kapital. Neste runde (N2) forberedes | Flere utviklere og en compliance-ansvarlig (personvern) |

**Styre og ledelse.** Du ønsker å være CEO med fokus på vitenskap, og å få COO, CFO, CLO, CMO og CTO på plass. Rekkefølgen som gir mening er:
1. CTO eller teknisk medgründer;
2. salg/COO;
3. CFO på deltid;
4. de øvrige etter Series A.

Folk finner du via rekrutteringsbyråer, LinkedIn, NTNU/UiO sine alumni- og karrierekanaler og investornettverket. Lønn og opsjoner skal settes med hjelp fra regnskapsfører og advokat. En opsjonspool på 10 % er allerede lagt inn i modellen ved seed.

---

## Hva du sitter igjen med (fra `investor\FUNDING-ROUND.md`, ESTIMAT)

| Etter | Din eierandel |
|---|---|
| Første runde (NOK 1M @ 10M) | 90,9 % |
| Seed (NOK 10M @ 40M) | 63,6 % |
| N2 (USD 4M) | 48,3 % |
| Series A (USD 12M) | 36,2 % |

Hva andelen er verdt, avhenger helt av om selskapet får kunder. Modellens basisscenario gir cirka 3,6 millioner USD i årlig gjentakende inntekt (ARR) i år 5.

## Beslutningspunkter der du bør snakke med rådgiver først

Navnebytte, publisering, hver investeringsavtale, hver ansettelse, flytting eller skattespørsmål, og alt som involverer forsvar, militæret eller eksportkontroll.
