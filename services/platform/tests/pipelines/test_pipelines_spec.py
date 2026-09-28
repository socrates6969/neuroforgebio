"""3.2 acceptance: PipelineVersion JSON Schema + model, canonical ID (frozen 0.5 vectors pass; key
order does not matter), immutable publish (identical re-publish idempotent, changes rejected),
``name@semver`` → digest resolution, per-tenant isolation, SEC-044."""

from __future__ import annotations

import copy
import json
import random
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from nf_platform.db.context import tenant_session
from nf_platform.pipelines import spec as ps
from nf_platform.provenance import api as prov
from nf_platform.storage.runtime import service_principal

REPO = Path(__file__).resolve().parents[4]
VECTORS = json.loads((REPO / "spec/test-vectors/ids.json").read_text(encoding="ascii"))
SCHEMA = json.loads((REPO / "docs/spec/pipeline-version.schema.json").read_text(encoding="utf-8"))
EXAMPLE = json.loads((REPO / "docs/spec/pipeline-version.example.json").read_text("utf-8"))
VALIDATOR = jsonschema.Draft202012Validator(SCHEMA)
DIGEST = "ab" * 32


def shuffled(v: Any, rng: random.Random) -> Any:
    """The same JSON value with every object's keys in a random order."""
    if isinstance(v, dict):
        keys = list(v)
        rng.shuffle(keys)
        return {k: shuffled(v[k], rng) for k in keys}
    if isinstance(v, list):
        return [shuffled(x, rng) for x in v]
    return v


# ---------------------------------------------------------------- canonical ID (0.5 vectors)
@pytest.mark.parametrize("case", VECTORS["pipeline_version"], ids=lambda c: c["name"])
def test_frozen_vectors(case):
    assert ps.id_payload(case["spec"]).decode() == case["payload"]
    assert ps.pipeline_version_id(case["spec"]) == case["id"]
    model = ps.parse_spec(case["spec"])  # the model round-trips to the same document and ID
    assert ps.id_payload(model).decode() == case["payload"]
    assert ps.pipeline_version_id(model) == case["id"]
    VALIDATOR.validate(case["spec"])


def test_vector_relations():
    by = {c["name"]: c["id"] for c in VECTORS["pipeline_version"]}
    assert by["renamed-same-content"] == by["eeg-basic@1.2.0"]  # meta is not hashed
    assert by["highpass-changed"] != by["eeg-basic@1.2.0"]


@pytest.mark.parametrize("seed", range(20))
def test_key_order_does_not_change_the_id(seed):
    rng = random.Random(seed)
    base = VECTORS["pipeline_version"][0]
    doc = shuffled(base["spec"], rng)
    assert list(doc) != list(base["spec"]) or seed  # at least some permutations differ
    assert ps.pipeline_version_id(doc) == base["id"]
    assert ps.pipeline_version_id(ps.parse_spec(doc)) == base["id"]
    # the same number spelled differently (40.0 / 40) is the same value
    doc2 = copy.deepcopy(doc)
    doc2["steps"][0]["params"]["h_freq"] = 40
    assert ps.pipeline_version_id(ps.parse_spec(doc2)) == base["id"]


def test_json_text_with_different_key_order_and_whitespace():
    base = VECTORS["pipeline_version"][0]
    text_a = json.dumps(base["spec"], sort_keys=True)
    text_b = json.dumps(shuffled(base["spec"], random.Random(7)), indent=3)
    assert text_a != text_b
    ids = {ps.pipeline_version_id(ps.parse_spec(json.loads(t))) for t in (text_a, text_b)}
    assert ids == {base["id"]}


# ---------------------------------------------------------------- schema and model agree
def _mut(fn):
    d = copy.deepcopy(EXAMPLE)
    fn(d)
    return d


