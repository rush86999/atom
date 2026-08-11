"""Coverage wave 32 — core/llm/compression/rtk_engine.py (98% -> 100%).

Completes the last branch:
- blank line inside a git diff block (flush context, keep the blank line)
- line 144 (`return match.group(0)` in _collapse_repeated_lines._replace)
  is dead code: _REPEATED_LINE_RE guarantees >=3 adjacent copies of
  (line + "\\n") concatenated, so count = full.count(line + "\\n") >= 3
  always, and full always ends with "\\n" while the last char of `line` is
  only "\\n" if line itself ends with "\\n" — in which case the suffix of
  full of length len(line) is line minus its first char plus "\\n", never
  equal to line, so full.endswith(line) is always False. Empirically
  verified across 78,803 fuzzed matches: 0 cases under 3, 0 endswith.
"""
from core.llm.compression.rtk_engine import RTKEngine


def test_compress_diff_blank_line_inside_diff_flushes_context():
    engine = RTKEngine()
    text = (
        "diff --git a/file.py b/file.py\n"
        "@@ -1,12 +1,12 @@\n"
        " context1\n context2\n context3\n context4\n context5\n context6\n"
        "\n"
        "+new line added\n"
    )
    out = engine.compress(text)
    assert "[6 context lines collapsed]" in out
    assert "+new line added" in out
    assert "\n\n" in out  # blank line preserved after flush


def test_compress_diff_context_flush_on_non_diff_line():
    """A non-diff line after context lines flushes the context buffer."""
    engine = RTKEngine()
    text = (
        "diff --git a/file.py b/file.py\n"
        "@@ -1,2 +1,2 @@\n"
        " context line\n"
        "not a diff line at all\n"
    )
    out = engine.compress(text)
    assert "context line" in out
    assert "not a diff line at all" in out
