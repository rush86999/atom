"""Tests for the RTK tool-output compression engine.

Covers: ANSI stripping, repeated-line collapse, test-output compression,
git-diff context collapse, structured-data safety guard (JSON/SQL/XML/code
blocks are NEVER compressed — the critical safety boundary for business
automation), length cap, and pipeline metrics.
"""
import pytest

from core.llm.compression.rtk_engine import RTKEngine
from core.llm.compression import (
    CompressionMetrics,
    CompressionPipeline,
    get_compression_pipeline,
)


@pytest.fixture(scope="module")
def engine() -> RTKEngine:
    return RTKEngine()


# --- ANSI / control char stripping -----------------------------------------


def test_strips_ansi_escape_sequences(engine):
    text = "\x1b[32mSuccess\x1b[0m: \x1b[1mbuild complete\x1b[0m with all modules compiled.\nDone."
    result = engine.compress(text)
    assert "\x1b" not in result
    assert "Success" in result
    assert "build complete" in result


def test_strips_control_chars(engine):
    text = "Building\x00\x07module\x0b...\nComplete with no errors found."
    result = engine.compress(text)
    for cc in ("\x00", "\x07", "\x0b"):
        assert cc not in result


# --- Structured data safety guard (CRITICAL) -------------------------------


def test_json_never_compressed(engine):
    """JSON objects with business data must pass through untouched."""
    json_text = '{"customer": "John Smith", "invoice_total": 4847.23, "status": "disputed", "items": [{"sku": "A1", "qty": 2}]}'
    result = engine.compress(json_text)
    assert result == json_text, "JSON was modified — business data integrity risk!"
    assert "4847.23" in result


def test_json_array_never_compressed(engine):
    json_text = '[{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}, {"id": 3, "name": "Charlie"}]'
    result = engine.compress(json_text)
    assert result == json_text


def test_sql_never_compressed(engine):
    sql = "SELECT invoice_total, customer_name FROM invoices WHERE status = 'disputed' ORDER BY date DESC LIMIT 100;"
    result = engine.compress(sql)
    assert result == sql, "SQL was modified — query integrity risk!"


def test_fenced_code_blocks_never_compressed(engine):
    """When >50% of text is fenced code blocks, skip entirely."""
    code = "```\nimport os\nprint('hello world')\nfor i in range(10):\n    print(i)\n```\n"
    result = engine.compress(code)
    assert result == code


# --- Repeated line collapse ------------------------------------------------


def test_collapses_repeated_lines(engine):
    text = "Compiling module...\n" * 10 + "Build complete.\n"
    result = engine.compress(text)
    assert "repeated lines" in result
    assert "Compiling module..." in result  # first instance kept
    assert "Build complete." in result


def test_does_not_collapse_two_repeats(engine):
    """Only 3+ consecutive identical lines are collapsed."""
    text = "Running step A...\nRunning step A...\nStep A done.\n" + "x" * 50
    result = engine.compress(text)
    assert "repeated lines" not in result


# --- Test output compression -----------------------------------------------


def test_compresses_jest_output(engine):
    text = (
        "PASS src/utils/helpers.test.js\n"
        "✓ should add numbers (5ms)\n"
        "✓ should multiply (3ms)\n"
        "FAIL src/parser.test.js\n"
        "✗ should parse JSON (10ms)\n"
        "  AssertionError: expected {} to equal {key: value}\n"
        "Tests: 2 passed, 1 failed\n"
        "Test Suites: 1 failed, 1 passed, 2 total\n"
    )
    result = engine.compress(text)
    assert "FAIL" in result
    assert "AssertionError" in result
    assert "Tests:" in result or "Test Suites" in result


def test_compresses_pytest_output(engine):
    text = (
        "test_one.py::test_basic PASSED\n"
        "test_one.py::test_advanced PASSED\n"
        "test_two.py::test_fail FAILED\n"
        "test_two.py::test_fail ERROR at setup\n"
        "===== 2 passed, 1 failed, 1 error in 1.23s =====\n"
    )
    result = engine.compress(text)
    assert "FAILED" in result or "FAIL" in result
    assert "ERROR" in result
    assert "=====" in result  # summary kept


# --- Git diff context collapse ---------------------------------------------


def test_collapses_diff_context(engine):
    text = (
        "diff --git a/main.py b/main.py\n"
        "@@ -10,5 +10,5 @@\n"
        " context line 1\n"
        " context line 2\n"
        " context line 3\n"
        " context line 4\n"
        " context line 5\n"
        " context line 6\n"
        "-old line\n"
        "+new line\n"
        " context line 7\n"
    )
    result = engine.compress(text)
    assert "+new line" in result
    assert "-old line" in result
    assert "context lines collapsed" in result


# --- Short text passthrough ------------------------------------------------


def test_short_text_unchanged(engine):
    text = "Short text."
    assert engine.compress(text) == text


def test_empty_text_unchanged(engine):
    assert engine.compress("") == ""
    assert engine.compress("   ") == "   "


# --- Pipeline metrics ------------------------------------------------------


def test_pipeline_returns_metrics():
    pipeline = get_compression_pipeline()
    verbose = ("Running build step...\n" * 20) + "BUILD FAILED: error in main.py\n"
    result, metrics = pipeline.compress_tool_output(verbose)
    assert isinstance(metrics, CompressionMetrics)
    assert metrics.original_tokens > 0
    assert metrics.savings_tokens > 0
    assert metrics.savings_pct > 0
    assert "rtk" in metrics.engines_applied


def test_pipeline_metrics_to_dict():
    m = CompressionMetrics(original_tokens=100, compressed_tokens=30, engines_applied=["rtk"])
    d = m.to_dict()
    assert d["savings_tokens"] == 70
    assert d["savings_pct"] == 70.0
    assert d["engines_applied"] == ["rtk"]


def test_pipeline_singleton():
    a = get_compression_pipeline()
    b = get_compression_pipeline()
    assert a is b


# --- Length cap ------------------------------------------------------------


def test_length_cap_truncates(engine, monkeypatch):
    monkeypatch.setattr("core.llm.compression.RTK_MAX_SECTION_CHARS", 200)
    # Use varied lines so they DON'T collapse via repeated-line detection,
    # forcing the length cap to fire.
    long_text = "\n".join(f"Unique log line number {i} with some content here." for i in range(100))
    result = engine.compress(long_text)
    assert len(result) <= 300  # capped + marker
    assert "truncated" in result
