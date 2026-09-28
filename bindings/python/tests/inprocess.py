"""An in-process platform for SDK tests and the docs snippet runner: real PostgreSQL (pgserver
locally, ``NF_TEST_DATABASE_URL`` in CI), the FastAPI app behind a ``TestClient``, a mock OIDC
IdP, local encrypted object storage, the step library's ``eeg-basic`` pipeline published, and a
worker thread that converts uploads and executes runs.

Test-only: it reuses the platform's test fixtures (``services/platform/tests/core/conftest.py``).
Demo data only (synthetic EDF from ``tools/synth``).
"""

from __future__ import annotations

import importlib.util
import os
import sys
import threading
import uuid
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
for p in (
    "services/platform",
    "services/workers/runner",
    "services/workers/steps/nf_steps",
    "tools/synth",
    "services/platform/tests/ingest",
):
    if str(REPO / p) not in sys.path:
        sys.path.insert(0, str(REPO / p))


def core_fixtures():
    """The platform's core test conftest (MockIdP, make_tree, ISSUER, AUDIENCE)."""
    if "nf_core_fixtures" in sys.modules:
        return sys.modules["nf_core_fixtures"]
    path = REPO / "services/platform/tests/core/conftest.py"
    spec = importlib.util.spec_from_file_location("nf_core_fixtures", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["nf_core_fixtures"] = mod
    spec.loader.exec_module(mod)
    return mod


@dataclass
class Stack:
    http: Any  # fastapi TestClient
    token: str  # scientist in tenant A
    owner_token: str
    tenant_id: str
    session_id: str
    ids: dict[str, str]
    engine: Any
    storage: Any
    idp: Any
    workdir: Path
    extra: dict[str, Any] = field(default_factory=dict)

    def headers(self, token: str | None = None) -> dict[str, str]:
        return {"Authorization": f"Bearer {token or self.token}"}


def demo_edf(path: Path, *, seed: int = 7, duration_s: int = 20) -> Path:
    """A synthetic 8-channel EEG recording written as EDF (demo data)."""
    from nf_synth.generate import SynthParams, generate
    from nf_synth.writers import write_edf

    data, truth = generate(SynthParams(seed=seed, duration_s=duration_s))
    return Path(write_edf(path, data, truth))


@contextmanager
def platform_stack(
    workdir: Path, *, pg_url: str | None = None, worker: bool = True, grpc: bool = False
) -> Iterator[Stack]:
    from fastapi.testclient import TestClient
    from nf_platform.app import create_app
    from nf_platform.config import OidcSettings, Settings, StaticSecretProvider
    from nf_platform.db import testing
    from nf_platform.ingest.policy import AllowAllPolicy
    from nf_platform.provenance import signing
    from nf_platform.storage.runtime import local_storage
    from nf_steps.pipelines import load as load_pipeline
    from sqlalchemy import create_engine, text

    core = core_fixtures()
    workdir.mkdir(parents=True, exist_ok=True)
    with ExitStack() as es:
        if pg_url is None:
            pg_url = es.enter_context(testing.postgres_server(workdir / "pg"))
        tpl = testing.migrated_template(pg_url)
        es.callback(testing.drop_database, pg_url, tpl)
        name = f"nf_sdk_{uuid.uuid4().hex[:10]}"
        db = testing.create_database(pg_url, name, template=tpl)
        es.callback(testing.drop_database, pg_url, name)
        engine = create_engine(db, pool_size=4, max_overflow=4)
        es.callback(engine.dispose)
        tenant = str(uuid.uuid4())
        with engine.begin() as c:
            c.execute(
                text("INSERT INTO tenant (id, name) VALUES (:i, 'sdk-tenant')"), {"i": tenant}
            )
        idp = core.MockIdP()
        settings = Settings(
            database_url=db,
            oidc=OidcSettings(issuer=core.ISSUER, audience=core.AUDIENCE),
            secrets=StaticSecretProvider(version="p1", pepper=os.urandom(32)),
        )
        storage = local_storage(workdir / "objects", engine=engine)
        policy = AllowAllPolicy()
        app = create_app(
            settings, engine=engine, jwks=idp.jwks, storage=storage, consent_policy=policy
        )
        http = es.enter_context(TestClient(app, raise_server_exceptions=False))
        owner = idp.token(sub="sdk-owner", tenant=tenant, roles=["owner"], exp_in=7200)
        user = idp.token(sub="sdk-scientist", tenant=tenant, roles=["scientist"], exp_in=7200)
        ids = core.make_tree(http, {"Authorization": f"Bearer {owner}"})
        # M5 5.4: data reads and runs need consent; the fixture subject consents to every scope.
        core.grant_consent(http, {"Authorization": f"Bearer {owner}"}, ids["subject_id"])
        r = http.post(
            "/v1/pipelines",
            json=load_pipeline("eeg-basic"),
            headers={"Authorization": f"Bearer {owner}"},
        )
        assert r.status_code in (200, 201), r.text
        ids["pipeline_ref"] = r.json()["ref"]
        signing.configure(signing.Keyring(signing.Ed25519Signer.generate("sdk-harness")))
        es.callback(signing.configure, None)
        stack = Stack(
            http, user, owner, tenant, ids["session_id"], ids, engine, storage, idp, workdir
        )
        if worker:
            from nf_runner.steprunner import InProcessRunner
            from nf_runner.worker import Worker

            (workdir / "work").mkdir(exist_ok=True)
            w = Worker(
                engine=engine,
                storage=storage,
                runner=InProcessRunner(),
                lease_s=60.0,
                heartbeat_s=1.0,
                workdir=workdir / "work",
                consent_policy=policy,
            )
            stop = threading.Event()
            th = threading.Thread(
                target=w.run_forever, kwargs={"idle_s": 0.1, "stop": stop}, daemon=True
            )
            th.start()

            def _stop() -> None:
                stop.set()
                th.join(timeout=120)

            es.callback(_stop)
            stack.extra["worker"] = w
        if grpc:
            from nf_platform.ingest.stream.server import build_server
            from nf_platform.ingest.stream.service import IngestServicer

            server, port = build_server(IngestServicer(storage, engine=engine), "127.0.0.1:0")
            server.start()
            es.callback(lambda: server.stop(grace=None).wait(5))
            stack.extra["ingest_target"] = f"127.0.0.1:{port}"
        yield stack
