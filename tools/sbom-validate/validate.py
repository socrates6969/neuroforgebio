"""Offline CycloneDX 1.6 JSON schema validation (EXC-150-1 condition 4; SEC-083).

Usage: python tools/sbom-validate/validate.py <bom.cdx.json> [...]
Exit 0 valid, 1 invalid, 2 usage/IO/integrity error.

The schemas are vendored in security/cyclonedx-schema/ (CycloneDX/specification tag 1.6.2,
Apache-2.0; see the README there). Before use, every schema file's SHA-256 is checked against
security/cyclonedx-schema/SHA256SUMS. The three schemas are preloaded into a `referencing` Registry
keyed by their `$id`; the Registry has NO retrieve function, so any $ref that is not one of the
vendored files raises Unresolvable instead of fetching anything: the validator never touches the
network. Uses only jsonschema/referencing from uv.lock.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from jsonschema import Draft7Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT7

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "security" / "cyclonedx-schema"
SCHEMAS = ("bom-1.6.schema.json", "spdx.schema.json", "jsf-0.82.schema.json")
ROOT = "bom-1.6.schema.json"


class IntegrityError(Exception):
    """A vendored schema file is missing or does not match its pinned SHA-256."""


def pinned_hashes(schema_dir: Path = SCHEMA_DIR) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in (schema_dir / "SHA256SUMS").read_text("utf-8").splitlines():
        if line.strip():
            digest, name = line.split(maxsplit=1)
            out[name.lstrip("*")] = digest
    return out


def load_schemas(schema_dir: Path = SCHEMA_DIR) -> dict[str, dict]:
    pins = pinned_hashes(schema_dir)
    schemas: dict[str, dict] = {}
    for name in SCHEMAS:
        raw = (schema_dir / name).read_bytes()
        got = hashlib.sha256(raw).hexdigest()
        if pins.get(name) != got:
            raise IntegrityError(
                f"{name}: sha256 {got} does not match SHA256SUMS ({pins.get(name)})"
            )
        schemas[name] = json.loads(raw)
    return schemas


def validator(schema_dir: Path = SCHEMA_DIR) -> Draft7Validator:
    schemas = load_schemas(schema_dir)
    registry = Registry().with_resources(
        (s["$id"], Resource.from_contents(s, default_specification=DRAFT7))
        for s in schemas.values()
    )
    return Draft7Validator(
        schemas[ROOT], registry=registry, format_checker=Draft7Validator.FORMAT_CHECKER
    )


def errors(bom: dict, v: Draft7Validator | None = None) -> list[str]:
    v = v or validator()
    return [
        f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
        for e in sorted(v.iter_errors(bom), key=lambda e: list(map(str, e.absolute_path)))
    ]


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: validate.py <bom.cdx.json> [...]", file=sys.stderr)
        return 2
    try:
        v = validator()
    except (OSError, IntegrityError, ValueError) as exc:
        print(f"sbom-validate: {exc}", file=sys.stderr)
        return 2
    bad = 0
    for path in argv:
        try:
            bom = json.loads(Path(path).read_text("utf-8"))
        except (OSError, ValueError) as exc:
            print(f"sbom-validate: {path}: {exc}", file=sys.stderr)
            return 2
        errs = errors(bom, v)
        for e in errs:
            print(f"{path}: {e}")
        print(f"{path}: {'INVALID' if errs else 'valid'} (CycloneDX 1.6, {len(errs)} error(s))")
        bad += bool(errs)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
