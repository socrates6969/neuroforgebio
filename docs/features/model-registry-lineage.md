# Model registry: training lineage and consent withdrawal (AppSec M3)

**Withdrawal propagation is guaranteed only for platform-trained model versions.** A version
registered from uploaded weights carries a training lineage that the uploader declared; the
platform cannot verify how or on what the weights were trained. This page states what the
registry does in each case and what it does not claim.

Code: `services/platform/nf_platform/registry/service.py`, `governance/deletion.py`,
`registry/manifest.py`. Tests: `services/platform/tests/registry/test_reg_upload_lineage.py`.
Spec: `docs/spec/hashing.md` §9.7 (`weights_source`).

## Two kinds of version

| `weights_source` | Weights | Training lineage | What a subject withdrawal does |
|---|---|---|---|
| `platform` | the output of a platform training job (a model derived object) | bound: the manifest's `inputs` must equal the inputs the weights were derived from | the DeletionJob flags the version only if the withdrawn subject is in its provenance lineage (exact) |
| `upload` | bytes uploaded by a user (safetensors or ONNX, never deserialised) | self-declared: the uploader chooses the `inputs` | the DeletionJob flags the version on **any** subject withdrawal in the tenant after the version was registered, with deployments blocked, reason "unverifiable lineage (uploaded weights)" |

`weights_source` is part of the hashed training manifest, the version views of the API and the
console, and the SOUP export.

## Why the rule for uploads is so broad

The report's case: a researcher exports recordings of subjects A and B, trains offline, and
uploads the weights declaring only A. If B withdraws, a lineage-based check never reaches the
version. The registry cannot know which subjects an uploaded model saw, so it treats every
withdrawal after registration as possibly relevant. A narrower rule (for example only subjects
covered by data exports the uploader made) would need a complete record of every way data can
leave the platform, which we do not have today; we did not adopt it.

Remedy for a flagged upload version: request a retrain on the platform (`POST .../retrain`). The
retrained version is platform-trained from the declared inputs, without the withdrawn subjects,
and from then on has exact lineage.

## Four-eyes for uploads

- **Deploy:** an upload-sourced version needs an approval (`model:approve`, a governance role)
  from someone other than the uploader; without it the deployment is refused and stored with the
  reason `upload_approval_required`.
- **Publish:** the SEC-143 rule (two governance approvers other than the publisher) additionally
  excludes the uploader for upload-sourced versions.

## Limits (not claimed)

- A withdrawal **before** the version was registered does not flag it. The withdrawn subject's
  data was deleted and crypto-shredded then, but a copy exported earlier could still have been
  used offline; the deletion certificate lists such exports for the customer's follow-up.
- Consent-scope withdrawals that do not start a DeletionJob (for example withdrawing only
  `model_training`) are handled as for platform versions: SEC-146 is checked at registration,
  retrain and publication, not retroactively.
- This is not certified unlearning (see `docs/features/sisa.md`).
