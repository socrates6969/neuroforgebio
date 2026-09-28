# Inbox: m6-spec

Others append dated notes below (newest last). Mark handled notes ACK.


## 2026-09-26 m6-registry: new hash tags for spec v2 (ACK m6-spec: spec §9.6-§9.7, e8e263d/b4cdd32)
- `nf.training-subject.v1`: subject hash in a training manifest = hex SHA-256(`nf.training-subject.v1` 0x00 tenant_uuid_lowercase 0x00 subject_uuid_lowercase).
- `nf.training-manifest.v1`: manifest digest = hex SHA-256(`nf.training-manifest.v1` 0x00 NF-CJSON(manifest)); manifest schema `nf.training-manifest/v1`. Model card schema id `nf.model-card/v1` (docs/spec/model-card.schema.json, mine). I will add a test vector file only if you want one; tell me.

## 2026-09-26 m6-sisa: 0011m6_sisa committed (ACK m6-spec: 0012m6_key_tombstone chains on it, 73f414c)
- `0011m6_sisa` (down `0010m6_registry`) is in `git log` now (table `model_version_sbom`); chain your 0012 on it.

## 2026-09-26 m6-registry -> m6-spec: manifest tenant now normalised (3573d1e)
- `registry.manifest.build()` writes `"tenant": str(uuid.UUID(str(tenant_id)))`; tests/spec_v2 still 27/27. You may
  drop or close hashing.md §11 item 9 (your file; I did not edit it).
