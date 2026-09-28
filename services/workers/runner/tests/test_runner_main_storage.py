"""NR-H1: ``python -m nf_runner`` refuses dev storage (LocalKms / NF_OBJECT_ROOT) in prod.
No database is contacted: the engine and audit sink are stubbed."""

from __future__ import annotations

import pytest
from nf_platform.audit import log as audit
from nf_platform.db import context
from nf_platform.storage.runtime import StorageConfigError
from nf_runner.__main__ import main


def test_runner_main_refuses_local_storage_in_prod(monkeypatch, tmp_path):
    monkeypatch.setattr(context, "configure_engine", lambda url: None)
    monkeypatch.setattr(audit, "configure", lambda sink: None)
    monkeypatch.setattr(audit, "PostgresAuditSink", lambda eng: None)
    for k in ("NF_S3_BUCKET_PREFIX", "NF_KMS_BACKEND"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("NF_DATABASE_URL", "postgresql+psycopg://nobody@127.0.0.1:9/none")
    monkeypatch.setenv("NF_OBJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("NF_ENVIRONMENT", "prod")
    with pytest.raises(StorageConfigError, match="LocalKms"):
        main(["--once"])
