"""Breaking-change check for the public API contract (BUILD-GUIDE 4.1; BLUEPRINT §4.3; SEC-077).

    python tools/openapi-diff/openapi_diff.py
        [--base openapi/baseline/v1.yaml] [--new openapi/v1.yaml]

Compares the new document with the committed baseline and lists changes as ``breaking`` or
``info``. Exit status: 0 = no breaking change, or the major version of ``info.version`` was bumped;
1 = breaking change without a major bump; 2 = usage/parse error.

Breaking (a client written against the baseline could fail):
- an operation or path removed, or newly ``x-nf-status: disabled``; a webhook removed;
- a parameter added as required, made required, removed, moved (``in``), or its schema narrowed;
- a request body made required; a request property added as required, made required, removed
  (while the schema is closed) or narrowed (type change, enum value removed, tighter bounds);
- a documented 2xx status removed; a response media type removed; a response property removed,
  made optional or changed in type; a response enum gaining a value (exhaustive clients break);
- an operation that was public now needs authentication; the API-key scope of an operation changed.
Additive changes (new operations, optional parameters, optional request properties, new response
properties, widened request constraints) are ``info``.

Only the standard library and PyYAML (already in the dev environment) are used.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
METHODS = ("get", "put", "post", "delete", "patch", "options", "head")
_TIGHTER_IF_BIGGER = ("minimum", "exclusiveMinimum", "minLength", "minItems", "minProperties")
_TIGHTER_IF_SMALLER = ("maximum", "exclusiveMaximum", "maxLength", "maxItems", "maxProperties")


@dataclass(frozen=True)
class Change:
    level: str  # "breaking" | "info"
    where: str
    what: str

    def __str__(self) -> str:
        return f"{self.level:8} {self.where}: {self.what}"


class Differ:
    def __init__(self, old: dict[str, Any], new: dict[str, Any]) -> None:
        self.old, self.new = old, new
        self.changes: list[Change] = []

    # ---------------------------------------------------------------- helpers
    def _add(self, level: str, where: str, what: str) -> None:
        self.changes.append(Change(level, where, what))

    @staticmethod
    def _deref(
        doc: dict[str, Any], s: Any, seen: frozenset[str] = frozenset()
    ) -> tuple[Any, frozenset[str]]:
        while isinstance(s, dict) and "$ref" in s:
            ref = s["$ref"]
            if ref in seen:
                return {}, seen
            seen = seen | {ref}
            node: Any = doc
            for part in ref.removeprefix("#/").split("/"):
                node = node.get(part, {}) if isinstance(node, dict) else {}
            s = node
        return s, seen

    @staticmethod
    def _types(s: dict[str, Any]) -> set[str]:
        """The JSON types a schema admits (``anyOf``/``oneOf`` flattened, refs not followed)."""
        if not isinstance(s, dict) or not s:
            return {"any"}
        out: set[str] = set()
        for alt in s.get("anyOf", []) + s.get("oneOf", []):
            out |= Differ._types(alt) if "$ref" not in alt else {"ref:" + alt["$ref"]}
        t = s.get("type")
        if isinstance(t, list):
            out |= set(t)
        elif isinstance(t, str):
            out.add(t)
        if "$ref" in s:
            out.add("ref:" + s["$ref"])
        if "enum" in s and not t:
            out.add("enum")
        return out or {"any"}

    # ---------------------------------------------------------------- schemas
    def schema(
        self,
        old: Any,
        new: Any,
        where: str,
        direction: str,
        seen_o: frozenset[str] = frozenset(),
        seen_n: frozenset[str] = frozenset(),
        depth: int = 0,
    ) -> None:
        if depth > 40:
            return
        o, seen_o = self._deref(self.old, old, seen_o)
        n, seen_n = self._deref(self.new, new, seen_n)
        if not isinstance(o, dict) or not isinstance(n, dict):
            return
        # nullable / type
        to, tn = self._types(o), self._types(n)
        to_plain = {t for t in to if not t.startswith("ref:")}
        tn_plain = {t for t in tn if not t.startswith("ref:")}
        if "any" not in to_plain and "any" not in tn_plain and to_plain != tn_plain:
            if direction == "request":
                lost = to_plain - tn_plain
                if lost and not ("number" in tn_plain and lost <= {"integer"}):
                    self._add(
                        "breaking",
                        where,
                        f"request type narrowed {sorted(to_plain)} -> {sorted(tn_plain)}",
                    )
                elif tn_plain - to_plain:
                    self._add("info", where, f"request type widened to {sorted(tn_plain)}")
            else:
                gained = tn_plain - to_plain
                if gained and not ("number" in to_plain and gained <= {"integer"}):
                    self._add(
                        "breaking",
                        where,
                        f"response type changed {sorted(to_plain)} -> {sorted(tn_plain)}",
                    )
        # enum
        eo, en = o.get("enum"), n.get("enum")
        if eo is not None or en is not None:
            so = set(map(repr, eo)) if eo is not None else None
            sn = set(map(repr, en)) if en is not None else None
            if direction == "request":
                if sn is not None and (so is None or so - sn):
                    self._add(
                        "breaking",
                        where,
                        f"request enum narrowed (removed {sorted((so or set()) - sn) or 'all'})",
                    )
            else:
                if so is not None and (sn is None or sn - so):
                    self._add(
                        "breaking",
                        where,
                        f"response enum gained {sorted((sn or {'<any>'}) - (so or set()))}",
                    )
        # bounds (request only: a tighter bound rejects values that used to pass)
        if direction == "request":
            for k in _TIGHTER_IF_BIGGER:
                if k in n and (k not in o or n[k] > o[k]):
                    self._add("breaking", where, f"request {k} tightened to {n[k]}")
            for k in _TIGHTER_IF_SMALLER:
                if k in n and (k not in o or n[k] < o[k]):
                    self._add("breaking", where, f"request {k} tightened to {n[k]}")
            if "pattern" in n and n.get("pattern") != o.get("pattern"):
                self._add("breaking", where, "request pattern changed")
        # alternatives with refs: compare pairwise when the shapes match
        for key in ("anyOf", "oneOf", "allOf"):
            ao, an = o.get(key), n.get(key)
            if isinstance(ao, list) and isinstance(an, list) and len(ao) == len(an):
                for i, (a, b) in enumerate(zip(ao, an, strict=True)):
                    self.schema(a, b, f"{where}.{key}[{i}]", direction, seen_o, seen_n, depth + 1)
        # arrays
        if "items" in o and "items" in n:
            self.schema(o["items"], n["items"], f"{where}[]", direction, seen_o, seen_n, depth + 1)
        # objects
        po, pn = o.get("properties") or {}, n.get("properties") or {}
        ro, rn = set(o.get("required") or []), set(n.get("required") or [])
        closed = o.get("additionalProperties") is False or n.get("additionalProperties") is False
        for name in sorted(set(po) | set(pn)):
            w = f"{where}.{name}"
            if name in po and name not in pn:
                if direction == "response":
                    self._add("breaking", w, "response property removed")
                elif closed:
                    self._add("breaking", w, "request property removed from a closed schema")
                else:
                    self._add("info", w, "request property removed (ignored if sent)")
            elif name not in po and name in pn:
                if direction == "request" and name in rn:
                    self._add("breaking", w, "new required request property")
                else:
                    self._add("info", w, f"{direction} property added")
            else:
                self.schema(po[name], pn[name], w, direction, seen_o, seen_n, depth + 1)
        if direction == "request":
            for name in sorted((rn - ro) & set(po)):
                self._add("breaking", f"{where}.{name}", "request property made required")
        else:
            for name in sorted((ro - rn) & set(pn)):
                self._add("breaking", f"{where}.{name}", "response property made optional")

    # ---------------------------------------------------------------- operations
    def _params(self, op: dict[str, Any], doc: dict[str, Any]) -> dict[tuple[str, str], dict]:
        out = {}
        for p in op.get("parameters", []):
            p, _ = self._deref(doc, p)
            out[(p.get("in", ""), p.get("name", ""))] = p
        return out

    def _is_public(self, op: dict[str, Any]) -> bool:
        return op.get("security") == []

    def operation(self, where: str, o: dict[str, Any], n: dict[str, Any]) -> None:
        if o.get("x-nf-status") != "disabled" and n.get("x-nf-status") == "disabled":
            self._add("breaking", where, "operation disabled")
        if self._is_public(o) and not self._is_public(n):
            self._add("breaking", where, "public operation now requires authentication")
        if o.get("x-nf-api-key-scope") != n.get("x-nf-api-key-scope") and "x-nf-api-key-scope" in o:
            self._add("breaking", where, "API-key scope changed")
        if not o.get("deprecated") and n.get("deprecated"):
            self._add("info", where, "operation deprecated")
        # parameters
        po, pn = self._params(o, self.old), self._params(n, self.new)
        by_name_o = {k[1]: k for k in po}
        for key in sorted(set(po) | set(pn)):
            w = f"{where} param {key[1]}"
            if key in po and key not in pn:
                moved = any(k[1] == key[1] for k in pn)
                self._add("breaking", w, "parameter moved" if moved else "parameter removed")
            elif key not in po:
                if pn[key].get("required"):
                    self._add("breaking", w, "new required parameter")
                elif key[1] not in by_name_o:
                    self._add("info", w, "optional parameter added")
            else:
                if pn[key].get("required") and not po[key].get("required"):
                    self._add("breaking", w, "parameter made required")
                self.schema(po[key].get("schema", {}), pn[key].get("schema", {}), w, "request")
        # request body
        bo, bn = o.get("requestBody"), n.get("requestBody")
        if bo is None and bn is not None and bn.get("required"):
            self._add("breaking", where, "new required request body")
        if bo is not None and bn is not None:
            if bn.get("required") and not bo.get("required"):
                self._add("breaking", where, "request body made required")
            co, cn = bo.get("content", {}), bn.get("content", {})
            for mt in sorted(set(co) - set(cn)):
                self._add("breaking", where, f"request media type {mt} removed")
            for mt in sorted(set(co) & set(cn)):
                self.schema(
                    co[mt].get("schema", {}), cn[mt].get("schema", {}), f"{where} body", "request"
                )
        # responses
        ro, rn = o.get("responses", {}), n.get("responses", {})
        for code in sorted(ro):
            if not str(code).startswith("2"):
                continue
            if code not in rn:
                self._add("breaking", where, f"success response {code} removed")
                continue
            a, _ = self._deref(self.old, ro[code])
            b, _ = self._deref(self.new, rn[code])
            ca, cb = a.get("content", {}) or {}, b.get("content", {}) or {}
            for mt in sorted(set(ca) - set(cb)):
                self._add("breaking", where, f"response {code} media type {mt} removed")
            for mt in sorted(set(ca) & set(cb)):
                self.schema(
                    ca[mt].get("schema", {}),
                    cb[mt].get("schema", {}),
                    f"{where} {code}",
                    "response",
                )

    def _ops(self, doc: dict[str, Any], section: str) -> dict[str, dict[str, Any]]:
        out = {}
        for name, item in (doc.get(section) or {}).items():
            for m in METHODS:
                if isinstance(item, dict) and m in item:
                    out[f"{m.upper()} {name}"] = item[m]
        return out

    def run(self) -> list[Change]:
        for section in ("paths", "webhooks"):
            oo, on = self._ops(self.old, section), self._ops(self.new, section)
            for k in sorted(set(oo) - set(on)):
                label = "webhook" if section == "webhooks" else "operation"
                self._add("breaking", k, f"{label} removed")
            for k in sorted(set(on) - set(oo)):
                self._add("info", k, "added")
            for k in sorted(set(oo) & set(on)):
                if section == "webhooks":
                    # the platform SENDS webhooks: payloads are compared like responses
                    bo = oo[k].get("requestBody", {}).get("content", {})
                    bn = on[k].get("requestBody", {}).get("content", {})
                    for mt in sorted(set(bo) & set(bn)):
                        self.schema(
                            bo[mt].get("schema", {}),
                            bn[mt].get("schema", {}),
                            f"{k} payload",
                            "response",
                        )
                    for mt in sorted(set(bo) - set(bn)):
                        self._add("breaking", k, f"payload media type {mt} removed")
                else:
                    self.operation(k, oo[k], on[k])
        # de-duplicate (a shared schema is reached from several operations)
        seen, out = set(), []
        for c in self.changes:
            if (c.level, c.where, c.what) not in seen:
                seen.add((c.level, c.where, c.what))
                out.append(c)
        return out


def major(doc: dict[str, Any]) -> int:
    v = str(doc.get("info", {}).get("version", "0"))
    try:
        return int(v.split(".")[0])
    except ValueError:
        raise ValueError(f"info.version {v!r} is not semver") from None


def diff(old: dict[str, Any], new: dict[str, Any]) -> tuple[list[Change], bool]:
    """(changes, ok). ``ok`` is False when a breaking change comes without a major version bump."""
    changes = Differ(old, new).run()
    breaking = [c for c in changes if c.level == "breaking"]
    return changes, not breaking or major(new) > major(old)


def load(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="OpenAPI breaking-change check")
    ap.add_argument("--base", type=Path, default=ROOT / "openapi" / "baseline" / "v1.yaml")
    ap.add_argument("--new", type=Path, default=ROOT / "openapi" / "v1.yaml")
    ap.add_argument("--quiet", action="store_true", help="print breaking changes only")
    a = ap.parse_args(argv)
    try:
        old, new = load(a.base), load(a.new)
        changes, ok = diff(old, new)
    except (OSError, yaml.YAMLError, ValueError) as e:
        print(f"openapi-diff: {e}", file=sys.stderr)
        return 2
    for c in changes:
        if c.level == "breaking" or not a.quiet:
            print(c)
    n_break = sum(c.level == "breaking" for c in changes)
    if ok:
        note = " (major version bumped)" if n_break else ""
        print(
            f"openapi-diff: OK, {n_break} breaking, {len(changes) - n_break} additive{note}",
            file=sys.stderr,
        )
        return 0
    print(
        f"openapi-diff: {n_break} breaking change(s) without a major version bump "
        f"({old['info']['version']} -> {new['info']['version']}); keep v1 additive or publish v2",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
