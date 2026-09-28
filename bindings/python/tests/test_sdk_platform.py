"""The SDK against the in-process platform (PostgreSQL required; skipped locally without it).

``test_website_snippet_runs_as_published`` executes the website's code snippet exactly as the
content package publishes it (``packages/content/content/home.json``, ``{pkg}`` substituted), in
a directory holding a synthetic EDF with the snippet's file name (demo data).
"""

from __future__ import annotations

import contextlib
import io
import json
import uuid

import neuroforge as nf
import numpy as np
import pytest
from inprocess import REPO, demo_edf

pytestmark = pytest.mark.postgres


def snippet_lines(page: str = "home") -> list[str]:
    path = (
        REPO
        / "packages/content/content"
        / ("home.json" if page == "home" else f"pages/{page}.json")
    )
    doc = json.loads(path.read_text("utf-8"))
    code = (
        doc["pipeline"]["code"]
        if page == "home"
        else next(s["code"] for s in doc["sections"] if "code" in s)
    )
    pkg = json.loads((REPO / "packages/content/brand.json").read_text("utf-8"))["codeIdentifiers"][
        "pythonImport"
    ]
    return [line.replace("{pkg}", pkg) for line in code["lines"]]


@pytest.fixture(scope="module")
def finished(stack, tmp_path_factory):
    """Run the published snippet once; later tests inspect the same run."""
    d = tmp_path_factory.mktemp("snippet")
    demo_edf(d / "sub-01_task-motor_eeg.edf")
    nf.configure(
        http=stack.http,
        token=stack.token,
        session=stack.session_id,
        poll_interval=0.1,
        synthetic=True,
    )
    code = "\n".join(snippet_lines("home"))
    assert code == "\n".join(snippet_lines("sdks")), "home and SDK page snippets differ"
    out = io.StringIO()
    with contextlib.chdir(d), contextlib.redirect_stdout(out):
        scope: dict = {}
        exec(compile(code, "home.json:pipeline.code", "exec"), scope)  # noqa: S102 - our own content
    return {"stdout": out.getvalue(), "scope": scope}


def test_website_snippet_runs_as_published(finished):
    printed = finished["stdout"].strip()
    uuid.UUID(printed)  # a provenance node id
    run = finished["scope"]["run"]
    assert run.state == "succeeded"
    assert run.provenance.id == printed
    rec = finished["scope"]["rec"]
    assert rec.blob_id.startswith("blob:sha256:") and rec.remote is not None


def test_run_record_and_lineage(finished, stack):
    run = finished["scope"]["run"]
    pipe = nf.pipelines.get("eeg-basic@1.0.0")
    assert (
        run.pipeline_version_id == pipe.id
    )  # recomputed locally by nf-core, equal to the server's
    steps = run.record["steps"]
    assert [s["params"] for s in steps] == [s["params"] for s in pipe.steps]  # every parameter
    lin = run.provenance.lineage("up")
    kinds = {n.get("kind") for n in lin["nodes"]}
    assert "activity" in kinds and "entity" in kinds
    exported = run.provenance.export("prov-json")
    assert isinstance(exported, dict) and exported


def test_remote_window_and_mne(finished):
    rec = finished["scope"]["rec"].remote
    header, data = rec.read(0.0, 2.0)
    assert data.shape[0] == len(header["channels"]) == 8
    assert data.shape[1] == int(round(2.0 * header["sfreq"]))
    pytest.importorskip("mne")
    raw = rec.to_mne(0.0, 2.0)
    assert raw.ch_names == header["channels"]
    local = finished["scope"]["rec"].to_mne()
    assert local.info["sfreq"] == header["sfreq"]


def test_errors_are_problem_documents(stack):
    c = nf.configure(http=stack.http, token=stack.token, session=stack.session_id, synthetic=True)
    with pytest.raises(nf.NfApiError) as e:
        nf.pipelines.get("no-such-pipeline@9.9.9")
    assert e.value.status == 404 and e.value.problem.get("status") == 404
    with pytest.raises(nf.NfApiError) as e:
        c.get(f"/v1/recordings/{uuid.uuid4()}")
    assert e.value.status == 404
    bad = nf.Client(http=stack.http, token="not-a-valid-token")
    with pytest.raises(nf.NfApiError) as e:
        bad.get("/v1/whoami")
    assert e.value.status == 401
    with pytest.raises(nf.NfApiError) as e:
        nf.Client("http://api.example.test", token="x")  # SEC-030: plain http only on loopback
    assert e.value.kind == "url"


def test_upload_hash_is_checked_client_side(stack, tmp_path):
    nf.configure(
        http=stack.http,
        token=stack.token,
        session=stack.session_id,
        poll_interval=0.1,
        synthetic=True,
    )
    p = demo_edf(tmp_path / "sub-02_task-rest_eeg.edf", seed=3)
    f = nf.open(p)
    assert f.blob_id == nf.canonical.blob_id(p.read_bytes())
    remote = f.upload()
    info = remote.info()
    assert info["source_format"] and info["channels"]
    header, data = remote.read(0.0, 1.0)
    assert np.isfinite(data).all()
