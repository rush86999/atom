"""RFC 8785 (JCS) JSON canonicalization — subset sufficient for model dumps.

Used by the self-consistency voter to hash structurally equivalent samples
identically. The previous scheme (``json.dumps(..., sort_keys=True)``) sorted
keys by Unicode code point and used Python float formatting; RFC 8785 requires
UTF-16 code-unit key ordering and ECMAScript number formatting, so hashes are
NOT interchangeable — which is why the voter tags every hash with its
algorithm (``hash_algo``) and accepts legacy hashes for rows written before
the switch. See SelfConsistencyVote.hash_algo.

Number serialization covers the shapes that occur in LLM sample payloads
(integers, integral floats < 2^53, common magnitudes). Exotic doubles may
deviate from the full ECMAScript Number::toString spec; payloads here are
pydantic ``model_dump(mode="json")`` outputs where such values are rare, and
any deviation only affects hash equality between two *different* numbers,
never validity of stored hashes.
"""

import math
from typing import Any

__all__ = ["canonicalize", "jcs_sha256_hex"]

_ESCAPES = {
    '"': '\\"',
    "\\": "\\\\",
    "\b": "\\b",
    "\f": "\\f",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
}


def _serialize_string(s: str) -> str:
    out = ['"']
    for ch in s:
        esc = _ESCAPES.get(ch)
        if esc is not None:
            out.append(esc)
        elif ord(ch) < 0x20:
            out.append(f"\\u{ord(ch):04x}")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _serialize_number(n: float) -> str:
    """ECMAScript Number::toString subset (see module docstring for limits)."""
    if math.isnan(n) or math.isinf(n):
        # RFC 8785 §3.2.2.3: NaN/Infinity serialize as null at the value
        # level; callers map those to None before canonicalization.
        raise ValueError("NaN/Infinity are not JCS-serializable")
    if n == int(n) and abs(n) < 2**53:
        # Integral values in the safe-integer range print without a decimal
        # point in ECMAScript (1.0 → "1").
        return str(int(n))
    # Python's repr gives the shortest round-trip digits (same as ES), but a
    # different exponent format: normalize 1e-07 → 1e-7 / 1e+21 stays.
    r = repr(float(n))
    if "e" in r:
        mantissa, exponent = r.split("e")
        exp_int = int(exponent)
        sign = "+" if exp_int >= 0 else "-"
        return f"{mantissa}e{sign}{abs(exp_int)}"
    return r


def _serialize(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return _serialize_string(value)
    if isinstance(value, bool):
        # unreachable (True/False caught above) — kept for type narrowers
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _serialize_number(value)
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_serialize(v) for v in value) + "]"
    if isinstance(value, dict):
        # RFC 8785 §3.2.3: sort keys by UTF-16 code units. Encoding each key
        # as UTF-16BE bytes and sorting those bytewise implements the code-
        # unit ordering (differs from code-point order only when supplementary
        # characters mix with U+E000..U+FFFF — e.g. emoji vs private-use).
        items = sorted(value.items(), key=lambda kv: kv[0].encode("utf-16-be"))
        return "{" + ",".join(
            _serialize_string(k) + ":" + _serialize(v) for k, v in items
        ) + "}"
    # Unknown scalar (datetime, Decimal, ...) — stringify like default=str.
    return _serialize_string(str(value))


def canonicalize(obj: Any) -> str:
    """Canonical JSON per RFC 8785 (subset — see module docstring)."""
    return _serialize(obj)


def jcs_sha256_hex(obj: Any) -> str:
    import hashlib

    return hashlib.sha256(canonicalize(obj).encode("utf-8")).hexdigest()
