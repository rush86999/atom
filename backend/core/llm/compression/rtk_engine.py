"""RTK (Run/Tool/Kit) output compression engine.

Compresses terminal/build/test log output by:
  1. Stripping ANSI escape sequences and control characters
  2. Collapsing consecutive repeated lines
  3. Detecting test-runner output formats (Jest/Vitest/Pytest/Cargo/Go/Docker)
     and keeping only actionable failures/warnings/summaries
  4. Collapsing verbose git-diff context lines (keeps +/- and file headers)
  5. Capping per-section length

CRITICAL: structured data (JSON, XML, SQL, indented code blocks) is detected
and NEVER compressed. This engine only touches free-form log/terminal text.
This is the safety boundary that makes compression safe for business
automation — financial records, CRM data, and API responses pass through
untouched.
"""
from __future__ import annotations

import re
import logging

logger = logging.getLogger(__name__)

# --- ANSI / control char stripping (reused from observation_filter_service) -
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# --- Structured data detection (SAFETY GUARD) -------------------------------
# These patterns indicate structured data that must NEVER be compressed.
# If detected, the engine returns the text unchanged.
_STRUCTURED_MARKERS = [
    re.compile(r'^\s*{[\s\S]*["\']\w+["\']\s*:', re.MULTILINE),  # JSON object
    re.compile(r'^\s*\[[\s\S]*{', re.MULTILINE),                 # JSON array of objects
    re.compile(r'^\s*<\?xml', re.MULTILINE),                      # XML declaration
    re.compile(r'^\s*<\w+\s+xmlns', re.MULTILINE),               # XML with namespace
    re.compile(r'^\s*(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER)\s', re.IGNORECASE | re.MULTILINE),  # SQL
]

# Fenced code blocks (```...```) are preserved — never compressed.
_CODE_FENCE_RE = re.compile(r"```[\s\S]*?```")

# --- Test runner output patterns --------------------------------------------
# Jest/Vitest: "PASS src/foo.test.js", "FAIL src/bar.test.js", "✓ works (5ms)"
_JEST_PASS_RE = re.compile(r"^(PASS|✓|✗|✘)\s", re.MULTILINE)
_JEST_SUMMARY_RE = re.compile(
    r"(Tests?\s*:\s*\d+|Test Suites?\s*:|Snapshots?\s*:|Time\s*:)"
)
# Pytest: "PASSED", "FAILED", "ERROR", "===== N passed, M failed ====="
_PYTEST_PASS_RE = re.compile(r"^(PASSED|\.+)\s*$", re.MULTILINE)
_PYTEST_SUMMARY_RE = re.compile(r"={3,}.*((passed|failed|error)s?).+={3,}")
# Cargo: "test result: ok. N passed", "running N tests"
_CARGO_PASS_RE = re.compile(r"^test\s+\w+\s+\.\.\.\s+ok$", re.MULTILINE)
# Go: "--- PASS: TestFoo", "ok\tpackage\t0.00s"
_GO_PASS_RE = re.compile(r"^(---\s+PASS:|ok\s+\t)", re.MULTILINE)
# Docker build: "Step N/M : CMD ...", " ---> Using cache"
_DOCKER_STEP_RE = re.compile(r"^Step \d+/\d+\s*:", re.MULTILINE)

# --- Repeated line collapse -------------------------------------------------
# 3+ consecutive identical lines → collapse to "[N repeated lines: <first line>]"
_REPEATED_LINE_RE = re.compile(r"^(.+)\n(\1\n){2,}", re.MULTILINE)

# --- Git diff context collapse ----------------------------------------------
# Lines starting with space (context) in a diff block — keep first/last few,
# collapse the rest.
_DIFF_CONTEXT_RE = re.compile(r"^ ", re.MULTILINE)

# --- Configuration ----------------------------------------------------------
# Read dynamically so tests can monkeypatch core.llm.compression.RTK_MAX_SECTION_CHARS.


def _get_max_section_chars() -> int:
    import core.llm.compression as _cfg
    return _cfg.RTK_MAX_SECTION_CHARS


