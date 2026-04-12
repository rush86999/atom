#!/usr/bin/env python3
"""
Update quality gate thresholds based on current coverage.

This script automatically adjusts thresholds when coverage improves.
Usage: python3 .github/scripts/update-quality-threshold.py
"""

import yaml
import json
import sys
from datetime import datetime
from pathlib import Path

def load_config():
    """Load quality gate configuration."""
    config_path = Path(".github/quality-gate-config.yml")
    with open(config_path) as f:
        return yaml.safe_load(f)

def get_current_coverage(component):
    """Get current coverage from latest measurement."""
    if component == "backend":
        coverage_file = Path("backend/tests/coverage_reports/metrics/coverage_latest.json")
    else:
        coverage_file = Path("frontend-nextjs/coverage/coverage-summary.json")

    if not coverage_file.exists():
        print(f"⚠️ Coverage file not found: {coverage_file}")
        return None

    with open(coverage_file) as f:
        data = json.load(f)

    if component == "backend":
        return data["totals"]["percent_covered"]
    else:
        return data["total"]["lines"]["pct"]

def update_threshold_if_improved(config, component):
    """Update threshold if coverage has improved."""
    current_cov = get_current_coverage(component)
    if current_cov is None:
        return False

    component_config = config["quality_gates"][component]
    current_threshold = component_config["current_threshold"]

    # Auto-increment threshold if coverage exceeds by 5%
    if current_cov >= current_threshold + 5:
        new_threshold = min(current_cov, 80)  # Cap at 80%
        component_config["current_threshold"] = new_threshold
        print(f"✅ {component.capitalize()} threshold updated: {current_threshold}% → {new_threshold}%")
        return True

    print(f"ℹ️ {component.capitalize()} threshold: {current_threshold}% (coverage: {current_cov:.2f}%)")
    return False

def save_config(config):
    """Save updated configuration."""
    config_path = Path(".github/quality-gate-config.yml")
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False)

def main():
    """Main execution."""
    config = load_config()

    print("🔍 Checking coverage for threshold updates...")
    print(f"Timestamp: {datetime.now().isoformat()}")

    backend_updated = update_threshold_if_improved(config, "backend")
    frontend_updated = update_threshold_if_improved(config, "frontend")

    if backend_updated or frontend_updated:
        save_config(config)
        print("\n✅ Configuration updated. Commit the changes to apply new thresholds.")
        return 0
    else:
        print("\nℹ️ No threshold updates needed.")
        return 0

if __name__ == "__main__":
    sys.exit(main())
