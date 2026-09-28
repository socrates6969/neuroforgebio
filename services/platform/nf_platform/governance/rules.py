"""Jurisdiction RuleSets and the classification engine (BUILD-GUIDE 5.2; BLUEPRINT §8.2).

A RuleSet is versioned data in the repo (``rules/``): a manifest ``ruleset.yaml`` (``version``,
the jurisdiction files, ``content_sha256``) plus one file per jurisdiction. Every rule carries its
citation, effective date, predicate, obligations and ``review_status``:

- ``draft``: encoded from ``market/regulation.md``, not reviewed by counsel (the default);
- ``unverified``: the research summary itself marks the source as not verified (Montana);
- ``counsel-reviewed``: ONLY with a reviewer record (``review: {reviewer, reviewed_on,
  record}``). The loader refuses the status without one, so editing the word is not enough.

``content_sha256`` is SHA-256 over the canonical JSON of the parsed rules (tag
``nf.ruleset.v1``): any change to a rule without a new manifest hash (and so a new version) fails
to load.

The engine never says that data is "not regulated". A rule that does not match reports
``not matched by RuleSet vN``; a rule without a verified predicate reports ``not evaluated``.
Neither is a statement about the law.

Predicates: ``{"all": [...]}``, ``{"any": [...]}``, ``{"not": p}``, ``{"attr": a, "eq": v}``,
``{"attr": a, "in": [...]}`` over the governance attributes ``nervous_system``,
``derived_from_non_neural`` and ``modality`` (BLUEPRINT §3.2).
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from nf_platform.audit import _canonical as cj

SCHEMA_MANIFEST = "nf.ruleset/v1"
SCHEMA_FILE = "nf.jurisdiction-rules/v1"
HASH_TAG = "nf.ruleset.v1"
REVIEW_STATUSES = ("draft", "unverified", "counsel-reviewed")
ATTRS = ("nervous_system", "derived_from_non_neural", "modality")
DISCLAIMER = (
    "Not legal advice. Rules are encoded from a research summary (market/regulation.md) and are "
    "drafts until counsel has reviewed them."
)


class RuleSetError(ValueError):
    """The RuleSet files are malformed or inconsistent (the loader fails closed)."""


@dataclass(frozen=True)
class Obligation:
    id: str
    text: str
    flag: str | None = None


@dataclass(frozen=True)
class Rule:
    id: str
    jurisdiction: str
    title: str
    instrument: str
    status_text: str
    effective_date: str | None
    citation: dict[str, Any]
    predicate: dict[str, Any] | None
    obligations: tuple[Obligation, ...]
    review_status: str
    review: dict[str, Any] | None = None
    notes: str | None = None
    assumptions: tuple[str, ...] = ()

    @property
    def draft(self) -> bool:
        return self.review_status != "counsel-reviewed"

    @property
    def badge(self) -> str:
        if self.review_status == "counsel-reviewed":
            return "COUNSEL-REVIEWED"
        if self.review_status == "unverified":
            return "UNVERIFIED: source not verified; draft, not counsel-reviewed"
        return "DRAFT: not counsel-reviewed"

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "jurisdiction": self.jurisdiction,
            "title": self.title,
            "instrument": self.instrument,
            "status_text": self.status_text,
            "effective_date": self.effective_date,
            "citation": self.citation,
            "predicate": self.predicate,
            "assumptions": list(self.assumptions),
            "obligations": [
                {"id": o.id, "text": o.text, **({"flag": o.flag} if o.flag else {})}
                for o in self.obligations
            ],
            "review_status": self.review_status,
            "review": self.review,
            "draft": self.draft,
            "badge": self.badge,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class RuleSet:
    version: int
    content_sha256: str
    rules: tuple[Rule, ...]
    jurisdictions: tuple[str, ...]
    names: dict[str, str] = field(default_factory=dict)

    @property
    def label(self) -> str:
        return f"RuleSet v{self.version}"

    def not_matched(self) -> str:
        return f"not matched by {self.label}"

    def not_evaluated(self) -> str:
        return f"not evaluated by {self.label}: no verified definition"


# ---------------------------------------------------------------- loading
def default_dir() -> Path:
    env = os.environ.get("NF_RULES_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[4] / "rules"


def _load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        raise RuleSetError(f"{path.name}: cannot read ({type(e).__name__})") from e


def _check_predicate(p: Any, where: str) -> None:
    if not isinstance(p, dict) or not p:
        raise RuleSetError(f"{where}: predicate must be a mapping")
    if "all" in p or "any" in p:
        key = "all" if "all" in p else "any"
        if set(p) != {key} or not isinstance(p[key], list) or not p[key]:
            raise RuleSetError(f"{where}: '{key}' needs a non-empty list")
        for i, x in enumerate(p[key]):
            _check_predicate(x, f"{where}.{key}[{i}]")
        return
    if "not" in p:
        if set(p) != {"not"}:
            raise RuleSetError(f"{where}: 'not' takes one predicate")
        _check_predicate(p["not"], f"{where}.not")
        return
    if p.get("attr") not in ATTRS:
        raise RuleSetError(f"{where}: unknown attribute {p.get('attr')!r}")
    ops = set(p) - {"attr"}
    if ops == {"eq"}:
        return
    if ops == {"in"} and isinstance(p["in"], list) and p["in"]:
        return
    raise RuleSetError(f"{where}: use exactly one of 'eq' or 'in' (non-empty list)")


def _rule(jur: str, raw: dict[str, Any], where: str) -> Rule:
    if not isinstance(raw, dict):
        raise RuleSetError(f"{where}: rule must be a mapping")
    for k in ("id", "title", "instrument", "status_text", "citation", "obligations"):
        if not raw.get(k):
            raise RuleSetError(f"{where}: missing {k}")
    status = raw.get("review_status")
    if status not in REVIEW_STATUSES:
        raise RuleSetError(f"{where}: review_status must be one of {REVIEW_STATUSES}")
    review = raw.get("review")
    if status == "counsel-reviewed":
        ok = isinstance(review, dict) and all(
            isinstance(review.get(k), str) and review.get(k)
            for k in ("reviewer", "reviewed_on", "record")
        )
        if not ok:
            raise RuleSetError(
                f"{where}: counsel-reviewed needs a reviewer record "
                "(review: {reviewer, reviewed_on, record})"
            )
    elif review is not None:
        raise RuleSetError(f"{where}: a review record requires review_status counsel-reviewed")
    pred = raw.get("predicate")
    if pred is None:
        if status != "unverified":
            raise RuleSetError(f"{where}: only an unverified rule may have no predicate")
    else:
        _check_predicate(pred, f"{where}.predicate")
    cit = raw["citation"]
    if not isinstance(cit, dict) or not cit.get("source") or not cit.get("research_ref"):
        raise RuleSetError(f"{where}: citation needs source and research_ref")
    eff = raw.get("effective_date")
    if eff is not None and not isinstance(eff, str):
        raise RuleSetError(f"{where}: effective_date must be a quoted YYYY-MM-DD string or null")
    obligations = []
    for i, o in enumerate(raw["obligations"]):
        if not isinstance(o, dict) or not o.get("id") or not o.get("text"):
            raise RuleSetError(f"{where}.obligations[{i}]: needs id and text")
        obligations.append(
            Obligation(str(o["id"]), " ".join(str(o["text"]).split()), o.get("flag"))
        )
    return Rule(
        id=str(raw["id"]),
        jurisdiction=jur,
        title=str(raw["title"]),
        instrument=str(raw["instrument"]),
        status_text=" ".join(str(raw["status_text"]).split()),
        effective_date=eff,
        citation={k: (" ".join(str(v).split()) if v is not None else None) for k, v in cit.items()},
        predicate=pred,
        obligations=tuple(obligations),
        review_status=status,
        review=review,
        notes=" ".join(str(raw["notes"]).split()) if raw.get("notes") else None,
        assumptions=tuple(" ".join(str(a).split()) for a in raw.get("assumptions") or ()),
    )


def content_hash(rules: list[Rule]) -> str:
    doc = [r.public() for r in rules]
    return cj.sha256_hex(cj.tagged_preimage(HASH_TAG, cj.canonicalize(doc)))


def load(directory: str | Path | None = None, *, check_hash: bool = True) -> RuleSet:
    d = Path(directory) if directory is not None else default_dir()
    man = _load_yaml(d / "ruleset.yaml")
    if not isinstance(man, dict) or man.get("schema") != SCHEMA_MANIFEST:
        raise RuleSetError(f"ruleset.yaml: schema must be {SCHEMA_MANIFEST}")
    version = man.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise RuleSetError("ruleset.yaml: version must be a positive integer")
    rules: list[Rule] = []
    names: dict[str, str] = {}
    for fname in man.get("files") or ():
        doc = _load_yaml(d / str(fname))
        if not isinstance(doc, dict) or doc.get("schema") != SCHEMA_FILE:
            raise RuleSetError(f"{fname}: schema must be {SCHEMA_FILE}")
        jur = doc.get("jurisdiction")
        if not isinstance(jur, str) or not jur or jur in names:
            raise RuleSetError(f"{fname}: jurisdiction missing or duplicated")
        names[jur] = str(doc.get("name") or jur)
        for i, raw in enumerate(doc.get("rules") or ()):
            rules.append(_rule(jur, raw, f"{fname}: rules[{i}]"))
    if not rules:
        raise RuleSetError("the RuleSet has no rules")
    ids = [r.id for r in rules]
    if len(set(ids)) != len(ids):
        raise RuleSetError("rule ids must be unique")
    digest = content_hash(rules)
    if check_hash and man.get("content_sha256") != digest:
        raise RuleSetError(
            "ruleset.yaml: content_sha256 does not match the rules (a rule changed without a new "
            "RuleSet version)"
        )
    return RuleSet(version, digest, tuple(rules), tuple(names), names)


_lock = threading.Lock()
_cached: RuleSet | None = None


def current() -> RuleSet:
    """The process-wide RuleSet (loaded once from ``default_dir()``)."""
    global _cached
    with _lock:
        if _cached is None:
            _cached = load()
        return _cached


def configure(rs: RuleSet | None) -> None:
    global _cached
    with _lock:
        _cached = rs


# ---------------------------------------------------------------- evaluation
def evaluate(pred: dict[str, Any], attrs: dict[str, Any]) -> bool:
    if "all" in pred:
        return all(evaluate(p, attrs) for p in pred["all"])
    if "any" in pred:
        return any(evaluate(p, attrs) for p in pred["any"])
    if "not" in pred:
        return not evaluate(pred["not"], attrs)
    v = attrs.get(pred["attr"])
    if isinstance(v, (list, tuple, set, frozenset)):  # an artifact's modality set
        vals = set(v)
        return pred["eq"] in vals if "eq" in pred else bool(vals & set(pred["in"]))
    return v == pred["eq"] if "eq" in pred else v in pred["in"]


def classify(attrs: dict[str, Any], ruleset: RuleSet | None = None) -> dict[str, Any]:
    """One Classification: every rule's result for these governance attributes.

    ``status`` is ``matched``, ``not_matched`` (``statement``: "not matched by RuleSet vN") or
    ``not_evaluated`` (unverified rule without a predicate). ``flags`` collects obligation flags of
    matched rules (e.g. ``limit_use``, ``gdpr_art9``). ``needs_review`` is set when an attribute
    is ``unknown``: a steward must set it before a "not matched" result means anything."""
    rs = ruleset or current()
    results = []
    flags: set[str] = set()
    for r in rs.rules:
        base = {
            "jurisdiction": r.jurisdiction,
            "rule_id": r.id,
            "review_status": r.review_status,
            "draft": r.draft,
            "badge": r.badge,
        }
        if r.predicate is None:
            results.append({**base, "status": "not_evaluated", "statement": rs.not_evaluated()})
            continue
        if evaluate(r.predicate, attrs):
            obl = [o.id for o in r.obligations]
            flags |= {o.flag for o in r.obligations if o.flag}
            results.append(
                {
                    **base,
                    "status": "matched",
                    "statement": f"matched by {rs.label}",
                    "obligations": obl,
                }
            )
        else:
            results.append({**base, "status": "not_matched", "statement": rs.not_matched()})
    return {
        "ruleset": {"version": rs.version, "label": rs.label, "content_sha256": rs.content_sha256},
        "attributes": {
            k: (sorted(v) if isinstance(v, (set, frozenset)) else v) for k, v in attrs.items()
        },
        "needs_review": attrs.get("nervous_system") == "unknown",
        "matched_jurisdictions": sorted(
            {x["jurisdiction"] for x in results if x["status"] == "matched"}
        ),
        "flags": sorted(flags),
        "results": results,
        "disclaimer": DISCLAIMER,
    }


def is_classified(classification: dict[str, Any]) -> bool:
    """True when any rule matched, or when the attributes are not known yet (fail safe: unknown
    data is handled as classified until a steward sets it)."""
    return bool(classification["matched_jurisdictions"]) or bool(classification["needs_review"])
