"""3.6 acceptance: on synthetic data with a KNOWN planted effect the sweep report recovers the
planted parameter sensitivity, and every report number links to a run ID (and provenance).

Construction (``sweeps_planted``): class 2 carries a Hann-tapered 5 Hz burst whose energy lies in
[3, 7] Hz; class 1 does not. Grid: ``notch.freqs`` in {[50], [60]} x ``filter.l_freq`` in
{1, 4, 10} Hz (band-pass to 40 Hz, MNE FIR defaults), features = log band power 4-30 Hz, metric =
cross-validated shrinkage-LDA accuracy (60 balanced trials, chance 0.5).

Expected ordering, derived BEFORE any run from the construction and the filters' own taps
(``retained_fraction`` = share of the class-2 burst energy a filter passes):

- l_freq = 1 and 4 Hz keep the burst (retained >= 0.9) -> decodable: accuracy >= 0.85;
- l_freq = 10 Hz puts [3, 7] Hz in its stop band (retained <= 1e-3) -> chance: accuracy <= 0.70;
- retained(1) >= retained(4), so accuracy(1) >= accuracy(4) (within one trial, 1/60);
- the notch (50 or 60 Hz) passes [3, 30] Hz unchanged (retained >= 0.999 for both), so the notch
  factor has no effect: range across notch levels <= 0.05; the high-pass factor's range >= 0.3.
"""

from __future__ import annotations

import json

import mne
import numpy as np
import pytest
from nf_platform.pipelines.spec import pipeline_version_id
from sqlalchemy import text
from sweeps_helpers import drain, planted_pipeline, publish, sweep_body
from sweeps_planted import Planted, burst, retained_fraction

pytestmark = pytest.mark.postgres

L_FREQS = [1.0, 4.0, 10.0]
NOTCHES = [[50.0], [60.0]]
ONE_TRIAL = 1 / 60


def _highpass_taps(p: Planted, l_freq: float) -> np.ndarray:
    # the same design nf_steps.filter@1 uses with its defaults (fir, firwin, hamming, zero phase)
    return mne.filter.create_filter(
        None,
        p.sfreq,
        l_freq,
        40.0,
        filter_length="auto",
        l_trans_bandwidth="auto",
        h_trans_bandwidth="auto",
        method="fir",
        phase="zero",
        fir_window="hamming",
        fir_design="firwin",
        verbose=False,
    )


def _notch_retained(p: Planted, freq: float) -> float:
    x = np.zeros(int(20 * p.sfreq))
    b = burst(p, 0.0)
    s0 = len(x) // 2
    x[s0 : s0 + len(b)] = b
    y = mne.filter.notch_filter(
        x, p.sfreq, [freq], notch_widths=1.0, trans_bandwidth=1.0, verbose=False
    )
    return float(np.sum(y**2) / np.sum(x**2))


def expected_design() -> dict:
    """Derived from the construction only (no pipeline run)."""
    p = Planted()
    retained = {lf: retained_fraction(p, _highpass_taps(p, lf)) for lf in L_FREQS}
    notch = {f[0]: _notch_retained(p, f[0]) for f in NOTCHES}
    return {"retained": retained, "notch": notch}


def test_expected_ordering_from_the_construction():
    d = expected_design()
    r = d["retained"]
    assert r[1.0] >= 0.99 and r[4.0] >= 0.9, r  # pass band covers [3, 7] Hz
    assert r[10.0] <= 1e-3, r  # stop band covers [3, 7] Hz
    assert r[1.0] >= r[4.0]
    assert all(v >= 0.999 for v in d["notch"].values()), d["notch"]


def _decrypt(storage, tenant, subject, key: str) -> bytes:
    blob = storage.objects.get("artifacts", key)
    return storage.keyring.decrypt(tenant, subject, f"artifacts/{key}", 1, blob)


