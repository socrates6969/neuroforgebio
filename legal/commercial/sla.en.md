> DRAFT – not legal advice. Must be reviewed by a Norwegian lawyer (advokat) before use.

# Schedule 1 – Service Level Agreement (SLA)

Part of the MSA (msa.en.md). Prevailing language: English [advokat choice]. **All numbers are ESTIMATES and negotiable.** The availability target mirrors the launch SLO in architecture\BLUEPRINT.md §9 (99.5%, a target, not measured).

## 1. Scope
Applies to generally available components of the production Service listed in the Order Form, for paid tiers where the Order Form says "SLA applies".
**Excluded:** Beta Features and anything marked preview/early access; Academic/free tiers; the open-source SDK; staging/sandbox environments; the public website; the deletion-job completion target (24 h, BLUEPRINT §8.4 – a design target, not SLA-backed) [negotiable for Enterprise].

## 2. Availability commitment
**Monthly Availability target: [99.5]%** per calendar month (UTC).
Availability % = (total minutes in month − Downtime minutes) ÷ (total minutes − Excluded minutes) × 100.
**Downtime**: minutes in which the Service API or console returns server errors (5xx) or fails to respond for > [50]% of valid requests, as measured by NeuroForge's external monitoring [planned], confirmed by the status page [status.neuroforge.bio – planned].

## 3. Exclusions (Excluded minutes)
(a) Scheduled maintenance announced ≥ [5] business days ahead, max [4] h/month, in [window, e.g. Sat 22:00–02:00 CET]; (b) emergency security maintenance [notified promptly]; (c) causes outside NeuroForge's reasonable control (MSA § 17.1), including failures of the upstream cloud region beyond NeuroForge's architecture commitments [negotiable]; (d) Customer's systems, networks, devices, integrations or breach of the MSA/AUP; (e) suspension under MSA § 14.3 or § 11.3; (f) usage above Order Form limits or rate limits.

## 4. Service credits
| Monthly Availability | Credit (% of that month's Fees for the affected Service) |
|---|---|
| < [99.5]% and ≥ [99.0]% | [5]% |
| < [99.0]% and ≥ [95.0]% | [10]% |
| < [95.0]% | [25]% |
- Claim in writing within [30] days after month end with dates/times; NeuroForge confirms within [15] days.
- Credits apply to the next invoice (no cash refund, except on termination). Total credits in a month ≤ [25]% of that month's Fees.
- **Chronic failure:** if Availability < [99.0]% in [3] consecutive months or any [4] months in 12, Customer may terminate the affected Order Form on [30] days' notice with a pro-rata refund of prepaid unused Fees.
- Credits and the termination right are Customer's **sole and exclusive remedy** for unavailability, except for liability that cannot be limited (MSA § 12.4) [negotiable]. Credits count toward the MSA § 12.2 cap.

## 5. Support (ESTIMATE)
| Severity | Definition | First response target (business hours [CET], [Mon–Fri 09–17]) |
|---|---|---|
| S1 Critical | Production Service unavailable or suspected personal-data breach | [4] h [Enterprise: 1 h, 24/7] |
| S2 High | Major feature impaired, no workaround | [1] business day |
| S3 Normal | Partial impairment / workaround exists | [2] business days |
| S4 Low | Questions, feature requests | [5] business days |
Response targets are not resolution guarantees and carry no credits unless the Order Form says so. Breach notices follow the DPA (within [24] h after confirmation), not this table.

## 6. Reporting
Monthly availability report on request [status page history – planned].

## Hjemmel / Legal basis
Contract template; limitation of remedies subject to avtaleloven § 36 (https://lovdata.no/dokument/NL/lov/1918-05-31-4/KAPITTEL_3, opened 2026-09-26). Targets: architecture\BLUEPRINT.md §9 (SLO 99.5% at launch, not measured) and §8.4 (deletion target 24 h, ESTIMATE). Credit tiers: drafter's ESTIMATE, not benchmarked against competitors (**UNVERIFIED**).
