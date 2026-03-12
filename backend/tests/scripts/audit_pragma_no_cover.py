#!/usr/bin/env python3
"""
Audit all '# pragma: no cover' directives in backend codebase.

Categories:
- LEGITIMATE: Platform-specific, unreachable defensive code, type checking only
- OUTDATED: Code that can now be tested, previously blocked tests
- QUESTIONABLE: Needs review, may be removable
"""
import re
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple

# Python 3.9+ compatibility
if sys.version_info >= (3, 9):
    from typing import Optional
else:
    from typing import Optional

# Backend directory
BACKEND_DIR = Path(__file__).parent.parent.parent

# Patterns that suggest legitimate pragmas
LEGITIMATE_PATTERNS = [
    (r'type:\s*ignore\b', 'Type checking pragma'),
    (r'if TYPE_CHECKING:', 'Type-only import'),
    (r'if sys\.platform\s*[!=]=\s*["\']darwin["\']', 'Platform-specific (macOS)'),
    (r'if sys\.platform\s*[!=]=\s*["\']linux["\']', 'Platform-specific (Linux)'),
    (r'if sys\.platform\s*[!=]=\s*["\']win32["\']', 'Platform-specific (Windows)'),
    (r'except\s*\*:', 'Bare exception handler (defensive)'),
    (r'except\s+Exception:', 'Generic exception handler'),
    (r'raise\s+NotImplementedError', 'Abstract method'),
    (r'assert\s+False', 'Unreachable code marker'),
    (r'#\s*DEBUG\s*:', 'Debug-only code'),
    (r'if __debug__:', 'Debug-only code'),
]

# Files that typically have legitimate pragmas
LEGITIMATE_FILE_PATTERNS = [
    r'.*\/__init__\.py$',  # Package imports
    r'.*\/conftest\.py$',  # Test configuration
]

def find_pragmas_in_file(file_path: Path) -> List[Dict]:
    """Find all pragma directives in a file."""
    pragmas = []
    try:
        content = file_path.read_text()
        lines = content.split('\n')

        for i, line in enumerate(lines, 1):
            if '# pragma: no cover' in line or '#pragma: no cover' in line:
                # Extract context (surrounding lines)
                context_start = max(0, i - 3)
                context_end = min(len(lines), i + 2)
                context = lines[context_start:context_end]

                # Check for legitimate patterns
                category = "QUESTIONABLE"
                reason = "No clear reason found"

                for pattern, legit_reason in LEGITIMATE_PATTERNS:
                    if re.search(pattern, line):
                        category = "LEGITIMATE"
                        reason = legit_reason
                        break

                # Check file patterns
                for pattern in LEGITIMATE_FILE_PATTERNS:
                    if re.match(pattern, str(file_path)):
                        if category != "LEGITIMATE":
                            category = "LEGITIMATE"
                            reason = "File type justification"
                        break

                pragmas.append({
                    "line_number": i,
                    "line": line.strip(),
                    "category": category,
                    "reason": reason,
                    "context": context,
                })
    except Exception as e:
        print(f"Error reading {file_path}: {e}")

    return pragmas

def audit_backend() -> Dict:
    """Audit all Python files in backend for pragmas."""
    results = {
        "audited_at": datetime.now().isoformat(),
        "files_audited": 0,
        "pragmas_found": 0,
        "by_category": {
            "LEGITIMATE": 0,
            "OUTDATED": 0,
            "QUESTIONABLE": 0,
        },
        "files": [],
    }

    # Find all Python files in backend
    py_files = list(BACKEND_DIR.rglob("*.py"))

    for py_file in py_files:
        # Skip test files and virtual environments
        if "tests" in str(py_file) or "venv" in str(py_file):
            continue

        pragmas = find_pragmas_in_file(py_file)
        if pragmas:
            results["files_audited"] += 1
            results["pragmas_found"] += len(pragmas)

            file_result = {
                "file": str(py_file.relative_to(BACKEND_DIR)),
                "pragmas": pragmas,
            }

            # Count by category
            for p in pragmas:
                results["by_category"][p["category"]] += 1

            results["files"].append(file_result)

    return results

def generate_markdown_report(results: Dict, output_path: Path):
    """Generate human-readable audit report."""
    lines = [
        "# Pragma No-Cover Audit Report",
        f"**Generated:** {results['audited_at']}",
        f"**Phase:** 171 - Gap Closure & Final Push",
        "",
        "## Summary",
        f"- **Files Audited:** {results['files_audited']}",
        f"- **Pragmas Found:** {results['pragmas_found']}",
        "",
        "## By Category",
        f"- **LEGITIMATE:** {results['by_category']['LEGITIMATE']} (keep)",
        f"- **QUESTIONABLE:** {results['by_category']['QUESTIONABLE']} (needs review)",
        f"- **OUTDATED:** {results['by_category']['OUTDATED']} (can remove)",
        "",
        "## Detailed Findings",
        ""
    ]

    for file_result in results["files"]:
        lines.append(f"### {file_result['file']}")
        lines.append("")
        lines.append(f"Total pragmas: {len(file_result['pragmas'])}")
        lines.append("")

        for pragma in file_result["pragmas"]:
            lines.append(f"**Line {pragma['line_number']}** - {pragma['category']}")
            lines.append(f"Reason: {pragma['reason']}")
            lines.append("```python")
            for ctx_line in pragma["context"]:
                lines.append(ctx_line)
            lines.append("```")
            lines.append("")

        lines.append("")

    # Add recommendations
    lines.extend([
        "## Recommendations",
        "",
        "### Immediate Actions",
        "",
        "1. **Remove OUTDATED pragmas** - These can be deleted immediately",
        "2. **Review QUESTIONABLE pragmas** - Add tests to cover these lines",
        "3. **Document LEGITIMATE pragmas** - Add inline comments for future reference",
        "",
        "### Priority Order",
        "",
        "1. Files with most QUESTIONABLE pragmas (potential coverage gain)",
        "2. Files in high-impact services (governance, LLM, episodes)",
        "3. Files with zero-coverage gaps combined with pragmas",
        "",
    ])

    output_path.write_text("\n".join(lines))
    print(f"Report written to: {output_path}")

def main():
    print("=" * 60)
    print("Auditing '# pragma: no cover' directives...")
    print("=" * 60)

    results = audit_backend()

    print(f"\nFiles audited: {results['files_audited']}")
    print(f"Pragmas found: {results['pragmas_found']}")
    print(f"\nBy category:")
    for category, count in results["by_category"].items():
        print(f"  {category}: {count}")

    # Generate report
    output_dir = Path(__file__).parent.parent / "coverage_reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "pragma_audit_report.md"

    generate_markdown_report(results, output_path)

    print("\n" + "=" * 60)
    print("Next steps:")
    print("1. Review pragma_audit_report.md")
    print("2. Run plan 171-03 to clean up outdated pragmas")
    print("=" * 60)

    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