def test_report_recovers_planted_sensitivity_and_links_every_number(
    client, as_role, planted_rec, quiet_tree, worker, engine, storage, tenants
):
    design = expected_design()
    detectable = {lf: design["retained"][lf] >= 0.5 for lf in L_FREQS}
    assert detectable == {1.0: True, 4.0: True, 10.0: False}

    h = as_role("scientist")
    base_doc = planted_pipeline()
    ref = publish(client, h, base_doc)
    grid = {"notch.freqs": NOTCHES, "filter.l_freq": L_FREQS}
    r = client.post(
        "/v1/sweeps", json=sweep_body(ref, [planted_rec["recording_id"]], grid), headers=h
    )
    assert r.status_code == 202, r.text
    sweep = r.json()
    assert sweep["state"] == "queued" and len(sweep["run_ids"]) == 6
    assert len(sweep["variants"]) == 6

    # every variant is its own published, content-addressed PipelineVersion
    for v in sweep["variants"]:
        doc = client.get(f"/v1/pipelines/{v['pipeline_ref']}", headers=h).json()
        assert doc["id"] == v["pipeline_version_id"] == pipeline_version_id(doc["spec"])
        steps = {s["name"]: s["params"] for s in doc["spec"]["steps"]}
        assert steps["notch"]["freqs"] == v["params"]["notch.freqs"]
        assert steps["filter"]["l_freq"] == v["params"]["filter.l_freq"]
    assert len({v["pipeline_version_id"] for v in sweep["variants"]}) == 6
    # the base (notch 50, l_freq 1) is one of the grid points: same content -> same ID
    base_id = client.get(f"/v1/pipelines/{ref}", headers=h).json()["id"]
    assert sweep["variants"][0]["pipeline_version_id"] == base_id

    assert drain(worker) == 6
    rep = client.get(f"/v1/sweeps/{sweep['id']}/report", headers=h)
    assert rep.status_code == 200, rep.text
    rep = rep.json()
    assert rep["state"] == "succeeded" and rep["complete"], rep
    assert rep["metric"]["name"] == "decode.accuracy"

    # ---- every number links to a run ID and the provenance node of the artifact holding it
    acc = {}
    for c in rep["cells"]:
        assert c["state"] == "succeeded" and c["value"] is not None
        run = client.get(f"/v1/runs/{c['run_id']}", headers=h).json()
        assert run["pipeline_version_id"] == c["pipeline_version_id"]
        assert run["prov_activity_id"] == c["prov_activity_id"]
        decode_info = next(s for s in run["record"]["execution"]["steps"] if s["name"] == "decode")
        assert decode_info["info"]["accuracy"] == c["value"]
        art = next(
            a for a in run["artifacts"] if a["step"] == "decode" and a["name"] == "signal.json"
        )
        assert art["id"] == c["artifact"]["id"] and art["sha256"] == c["artifact"]["sha256"]
        node = client.get(f"/v1/provenance/{c['prov_node_id']}", headers=h).json()
        assert node["node"]["ref_id"] == art["id"]
        assert node["node"]["content_hash"] == f"blob:sha256:{art['sha256']}"
        assert any(
            e["rel"] == "wasGeneratedBy" and e["dst"] == c["prov_activity_id"]
            for e in node["edges_out"]
        )
        # the artifact itself carries the same number (content-hashed, provenance-linked)
        with engine.connect() as conn:
            key = conn.execute(
                text("SELECT object_key FROM run_artifact WHERE id = :i"), {"i": art["id"]}
            ).scalar_one()
        meta = json.loads(_decrypt(storage, tenants.a, quiet_tree["subject_id"], key))
        assert meta["meta"]["decode"]["accuracy"] == c["value"]
        acc[(c["params"]["notch.freqs"][0], c["params"]["filter.l_freq"])] = c["value"]

    all_runs = {c["run_id"] for c in rep["cells"]}
    for v in rep["variants"]:
        assert set(v["run_ids"]) <= all_runs and v["n"] == len(v["run_ids"]) == 1
        vals = [c["value"] for c in rep["cells"] if c["run_id"] in v["run_ids"]]
        assert v["mean"] == pytest.approx(sum(vals) / len(vals))
    for f in rep["sensitivity"]:
        for lv in f["levels"]:
            assert lv["run_ids"] and set(lv["run_ids"]) <= all_runs
            vals = [c["value"] for c in rep["cells"] if c["run_id"] in lv["run_ids"]]
            assert lv["mean"] == pytest.approx(sum(vals) / len(vals))
    assert set(rep["best"]["run_ids"]) <= all_runs

    # ---- the planted sensitivity is recovered (ordering stated above, from the construction)
    for notch in (50.0, 60.0):
        for lf in L_FREQS:
            if detectable[lf]:
                assert acc[(notch, lf)] >= 0.85, acc
            else:
                assert acc[(notch, lf)] <= 0.70, acc
        assert acc[(notch, 1.0)] >= acc[(notch, 4.0)] - ONE_TRIAL, acc
    sens = {f["factor"]: f for f in rep["sensitivity"]}
    assert sens["filter.l_freq"]["range"] >= 0.3
    assert sens["notch.freqs"]["range"] <= 0.05
    lvl = {lv["value"]: lv["mean"] for lv in sens["filter.l_freq"]["levels"]}
    assert min(lvl[1.0], lvl[4.0]) > lvl[10.0] + 0.3
    assert rep["best"]["params"]["filter.l_freq"] in (1.0, 4.0)

    # ---- the sweep itself is a provenance activity linked to every PipelineVersion + input
    node = client.get(f"/v1/provenance/{rep['prov_node_id']}", headers=h).json()
    assert node["node"]["type"] == "sweep" and node["node"]["ref_id"] == sweep["id"]
    assoc = [e for e in node["edges_out"] if e["rel"] == "wasAssociatedWith"]
    assert len(assoc) == 6  # base == variant 0, so 6 distinct PipelineVersion agents
    used = [e for e in node["edges_out"] if e["rel"] == "used"]
    assert len(used) == 1
