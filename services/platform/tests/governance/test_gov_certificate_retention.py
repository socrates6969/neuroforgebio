"""M2-REVIEW F3 (SEC-034/120/124): the deletion certificate states when the shred is complete in
every copy, from the configured DB backup window (``NF_DB_BACKUP_WINDOW_DAYS``). The restore drill
(re-applying shreds) is ``test_gov_deletion.py::test_restore_drill_reapplies_shreds``."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from nf_platform.governance import certificate, deletion


def test_retention_statement_names_window_and_end_date():
    at = datetime(2026, 9, 26, 23, 30, tzinfo=UTC)
    assert deletion.retention_statement(at, 14) == (
        "Unrecoverable in all copies after the backup retention window of 14 days "
        "(ends 2026-10-10)."
    )
    # the end date is a UTC day, whatever the offset of the timestamp
    oslo = at.astimezone(timezone(timedelta(hours=2)))  # 2026-09-27 01:30 local
    assert "(ends 2026-10-10)" in deletion.retention_statement(oslo, 14)
    assert "0 days (ends 2026-09-26)" in deletion.retention_statement(at, 0)


def test_backup_window_comes_from_config(monkeypatch):
    monkeypatch.delenv("NF_DB_BACKUP_WINDOW_DAYS", raising=False)
    assert deletion.backup_window_days() == deletion.DEFAULT_DB_BACKUP_WINDOW_DAYS
    monkeypatch.setenv("NF_DB_BACKUP_WINDOW_DAYS", "14")
    assert deletion.backup_window_days() == 14
    monkeypatch.setenv("NF_DB_BACKUP_WINDOW_DAYS", "-1")
    with pytest.raises(ValueError):
        deletion.backup_window_days()


@pytest.mark.postgres
def test_certificate_states_backup_window(client, as_role, tree, worker, monkeypatch):
    monkeypatch.setenv("NF_DB_BACKUP_WINDOW_DAYS", "14")
    h = as_role("owner")
    assert client.post(f"/v1/runs/{tree['run_id']}/cancel", headers=h).status_code == 202
    steward = as_role("data-steward")
    r = client.post(f"/v1/subjects/{tree['subject_id']}/withdrawals", json={}, headers=steward)
    assert r.status_code == 202, r.text
    assert worker.run_once() is not None
    out = client.get(f"/v1/deletion-jobs/{r.json()['id']}", headers=steward).json()
    assert out["state"] == "succeeded", out["error"]
    cert = out["certificate"]
    kd = cert["key_destruction"]
    shredded_at = datetime.fromisoformat(kd["at"])
    ends = (shredded_at.astimezone(UTC) + timedelta(days=14)).date().isoformat()
    expected = (
        f"Unrecoverable in all copies after the backup retention window of 14 days (ends {ends})."
    )
    assert kd["db_backup_window_days"] == 14
    assert kd["statement"] == expected
    assert cert["statement"].endswith(expected)
    assert kd["unrecoverable_in_all_copies_after"].startswith(ends)
    assert "SEC-124" in kd["restore_rule"]
    key = client.get("/v1/governance/certificate-key", headers=steward).json()
    assert certificate.verify(cert, key["public_key"])  # the statement is signed
