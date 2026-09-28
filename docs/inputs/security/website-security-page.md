# /security page: copy (EN + NO), for the website build

Owner: security expert. Status: **DRAFT copy v0.1**, 2026-09-26. The owner must approve it before publishing 🔒.

## Notes for the frontend (not page copy)

- **One page shared by both themes.** Put the strings in `packages/content` (e.g. `security.en.json` / `security.no.json` or MDX). Use the shared components: the ComplianceGrid for the status table and the SecurityVisual slot for the ornament. No theme-specific wording (D8).
- **Status pills:** use the existing labels only. EN: `Designed`, `Planned`, `Roadmap`. NO: `Designet`, `Planlagt`, `Veikart`. The pill legend below the table is part of the copy.
- **Copy-lint:** this text was written to pass the banned-terms list in BUILD-GUIDE 0.4, so it contains no "built-in", "live", "certified", "HIPAA-compliant", "SOC 2 compliant", "restore", "treat", "diagnose" or "cure". Please keep it that way when editing.
- **Anchors:** `#data`, `#never`, `#software`, `#standards`, `#testing`, `#incidents`, `#disclosure`. The anchor `#disclosure` is the `Policy:` target in security.txt.
- `<title>`: EN "Security | NeuroForge Bio" / NO "Sikkerhet | NeuroForge Bio". Meta description: see each language block. The brand name comes from `brand.json` (BUILD-GUIDE 1.2 brand-token test). `NeuroForge Bio` below stands for that token.
- The domain is not decided: keep `security@<domain TBD>` and `https://<domain TBD>` as placeholders, and let the build fail if a placeholder reaches a **public** build (previews may keep it).
- Language switch: the site's normal EN/NO mechanism. `lang="no"`, or `nb` if the site uses BCP 47 `nb` for bokmål; pick one and keep it consistent with the rest of the site.

---

## ENGLISH

**Meta description:** How NeuroForge Bio is designed to protect neural data: encryption, per-subject keys, access control, audit, deletion and honest status labels.

### Security at NeuroForge Bio

Neural data is not like other data. You can reset a password, but you cannot reset a brain. A recording can identify the person it came from even after names are removed. That is why security is part of the product, not a feature.

**An honest note first:** NeuroForge Bio is in development. Nothing on this page describes a running service yet. Every item carries a status:

- **Designed**: specified in our architecture, not yet built.
- **Planned**: scheduled in our build plan, with tests defined.
- **Roadmap**: we intend to do it, and it depends on funding, customers or an outside party.

We have no independent audit reports or third-party attestations today. When that changes, this page will say so and link to the evidence.

### How your neural data is protected {#data}

| What | How | Status |
|---|---|---|
| Encryption in transit | TLS 1.3 for every connection to our platform. Older protocols are refused | Designed |
| Encryption at rest | AES-256-GCM, with keys held in a cloud key-management service. Every research subject's data has **its own key** | Designed |
| Deletion you can verify | When a subject withdraws consent, we delete their data, destroy their key so that backup copies become unreadable, flag any model trained on it, and give you a signed deletion certificate. Copies you exported earlier cannot be recalled, so the certificate lists them for your follow-up | Designed |
| Access control | Single sign-on with multi-factor authentication. **Administrators must use passkeys** (phishing-resistant sign-in). Roles limit who can see, export or train on data, and sensitive exports need a second approver | Designed |
| Tenant separation | Each customer's data is separated in the application, in the database and by separate encryption keys | Designed |
| Audit trail | Every read, export, consent change, admin action and deletion is logged in a tamper-evident, append-only log that your auditors can export and verify | Designed |
| Pseudonymisation | We store subject codes, not names. Identifying fields in file headers are moved out of the working copy | Planned |
| Data stays out of logs | Our logs never contain signal samples, subject codes or free-text notes | Designed |
| Real data only in production | Development and test systems use synthetic or public data only | Designed |
| Data location | One US region at launch; an EU region is planned. Your data stays in the region you choose | Planned / Roadmap (EU) |
| Healthcare customers (US) | Infrastructure for HIPAA-aligned workflows, and a business associate agreement (BAA) for enterprise customers | Planned |

**We never call neural data "anonymous".** Brain signals can identify people, so we protect pseudonymised recordings as personal data.

### What we will never do {#never}

