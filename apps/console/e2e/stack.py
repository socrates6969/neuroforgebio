"""CI-only end-to-end stack for the console Playwright tests (BUILD-GUIDE 3.8).

One process: a throwaway Postgres (pgserver, or $NF_TEST_DATABASE_URL), migrations, one tenant, the
platform API (uvicorn; CI adds it with `uv run --with`, it is not in uv.lock) and a worker thread
that shares the API's storage object. They must share it: the dev LocalKms keeps keys in process
memory, so a separate worker process could not decrypt uploads.
Consent policy: AllowAllPolicy (synthetic data only; the stub would quarantine every recording).

Also writes a synthetic EDF (tools/synth) to apps/console/e2e/.out/ for the upload test.

Environment: NF_E2E_API_PORT (8710), NF_E2E_ISSUER (http://127.0.0.1:4173/mock-idp),
NF_E2E_AUDIENCE (nf-platform), NF_E2E_TENANT (fixed UUID below). Never run against real data.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

import uvicorn
from nf_platform.app import create_app
from nf_platform.config import OidcSettings, Settings, StaticSecretProvider
from nf_platform.db import migrate, testing
from nf_platform.db.context import configure_engine
from nf_platform.ingest.policy import AllowAllPolicy
from nf_platform.storage.runtime import local_storage
from nf_runner.steprunner import make_runner
from nf_runner.worker import Worker
from sqlalchemy import text

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TENANT = os.environ.get("NF_E2E_TENANT", "5e2e0000-0000-4000-8000-000000000001")
ISSUER = os.environ.get("NF_E2E_ISSUER", "http://127.0.0.1:4173/mock-idp")
AUDIENCE = os.environ.get("NF_E2E_AUDIENCE", "nf-platform")
PORT = int(os.environ.get("NF_E2E_API_PORT", "8710"))


def synth_fixture(out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PYTHONPATH": str(ROOT / "tools" / "synth")}
    cmd = [sys.executable, "-m", "nf_synth", "--seed", "3", "--formats", "edf", "--out", str(out)]
    subprocess.run(cmd, check=True, env=env)
    return out / "synth-seed3.edf"


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="nf-console-e2e-"))
    print("synthetic fixture:", synth_fixture(HERE / ".out"), flush=True)
    with testing.postgres_server(work / "pg") as admin_url:
        url = testing.create_database(admin_url, "console_e2e")
        migrate.upgrade(url)
        engine = configure_engine(url)
        with engine.begin() as c:  # provisioning bypasses RLS by design (superuser)
            c.execute(
                text("INSERT INTO tenant (id, name) VALUES (:i, 'console-e2e')"), {"i": TENANT}
            )
        storage = local_storage(work / "objects", engine=engine)
        settings = Settings(
            database_url=url,
            oidc=OidcSettings(issuer=ISSUER, audience=AUDIENCE, jwks_uri=f"{ISSUER}/jwks"),
            secrets=StaticSecretProvider("e2e", os.urandom(32)),
            environment="dev",
        )
        app = create_app(settings, engine=engine, storage=storage, consent_policy=AllowAllPolicy())
        stop = threading.Event()
        worker = Worker(
            engine=engine,
            storage=storage,
            runner=make_runner("inprocess"),
            consent_policy=AllowAllPolicy(),
            workdir=work / "worker",
        )
        t = threading.Thread(target=worker.run_forever, kwargs={"stop": stop}, daemon=True)
        t.start()
        try:
            uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
        finally:
            stop.set()
            t.join(timeout=10)
    return 0


if __name__ == "__main__":
    sys.exit(main())
