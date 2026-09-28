"""5.1 acceptance: channel/artifact governance attributes (SEC-022).

- modality defaults on create; a non-steward may not set other values (SEC-022);
- per-channel edits and the bulk editor: data-steward/admin only, every change emits an audit
  event carrying the old and new values;
- lineage inheritance: a derived artifact inherits the strictest attributes of its inputs, an
  explicit steward value overrides inheritance and flows on to its descendants.
"""

from __future__ import annotations

import uuid

import pytest
from gov_helpers import EEG, EMG, audit_rows, make_recording, principal
from nf_platform.db.context import tenant_session
from nf_platform.governance import attributes
from nf_platform.provenance import api as prov

pytestmark = pytest.mark.postgres
ECG = {"name": "ECG1", "modality": "ECG", "sampling_rate": 256.0, "units": "uV"}


def _channels(client, h, rid):
    r = client.get(f"/v1/recordings/{rid}", headers=h)
    assert r.status_code == 200, r.text
    return {c["name"]: c for c in r.json()["channels"]}


def test_modality_defaults_and_sec022_on_create(client, as_role, tree, storage, engine, tenants):
    sci = as_role("scientist")
    rid = make_recording(
        client,
        sci,
        tree["session_id"],
        storage=storage,
        engine=engine,
        tenant_id=tenants.a,
        subject_id=tree["subject_id"],
        channels=(EEG, EMG, ECG),
    )
    ch = _channels(client, sci, rid)
    assert (ch["Cz"]["nervous_system"], ch["EMG1"]["nervous_system"]) == ("central", "peripheral")
    assert ch["ECG1"]["nervous_system"] == "unknown"  # a steward decides
    # a scientist may confirm the default but not set anything else
    body = {"label": "x", "channels": [{**EMG, "nervous_system": "central"}]}
    r = client.post(f"/v1/sessions/{tree['session_id']}/recordings", json=body, headers=sci)
    assert r.status_code == 403 and "data-steward" in r.json()["detail"]
    body = {"label": "x", "channels": [{**EMG, "nervous_system": "peripheral"}]}
    assert (
        client.post(
            f"/v1/sessions/{tree['session_id']}/recordings", json=body, headers=sci
        ).status_code
        == 201
    )
    body = {"label": "x", "channels": [{**EMG, "derived_from_non_neural": True}]}
    assert (
        client.post(
            f"/v1/sessions/{tree['session_id']}/recordings",
            json=body,
            headers=as_role("data-steward"),
        ).status_code
        == 201
    )
    d = client.get("/v1/governance/modality-defaults", headers=sci).json()["defaults"]
    assert d["EMG"] == {"nervous_system": "peripheral", "derived_from_non_neural": False}


def test_channel_edits_are_steward_only_and_audited(client, as_role, tree, engine):
    rid = tree["recording_id"]
    body = {
        "changes": [{"index": 1, "nervous_system": "central", "derived_from_non_neural": True}],
        "reason": "review",
    }
    for role in ("scientist", "viewer", "auditor"):
        r = client.patch(f"/v1/recordings/{rid}/channels", json=body, headers=as_role(role))
        assert r.status_code == 403, role
    r = client.patch(f"/v1/recordings/{rid}/channels", json=body, headers=as_role("data-steward"))
    assert r.status_code == 200, r.text
    changes = r.json()["changes"]
    assert {(c["field"], c["old"], c["new"]) for c in changes} == {
        ("nervous_system", "peripheral", "central"),
        ("derived_from_non_neural", False, True),
    }
    ev = audit_rows(engine, request_id=r.headers["x-request-id"], type="governance.attributes")
    assert len(ev) == 1 and ev[0]["details"]["changes"] == changes
    assert ev[0]["actor_id"] == "user-data-steward" and ev[0]["resource_id"] == rid
    # a no-op edit changes nothing but is still recorded
    r = client.patch(f"/v1/recordings/{rid}/channels", json=body, headers=as_role("admin"))
    assert r.json()["changes"] == []
    assert audit_rows(engine, request_id=r.headers["x-request-id"], type="governance.attributes")
    # bad input
    bad = {"changes": [{"index": 9, "nervous_system": "central"}]}
    assert (
        client.patch(
            f"/v1/recordings/{rid}/channels", json=bad, headers=as_role("admin")
        ).status_code
        == 422
    )
    other = client.patch(
        f"/v1/recordings/{uuid.uuid4()}/channels", json=body, headers=as_role("admin")
    )
    assert other.status_code == 404


def test_bulk_editor(client, as_role, tree, storage, engine, tenants, idp):
    sci = as_role("scientist")
    rids = [
        make_recording(
            client,
            sci,
            tree["session_id"],
            storage=storage,
            engine=engine,
            tenant_id=tenants.a,
            subject_id=tree["subject_id"],
        )
        for _ in range(3)
    ]
    body = {"recording_ids": rids, "modality": "EMG", "set": {"derived_from_non_neural": True}}
    assert client.post("/v1/governance/channels/bulk", json=body, headers=sci).status_code == 403
    r = client.post("/v1/governance/channels/bulk", json=body, headers=as_role("data-steward"))
    assert r.status_code == 200, r.text
    assert r.json()["count"] == 3
    assert {c["recording_id"] for c in r.json()["changes"]} == set(rids)
    for rid in rids:
        ch = _channels(client, sci, rid)
        assert ch["EMG1"]["derived_from_non_neural"] and not ch["Cz"]["derived_from_non_neural"]
    ev = audit_rows(engine, request_id=r.headers["x-request-id"], type="governance.attributes")
    assert ev and ev[0]["details"]["count"] == 3
    # tenant B's steward cannot touch tenant A's channels (not found)
    hb = {"Authorization": "Bearer " + idp.token(sub="b", tenant=tenants.b, roles=["data-steward"])}
    r = client.post("/v1/governance/channels/bulk", json={**body, "modality": None}, headers=hb)
    assert r.status_code == 404


