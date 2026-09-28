"""Worker process for tests/storage/test_key_tombstone_race.py (SEC-034a, M2-REVIEW F1).

Run as its own OS process: ``python _key_race_worker.py <json config>``. It opens its own engine and
Keyring on the real Postgres (as the app role, through ``tenant_session``) and prints one JSON line
per subject it handled: ``{"subject", "result": "ok"|"SubjectKeyUnavailable"|"error", ...}``.

Roles:
- ``encrypt``: ``Keyring.encrypt`` for each subject.
- ``shred``: ``Keyring.shred_subject`` for each subject.

Modes:
- ``toctou``: deterministic interleaving. The encrypt side passes the application's tombstone check
  and then, right before it writes the key row (``put_wrapped``), signals ``checked`` and waits for
  the shred side to commit (``shredded``). Only the database guard can stop it now.
- ``race``: free-running. Before each subject both processes block on a shared advisory lock that
  the test holds; the test releases it once both are waiting, so they start together.
"""

from __future__ import annotations

import json
import sys
import time
import traceback
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from nf_platform.db.context import Principal, tenant_session
from nf_platform.storage import Keyring, LocalKms, SubjectKeyUnavailable
from nf_platform.storage.keyring import WrappedDek
from nf_platform.storage.sql_keystore import SqlKeyStore
from sqlalchemy import create_engine, text

TIMEOUT_S = 60.0


def _wait_for(path: Path) -> None:
    deadline = time.monotonic() + TIMEOUT_S
    while not path.exists():
        if time.monotonic() > deadline:
            raise TimeoutError(f"no {path.name} within {TIMEOUT_S}s")
        time.sleep(0.005)


class _PausingStore(SqlKeyStore):
    """Pauses before writing a key row (after the Keyring's tombstone check has passed)."""

    def __init__(self, session_for: Any, sync: Path) -> None:
        super().__init__(session_for)
        self.sync = sync
        self.armed = False

    def put_wrapped(self, rec: WrappedDek) -> None:
        if self.armed:
            self.armed = False
            (self.sync / f"checked-{rec.subject_id}").write_text("1")
            _wait_for(self.sync / f"shredded-{rec.subject_id}")
        super().put_wrapped(rec)


def main(cfg: dict[str, Any]) -> None:
    role, mode, tenant = cfg["role"], cfg["mode"], cfg["tenant"]
    sync = Path(cfg["sync_dir"])
    eng = create_engine(cfg["db_url"], pool_size=1, max_overflow=1)

    @contextmanager
    def session_for(tenant_id: str):
        p = Principal(
            id=f"svc-race-{role}",
            tenant_id=tenant_id,
            roles=frozenset({"service"}),
            scopes=frozenset(),
            kind="api_key",
            mfa_phr=False,
        )
        with tenant_session(p, engine=eng) as s:
            yield s

    store = _PausingStore(session_for, sync)
    kr = Keyring(LocalKms(), store, max_encryptions_per_dek=cfg.get("max_per_dek", 2**32))
    gate = eng.connect() if mode == "race" else None
    for i, subject in enumerate(cfg["subjects"]):
        out: dict[str, Any] = {"role": role, "subject": subject}
        try:
            if mode == "toctou":
                if role == "encrypt":
                    for _ in range(cfg.get("pre_encrypts", 0)):  # e.g. fill a DEK to its limit
                        kr.encrypt(tenant, subject, "raw/pre", 1, b"pre")
                    store.armed = True
                else:
                    _wait_for(sync / f"checked-{subject}")
            else:
                assert gate is not None
                gate.execute(
                    text("SELECT pg_advisory_lock_shared(:k)"), {"k": cfg["gate_base"] + i}
                )
                gate.execute(
                    text("SELECT pg_advisory_unlock_shared(:k)"), {"k": cfg["gate_base"] + i}
                )
                gate.commit()
                # stagger the shred by 0, 1, 2, ... x jitter so both orders (and overlaps) occur
                time.sleep((i % cfg.get("jitter_steps", 1)) * cfg.get("jitter_s", 0.0))
            if role == "encrypt":
                blob = kr.encrypt(tenant, subject, "raw/x", 1, b"payload")
                out.update(result="ok", blob_len=len(blob))
            else:
                out.update(result="ok", destroyed=kr.shred_subject(tenant, subject))
                (sync / f"shredded-{subject}").write_text("1")
        except SubjectKeyUnavailable as e:
            out.update(result="SubjectKeyUnavailable", detail=str(e))
        except Exception as e:  # reported, and the test fails on it
            out.update(result="error", type=type(e).__name__, detail=traceback.format_exc())
        print(json.dumps(out), flush=True)
    if gate is not None:
        gate.close()
    eng.dispose()


if __name__ == "__main__":
    main(json.loads(sys.argv[1]))
