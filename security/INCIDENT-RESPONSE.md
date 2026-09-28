# NeuroForge Bio: incident response plan

Status: **DRAFT policy v0.1**, 2026-09-26, security expert. It is not yet adopted, and the owner approves it at adoption. Legal notification duties must be confirmed by nfb-legal and a Norwegian lawyer (advokat) before use. **Not legal advice.**
Related: `THREAT-MODEL.md` (scenarios), `SECURITY-REQUIREMENTS.md` SEC-100…106 (detection), SEC-115 (tabletops), SEC-133 (CRA), `VULN-DISCLOSURE.md`.

## 1. Purpose and scope

This plan covers any event that threatens the confidentiality, integrity or availability of:
- customer neural data and metadata;
- keys;
- provenance, audit and consent records;
- our released software (SDKs, images, website);
- our own personal data, such as early-access sign-ups and staff data.

It covers all environments and suppliers (cloud, IdP, CI, CDN).

**Principles**
1. Protect data subjects first, then customers' ability to meet their own duties, then us.
2. Preserve evidence before changing anything that can be preserved.
3. Say only what we know, and label estimates as estimates.
4. The notification clocks start at **awareness**, so escalate early. A false alarm costs little.

## 2. Roles (small-team version; one person may hold several)

| Role | Who (placeholder) | Duties |
|---|---|---|
| Incident commander (IC) | Security lead `[name]` | Declares severity, runs the timeline, decides containment |
| Executive | Owner, Marius Carlsson | Approves external notices, customer communication and spend |
| Technical lead | On-call engineer `[name]` | Investigation, containment, recovery |
| Legal / privacy | nfb-legal → external advokat `[firm]` | Classifies notification duties; drafts regulator notices |
| Communications | `[name]` | Customer notices, status page, press (only with Executive approval) |
| Scribe | `[name]` | Timestamped log in the incident record (UTC) |

A contact sheet with phone numbers, the cloud provider's support case route, the IdP, the CDN and the advokat lives in `[private runbook location]`, **not** in the repo.

## 3. Severity

| Sev | Definition | Examples | Response target |
|---|---|---|---|
| **SEV-1** | Confirmed or likely exposure, alteration or loss of **neural data or keys**; compromise of a release or the signing identity; any discovered path from our software to controlling a device | Cross-tenant read; KMS key misuse; backdoored wheel; stream forgery accepted into a customer's evidence | IC engaged ≤ 30 min, 24/7 |
| **SEV-2** | Security control failure with no confirmed data exposure; a significant availability loss | Audit-chain mismatch; admin account takeover contained before any data access; a prod outage > 4 h | IC ≤ 2 h (business hours ≤ 1 h) |
| **SEV-3** | Limited-impact vulnerability or event | A vulnerability report rated high with no evidence of exploitation; website defacement | Next business day |
| **SEV-4** | Informational | Scanner noise, a low-severity report | Weekly review |

Any incident touching **neural data or the stimulation-exclusion invariant (SEC-090…094)** is at least SEV-2 until it is disproven.

## 4. Phases

1. **Detect and triage.** Sources: alerts (SEC-102), the audit-chain job, customer reports, the disclosure mailbox, supplier notices, Rekor monitoring (SEC-106). The IC opens an incident record, sets the severity and **records the awareness time**, which starts the clocks in §6.
2. **Contain.** Revoke keys and tokens (≤ 60 s propagation, SEC-017). Disable the affected routes behind feature flags. Isolate workers. Freeze deployments. Rotate CI identities. Pull or yank compromised releases and publish a revocation notice. **Do not destroy subject keys as a containment step** unless the Executive approves: it is irreversible.
3. **Preserve evidence.** Snapshot the affected volumes and DBs to a locked evidence account. Export audit and WORM batches and verify the hash chains. Keep CI logs and the Rekor entries. Keep a chain-of-custody note.
4. **Investigate.** Establish scope: which tenants, subjects (pseudonyms), channels, time ranges, artefacts and models. Use the provenance graph to find every derivative of the affected data. This is the same traversal as a DeletionJob, run read-only.
5. **Eradicate and recover.** Fix the root cause. Rebuild from signed, provenance-checked artefacts. Recover from backups with the deletion ledger re-applied (SEC-124). Re-verify the chains.
6. **Notify** (see §6), in parallel with steps 2–5.
7. **Post-incident review** within 10 business days, blameless. Record the root cause, the threat-model update (SEC-113), new tests, and the SSDF RV.3 root-cause actions.

## 5. Playbooks (neural-data specific)

| Scenario | Key first actions |
|---|---|
| **Cross-tenant data exposure (T-03)** | Disable the route; list the requests from the audit log; identify the tenants and subject pseudonyms exposed; notify affected customers (controllers) ≤ 24 h; preserve the logs |
| **Stolen API key / device token (T-11, T-01)** | Revoke; list reads and streams since issue; mark streamed segments from that token after the suspected compromise as `suspect` (SEC-041) so customers do not rely on them as evidence |
| **Forged or tampered stream data accepted (T-01, T-02, T-43)** | Mark the segments `suspect`; trace every derived run and model (provenance down-traversal); notify customers whose sweeps, models or FDA evidence packages used them; re-derive after cleanup |
| **Signing identity or release compromise (T-50)** | Yank the releases; publish an advisory + revocation (the affected versions and digests); rotate the CI OIDC trust; re-release from clean builds with new provenance; notify customers who embed our components as SOUP so they can run their own device assessment; start the CRA Art. 14 clock if applicable |
| **KMS key deletion scheduled or key misuse (T-30)** | Cancel the deletion within the waiting period; lock the KMS admin roles; review the key usage logs |
| **Lost or stolen customer lab PC with a WAL (T-10)** | Revoke the device token; confirm the WAL encryption (SEC-037); support the customer's own breach assessment (they are the controller) |
| **Discovery of any path by which our software can command a device (T-40)** | SEV-1. Disable the feature or release; issue an advisory to all SDK users; the Executive decides on a regulatory consultation. Treat it as a potential safety issue, not only a security issue |
| **Withdrawn subject found in a restored backup or cache (P-08, T-32)** | Re-run the deletion; issue a corrected deletion certificate that states the error; notify the customer |
| **Website defacement or a tracker injected (T-60)** | Roll back to the last signed bundle; rotate the hosting credentials; check the CSP reports |