- **Control stimulation or any device.** Our platform, API and software kits only *receive* data from recording hardware. They cannot send commands to stimulators or any other device, and we test for that in every build.
- **Sit in your real-time loop.** Closed-loop timing stays on your own hardware. Our cloud stores and analyses data; it never gates acquisition.
- **Sell or share your data**, or use it to train our own models without your explicit, recorded permission.
- **Load trackers on this website.** No third-party analytics, fonts or scripts, and a strict content security policy.

### Software you install {#software}

| What | Status |
|---|---|
| Every release signed with Sigstore (keyless signing, public transparency log) | Planned |
| A software bill of materials (CycloneDX) with each release, including the support status of each component | Planned |
| Build provenance (SLSA) for each release, so you can check where and how it was built | Planned |
| Vulnerability statements (VEX) that say whether known flaws affect our software | Planned |
| A stated support period for each software kit version | Planned |

This is the evidence device makers ask for when they use outside software in a regulated product. It is also why our core SDK is written in a memory-safe language.

### Standards we build toward {#standards}

We use these frameworks to design and check our work. Using a framework is not the same as being audited against it.

| Standard | What it means for you | Status |
|---|---|---|
| OWASP ASVS 5.0, Level 2, with Level 3 for neural-data paths | A detailed checklist for application security, verified at each milestone | Designed |
| NIST Secure Software Development Framework (SP 800-218) | How we write, build, release and patch software | Designed |
| NIST Cybersecurity Framework 2.0 | How we run security as a company | Designed |
| IEC 81001-5-1 (health software security lifecycle) | Lifecycle evidence for components you may use in a device | Planned |
| GDPR Article 32 (security of processing) | Encryption, resilience, recovery and regular testing | Designed |
| EU Cyber Resilience Act | Security requirements, vulnerability handling and reporting for our software kits | Planned |
| ISO/IEC 27001 and ISO/IEC 27701 | Certification of our security and privacy management | Roadmap |
| SOC 2 Type II | An independent auditor's report on our controls | Roadmap |

### Testing {#testing}

- Automated security tests on every code change: static analysis, dependency checks, secret scanning and fuzzing of the file readers. *Planned.*
- An external penetration test before the first customer data enters production, then every year. *Roadmap.*
- Recovery drills every quarter, with the measured recovery times recorded. *Planned.*

### If something goes wrong {#incidents}

We keep a written incident response plan. If a security incident affects your data, we will tell you without undue delay, and in any case within 24 hours of confirming it. You can then meet your own legal deadlines, such as the 72-hour notification under the GDPR. We will tell you what happened, what data was involved and what we are doing about it. *Designed.*

### Report a vulnerability {#disclosure}

If you think you have found a security problem in our website, platform or software, please tell us.

- **Email:** security@<domain TBD> (an encrypted channel is on our roadmap)
- **What to include:** what you found, where, and how to reproduce it. Please do not include real people's data.
- **Our commitment:** we reply within 3 business days, keep you updated, fix confirmed issues, and credit you if you wish.
- **Good faith:** we will not pursue legal action against research done in good faith under our disclosure policy. That policy is: test only against your own accounts or data, avoid privacy harm and service disruption, never access or keep other people's neural data, and give us reasonable time to fix before you publish.
- Machine-readable contact: [/.well-known/security.txt](/.well-known/security.txt)

---

## NORSK (bokmål)

**Metabeskrivelse:** Slik er NeuroForge Bio utformet for å beskytte nevrale data: kryptering, tilgangsstyring, revisjonslogg, sletting og ærlige statusmerker.

### Sikkerhet hos NeuroForge Bio

Nevrale data er ikke som andre data. Et passord kan byttes, men ikke en hjerne. Et opptak kan identifisere personen det kommer fra, også etter at navnet er fjernet. Derfor ser vi sikkerhet som en del av produktet, ikke som en tilleggsfunksjon.

**Først en ærlig merknad:** NeuroForge Bio er under utvikling. Ingenting på denne siden beskriver en tjeneste som er i drift ennå. Hvert punkt har en status:

- **Designet**: beskrevet i arkitekturen vår, ikke bygget ennå.
- **Planlagt**: lagt inn i byggeplanen vår, med definerte tester.
- **Veikart**: noe vi har tenkt å gjøre, og som avhenger av finansiering, kunder eller en ekstern part.

Vi har i dag ingen uavhengige revisjonsrapporter eller tredjepartsbekreftelser. Når det endrer seg, sier denne siden det og lenker til dokumentasjonen.

