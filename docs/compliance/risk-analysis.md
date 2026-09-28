# Risk analysis for PHI tenants — DRAFT v0.1

**DRAFT for counsel review. Not legal advice. Not adopted. No claim of HIPAA compliance.**
Delivered to counsel: pending (owner action). The owner approves it at adoption.

## 1. Purpose

Before the first clinical customer (BLUEPRINT §8.5 step 2), identify the risks to PHI that a
`phi=true` tenant's data would face on the platform, and the safeguards that address them. The
HIPAA Security Rule's risk-analysis expectation is referenced by name only; its text was not opened
in our research (**UNVERIFIED**; counsel confirms scope and method).

## 2. Scope

- Data: recordings, derived artifacts, provenance, consent records and audit events of `phi=true`
  tenants.
- Systems: the services in `infra/policy/phi-services.json` (only listed services may hold PHI;
  `nf_platform.placement` and `infra/modules/phi-guard` enforce it), the platform API and workers,
  the IdP, CI/CD, and the people with access.
- Out of scope until a provider BAA is signed: any real PHI. Dev and staging are synthetic-only
  (SEC-071).

## 3. Method

1. Start from `security/THREAT-MODEL.md` (STRIDE) and add PHI-specific scenarios.
2. For each scenario: likelihood (1-5), impact (1-5), existing safeguard (with the test or record
   that proves it), residual risk, owner, decision (accept / mitigate / transfer).
3. Re-run at each milestone exit (SEC-113) and after any change to the service list.
4. Scores are judgement calls by named people. They are **estimates**, not measurements.

## 4. First risk register (to be scored by the owner and the security lead)

| # | Scenario | Existing safeguard (evidence) | Open |
|---|---|---|---|
| R1 | PHI stored on a service without a BAA | placement guard in code and IaC, fail closed (`test_gov_phi_placement.py`) | provider BAA not signed; current database/compute services not listed |
| R2 | Cross-tenant read | RLS + app tenant check (SEC-021; tenant isolation tests) | external pen test (SEC-110) |
| R3 | Stolen admin session | phishing-resistant MFA for admin roles (SEC-011; authz matrix test) | IdP configuration (owner) |
| R4 | Data kept after consent withdrawal | deletion propagation, crypto-shred, certificate (5.5 tests) | KMS-held certificate key |
| R5 | Tampered audit or consent records | hash chains + WORM anchors (2.8, 5.3 tests) | scheduler for anchor jobs |
| R6 | Key or secret exposure | envelope encryption; rotation runbook (SEC-052, `access-review.md`) | runbook drill record |
| R7 | Undetected incident | weekly log review (SEC-104); IR plan + PHI addendum | alert rules (SEC-102) |
| R8 | Workforce error | training before access (`workforce-training.md`) | first training record |

## 5. Records

The scored register, its date and the approver are kept with the compliance records (location
decided by the owner). This draft holds no scores.
