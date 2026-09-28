"""SEC-034a database guard (M2-REVIEW F1 extra hardening; migration 0012m6_key_tombstone).

On the real local Postgres (pgserver; NF_TEST_DATABASE_URL in CI):
- the trigger rejects a new key row for a shredded subject and any "un-shred" UPDATE;
- TWO OS PROCESSES: one crypto-shreds a subject while the other encrypts for it. In the
  deterministic interleaving the encrypt side has already passed the application's tombstone
  check when the shred commits; the database guard makes it fail loudly
  (``SubjectKeyUnavailable``) and no live key row exists afterwards. The same interleaving with
  the trigger disabled leaves a live key (negative control: the guard is what closes the window).
- free-running rounds (both processes released together per subject): every round ends with no
  live key row, and every encrypt either succeeded before the shred or raised
  ``SubjectKeyUnavailable``.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from nf_platform.db import migrate, testing
from nf_platform.db.context import Principal, tenant_session
from nf_platform.storage import Keyring, LocalKms, SubjectKeyUnavailable
from nf_platform.storage.sql_keystore import TOMBSTONE_SQLSTATE, SqlKeyStore, _tombstone_errors
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.postgres

WORKER = Path(__file__).with_name("_key_race_worker.py")
GATE_BASE = 0x5EC034A0  # advisory-lock keys used as the per-round start gate
ROUNDS = 12


@pytest.fixture
def db(pg_url, template_db) -> Iterator[tuple[str, Engine]]:
    name = f"nf_kt_{uuid.uuid4().hex[:8]}"
    url = testing.create_database(pg_url, name, template=template_db)
    eng = create_engine(url, pool_size=2, max_overflow=2)
    yield url, eng
    eng.dispose()
    testing.drop_database(pg_url, name)


def _provision(eng: Engine, n_subjects: int) -> tuple[str, list[str]]:
    tid, pid, did = (str(uuid.uuid4()) for _ in range(3))
    subs = [str(uuid.uuid4()) for _ in range(n_subjects)]
    with eng.begin() as c:  # superuser provisioning (bypasses RLS by design)
        c.execute(text("INSERT INTO tenant (id, name) VALUES (:i, 'race')"), {"i": tid})
        c.execute(
            text("INSERT INTO project (id, tenant_id, name, created_by) VALUES (:p,:t,'p','x')"),
            {"p": pid, "t": tid},
        )
        c.execute(
            text(
                "INSERT INTO dataset (id, tenant_id, project_id, name, created_by) "
                "VALUES (:d,:t,:p,'d','x')"
            ),
            {"d": did, "t": tid, "p": pid},
        )
        for i, sid in enumerate(subs):
            c.execute(
                text(
                    "INSERT INTO subject (id, tenant_id, dataset_id, label, created_by) "
                    "VALUES (:s,:t,:d,:l,'x')"
                ),
                {"s": sid, "t": tid, "d": did, "l": f"S{i}"},
            )
    return tid, subs


def _keystore(eng: Engine) -> SqlKeyStore:
    @contextmanager
    def session_for(tenant_id: str):
        p = Principal(
            id="svc-keyring",
            tenant_id=tenant_id,
            roles=frozenset({"service"}),
            scopes=frozenset(),
            kind="api_key",
            mfa_phr=False,
        )
        with tenant_session(p, engine=eng) as s:
            yield s

    return SqlKeyStore(session_for)


def _rows(eng: Engine, sid: str) -> list[tuple[int, str, bool]]:
    with eng.connect() as c:
        return [
            (r.dek_version, r.state, r.wrapped_dek is None)
            for r in c.execute(
                text(
                    "SELECT dek_version, state, wrapped_dek FROM subject_key "
                    "WHERE subject_id = :s ORDER BY dek_version"
                ),
                {"s": sid},
            )
        ]


def _live(eng: Engine, sid: str) -> list[tuple[int, str, bool]]:
    return [r for r in _rows(eng, sid) if r[1] != "shredded" or not r[2]]


def _spawn(cfg: dict[str, Any]) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, str(WORKER), json.dumps(cfg)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _collect(proc: subprocess.Popen[str]) -> list[dict[str, Any]]:
    out, err = proc.communicate(timeout=180)
    assert proc.returncode == 0, err
    return [json.loads(line) for line in out.splitlines() if line.startswith("{")]


# ---------------------------------------------------------------- single-process guard checks
def test_db_rejects_new_key_row_and_unshred_for_tombstoned_subject(db) -> None:
    _url, eng = db
    tid, (s_keyed, s_never) = _provision(eng, 2)
    ks = _keystore(eng)
    kr = Keyring(LocalKms(), ks)
    kr.encrypt(tid, s_keyed, "raw/x", 1, b"x")
    assert kr.shred_subject(tid, s_keyed) == 1
    # A subject that never had a key still gets a tombstone row (dek_version 0, no key material).
    assert kr.shred_subject(tid, s_never) == 0
    assert _rows(eng, s_never) == [(0, "shredded", True)]
    assert kr.shred_subject(tid, s_never) == 0  # idempotent: still one tombstone
    assert _rows(eng, s_never) == [(0, "shredded", True)]
    with pytest.raises(SubjectKeyUnavailable):
        kr.encrypt(tid, s_never, "raw/x", 1, b"x")

    # Bypassing the Keyring: the app role (RLS session) cannot insert a live key row ...
    for sid in (s_keyed, s_never):
        with pytest.raises(DBAPIError) as ei, ks._session_for(tid) as s:
            s.execute(
                text(
                    "INSERT INTO subject_key (tenant_id, subject_id, dek_version, kek_id, "
                    "kek_version, wrapped_dek) VALUES (:t, :s, 7, 'k', 1, '\\x00')"
                ),
                {"t": tid, "s": sid},
            )
        assert ei.value.orig.sqlstate == TOMBSTONE_SQLSTATE
    # ... nor turn a tombstone back into a live key (not even the superuser, outside a restore).
    for c_eng in (None, eng):
        with pytest.raises(DBAPIError) as ei:
            if c_eng is None:
                with ks._session_for(tid) as s:
                    s.execute(
                        text(
                            "UPDATE subject_key SET state='active', wrapped_dek='\\x01' "
                            "WHERE subject_id = :s"
                        ),
                        {"s": s_keyed},
                    )
            else:
                with c_eng.begin() as c:
                    c.execute(
                        text("UPDATE subject_key SET wrapped_dek='\\x01' WHERE subject_id = :s"),
                        {"s": s_keyed},
                    )
        assert ei.value.orig.sqlstate == TOMBSTONE_SQLSTATE
    assert _live(eng, s_keyed) == [] and _live(eng, s_never) == []


# ---------------------------------------------------------------- two OS processes
def _toctou(url: str, tid: str, sid: str, sync: Path, pre_encrypts: int) -> dict[str, Any]:
    base = {"db_url": url, "tenant": tid, "subjects": [sid], "sync_dir": str(sync)}
    enc = _spawn(
        dict(base, role="encrypt", mode="toctou", pre_encrypts=pre_encrypts, max_per_dek=1)
    )
    shr = _spawn(dict(base, role="shred", mode="toctou"))
    (e,), (s,) = _collect(enc), _collect(shr)
    assert s["result"] == "ok", s
    return e


@pytest.mark.parametrize(
    "pre_encrypts", [0, 1], ids=["first-key-insert", "retire-and-rekey-at-limit"]
)
def test_two_process_shred_vs_encrypt_toctou(db, tmp_path, pre_encrypts) -> None:
    url, eng = db
    tid, (sid,) = _provision(eng, 1)
    e = _toctou(url, tid, sid, tmp_path, pre_encrypts)
    # The encrypt side had passed the Keyring's tombstone check before the shred committed.
    assert (tmp_path / f"checked-{sid}").exists() and (tmp_path / f"shredded-{sid}").exists()
    assert e["result"] == "SubjectKeyUnavailable", e
    assert "SEC-034a" in e["detail"]
    rows = _rows(eng, sid)
    assert rows and all(state == "shredded" and no_key for _v, state, no_key in rows), rows
    assert _live(eng, sid) == []


def test_two_process_toctou_without_the_db_guard_leaves_a_live_key(db, tmp_path) -> None:
    """Negative control: same interleaving, trigger disabled -> a key survives the shred."""
    url, eng = db
    tid, (sid,) = _provision(eng, 1)
    with eng.begin() as c:
        c.execute(text("ALTER TABLE subject_key DISABLE TRIGGER subject_key_tombstone_guard"))
    e = _toctou(url, tid, sid, tmp_path, 0)
    assert e["result"] == "ok"
    assert _live(eng, sid) != []  # the window the migration closes


def _waiters(eng: Engine, key: int) -> int:
    with eng.connect() as c:
        return int(
            c.execute(
                text(
                    "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND NOT granted "
                    "AND classid = :hi AND objid = :lo"
                ),
                {"hi": key >> 32, "lo": key & 0xFFFFFFFF},
            ).scalar_one()
        )


def test_two_process_free_race_rounds(db, tmp_path) -> None:
    url, eng = db
    tid, subs = _provision(eng, ROUNDS)
    keys = [GATE_BASE + i for i in range(ROUNDS)]
    base = {"db_url": url, "tenant": tid, "subjects": subs, "sync_dir": str(tmp_path)}
    with eng.connect() as gate:
        for k in keys:  # close every start gate
            gate.execute(text("SELECT pg_advisory_lock(:k)"), {"k": k})
        gate.commit()
        enc = _spawn(dict(base, role="encrypt", mode="race", gate_base=GATE_BASE))
        shr = _spawn(
            dict(
                base, role="shred", mode="race", gate_base=GATE_BASE, jitter_steps=6, jitter_s=0.01
            )
        )
        for k in keys:  # open each gate once both processes wait at it
            deadline = time.monotonic() + 120
            while _waiters(eng, k) < 2:
                assert enc.poll() is None and shr.poll() is None, "a worker exited early"
                assert time.monotonic() < deadline, f"workers never reached gate {k}"
                time.sleep(0.01)
            gate.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": k})
            gate.commit()
        results = _collect(enc) + _collect(shr)
    by = {(r["role"], r["subject"]): r for r in results}
    outcomes = {"ok": 0, "SubjectKeyUnavailable": 0}
    for sid in subs:
        assert by[("shred", sid)]["result"] == "ok", by[("shred", sid)]
        e = by[("encrypt", sid)]
        assert e["result"] in outcomes, e  # never a silent success after the shred, never a crash
        outcomes[e["result"]] += 1
        assert _live(eng, sid) == [], (sid, _rows(eng, sid))
        assert any(state == "shredded" for _v, state, _n in _rows(eng, sid))
    print(f"SEC-034a free race over {ROUNDS} rounds: encrypt outcomes {outcomes}")


# ---------------------------------------------------------------- BUG-HUNT M4: bump_count window
class _ShredBeforeBump(SqlKeyStore):
    """Pauses the encrypt path between ``Keyring._active`` returning a live key and
    ``bump_count``: another keystore (another process's session) shreds the subject and commits
    right there."""

    def __init__(self, session_for, shredder: SqlKeyStore) -> None:
        super().__init__(session_for)
        self._shredder = shredder
        self.shreds = 0

    def bump_count(self, tenant_id: str, subject_id: str, dek_version: int, n: int = 1) -> int:
        self.shreds += self._shredder.delete_subject(tenant_id, subject_id)
        return super().bump_count(tenant_id, subject_id, dek_version, n)


class _Stored:
    """Where encrypt's output would go: nothing may land here."""

    def __init__(self) -> None:
        self.blobs: list[bytes] = []


def test_shred_between_active_key_and_bump_count_refuses_the_encryption(db) -> None:
    _url, eng = db
    tid, (sid,) = _provision(eng, 1)
    kms, plain = LocalKms(), _keystore(eng)
    Keyring(kms, plain).encrypt(tid, sid, "raw/first", 1, b"x")  # a live key exists
    ks = _ShredBeforeBump(plain._session_for, _keystore(eng))
    kr = Keyring(kms, ks)  # fresh cache; far below the per-DEK limit: _active returns that key
    stored = _Stored()
    with pytest.raises(SubjectKeyUnavailable):
        stored.blobs.append(kr.encrypt(tid, sid, "raw/second", 1, b"secret"))
    assert ks.shreds == 1  # the shred really ran inside the window
    assert stored.blobs == []  # no ciphertext produced or stored
    assert _live(eng, sid) == []
    with eng.connect() as c:
        counts = c.execute(
            text("SELECT encryption_count FROM subject_key WHERE subject_id = :s"), {"s": sid}
        ).scalars()
        assert list(counts) == [1]  # the refused encryption was not counted on the tombstone


def test_db_rejects_any_update_of_a_shredded_row(db) -> None:
    """Hardened trigger: every UPDATE of a shredded row that changes anything is refused, not
    only un-shredding (e.g. bump_count's counter, if its app-level filter were ever dropped)."""
    _url, eng = db
    tid, (sid,) = _provision(eng, 1)
    ks = _keystore(eng)
    kr = Keyring(LocalKms(), ks)
    kr.encrypt(tid, sid, "raw/x", 1, b"x")
    assert kr.shred_subject(tid, sid) == 1
    changes = [
        "encryption_count = encryption_count + 1",
        "kek_id = 'other'",
        "kek_version = kek_version + 1",
        "alg = 'X'",
        "shredded_at = now() + interval '1 day'",
    ]
    for change in changes:
        for c_eng in (None, eng):  # the app role and the superuser (outside replica mode)
            stmt = text(f"UPDATE subject_key SET {change} WHERE subject_id = :s")
            with pytest.raises(DBAPIError) as ei:
                if c_eng is None:
                    with ks._session_for(tid) as s:
                        s.execute(stmt, {"s": sid})
                else:
                    with c_eng.begin() as c:
                        c.execute(stmt, {"s": sid})
            assert ei.value.orig.sqlstate == TOMBSTONE_SQLSTATE, change
    # a no-op UPDATE is not a change: allowed
    with eng.begin() as c:
        c.execute(text("UPDATE subject_key SET state = state WHERE subject_id = :s"), {"s": sid})
    # the unfiltered counter UPDATE surfaces as SubjectKeyUnavailable through the keystore
    with pytest.raises(SubjectKeyUnavailable), _tombstone_errors(), ks._session_for(tid) as s:
        s.execute(
            text(
                "UPDATE subject_key SET encryption_count = encryption_count + 1 "
                "WHERE subject_id = :s"
            ),
            {"s": sid},
        )
    # shredding again stays a no-op and works
    assert kr.shred_subject(tid, sid) == 0
    assert _rows(eng, sid) == [(1, "shredded", True)]


def test_shred_freeze_migration_up_down(pg_url) -> None:
    name = f"nf_m_{uuid.uuid4().hex[:10]}"
    url = testing.create_database(pg_url, name)
    eng = create_engine(url)

    def body() -> str:
        with eng.connect() as c:
            return c.execute(
                text("SELECT prosrc FROM pg_proc WHERE proname = 'nf_subject_key_tombstone_guard'")
            ).scalar_one()

    try:
        migrate.upgrade(url, "0014m6_key_shred_freeze")
        assert "NEW IS DISTINCT FROM OLD" in body()
        migrate.downgrade(url, "0013m6_retrain_active")
        assert "NEW IS DISTINCT FROM OLD" not in body() and "cannot be restored" in body()
        migrate.upgrade(url, "0014m6_key_shred_freeze")
        assert "NEW IS DISTINCT FROM OLD" in body()
    finally:
        eng.dispose()
        testing.drop_database(pg_url, name)