### Slik beskyttes de nevrale dataene dine {#data}

| Hva | Hvordan | Status |
|---|---|---|
| Kryptering under overføring | TLS 1.3 på alle forbindelser til plattformen. Eldre protokoller avvises | Designet |
| Kryptering av lagrede data | AES-256-GCM, med nøkler i en skybasert nøkkeltjeneste. Data fra hver forsøksperson har **sin egen nøkkel** | Designet |
| Sletting du kan kontrollere | Når en forsøksperson trekker samtykket, sletter vi dataene, ødelegger nøkkelen slik at sikkerhetskopier blir uleselige, merker modeller som er trent på dataene, og gir deg et signert slettebevis. Kopier du har eksportert tidligere kan ikke hentes tilbake, så beviset lister dem opp for din oppfølging | Designet |
| Tilgangsstyring | Felles pålogging (SSO) med flerfaktorautentisering. **Administratorer må bruke passnøkler** (passkeys, pålogging som tåler phishing). Roller begrenser hvem som kan se, eksportere eller trene modeller på data, og sensitive eksporter krever godkjenning fra en person til | Designet |
| Atskillelse mellom kunder | Hver kundes data holdes atskilt i applikasjonen, i databasen og med egne krypteringsnøkler | Designet |
| Revisjonsspor | All lesing, eksport, endring av samtykke, administratorhandling og sletting logges i en logg som bare kan utvides og som avslører endringer. Revisorene dine kan eksportere og kontrollere den | Designet |
| Pseudonymisering | Vi lagrer koder for forsøkspersoner, ikke navn. Identifiserende felt i filhoder flyttes ut av arbeidskopien | Planlagt |
| Data holdes utenfor logger | Loggene våre inneholder aldri signalverdier, personkoder eller fritekstnotater | Designet |
| Ekte data bare i produksjon | Utviklings- og testsystemer bruker bare syntetiske eller offentlige data | Designet |
| Hvor data lagres | Én amerikansk region ved oppstart; en EU-region er planlagt. Dataene blir i regionen du velger | Planlagt / Veikart (EU) |
| Helsekunder (USA) | Infrastruktur for arbeidsflyter tilpasset HIPAA, og databehandleravtale etter HIPAA (BAA) for bedriftskunder | Planlagt |

**Vi kaller aldri nevrale data «anonyme».** Hjernesignaler kan identifisere mennesker, så vi beskytter pseudonymiserte opptak som personopplysninger.

### Dette gjør vi aldri {#never}

- **Styre stimulering eller andre enheter.** Plattformen, API-et og programvaresettene våre *mottar* bare data fra opptaksutstyr. De kan ikke sende kommandoer til stimulatorer eller andre enheter, og vi tester for dette i hvert bygg.
- **Stå i sanntidssløyfen din.** Tidskritisk lukket sløyfe skjer på ditt eget utstyr. Skyen vår lagrer og analyserer data og styrer aldri datainnsamlingen.
- **Selge eller dele dataene dine**, eller bruke dem til å trene egne modeller uten din uttrykkelige, registrerte tillatelse.
- **Laste sporingsverktøy på dette nettstedet.** Ingen analyse, fonter eller skript fra tredjeparter, og en streng innholdssikkerhetspolicy (CSP).

### Programvare du installerer {#software}

| Hva | Status |
|---|---|
| Hver utgivelse signeres med Sigstore (nøkkelfri signering, offentlig åpenhetslogg) | Planlagt |
| En programvarestykkliste (SBOM, CycloneDX) følger hver utgivelse, med støttestatus for hver komponent | Planlagt |
| Byggeproveniens (SLSA) for hver utgivelse, slik at du kan kontrollere hvor og hvordan den ble bygget | Planlagt |
| Sårbarhetserklæringer (VEX) som sier om kjente feil påvirker programvaren vår | Planlagt |
| En oppgitt støtteperiode for hver versjon av programvaresettene | Planlagt |

Dette er dokumentasjonen produsenter av medisinsk utstyr ber om når de bruker programvare fra andre i et regulert produkt. Det er også grunnen til at kjernen i programvaresettene er skrevet i et minnesikkert språk.

### Standarder vi bygger etter {#standards}

Vi bruker disse rammeverkene til å utforme og kontrollere arbeidet vårt. Å bruke et rammeverk er ikke det samme som å være revidert etter det.