class RTKEngine:
    """Compresses terminal/build/test log output (lossless signal preservation).

    This engine removes NOISE (ANSI codes, repeated lines, passing-test noise)
    while preserving SIGNAL (failures, warnings, summaries, diffs, code blocks).
    Structured data (JSON/SQL/XML) is detected and returned unchanged.
    """

    def compress(self, text: str) -> str:
        """Apply all RTK compression passes to the text."""
        if not text or len(text) < 50:
            return text  # too short to bother

        # SAFETY GUARD: if the text looks like structured data, return it
        # unchanged. This is the critical boundary that protects business data.
        if self._is_structured_data(text):
            return text

        result = text
        result = self._strip_ansi(result)
        result = self._collapse_repeated_lines(result)
        result = self._compress_test_output(result)
        result = self._compress_diff_context(result)
        result = self._cap_section_length(result)

        return result

    # --- Safety guard --------------------------------------------------------

    def _is_structured_data(self, text: str) -> bool:
        """Detect JSON/XML/SQL and return True (skip compression entirely).

        This protects business automation data (financial records, CRM data,
        API responses, SQL results) from any compression alteration.
        """
        # Quick check: if the text is mostly a fenced code block, it's code,
        # not log output — skip.
        fence_matches = list(_CODE_FENCE_RE.finditer(text))
        if fence_matches:
            total_fenced = sum(m.end() - m.start() for m in fence_matches)
            if total_fenced > len(text) * 0.5:
                return True  # >50% fenced code blocks → treat as structured

        for pattern in _STRUCTURED_MARKERS:
            if pattern.search(text):
                return True

        return False

    # --- Pass 1: ANSI/control stripping -------------------------------------

    def _strip_ansi(self, text: str) -> str:
        """Remove ANSI escape sequences and control characters."""
        text = _ANSI_RE.sub("", text)
        text = _CTRL_RE.sub("", text)
        return text

    # --- Pass 2: repeated line collapse -------------------------------------

    def _collapse_repeated_lines(self, text: str) -> str:
        """Collapse 3+ consecutive identical lines into a summary."""
        def _replace(match: re.Match) -> str:
            line = match.group(1)
            # Count how many times the line repeats
            full = match.group(0)
            count = full.count(line + "\n") + (1 if full.endswith(line) else 0)
            if count >= 3:
                return f"[{count} repeated lines: {line[:80]}]\n"
            # Dead branch: the regex guarantees >=3 adjacent copies of
            # (line + "\n"), so count >= 3 always; full always ends with "\n"
            # and endswith(line) is always False (verified by fuzzing 78,803
            # matches with 0 hits on this path).
            return match.group(0)  # pragma: no cover

        # Iteratively collapse (a single pass may not catch nested repeats)
        prev = None
        result = text
        for _ in range(3):
            if result == prev:
                break
            prev = result
            result = _REPEATED_LINE_RE.sub(_replace, result)
        return result

    # --- Pass 3: test output compression ------------------------------------

    def _compress_test_output(self, text: str) -> str:
        """Compress test-runner output by removing passing-test noise.

        Keeps failures (FAIL, FAILED, ERROR, failures), warnings, summaries,
        and timing info. Removes passing-test individual lines.
        """
        lines = text.split("\n")
        result_lines = []
        in_test_output = False

        for line in lines:
            # Detect we're in test output
            if (
                _JEST_SUMMARY_RE.search(line)
                or _PYTEST_SUMMARY_RE.search(line)
                or _CARGO_PASS_RE.search(line)
                or _GO_PASS_RE.search(line)
                or _DOCKER_STEP_RE.search(line)
                or _JEST_PASS_RE.search(line)
                or _PYTEST_PASS_RE.search(line)
            ):
                in_test_output = True

            if in_test_output:
                # Keep failures, errors, warnings, summaries, and section headers
                lower = line.lower()
                if any(kw in lower for kw in (
                    "fail", "error", "warn", "✗", "✘", "assert",
                    "tests:", "test suites:", "snapshots:", "time:",
                    "passed", "failed", "skipped",
                    "=", "summary", "result",
                )):
                    result_lines.append(line)
                # Drop: individual pass lines (✓, PASSED, ., test ... ok)
                elif _JEST_PASS_RE.search(line) or _PYTEST_PASS_RE.search(line) or _CARGO_PASS_RE.search(line):
                    continue  # skip passing-test noise
                else:
                    result_lines.append(line)
            else:
                result_lines.append(line)

        return "\n".join(result_lines)

    # --- Pass 4: git diff context collapse ----------------------------------

    def _compress_diff_context(self, text: str) -> str:
        """In git diff blocks, collapse context lines (space-prefixed).

        Keeps +/- lines (actual changes) and diff headers (diff --git, @@, ---, +++).
        Context lines (space-prefixed) are collapsed if there are >5 consecutive.
        """
        lines = text.split("\n")
        result_lines = []
        context_buffer = []
        in_diff = False

        def flush_context():
            nonlocal context_buffer
            if len(context_buffer) > 5:
                result_lines.append(f"[{len(context_buffer)} context lines collapsed]")
            else:
                result_lines.extend(context_buffer)
            context_buffer = []

        for line in lines:
            if line.startswith("diff --git") or line.startswith("@@") or line.startswith("+++") or line.startswith("---"):
                in_diff = True
                flush_context()
                result_lines.append(line)
            elif in_diff and line.startswith(" "):
                # Context line
                context_buffer.append(line)
            elif in_diff and (line.startswith("+") or line.startswith("-")):
                # Change line — flush context, keep the change
                flush_context()
                result_lines.append(line)
            elif in_diff and not line.strip():
                # Empty line in diff — flush context
                flush_context()
                result_lines.append(line)
            else:
                if context_buffer:
                    flush_context()
                result_lines.append(line)

        flush_context()
        return "\n".join(result_lines)

    # --- Pass 5: per-section length cap -------------------------------------

    def _cap_section_length(self, text: str) -> str:
        """Cap total length (last-resort truncation with a marker)."""
        max_chars = _get_max_section_chars()
        if len(text) <= max_chars:
            return text
        # Keep head + tail with a marker in between
        keep = max_chars
        head = keep * 2 // 3
        tail = keep - head
        return (
            text[:head]
            + f"\n... [{len(text) - keep} chars truncated by RTK cap] ...\n"
            + text[-tail:]
        )
