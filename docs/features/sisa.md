# SISA sharded training (BUILD-GUIDE 6.4)

**This is not certified unlearning.** SISA sharding limits which part of a model has to be
retrained after a consent withdrawal. It does not prove or bound what a model, an earlier model
version, an exported prediction, a log or a backup outside the crypto-shred scope still reveals
about a withdrawn subject. We make no claim beyond what this page states and the tests check.

Reference: Bourtoule et al., "Machine Unlearning", arXiv:1912.03817 (cited by ID only).

Code: `services/workers/steps/nf_train` (`nf_train.sisa` = pure NumPy core, `nf_train.platform` =
platform glue). Tests: `services/platform/tests/sisa`. Requirements: `REQ-SISA-001`,
`REQ-SISA-002` in `docs/requirements/sisa-soup.yaml`.

## What it does

- The training **subjects** are split into `S` shards. Each shard is split into `R` slices. The
  unit is a subject, not a sample: all of a subject's data goes to one shard and one slice,
  because a consent withdrawal removes a subject.
- Assignment is by hash of the registry's subject hash (`nf.training-subject.v1`) and a seed.
  A subject's place does not depend on the other subjects, so removing one subject moves nobody
  else. Shards are balanced only on average.
- Per shard, stage `r` trains on slices `0..r` (warm start from checkpoint `r-1`) and saves a
  checkpoint. One constituent model per shard; the prediction is the mean of the constituents'
  class probabilities.
- The decoder is a toy: L2-regularised logistic regression on band-power features of synthetic
  EEG (`nf_train.toydata`, from `tools/synth`). Synthetic data only.

## On the platform

- Every `(shard, slice)` checkpoint is an encrypted `derived_object` (bucket `models`, its own
  data key, `params.role = "sisa_checkpoint"`) and a provenance entity `model_checkpoint`. It
  `wasDerivedFrom` the inputs it was trained on and the previous checkpoint of its shard.
- The ensemble is a `derived_object` of kind `model`, derived from the inputs and each shard's
  final checkpoint. `nf_train.platform.manifest_for(row)` gives the registry's
  `TrainingManifest` (subject hash -> shard, recipe `sisa`).
- Inputs must be single-subject artifacts (one subject per input, resolved through the
  provenance lineage); a group average is refused. Training is policy-checked as `model:train`
  (consent scope `model_training`, SEC-146).
- **Withdrawal.** The M5 DeletionJob marks the checkpoints that contain the subject `stale` and
  flags the model `retrain_required`. The retrain (registry recipe `sisa`) then:
  - reads only the last checkpoint of the affected shard **before** the subject's slice;
  - loads only the remaining subjects of that shard, never the withdrawn subject;
  - writes new checkpoints for that shard from the subject's slice on;
  - crypto-shreds the superseded checkpoints (data key destroyed, object deleted, WORM
    shred-ledger entry so a restore re-applies it, status `superseded` with `replaced_by`);
  - leaves every checkpoint of the other shards unread and unchanged (same row, same bytes).
  The new ensemble records a checkpoint audit (`params.checkpoint_audit`: read, written and
  discarded `(shard, slice)` pairs).
- The old ensemble and the older model versions are not destroyed by the retrain. What happens
  to them (deployments blocked, retirement) is the registry's decision (6.3).

## Acceptance evidence

1. **Only one shard is touched** (test `test_sisa_platform_withdrawal_retrains_only_one_shard`,
   Postgres): after a real withdrawal and DeletionJob, the retrain reads/writes/discards
   checkpoints of one shard only. The other shards' checkpoints are byte-identical in the
   object store, keep their row, key and provenance node, and have no new checkpoint. The
   retrained ensemble is bit-identical to SISA trained from scratch without the subject.
2. **Accuracy relative to full retraining is measured**, not claimed
   (`python -m nf_train evaluate`, with `tools/synth` and `services/workers/steps/nf_train` on
   `PYTHONPATH`). "Full retraining" = the monolithic decoder (one model, no shards) trained from
   scratch without the withdrawn subject.

### Measured numbers (2026-09-26, local run)

Configuration: 4 shards x 3 slices, 48 training subjects and 24 held-out test subjects
(16 epochs each, 384 test epochs), logistic regression 200 iterations, learning rate 0.5,
L2 0.01; seeds 0-4; one withdrawn subject per seed.

| seed | SISA before | SISA after shard retrain | SISA from scratch | monolithic before | monolithic full retrain |
|---|---|---|---|---|---|
| 0 | 0.6823 | 0.6771 | 0.6771 | 0.6667 | 0.6615 |
| 1 | 0.7422 | 0.7266 | 0.7266 | 0.7188 | 0.7135 |
| 2 | 0.6849 | 0.6823 | 0.6823 | 0.6797 | 0.6615 |
| 3 | 0.6354 | 0.6354 | 0.6354 | 0.6432 | 0.6406 |
| 4 | 0.7422 | 0.7344 | 0.7344 | 0.7161 | 0.7188 |
| mean | 0.6974 | 0.6911 | 0.6911 | 0.6849 | 0.6792 |

- In all 5 runs the shard retrain was identical to SISA trained from scratch without the subject.
- A retrain touched 1 of 4 shards and loaded 7 to 18 of the 47 remaining subjects.
- In this configuration the SISA ensemble was on average 0.012 above the monolithic decoder
  after the withdrawal (range -0.005 to +0.021 per seed). A second configuration in the unit
  test (24 training and 12 test subjects, 3 shards x 2 slices, 60 iterations, seeds 0-1) printed the opposite
  sign: SISA 0.7135 vs monolithic 0.7370 mean. **The difference depends on the configuration;
  neither result generalises beyond this toy dataset.** Re-run the command for current numbers.

## Limits

- Not certified unlearning (see top). Warm starts and the ensemble make no privacy guarantee.
- Shard balance is random; a small tenant can have empty or tiny shards.
- A withdrawal in slice 0 retrains the whole shard.
- Not intended for real-time or safety-critical control.