| Standard | Hva det betyr for deg | Status |
|---|---|---|
| OWASP ASVS 5.0, nivå 2, med nivå 3 for nevrale data | En detaljert sjekkliste for applikasjonssikkerhet, kontrollert ved hver milepæl | Designet |
| NIST Secure Software Development Framework (SP 800-218) | Hvordan vi skriver, bygger, gir ut og retter programvare | Designet |
| NIST Cybersecurity Framework 2.0 | Hvordan vi driver sikkerhetsarbeidet i selskapet | Designet |
| IEC 81001-5-1 (sikkerhet i livsløpet for helseprogramvare) | Livsløpsdokumentasjon for komponenter du kan bruke i medisinsk utstyr | Planlagt |
| GDPR artikkel 32 (sikkerhet ved behandlingen) | Kryptering, robusthet, gjenoppretting og jevnlig testing | Designet |
| EUs Cyber Resilience Act (forordningen om cyberrobusthet) | Sikkerhetskrav, sårbarhetshåndtering og rapportering for programvaresettene våre | Planlagt |
| ISO/IEC 27001 og ISO/IEC 27701 | Sertifisering av styringssystemet for informasjonssikkerhet og personvern | Veikart |
| SOC 2 Type II | En uavhengig revisors rapport om kontrollene våre | Veikart |

### Testing {#testing}

- Automatiske sikkerhetstester ved hver kodeendring: statisk analyse, kontroll av avhengigheter, søk etter hemmeligheter og fuzzing av filleserne. *Planlagt.*
- En ekstern penetrasjonstest før de første kundedataene tas inn i produksjon, deretter hvert år. *Veikart.*
- Gjenopprettingsøvelser hvert kvartal, med målte gjenopprettingstider registrert. *Planlagt.*

### Hvis noe går galt {#incidents}

Vi har en skriftlig plan for håndtering av sikkerhetshendelser. Hvis en sikkerhetshendelse berører dataene dine, varsler vi deg uten ugrunnet opphold, og i alle tilfeller innen 24 timer etter at hendelsen er bekreftet. Da kan du overholde dine egne lovpålagte frister, for eksempel varsling innen 72 timer etter GDPR. Vi forteller hva som skjedde, hvilke data som var berørt og hva vi gjør med det. *Designet.*

### Meld fra om en sårbarhet {#disclosure}

Tror du at du har funnet et sikkerhetsproblem på nettstedet, i plattformen eller i programvaren vår? Gi oss beskjed.

- **E-post:** security@<domain TBD> (en kryptert kanal står på veikartet)
- **Ta med:** hva du fant, hvor, og hvordan det kan gjenskapes. Ikke send oss data om ekte personer.
- **Dette lover vi:** vi svarer innen 3 virkedager, holder deg oppdatert, retter bekreftede feil og krediterer deg hvis du ønsker det.
- **God tro:** vi går ikke rettslig til verks mot undersøkelser gjort i god tro etter retningslinjene våre for sårbarhetsvarsling. Retningslinjene er: test bare mot dine egne kontoer eller data, unngå skade på personvern og drift, ikke åpne eller behold andres nevrale data, og gi oss rimelig tid til å rette feilen før du publiserer.
- Maskinlesbar kontakt: [/.well-known/security.txt](/.well-known/security.txt)

---

## security.txt draft (RFC 9116), served at `/.well-known/security.txt`

Identical in both builds except `Canonical` (each build lists its own host; the canonical host is listed first). `Expires` is generated at build time: build date + 180 days, which respects RFC 9116's recommendation of less than a year. Serve as `text/plain; charset=utf-8` over HTTPS only.

```text
# NeuroForge Bio security contact (RFC 9116)
Contact: mailto:security@<domain TBD>
Expires: <BUILD_DATE + 180 days, ISO 8601, e.g. 2027-03-25T00:00:00.000Z>
Preferred-Languages: en, no
Canonical: https://<domain TBD>/.well-known/security.txt
Policy: https://<domain TBD>/security#disclosure
# Encryption: roadmap (OpenPGP key or a web form over TLS)
# Acknowledgments: roadmap (/security/thanks)
```

Rules from RFC 9116 (rfc-editor.org/rfc/rfc9116, opened 2026-09-26): `Contact` "MUST always be present"; `Expires` "MUST always be present and MUST NOT appear more than once"; the file access "MUST use the 'https' scheme"; an `Expires` value "less than a year into the future" is recommended.
