"""NF-CJSON v1 canonical JSON (docs/spec/hashing.md §3), vendored from the spec reference.

Source: spec/reference/python/nf_canonical.py. Only canonicalisation + hashing helpers are copied; a
test checks this copy against spec/test-vectors/canonical-json.json so it cannot drift from the
spec.
"""

from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from decimal import Decimal
from typing import Any

MAX_SAFE_INT = 2**53 - 1


class CanonicalError(ValueError):
    """Input cannot be canonicalised (NaN, big integer, lone surrogate, duplicate key...)."""


# ---------------------------------------------------------------- numbers (RFC 8785 §3.2.2.3)
def format_number(x: int | float) -> str:
    """ECMAScript Number.prototype.toString for a finite double; integers must be safe."""
    if isinstance(x, bool):
        raise CanonicalError("bool is not a number")
    if isinstance(x, int):
        if abs(x) > MAX_SAFE_INT:
            raise CanonicalError(f"integer {x} exceeds 2^53-1; encode it as a string")
        return str(x)
    if not math.isfinite(x):
        raise CanonicalError("NaN and Infinity are not allowed")
    if x == 0:
        return "0"  # also -0
    sign = "-" if x < 0 else ""
    # repr() gives the shortest round-trip digits (Python >= 3.1).
    t = Decimal(repr(abs(x))).normalize().as_tuple()
    digits = "".join(map(str, t.digits))
    k = len(digits)
    n = t.exponent + k  # value = 0.d1d2..dk * 10^n
    if k <= n <= 21:
        s = digits + "0" * (n - k)
    elif 0 < n <= 21:
        s = digits[:n] + "." + digits[n:]
    elif -6 < n <= 0:
        s = "0." + "0" * (-n) + digits
    else:
        e = n - 1
        es = ("+" if e >= 0 else "-") + str(abs(e))
        s = digits + "e" + es if k == 1 else digits[0] + "." + digits[1:] + "e" + es
    return sign + s


# ---------------------------------------------------------------- strings
_ESC = {'"': '\\"', "\\": "\\\\", "\b": "\\b", "\f": "\\f", "\n": "\\n", "\r": "\\r", "\t": "\\t"}


def nfc(s: str) -> str:
    try:
        s.encode("utf-8")
    except UnicodeEncodeError as e:
        raise CanonicalError("lone surrogate in string") from e
    return unicodedata.normalize("NFC", s)


def format_string(s: str) -> str:
    out = ['"']
    for ch in nfc(s):
        if ch in _ESC:
            out.append(_ESC[ch])
        elif ord(ch) < 0x20:
            out.append(f"\\u{ord(ch):04x}")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _utf16_key(s: str) -> bytes:
    return s.encode("utf-16-be")


# ---------------------------------------------------------------- canonical JSON
def canonical_text(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return format_number(value)
    if isinstance(value, str):
        return format_string(value)
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(canonical_text(v) for v in value) + "]"
    if isinstance(value, dict):
        items: dict[str, Any] = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise CanonicalError("object keys must be strings")
            nk = nfc(k)
            if nk in items:
                raise CanonicalError(f"duplicate key after NFC: {nk!r}")
            items[nk] = v
        keys = sorted(items, key=_utf16_key)
        return "{" + ",".join(format_string(k) + ":" + canonical_text(items[k]) for k in keys) + "}"
    raise CanonicalError(f"unsupported type {type(value).__name__}")


def canonicalize(value: Any) -> bytes:
    """Canonical UTF-8 bytes of a JSON value (docs/spec/hashing.md §3)."""
    return canonical_text(value).encode("utf-8")


def _no_dupes(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    d: dict[str, Any] = {}
    for k, v in pairs:
        if k in d:
            raise CanonicalError(f"duplicate key: {k!r}")
        d[k] = v
    return d


def _bad_constant(name: str) -> Any:
    raise CanonicalError(f"{name} is not valid JSON")


def parse(text: str) -> Any:
    """Parse JSON text strictly (duplicate keys, NaN/Infinity rejected)."""
    return json.loads(text, object_pairs_hook=_no_dupes, parse_constant=_bad_constant)


def canonicalize_text(text: str) -> bytes:
    return canonicalize(parse(text))


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def tagged_preimage(tag: str, payload: bytes) -> bytes:
    return tag.encode("ascii") + b"\x00" + payload
