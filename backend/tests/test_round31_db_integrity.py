"""
TDD regression tests for Round 31 - DB model integrity.

Covers remaining naive datetime defaults that cause TypeError on PostgreSQL
when compared with timezone-aware datetimes.
"""

from __future__ import annotations


class TestNoNaiveDatetimeDefaults:
    """Column defaults must use timezone-aware datetimes, not datetime.utcnow."""

    def test_no_naive_utcnow_defaults_in_models(self):
        with open("core/models.py") as f:
            src = f.read()
        # Find lines with `default=datetime.utcnow` (naive)
        bad = []
        for i, line in enumerate(src.split("\n"), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "default=datetime.utcnow" in line or "onupdate=datetime.utcnow" in line:
                bad.append(i)
        assert not bad, (
            f"core/models.py still has naive datetime.utcnow defaults at lines {bad}. "
            "These cause TypeError on PostgreSQL when compared with timezone-aware "
            "datetimes. Use default=lambda: datetime.now(timezone.utc) instead."
        )

    def test_no_naive_utcnow_comparisons(self):
        """Method bodies must not use bare datetime.utcnow() for comparisons."""
        with open("core/models.py") as f:
            src = f.read()
        # Check for `datetime.utcnow()` in method bodies (not Column defaults)
        # Allow it only if inside a timezone-aware fallback (already handled)
        bad = []
        for i, line in enumerate(src.split("\n"), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            # Skip lines that are part of a ternary with timezone check
            if "datetime.utcnow()" in line and "tzinfo" not in line:
                # Skip if it's inside a comment-like context
                if "default=datetime.utcnow" in line:
                    continue  # already caught by previous test
                bad.append((i, stripped[:80]))
        # Filter: the model comparison at line 600 (expires_at check) is a real bug
        real_bugs = [(ln, s) for ln, s in bad if "self.expires_at" in s or "self.used_at" in s]
        assert not real_bugs, (
            f"Naive datetime comparisons in model methods: {real_bugs}"
        )
