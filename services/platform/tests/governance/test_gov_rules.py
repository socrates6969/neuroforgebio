"""5.2 acceptance: RuleSet format, classification engine, jurisdiction-rules API.

- table-driven: EMG (peripheral) is matched by CO and CA and NOT by CT; a CA channel with
  derived_from_non_neural=true is not matched by CA; ...
- the API never outputs "not regulated", only "not matched by RuleSet vN";
- every rule without counsel-reviewed status carries a draft flag and badge; nothing in the repo
  is counsel-reviewed (an owner action) and the status needs a reviewer record;
- facts come only from market/regulation.md: every quoted definition appears there verbatim.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest
import yaml
from nf_platform.governance import rules

ROOT = Path(__file__).resolve().parents[4]
REGULATION = ROOT / "market" / "regulation.md"

# (attributes) -> jurisdictions whose rule must match; MT is never evaluated (unverified)
CASES = [
    (
        "EMG peripheral",
        {"nervous_system": "peripheral", "derived_from_non_neural": False, "modality": "EMG"},
        {"CO", "CA", "EU"},
    ),
    (
        "EEG central",
        {"nervous_system": "central", "derived_from_non_neural": False, "modality": "EEG"},
        {"CO", "CA", "CT", "EU"},
    ),
    (
        "CA channel inferred from non-neural data",
        {"nervous_system": "central", "derived_from_non_neural": True, "modality": "EEG"},
        {"CO", "CT", "EU"},
    ),
    (
        "EMG inferred from non-neural data",
        {"nervous_system": "peripheral", "derived_from_non_neural": True, "modality": "EMG"},
        {"CO", "EU"},
    ),
    (
        "unknown",
        {"nervous_system": "unknown", "derived_from_non_neural": False, "modality": "ECG"},
        set(),
    ),
    (
        "artifact modality set",
        {"nervous_system": "central", "derived_from_non_neural": False, "modality": ["EEG", "EMG"]},
        {"CO", "CA", "CT", "EU"},
    ),
]


@pytest.mark.parametrize(("name", "attrs", "matched"), CASES, ids=[c[0] for c in CASES])
def test_classification_table(name, attrs, matched):
    c = rules.classify(attrs)
    by = {r["jurisdiction"]: r for r in c["results"]}
    assert set(c["matched_jurisdictions"]) == matched, name
    for jur, r in by.items():
        if jur == "MT":
            assert r["status"] == "not_evaluated"
            assert r["statement"].startswith("not evaluated by RuleSet v1")
        elif jur in matched:
            assert r["status"] == "matched" and r["obligations"]
        else:
            assert r["status"] == "not_matched"
            assert r["statement"] == "not matched by RuleSet v1"
        assert r["draft"] is True and r["badge"].startswith(("DRAFT", "UNVERIFIED"))
    assert c["needs_review"] == (attrs["nervous_system"] == "unknown")
    assert ("limit_use" in c["flags"]) == ("CA" in matched)
    assert "not regulated" not in repr(c).lower()


def test_emg_acceptance_row_explicitly():
    """BUILD-GUIDE 5.2: EMG (peripheral) matched by CO and CA, not by CT; a CA channel with
    derived_from_non_neural=true not matched by CA."""
    emg = rules.classify(
        {"nervous_system": "peripheral", "derived_from_non_neural": False, "modality": "EMG"}
    )
    st = {r["jurisdiction"]: r["status"] for r in emg["results"]}
    assert (st["CO"], st["CA"], st["CT"]) == ("matched", "matched", "not_matched")
    ca = rules.classify(
        {"nervous_system": "central", "derived_from_non_neural": True, "modality": "EEG"}
    )
    assert {r["jurisdiction"]: r["status"] for r in ca["results"]}["CA"] == "not_matched"


def test_repo_ruleset_is_draft_and_sourced_from_regulation_md():
    rs = rules.load()
    assert rs.version == 1 and rs.label == "RuleSet v1"
    assert set(rs.jurisdictions) == {"CO", "CA", "CT", "MT", "EU"}
    md = REGULATION.read_text(encoding="utf-8").replace("**", "")
    md_flat = " ".join(md.split())
    for r in rs.rules:
        assert r.review_status in ("draft", "unverified"), r.id  # counsel review = owner action
        assert r.review is None and r.draft
        assert r.citation["research_ref"].startswith("market/regulation.md")
        d = r.citation.get("definition")
        if d:
            assert d in md_flat, f"{r.id}: definition not verbatim in regulation.md"
        for token in re.findall(
            r"\b(?:HB24-1058|SB 1223|PA 25-113|SB 163|Ch\. 887)\b", r.instrument
        ):
            assert token in md_flat, token
    by = {r.jurisdiction: r for r in rs.rules}
    assert by["MT"].review_status == "unverified" and by["MT"].predicate is None
    assert by["CO"].effective_date == "2024-08-07" and "7 Aug 2024" in md
    assert by["CT"].effective_date == "2026-07-01" and "Effective July 1, 2026" in md
    assert by["CA"].effective_date is None and by["EU"].effective_date is None  # none invented


def _copy(tmp_path: Path) -> Path:
    d = tmp_path / "rules"
    shutil.copytree(ROOT / "rules", d)
    return d


def _edit(d: Path, fname: str, fn) -> None:
    doc = yaml.safe_load((d / fname).read_text(encoding="utf-8"))
    fn(doc)
    (d / fname).write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")


def _rehash(d: Path) -> None:
    man = yaml.safe_load((d / "ruleset.yaml").read_text(encoding="utf-8"))
    man["content_sha256"] = rules.load(d, check_hash=False).content_sha256
    (d / "ruleset.yaml").write_text(yaml.safe_dump(man, sort_keys=False), encoding="utf-8")


def test_counsel_reviewed_needs_a_reviewer_record(tmp_path):
    d = _copy(tmp_path)
    _edit(d, "ct.yaml", lambda doc: doc["rules"][0].update(review_status="counsel-reviewed"))
    with pytest.raises(rules.RuleSetError, match="reviewer record"):
        rules.load(d, check_hash=False)
    rec = {"reviewer": "Counsel X (placeholder)", "reviewed_on": "2026-10-01", "record": "doc-1"}
    _edit(d, "ct.yaml", lambda doc: doc["rules"][0].update(review=rec))
    _rehash(d)
    rs = rules.load(d)
    ct = next(r for r in rs.rules if r.jurisdiction == "CT")
    assert ct.review_status == "counsel-reviewed" and not ct.draft
    assert ct.badge == "COUNSEL-REVIEWED"
    # a review record on a draft rule is refused as well
    d2 = _copy(tmp_path / "b")
    _edit(d2, "co.yaml", lambda doc: doc["rules"][0].update(review=rec))
    with pytest.raises(rules.RuleSetError, match="requires review_status"):
        rules.load(d2, check_hash=False)


def test_rule_change_without_new_version_hash_is_refused(tmp_path):
    d = _copy(tmp_path)
    _edit(d, "ct.yaml", lambda doc: doc["rules"][0]["predicate"]["all"][0].update(eq="peripheral"))
    with pytest.raises(rules.RuleSetError, match="content_sha256"):
        rules.load(d)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda doc: doc["rules"][0]["predicate"]["all"][0].update(attr="age"),
        lambda doc: doc["rules"][0].update(predicate=None),  # only unverified may lack one
        lambda doc: doc["rules"][0].update(review_status="final"),
        lambda doc: doc["rules"][0]["citation"].pop("research_ref"),
    ],
)
def test_loader_rejects_malformed_rules(tmp_path, mutate):
    d = _copy(tmp_path)
    _edit(d, "co.yaml", mutate)
    with pytest.raises(rules.RuleSetError):
        rules.load(d, check_hash=False)


def test_api_never_says_not_regulated(client, as_role, tree):
    h = as_role("viewer")
    r = client.get("/v1/jurisdiction-rules", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["label"] == "RuleSet v1" and len(body["rules"]) == 5
    assert all(x["draft"] and x["badge"] for x in body["rules"])
    assert {x["jurisdiction"]: x["review_status"] for x in body["rules"]}["MT"] == "unverified"
    assert "not legal advice" in body["disclaimer"].lower()
    c = client.get(f"/v1/classifications?recording_id={tree['recording_id']}", headers=h)
    assert c.status_code == 200, c.text
    out = c.json()
    emg = next(ch for ch in out["channels"] if ch["name"] == "EMG1")["classification"]
    assert set(emg["matched_jurisdictions"]) == {"CO", "CA", "EU"}
    ct = next(x for x in emg["results"] if x["jurisdiction"] == "CT")
    assert ct["statement"] == "not matched by RuleSet v1"
    for text in (r.text, c.text):
        assert "not regulated" not in text.lower()
        assert "unregulated" not in text.lower()
    assert client.get("/v1/classifications", headers=h).status_code == 422
