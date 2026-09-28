# Access review, keys, secret rotation and log review — DRAFT v0.1

**DRAFT for counsel review. Not legal advice. Not adopted. No claim of HIPAA compliance.**
Delivered to counsel: pending (owner action).

Implements the process side of SEC-012, SEC-052, SEC-104 and SEC-114
(`docs/inputs/security/SECURITY-REQUIREMENTS.md`). The HIPAA administrative safeguards are
referenced by name only (**UNVERIFIED**; counsel confirms the mapping).

## 1. Quarterly access review (SEC-114)

Every quarter the security lead and the owner review:

- people: IdP accounts, their platform roles per tenant, and whether each still needs them;
- keys: API keys (roles, scopes, expiry, last use), device keys, service roles in the cloud account;
- PHI tenants: who can reach `phi=true` tenant data, and that the tenant's placement uses listed
  services only (`infra/policy/phi-services.json`).

Record: date, reviewers, list reviewed, changes made, signature of both reviewers. A review without
a record did not happen.

## 2. Hardware keys for privileged identities (SEC-012)

Break-glass and KMS-admin accounts use hardware-bound, non-syncable security keys: two keys per
person, stored separately. The quarterly record lists the key type per privileged identity.

## 3. Secret rotation (SEC-052)

Secrets rotate at least yearly, and immediately on a staff change or suspected exposure. The
rotation runbook is drilled; the drill record (date, secret class, result) is kept with the
access-review records.

## 4. Weekly security log review (SEC-104)

A lightweight weekly review of `authz.denied` events (including `phi:placement` denials), auth
failures, audit-chain verification results and consent-chain alerts. Record: date, reviewer,
findings, follow-ups, sign-off. Tooling is roadmap.
