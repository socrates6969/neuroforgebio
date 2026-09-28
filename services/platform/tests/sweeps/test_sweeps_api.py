"""3.6: sweep API validation, idempotent variant publishing, audit, and two-tenant isolation."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sweeps_helpers import planted_pipeline, publish, sweep_body

pytestmark = pytest.mark.postgres


@pytest.fixture
def base_ref(client, as_role, quiet_tree) -> str:
    return publish(client, as_role("scientist"), planted_pipeline())


def _post(client, h, body):
    return client.post("/v1/sweeps", json=body, headers=h)


@pytest.mark.parametrize(
    ("grid", "metric", "kind"),
    [
        ({"nosuch.l_freq": [1.0]}, "decode", "invalid-grid"),
        ({"filter.nosuch": [1.0]}, "decode", "invalid-grid"),
        ({"filter": [1.0]}, "decode", "invalid-grid"),
        ({"filter.l_freq": [1.0, 1.0]}, "decode", "invalid-grid"),
        ({"filter.l_freq": []}, "decode", "invalid-grid"),
        ({"filter.l_freq": [1.0]}, "nosuch", "invalid-metric"),
        (
            {
                "filter.l_freq": [1.0 + i / 10 for i in range(9)],
                "filter.h_freq": [float(30 + i) for i in range(8)],
            },
            "decode",
            "too-large",
        ),
    ],
)
def test_invalid_sweeps_are_rejected(client, as_role, quiet_tree, base_ref, grid, metric, kind):
    body = sweep_body(base_ref, [quiet_tree["recording_id"]], grid)
    body["metric"]["step"] = metric
    r = _post(client, as_role("scientist"), body)
    assert r.status_code == 422, r.text
    assert r.json()["type"].endswith(kind), r.json()


def test_unknown_pipeline_and_recording_are_404(client, as_role, quiet_tree, base_ref):
    h = as_role("scientist")
    grid = {"filter.l_freq": [1.0]}
    r = _post(client, h, sweep_body("nope@1.0.0", [quiet_tree["recording_id"]], grid))
    assert r.status_code == 404
    r = _post(client, h, sweep_body(base_ref, [str(uuid.uuid4())], grid))
    assert r.status_code == 404


def test_failed_sweep_leaves_no_rows(client, as_role, quiet_tree, base_ref, engine):
    """One unknown recording after a valid one: the whole sweep (variants, runs, rows) rolls
    back."""
    h = as_role("scientist")
    recs = [quiet_tree["recording_id"], str(uuid.uuid4())]
    assert _post(client, h, sweep_body(base_ref, recs, {"filter.l_freq": [2.0]})).status_code == 404
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM sweep")).scalar_one() == 0
        assert c.execute(text("SELECT count(*) FROM sweep_run")).scalar_one() == 0
        assert c.execute(text("SELECT count(*) FROM run")).scalar_one() == 1  # the tree's run
        assert (
            c.execute(
                text("SELECT count(*) FROM pipeline_version WHERE name LIKE '%.mv-%'")
            ).scalar_one()
            == 0
        )


def test_request_shape_is_strict(client, as_role, quiet_tree, base_ref):
    h = as_role("scientist")
    body = sweep_body(base_ref, [quiet_tree["recording_id"]], {"filter.l_freq": [1.0]})
    assert _post(client, h, {**body, "extra": 1}).status_code == 422
    dup = sweep_body(base_ref, [quiet_tree["recording_id"]] * 2, {"filter.l_freq": [1.0]})
    assert _post(client, h, dup).status_code == 422


def test_variants_are_published_idempotently_and_runs_are_queued(
    client, as_role, quiet_tree, base_ref, engine
):
    h = as_role("scientist")
    grid = {"filter.l_freq": [1.0, 2.0], "decode.shrinkage": [0.1, 0.5]}
    body = sweep_body(base_ref, [quiet_tree["recording_id"]], grid, name="s1")
    a = _post(client, h, body)
    b = _post(client, h, body)
    assert a.status_code == b.status_code == 202, (a.text, b.text)
    a, b = a.json(), b.json()
    assert a["id"] != b["id"] and set(a["run_ids"]).isdisjoint(b["run_ids"])
    assert [v["pipeline_version_id"] for v in a["variants"]] == [
        v["pipeline_version_id"] for v in b["variants"]
    ]
    # factor order as given, the last factor varies fastest
    assert [v["params"] for v in a["variants"]] == [
        {"filter.l_freq": 1.0, "decode.shrinkage": 0.1},
        {"filter.l_freq": 1.0, "decode.shrinkage": 0.5},
        {"filter.l_freq": 2.0, "decode.shrinkage": 0.1},
        {"filter.l_freq": 2.0, "decode.shrinkage": 0.5},
    ]
    assert a["name"] == "s1" and a["state"] == "queued" and a["run_states"] == {"queued": 4}
    for rid in a["run_ids"]:
        run = client.get(f"/v1/runs/{rid}", headers=h).json()
        assert run["state"] == "queued"
    got = client.get(f"/v1/sweeps/{a['id']}", headers=as_role("viewer"))
    assert got.status_code == 200 and got.json()["run_ids"] == a["run_ids"]
    rep = client.get(f"/v1/sweeps/{a['id']}/report", headers=as_role("viewer")).json()
    assert rep["state"] == "queued" and not rep["complete"]
    assert all(c["value"] is None for c in rep["cells"]) and rep["best"] is None
    assert all(f["range"] is None for f in rep["sensitivity"])
    # audit: create + reads, tenant-scoped
    with engine.connect() as c:
        rows = c.execute(
            text("SELECT type, resource_type FROM audit_event WHERE resource_id = :i ORDER BY seq"),
            {"i": a["id"]},
        ).all()
    assert [tuple(r) for r in rows] == [
        ("data.create", "sweep"),
        ("data.read", "sweep"),
        ("data.read", "sweep_report"),
    ]


def test_two_tenant_isolation(client, as_role, tenants, quiet_tree, base_ref, idp):
    h_a = as_role("scientist")
    body = sweep_body(base_ref, [quiet_tree["recording_id"]], {"filter.l_freq": [1.0]})
    sw = _post(client, h_a, body).json()
    h_b = as_role("owner", tenant=tenants.b, sub="user-b")
    # B cannot read A's sweep or report (404, not 403: existence is not revealed)
    assert client.get(f"/v1/sweeps/{sw['id']}", headers=h_b).status_code == 404
    assert client.get(f"/v1/sweeps/{sw['id']}/report", headers=h_b).status_code == 404
    # B cannot sweep A's pipeline, nor A's recording with its own pipeline
    assert _post(client, h_b, body).status_code == 404
    ref_b = publish(client, h_b, planted_pipeline())
    body_b = sweep_body(ref_b, [quiet_tree["recording_id"]], {"filter.l_freq": [1.0]})
    assert _post(client, h_b, body_b).status_code == 404
    # A still sees its own
    assert client.get(f"/v1/sweeps/{sw['id']}", headers=h_a).status_code == 200


def test_viewer_cannot_create(client, as_role, quiet_tree, base_ref):
    body = sweep_body(base_ref, [quiet_tree["recording_id"]], {"filter.l_freq": [1.0]})
    assert _post(client, as_role("viewer"), body).status_code == 403
