#!/usr/bin/env python3
"""Detect breaking changes in OpenAPI specification using openapi-diff."""
import argparse
import json
import subprocess
import sys
from pathlib import Path


def check_openapi_diff_installed():
    """Check if openapi-diff is available."""
    try:
        result = subprocess.run(
            ["npx", "openapi-diff", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def detect_breaking_changes(base_spec, current_spec, output_format="json"):
    """Compare OpenAPI specs and detect breaking changes.

    Args:
        base_spec: Path to baseline OpenAPI spec (e.g., openapi.json)
        current_spec: Path to current OpenAPI spec (newly generated)
        output_format: Output format (json or text)

    Returns:
        Dict with breaking_changes detected and details
    """
    if not check_openapi_diff_installed():
        print("ERROR: openapi-diff not found. Install with: npm install -g openapi-diff")
        sys.exit(1)

    print(f"Comparing OpenAPI specs:")
    print(f"  Base: {base_spec}")
    print(f"  Current: {current_spec}")

    result = subprocess.run([
        "npx", "openapi-diff",
        base_spec,
        current_spec,
        f"--format={output_format}"
    ], capture_output=True, text=True, timeout=30)

    diff_data = {
        "breaking_changes": [],
        "non_breaking_changes": [],
        "exit_code": result.returncode,
        "has_breaking_changes": False
    }

    # Parse JSON output
    if output_format == "json" and result.stdout:
        try:
            changes = json.loads(result.stdout)
            if isinstance(changes, list):
                diff_data["breaking_changes"] = [
                    c for c in changes
                    if c.get("severity") == "BREAKING"
                ]
                diff_data["non_breaking_changes"] = [
                    c for c in changes
                    if c.get("severity") != "BREAKING"
                ]
                diff_data["has_breaking_changes"] = len(diff_data["breaking_changes"]) > 0
        except json.JSONDecodeError:
            # Fallback to text parsing
            diff_data["raw_output"] = result.stdout
            # Check exit code for breaking changes
            diff_data["has_breaking_changes"] = result.returncode != 0

    # Check exit code as fallback
    if result.returncode != 0 and not diff_data.get("breaking_changes"):
        diff_data["has_breaking_changes"] = True

    return diff_data


def main():
    """CLI entry point for breaking change detection."""
    parser = argparse.ArgumentParser(
        description="Detect breaking API changes using OpenAPI diff"
    )
    parser.add_argument(
        "--base",
        default="backend/openapi.json",
        help="Baseline OpenAPI spec (default: backend/openapi.json)"
    )
    parser.add_argument(
        "--current",
        help="Current OpenAPI spec (default: auto-generate)"
    )
    parser.add_argument(
        "--allow-breaking",
        action="store_true",
        help="Exit 0 even if breaking changes found (for documentation)"
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Update baseline with current spec (use with care)"
    )

    args = parser.parse_args()

    # Generate current spec if not provided
    if args.current:
        current_spec = args.current
    else:
        # Generate temporary current spec
        current_spec = "/tmp/openapi_current.json"
        print("Generating current OpenAPI spec...")
        subprocess.run([
            "python", "tests/scripts/generate_openapi_spec.py",
            "-o", current_spec
        ], check=True)

    base_spec = args.base

    # Verify files exist
    if not Path(base_spec).exists():
        print(f"ERROR: Baseline spec not found: {base_spec}")
        print("Run: python tests/scripts/generate_openapi_spec.py")
        sys.exit(1)

    if not Path(current_spec).exists():
        print(f"ERROR: Current spec not found: {current_spec}")
        sys.exit(1)

    # Detect breaking changes
    result = detect_breaking_changes(base_spec, current_spec)

    # Report results
    if result.get("breaking_changes"):
        print(f"\n❌ Found {len(result['breaking_changes'])} breaking changes:")
        for change in result["breaking_changes"]:
            print(f"  - {change.get('type', 'unknown')}: {change.get('message', 'no message')}")
    elif result.get("has_breaking_changes"):
        print("\n❌ Breaking changes detected (see output above)")
    else:
        print("\n✅ No breaking changes detected")

    if result.get("non_breaking_changes"):
        print(f"\nℹ️  {len(result['non_breaking_changes'])} non-breaking changes")

    # Update baseline if requested
    if args.update_baseline:
        import shutil
        shutil.copy(current_spec, base_spec)
        print(f"\nUpdated baseline: {base_spec}")

    # Exit with error on breaking changes (unless --allow-breaking)
    if result.get("has_breaking_changes") and not args.allow_breaking:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