def _derive(s, svc, parents: list[uuid.UUID], type_: str = "feature") -> uuid.UUID:
    c = prov.record(
        s,
        svc,
        [
            prov.NodeSpec(prov.ProvKind.ACTIVITY, "compute"),
            prov.NodeSpec(prov.ProvKind.ENTITY, type_),
        ],
        [(0, prov.EdgeType.USED, p) for p in parents] + [(1, prov.EdgeType.WAS_GENERATED_BY, 0)],
    )
    return c.node_ids[1]


def test_artifacts_inherit_the_strictest_attributes_through_the_lineage(
    client, as_role, tree, storage, engine, tenants
):
    """R_emg (peripheral, derived_from_non_neural after review) -> F1; R_eeg (central) + F1 -> G.
    F1 is peripheral + non-neural; G is central and NOT non-neural (strictest); an explicit steward
    value on F1 overrides its inheritance and flows on into G."""
    sci = as_role("scientist")
    emg_only = make_recording(
        client,
        sci,
        tree["session_id"],
        storage=storage,
        engine=engine,
        tenant_id=tenants.a,
        subject_id=tree["subject_id"],
        channels=(EMG,),
    )
    eeg_only = make_recording(
        client,
        sci,
        tree["session_id"],
        storage=storage,
        engine=engine,
        tenant_id=tenants.a,
        subject_id=tree["subject_id"],
        channels=(EEG,),
    )
    r = client.patch(
        f"/v1/recordings/{emg_only}/channels",
        json={"changes": [{"index": 0, "derived_from_non_neural": True}]},
        headers=as_role("data-steward"),
    )
    assert r.status_code == 200
    svc = principal(tenants.a, "owner")
    with tenant_session(svc, engine=engine) as s:
        r_emg = prov.record(
            s, svc, [prov.NodeSpec(prov.ProvKind.ENTITY, "recording", emg_only)], []
        ).node_ids[0]
        r_eeg = prov.record(
            s, svc, [prov.NodeSpec(prov.ProvKind.ENTITY, "recording", eeg_only)], []
        ).node_ids[0]
        f1 = _derive(s, svc, [r_emg])
        g = _derive(s, svc, [r_eeg, f1], "group_average")
    h = as_role("viewer")
    a_f1 = client.get(f"/v1/artifacts/{f1}/governance", headers=h).json()
    a_g = client.get(f"/v1/artifacts/{g}/governance", headers=h).json()
    assert (a_f1["nervous_system"], a_f1["derived_from_non_neural"], a_f1["source"]) == (
        "peripheral",
        True,
        "inherited",
    )
    assert a_f1["modalities"] == ["EMG"]
    assert (a_g["nervous_system"], a_g["derived_from_non_neural"]) == ("central", False)
    assert a_g["modalities"] == ["EEG", "EMG"] and a_g["source"] == "inherited"
    # classification of the artifact follows (CA excludes non-neural-derived data)
    cf1 = client.get(f"/v1/classifications?node_id={f1}", headers=h).json()["classification"]
    assert cf1["matched_jurisdictions"] == ["CO", "EU"]
    cg = client.get(f"/v1/classifications?node_id={g}", headers=h).json()["classification"]
    assert cg["matched_jurisdictions"] == ["CA", "CO", "CT", "EU"]

    # explicit override on F1 (steward only, audited) -> flows into G's inheritance
    body = {"nervous_system": "central", "derived_from_non_neural": False, "reason": "review"}
    assert (
        client.put(
            f"/v1/artifacts/{f1}/governance", json=body, headers=as_role("scientist")
        ).status_code
        == 403
    )
    r = client.put(f"/v1/artifacts/{f1}/governance", json=body, headers=as_role("data-steward"))
    assert r.status_code == 200, r.text
    assert r.json()["source"] == "explicit" and r.json()["nervous_system"] == "central"
    assert {c["field"] for c in r.json()["changes"]} == {
        "nervous_system",
        "derived_from_non_neural",
    }
    ev = audit_rows(engine, request_id=r.headers["x-request-id"], type="governance.attributes")
    assert ev and ev[0]["resource_id"] == str(f1)
    with tenant_session(svc, engine=engine) as s:
        eff = attributes.node_attributes(s, g)
    assert eff["nervous_system"] == "central" and eff["derived_from_non_neural"] is False
    # recordings take their channels, not an override
    rec_node = tree["node_id"]
    r = client.put(f"/v1/artifacts/{rec_node}/governance", json=body, headers=as_role("admin"))
    assert r.status_code == 422


def test_unknown_input_marks_needs_review():
    a = attributes.strictest(
        [
            {
                "nervous_system": "peripheral",
                "derived_from_non_neural": False,
                "modalities": ["EMG"],
            },
            {"nervous_system": "unknown", "derived_from_non_neural": False, "modalities": ["ECG"]},
        ]
    )
    assert a["nervous_system"] == "peripheral" and a["needs_review"]
    assert attributes.strictest([]) is None
