# Object storage: production vs CI

**Object storage in production is the cloud provider's S3** (DECISIONS.md D4, ADR 0004: platform on AWS; PHI only
on BAA-covered services such as S3). Deployments use S3 with the provider's KMS integration and Object Lock for the
WORM `audit` bucket (audit batches, chain anchors, shred ledger, deletion certificates), as in BLUEPRINT §6-§7.

**MinIO is used only in CI tests.** `services/platform/docker-compose.ci.yml` starts `bitnamilegacy/minio` as a
disposable S3 + Object Lock test double for the integration tests. The conditions come from the M2-REVIEW MinIO
decision (`security/M2-REVIEW.md`):

- the image is pinned by digest;
- it only ever holds synthetic data;
- it is a frozen, unmaintained community build (listed in the SBOM with `nfb:supportLevel=unmaintained`, SEC-083);
- it must never appear in a staging or production compose file or `infra/` module;
- it is to be replaced (candidates, not evaluated: another S3-compatible test server, or moto's S3 mode). The
  replacement is an open item in `docs/security/SEC-COVERAGE.md` (known gaps).

In code, `nf_platform/storage/objects.py` `S3ObjectStore` talks the S3 API (boto3); it is unit-tested with moto,
and only the CI run points it at MinIO. Nothing in the platform depends on MinIO-specific behaviour.

Enforced by `services/platform/tests/security/test_minio_ci_only.py`: no compose, Dockerfile, Terraform/HCL file
or file under an infrastructure directory (`infra/`, `deploy/`, `k8s/`, `helm/`, `charts/`, ...) other than the CI
compose file may mention MinIO; every CI image is digest-pinned; the SBOM entry is `ci-only` and `unmaintained`
with the same digest.
