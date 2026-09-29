"""Tests for core.log_redaction.

The contract under test is negative: no value that reaches a log line may be
recoverable from it. Each test therefore asserts on the ABSENCE of the
sensitive literal, not merely on the presence of a replacement, because a
shape helper that leaked a value inside a length field would still pass a
"does it log a length?" test.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import log_redaction as L  # noqa: E402

SECRET = "steve@example.com"
BODY = "PRIVATE-BODY-TEXT"


def _ctx():
    return {"canvas": {"id": "canvas-1"}, "canvas_content": BODY, "n": 3}


def test_shape_never_contains_content():
    out = json.dumps(L.shape(_ctx()))
    assert SECRET not in out
    assert BODY not in out


def test_shape_preserves_schema():
    s = L.shape(_ctx())
    # keys, nesting and types are the diagnostic signal and must survive
    assert set(s) == {"canvas", "canvas_content", "n"}
    assert s["n"] == "int"
    assert s["canvas"]["id"] == "str(len=8)"
    assert s["canvas_content"] == f"str(len={len(BODY)})"


def test_describe_string_is_length_and_fingerprint_only():
    msg = "change the quote validity to 30 days"
    line = L.describe(msg)
    assert "30 days" not in line
    assert f"len={len(msg)}" in line
    assert L.fingerprint(msg) in line


def test_fingerprint_is_stable_for_equal_content():
    assert L.fingerprint("abc") == L.fingerprint("abc")
    assert L.fingerprint("abc") != L.fingerprint("abd")
    # dicts fingerprint by content, not by insertion order
    assert L.fingerprint({"a": 1, "b": 2}) == L.fingerprint({"b": 2, "a": 1})


def test_shape_bounds_recursion_and_width():
    deep = {"a": {"b": {"c": {"d": {"e": {"f": 1}}}}}}
    assert "..." in json.dumps(L.shape(deep))
    wide = L.shape({str(i): i for i in range(100)})
    assert any("more keys" in str(v) for v in wide.values())


def test_capture_is_off_by_default():
    assert L.capture_enabled() is False
    assert L.capture(_ctx(), "t") is None


def test_capture_writes_payload_to_separate_file_only():
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "evidence.jsonl")
        os.environ["ATOM_ACCEPTANCE_CAPTURE_PAYLOAD"] = path
        try:
            assert L.capture_enabled() is True
            assert L.capture(_ctx(), "chat_message") == path
            rec = json.loads(Path(path).read_text().splitlines()[0])
            assert rec["label"] == "chat_message"
            assert rec["payload"]["canvas_content"] == BODY
            # the shape recorded alongside it is still value-free
            assert BODY not in json.dumps(rec["shape"])
        finally:
            os.environ.pop("ATOM_ACCEPTANCE_CAPTURE_PAYLOAD", None)


def test_capture_does_not_leak_into_stdout_logging():
    """A routine log line must not acquire the payload when capture is on."""
    script = (
        "import sys; sys.path.insert(0, %r)\n"
        "import logging, os\n"
        "from core import log_redaction as L\n"
        "logging.basicConfig(level=logging.INFO, stream=sys.stdout, "
        "format='%%(message)s')\n"
        "L.capture({'canvas_content': %r}, 'x')\n"
        "logging.getLogger('t').info('ctx=%%s', L.describe("
        "{'canvas_content': %r}, 'shape'))\n"
    ) % (str(Path(__file__).resolve().parents[2]), BODY, BODY)
    with tempfile.TemporaryDirectory() as td:
        env = dict(os.environ, ATOM_ACCEPTANCE_CAPTURE_PAYLOAD=os.path.join(td, "e.jsonl"))
        r = subprocess.run([sys.executable, "-c", script], capture_output=True,
                           text=True, env=env, timeout=120)
    assert r.returncode == 0, r.stderr
    assert BODY not in r.stdout
    assert "canvas_content" in r.stdout
