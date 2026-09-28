# BAA-readiness pack (BUILD-GUIDE 5.7) — DRAFT

**Status: DRAFT for counsel review. Not legal advice. Nothing in this folder claims HIPAA compliance.**
No provider BAA is signed and we offer no BAA of our own yet: both are owner actions. The website
keeps "BAA (planned)" until the owner signs a provider BAA (tested:
`services/platform/tests/governance/test_gov_phi_placement.py::test_website_keeps_baa_planned`).

**Delivered to counsel: pending (owner action).** No agent contacts counsel. When the owner sends the
pack, record it in the table at the end of this file (date, recipient, version/commit).

## 1. BAA-covered services for PHI tenants

Source: `market/regulation.md` §3 (grade D, "AWS HIPAA reference, updated 3 Sep 2026"): AWS lists
"175+" HIPAA-eligible services, including S3, Timestream and SageMaker AI, under an AWS BAA.

We list **only the services that source names**. Every other service stays denied for `phi=true`
tenants until the owner checks it against the provider's current list and adds it with a citation.

| Service id | Service | Cited as | Role in our stack |
|---|---|---|---|
| `aws_s3` | Amazon S3 | "S3" | object storage (raw + derived data) |
| `aws_timestream` | Amazon Timestream | "Timestream" | not used today |
| `aws_sagemaker_ai` | Amazon SageMaker AI | "SageMaker AI" | not used today |

Machine-readable single source of truth: `infra/policy/phi-services.json`. Both enforcement points
read it:

- **Platform:** tenant flag `tenant.phi` (migration `0009m5_phi`, default false). The deployment's
  placement (`NF_PLACEMENT_STORAGE`, `NF_PLACEMENT_DATABASE`, `NF_PLACEMENT_COMPUTE`, catalog ids)
  is checked by `nf_platform.placement` on uploads and streams (storage + database) and on runs
  (compute too). A phi tenant on any non-listed service gets 403, and the denial is audited
  (`authz.denied`, action `phi:placement`). An unknown or unreadable policy is a denial.
- **IaC:** `infra/modules/phi-guard` (OpenTofu) fails the plan when `phi = true` and any service the
  environment uses is not listed, or when a module has no service mapping. `infra/envs/dev` declares
  its modules to the guard and pins `phi = false` (synthetic data only). `tofu test` runs are
  CI-only (`.github/workflows/infra.yml`).

**Consequence today (known gap, owner decision):** the current stack uses RDS PostgreSQL, ECS
Fargate, KMS, Secrets Manager and VPC endpoints. None of them is named in our source, so **no PHI
tenant can be placed** until the owner verifies those services against the provider's HIPAA-eligible
list (and adds them here with the citation) or changes the architecture. This is deliberate: the
guard fails closed.

## 2. Draft policies (for counsel review)

| Document | Covers | SEC rows |
|---|---|---|
| [risk-analysis.md](risk-analysis.md) | risk analysis method and a first risk register for PHI tenants | SEC-113 (input) |
| [incident-response.md](incident-response.md) | PHI addendum to `security/INCIDENT-RESPONSE.md` | SEC-115 |
| [access-review.md](access-review.md) | quarterly access review, hardware keys, secret rotation, weekly log review | SEC-012, SEC-052, SEC-104, SEC-114 |
| [workforce-training.md](workforce-training.md) | training before PHI access, yearly refresh, records | — |

Every legal statement in these drafts that is not in `market/regulation.md` is marked **UNVERIFIED**
and must be confirmed by US HIPAA counsel. The drafts name the HIPAA Security Rule and the Breach
Notification Rule but do not quote them (their text was not opened in our research).

## 3. Delivery record

| Version | Delivered to counsel | Date | By | Response |
|---|---|---|---|---|
| draft v0.1 | pending (owner action) | — | — | — |