BAD = {
    "tagged-image": lambda d: d["steps"][0].update(image="registry/x:latest"),
    "tag-and-digest": lambda d: d["steps"][0].update(image=f"registry/x:1.0@sha256:{DIGEST}"),
    "short-digest": lambda d: d["steps"][0].update(image="registry/x@sha256:abc"),
    "missing-seed": lambda d: d.pop("seed"),
    "negative-seed": lambda d: d.update(seed=-1),
    "extra-top-level": lambda d: d.update(extra=1),
    "extra-step-key": lambda d: d["steps"][0].update(timeout=3),
    "exact-with-value": lambda d: d["steps"][0].update(tolerance={"kind": "exact", "value": 1}),
    "abs-without-value": lambda d: d["steps"][0].update(tolerance={"kind": "abs"}),
    "zero-tolerance": lambda d: d["steps"][0].update(tolerance={"kind": "rel", "value": 0}),
    "unknown-tolerance": lambda d: d["steps"][0].update(tolerance={"kind": "approx"}),
    "no-steps": lambda d: d.update(steps=[]),
    "bad-semver": lambda d: d["meta"].update(version="1.0"),
    "bad-name": lambda d: d["meta"].update(name="Bad Name"),
    "wrong-schema": lambda d: d.update(schema="nf.pipeline-version/v2"),
    "missing-params": lambda d: d["steps"][0].pop("params"),
    "empty-entrypoint": lambda d: d["steps"][0].update(entrypoint=[]),
    "bad-step-ref": lambda d: d["steps"][0].update(step="filter"),
}


def test_example_is_valid():
    VALIDATOR.validate(EXAMPLE)
    assert ps.parse_spec(EXAMPLE).ref == "eeg-basic@1.0.0"


@pytest.mark.parametrize("name", sorted(BAD))
def test_invalid_specs_are_rejected_by_schema_and_model(name):
    doc = _mut(BAD[name])
    assert not VALIDATOR.is_valid(doc), name
    with pytest.raises(ps.PipelineError):
        ps.parse_spec(doc)


@pytest.mark.parametrize(
    "image",
    [
        f"nf-steps@sha256:{DIGEST}",
        f"ghcr.io/org/nf-steps@sha256:{DIGEST}",
        f"localhost:5000/a/b_c/d-e@sha256:{DIGEST}",
    ],
)
def test_digest_pinned_images_accepted(image):
    doc = _mut(lambda d: d["steps"][0].update(image=image))
    VALIDATOR.validate(doc)
    ps.parse_spec(doc)


def test_model_only_checks():
    """Constraints JSON Schema cannot express: unique step names, canonical JSON params."""
    dup = _mut(lambda d: d["steps"][1].update(name="filter"))
    with pytest.raises(ps.PipelineError, match="unique"):
        ps.parse_spec(dup)
    big = _mut(lambda d: d["steps"][0]["params"].update(n=2**53))
    with pytest.raises(ps.PipelineError):
        ps.parse_spec(big)


def test_contract_views():
    s = ps.parse_spec(EXAMPLE)
    f, r = s.steps
    assert (f.id, f.tolerance_class, f.rtol, f.atol) == ("filter", "exact", None, None)
    assert (r.tolerance_class, r.atol, r.rtol) == ("tolerance", 1e-9, None)
    assert s.seed == 42 and s.name == "eeg-basic" and s.version == "1.0.0"


# ---------------------------------------------------------------- defaults from the step library
class FakeCatalog:
    LIB = {"nf.filter@1.0.0": {"l_freq": 0.1, "h_freq": 40.0, "method": "fir", "phase": "zero"}}

    def defaults(self, ref):
        return self.LIB.get(ref)


def test_defaults_are_filled_before_hashing():
    explicit = _mut(lambda d: d["steps"][0].update(step="nf.filter@1.0.0"))
    partial = _mut(lambda d: d["steps"][0].update(step="nf.filter@1.0.0", params={"h_freq": 40.0}))
    a = ps.fill_defaults(ps.parse_spec(explicit), FakeCatalog())
    b = ps.fill_defaults(ps.parse_spec(partial), FakeCatalog())
    assert b.steps[0].params == FakeCatalog.LIB["nf.filter@1.0.0"]
    assert ps.pipeline_version_id(a) == ps.pipeline_version_id(b)
    unknown_param = _mut(
        lambda d: d["steps"][0].update(step="nf.filter@1.0.0", params={"order": 4})
    )
    with pytest.raises(ps.PipelineError, match="unknown parameters"):
        ps.fill_defaults(ps.parse_spec(unknown_param), FakeCatalog())
    unknown_step = _mut(lambda d: d["steps"][0].update(step="nf.nope@1.0.0"))
    with pytest.raises(ps.PipelineError, match="unknown step"):
        ps.fill_defaults(ps.parse_spec(unknown_step), FakeCatalog())