## 6. Notification clocks

All clocks run from **awareness**. The IC records the timestamp in UTC.

| Duty | Who notifies whom | Deadline | Source / status |
|---|---|---|---|
| **Customer notice** (our commitment in contracts) | NeuroForge Bio → the affected customer | **Without undue delay, ≤ [24] h after confirmation** of a personal-data breach or a significant incident. We must not postpone confirmation | Fixed in MSA Schedule 2 S7, DPA § 8.1 and SLA § 5 (nfb-legal, 2026-09-26). 24 h is the default; the bracket allows negotiation per deal |
| GDPR Art. 33(2) (as processor) | Processor → controller (the customer) | "without undue delay" | Reg. 2016/679, opened |
| GDPR Art. 33(1) (as controller, for our own data: early-access list, staff, the website) | NeuroForge Bio → **Datatilsynet** (personopplysningsloven § 20, opened by nfb-legal). Also record every breach internally (Art. 33(5), **UNVERIFIED**) | "without undue delay and, where feasible, not later than 72 hours"; reasons required if later | Opened. Datatilsynet's online breach form was not opened |
| GDPR Art. 34 (as controller) | → data subjects, when there is a high risk | Without undue delay | Art. 34 exists; the text was not quoted in this pass (**UNVERIFIED** detail) |
| **CRA Art. 14**: actively exploited vulnerability in our SDK/product, or a severe incident affecting its security | Manufacturer → the CSIRT designated as coordinator, through ENISA's single reporting platform. Which Member State's CSIRT applies to a Norwegian manufacturer depends on EEA status (**UNVERIFIED**, legal B2/B3) | Early warning **≤ 24 h**; notification **≤ 72 h**; final report within one month of the notification for incidents, and after a corrective measure is available for vulnerabilities | Reg. 2024/2847 Art. 14, applicable since 11 Sep 2026, opened. Applies once an SDK is on the EU market commercially |
| CRA: inform users | Manufacturer → affected users | After becoming aware, "where applicable" (**UNVERIFIED** detail) | — |
| NIS2 Art. 23 (not us, probably; our **customers** if they are in scope) | Customer → their CSIRT | 24 h early warning; 72 h; final report ≤ 1 month | Opened. Our ≤ 24 h customer notice supports this |
| HIPAA Breach Notification Rule (when we are a business associate) | BA → covered entity | Rule (45 CFR 164.410, **UNVERIFIED**): without unreasonable delay, ≤ 60 calendar days after discovery. **Our BAA (planned):** breach ≤ [10] calendar days; security incident ≤ [5] business days; confirmed incidents ≤ [24] h | nfb-legal; US HIPAA counsel to confirm |
| US state breach laws | Customer or controller → residents and the Attorney General (AG), per state | CO (C.R.S. 6-1-716): 30 days, AG if ≥ 500 residents · CA (Civ. Code 1798.82): most expedient time, AG copy if > 500 · CT (C.G.S. 36a-701b): 60 days, AG notice · MT (MCA 30-14-1704): without unreasonable delay. Neural data is generally **not** a listed trigger; biometric data often is, usually only together with a name. Notice is often not required when the data is encrypted and the key is uncompromised, so SEC-031/034 matter here too | **All UNVERIFIED** (nfb-legal drafter knowledge; statutes not opened). Separately, the CO/CA/CT privacy acts treat neural data as sensitive data |
| FDA / device makers | We notify customers who embed our components; **they** own any FDA reporting | Per the customer contract | — |

**Customer notice content (template):** what happened; when we became aware; the data categories and pseudonyms/tenants affected, as far as known; the likely consequences; what we have done; what the customer should do; a contact person; the next update time. Mark unknowns as unknown.

## 7. Preparedness

- Tabletop twice a year (SEC-115). One scenario each year must run the GDPR and CRA clocks together.
- Keep pre-approved notice templates (EN/NO) drafted with nfb-legal.
- Keep an out-of-band communication channel (the cloud and CI may be the compromised systems).
- Hold a retainer for incident-response support: **roadmap**, owner spend 🔒.
- Cyber insurance evaluation: **roadmap**, owner decision 🔒.

## 8. Records

Every incident record keeps: the timeline, severity changes, decisions and who made them, the evidence locations, the notifications sent (to whom and when), the post-incident actions and their closure. Retention: at least 6 years (legal to confirm).

**Retention after a subject withdraws consent** (nfb-legal answer B6, proposal):
- **Keep** only the minimal consent-ledger entries (pseudonym, form hash, scopes, timestamps) and the deletion certificate, for the relationship plus [3] years.
- **Crypto-shred** all signal data, derived data and the subject key.
- Audit logs keep pseudonyms only: 3 years by default, 6 years for BAA tenants.

The Norwegian lawyer (advokat) still has to confirm that keeping the pseudonym meets data minimisation.
