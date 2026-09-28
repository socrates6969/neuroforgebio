"""Fixtures for the SDK tests. ``stack`` is one in-process platform per test module (PostgreSQL via
pgserver locally or ``NF_TEST_DATABASE_URL``); tests that need it skip when no PostgreSQL is
available outside CI."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import inprocess  # noqa: E402

pytest.importorskip(
    "neuroforge._native", reason="build it first: maturin develop -m bindings/python/Cargo.toml"
)

REPO = inprocess.REPO


@pytest.fixture(scope="module")
def stack(tmp_path_factory):
    from nf_platform.db import testing

    try:
        with inprocess.platform_stack(tmp_path_factory.mktemp("stack"), grpc=True) as s:
            yield s
    except testing.PostgresUnavailable as e:
        if os.environ.get("CI"):
            raise
        pytest.skip(f"no PostgreSQL available: {e}")


@pytest.fixture
def nf_client(stack):
    import neuroforge as nf

    c = nf.configure(
        http=stack.http,
        token=stack.token,
        session=stack.session_id,
        poll_interval=0.1,
        synthetic=True,
    )
    yield c