# ---------------------------------------------------------------- publish / resolve (API + DB)
pg = pytest.mark.postgres


@pg
def test_publish_is_immutable_and_idempotent(client, as_role, tenants, engine):
    h = as_role("scientist")
    doc = _mut(lambda d: d["meta"].update(version="2.0.0"))
    r1 = client.post("/v1/pipelines", json=doc, headers=h)
    assert r1.status_code == 201, r1.text
    pv = r1.json()["id"]
    assert pv == ps.pipeline_version_id(doc) and r1.json()["ref"] == "eeg-basic@2.0.0"
    # identical (even with other key order) -> 200, same id
    r2 = client.post("/v1/pipelines", json=shuffled(doc, random.Random(3)), headers=h)
    assert r2.status_code == 200 and r2.json()["id"] == pv
    # any change under the same name@version -> 409
    for change in (
        lambda d: d["steps"][0]["params"].update(l_freq=1.0),
        lambda d: d.update(seed=43),
        lambda d: d["steps"][0].update(image=f"registry.example.invalid/other@sha256:{DIGEST}"),
        lambda d: d["meta"].update(description="changed text"),
    ):
        changed = copy.deepcopy(doc)
        change(changed)
        r = client.post("/v1/pipelines", json=changed, headers=h)
        assert r.status_code == 409, r.text
        assert r.headers["content-type"].startswith("application/problem+json")
    # resolution name@semver -> digest, and by digest
    g = client.get("/v1/pipelines/eeg-basic@2.0.0", headers=as_role("viewer"))
    assert g.status_code == 200 and g.json()["id"] == pv and g.json()["spec"]["seed"] == 42
    assert client.get(f"/v1/pipelines/{pv}", headers=h).json()["ref"] == "eeg-basic@2.0.0"
    assert client.get("/v1/pipelines/eeg-basic@9.9.9", headers=h).status_code == 404
    assert client.get("/v1/pipelines/not-a-ref", headers=h).status_code == 422
    # a renamed copy of the same content has the same digest (meta is not hashed)
    doc_copy = copy.deepcopy(doc)
    doc_copy["meta"] = {"name": "my-copy", "version": "0.1.0"}
    r3 = client.post("/v1/pipelines", json=doc_copy, headers=h)
    assert r3.status_code == 201 and r3.json()["id"] == pv
    # the PipelineVersion is a PROV agent (runs will be wasAssociatedWith it), created once
    with tenant_session(service_principal(tenants.a), engine=engine) as s:
        assert prov.find_node(s, prov.ProvKind.AGENT, "pipeline_version", pv) is not None
        row = ps.resolve(s, "eeg-basic@2.0.0")
        assert row.spec.steps[0].params["l_freq"] == 0.1


@pg
def test_invalid_spec_is_422_and_viewer_cannot_publish(client, as_role):
    bad = _mut(BAD["tagged-image"])
    r = client.post("/v1/pipelines", json=bad, headers=as_role("scientist"))
    assert r.status_code == 422 and "digest" in r.json()["detail"]
    assert client.post("/v1/pipelines", json=EXAMPLE, headers=as_role("viewer")).status_code == 403


@pg
def test_pipelines_are_per_tenant(client, as_role, tenants):
    r = client.post("/v1/pipelines", json=EXAMPLE, headers=as_role("scientist"))
    assert r.status_code == 201
    hb = as_role("owner", tenant=tenants.b)
    assert client.get("/v1/pipelines/eeg-basic@1.0.0", headers=hb).status_code == 404
    assert client.get(f"/v1/pipelines/{r.json()['id']}", headers=hb).status_code == 404
    # tenant B can publish its own eeg-basic@1.0.0 with other content: no cross-tenant conflict
    other = _mut(lambda d: d.update(seed=1))
    assert client.post("/v1/pipelines", json=other, headers=hb).status_code == 201
