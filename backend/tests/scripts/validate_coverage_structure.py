#!/usr/bin/env python3
"""
Validate coverage JSON structure for Phase 292-295 reproducibility.

Usage:
    python validate_coverage_structure.py [--coverage-file path/to/coverage.json]
"""

import json
import sys
from pathlib import Path


def validate_coverage(coverage_path: Path) -> None:
    """Validate that coverage.json has all required structural fields."""
    with open(coverage_path) as f:
        data = json.load(f)

    errors = []

    # Check meta
    if "meta" not in data:
        errors.append("MISSING: meta")
    if "files" not in data:
        errors.append("MISSING: files")
    if "totals" not in data:
        errors.append("MISSING: totals")

    if "files" in data:
        sample_count = 0
        for fname, fdata in data["files"].items():
            if "executed_lines" not in fdata:
                errors.append(f"MISSING executed_lines in {fname}")
            if "summary" not in fdata:
                errors.append(f"MISSING summary in {fname}")
            else:
                if "percent_covered" not in fdata["summary"]:
                    errors.append(f"MISSING summary.percent_covered in {fname}")
                if "missing_lines" not in fdata:
                    errors.append(f"MISSING missing_lines in {fname}")
            sample_count += 1
            # Only check first 10 files for efficiency on large reports
            if sample_count >= 10:
                break

    # Check totals has a percentage
    if "totals" in data:
        if "percent_covered" not in data["totals"]:
            errors.append("MISSING totals.percent_covered")
        else:
            pct = data["totals"]["percent_covered"]
            if not isinstance(pct, (int, float)) or pct < 0 or pct > 100:
                errors.append(f"INVALID totals.percent_covered: {pct} (expected 0-100)")

    if errors:
        print(f"VALIDATION FAILED: {len(errors)} errors")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print(f"VALIDATION PASSED")
        print(f"Overall coverage: {data['totals']['percent_covered']:.2f}%")
        print(f"Files measured: {len(data['files'])}")


def main():
    coverage_path = Path(
        sys.argv[1] if len(sys.argv) > 1
        else "tests/coverage_reports/metrics/coverage.json"
    )
    if not coverage_path.exists():
        print(f"Error: Coverage file not found: {coverage_path}", file=sys.stderr)
        sys.exit(1)
    validate_coverage(coverage_path)


if __name__ == "__main__":
    main()
