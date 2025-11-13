#!/usr/bin/env python3
"""
File Organization Automation Script for ATOM Project
Enforces file organization rules to maintain clean project structure
"""

import argparse
import fnmatch
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List


class FileOrganizer:
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root).resolve()
        # Look for rules file in multiple possible locations
        possible_locations = [
            self.project_root / ".file-organization-rules.json",
            self.project_root / "config" / ".file-organization-rules.json",
        ]

        for location in possible_locations:
            if location.exists():
                self.rules_file = location
                break
        else:
            self.rules_file = possible_locations[0]  # Use first location as default
        self.setup_logging()
        self.load_rules()

    def setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(
                    self.project_root / "logs" / "file-organization.log"
                ),
                logging.StreamHandler(),
            ],
        )
        self.logger = logging.getLogger(__name__)

    def load_rules(self):
        """Load organization rules from JSON file"""
        if not self.rules_file.exists():
            raise FileNotFoundError(f"Rules file not found: {self.rules_file}")

        with open(self.rules_file, "r") as f:
            self.rules = json.load(f)

        self.logger.info(f"Loaded {len(self.rules['rules'])} organization rules")

    def is_protected(self, file_path: Path) -> bool:
        """Check if a file or directory is protected from organization"""
        # Check protected files
        if file_path.name in self.rules.get("protected_files", []):
            return True

        # Check protected directories
        for protected_dir in self.rules.get("protected_directories", []):
            if protected_dir in str(file_path.relative_to(self.project_root)):
                return True

        return False

    def get_target_directory(self, file_path: Path) -> str:
        """Determine target directory for a file based on rules"""
        filename = file_path.name

        # Sort rules by priority (highest first)
        sorted_rules = sorted(
            self.rules["rules"], key=lambda x: x.get("priority", 999), reverse=True
        )

        for rule in sorted_rules:
            pattern = rule["pattern"]

            # Check if file matches pattern
            if fnmatch.fnmatch(filename, pattern):
                # Check exceptions
                exceptions = rule.get("exceptions", [])
                for exception in exceptions:
                    if fnmatch.fnmatch(filename, exception):
                        continue  # Skip this rule, check next one

                self.logger.debug(
                    f"File {filename} matched rule: {rule['description']}"
                )
                return rule["target_directory"]

        return None

    def scan_root_directory(self) -> List[Path]:
        """Scan root directory for files that need organization"""
        root_files = []

        for item in self.project_root.iterdir():
            if item.is_file() and not self.is_protected(item):
                root_files.append(item)

        return root_files

    def organize_file(self, file_path: Path, dry_run: bool = False) -> bool:
        """Organize a single file according to rules"""
        if self.is_protected(file_path):
            self.logger.debug(f"Skipping protected file: {file_path}")
            return False

        target_dir_name = self.get_target_directory(file_path)
        if not target_dir_name:
            self.logger.debug(f"No rule found for file: {file_path}")
            return False

        target_dir = self.project_root / target_dir_name
        target_path = target_dir / file_path.name

        # Check if target directory exists
        if not target_dir.exists():
            if dry_run:
                self.logger.info(f"Would create directory: {target_dir}")
            else:
                target_dir.mkdir(parents=True, exist_ok=True)
                self.logger.info(f"Created directory: {target_dir}")

        # Check for conflicts
        if target_path.exists():
            self.logger.warning(f"Target file already exists: {target_path}")
            return False

        # Move the file
        if dry_run:
            self.logger.info(f"Would move: {file_path} -> {target_path}")
            return True
        else:
            try:
                shutil.move(str(file_path), str(target_path))
                self.logger.info(f"Moved: {file_path} -> {target_path}")
                return True
            except Exception as e:
                self.logger.error(f"Failed to move {file_path}: {e}")
                return False

    def organize_all(self, dry_run: bool = False) -> Dict[str, Any]:
        """Organize all files in root directory according to rules"""
        self.logger.info(f"Starting file organization (dry_run: {dry_run})")

        root_files = self.scan_root_directory()
        results = {
            "total_files": len(root_files),
            "organized": 0,
            "skipped": 0,
            "failed": 0,
            "details": [],
        }

        for file_path in root_files:
            if self.organize_file(file_path, dry_run):
                results["organized"] += 1
                results["details"].append(
                    {
                        "file": file_path.name,
                        "action": "moved" if not dry_run else "would_move",
                        "status": "success",
                    }
                )
            else:
                results["skipped"] += 1
                results["details"].append(
                    {
                        "file": file_path.name,
                        "action": "skipped",
                        "status": "no_rule_or_protected",
                    }
                )

        self.logger.info(
            f"Organization complete: {results['organized']} files organized, "
            f"{results['skipped']} skipped, {results['failed']} failed"
        )

        return results

    def validate_structure(self) -> Dict[str, Any]:
        """Validate current project structure against rules"""
        self.logger.info("Validating project structure...")

        violations = []
        root_files = self.scan_root_directory()

        for file_path in root_files:
            if not self.is_protected(file_path):
                target_dir = self.get_target_directory(file_path)
                if target_dir:
                    violations.append(
                        {
                            "file": file_path.name,
                            "expected_location": target_dir,
                            "current_location": "root",
                            "rule_applied": True,
                        }
                    )
                else:
                    violations.append(
                        {
                            "file": file_path.name,
                            "expected_location": "unknown",
                            "current_location": "root",
                            "rule_applied": False,
                        }
                    )

        return {
            "total_files_in_root": len(root_files),
            "violations": violations,
            "violation_count": len(violations),
        }

    def create_git_hook(self):
        """Create git pre-commit hook for automatic organization"""
        hook_content = """#!/bin/bash
# File organization pre-commit hook
echo "Running file organization check..."
python scripts/organize-files.py --validate

# If validation fails, organize files
if [ $? -ne 0 ]; then
    echo "Organizing files..."
    python scripts/organize-files.py --organize
    git add .
fi
"""

        hooks_dir = self.project_root / ".git" / "hooks"
        pre_commit_hook = hooks_dir / "pre-commit"

        if not hooks_dir.exists():
            self.logger.warning("Git hooks directory not found")
            return

        with open(pre_commit_hook, "w") as f:
            f.write(hook_content)

        pre_commit_hook.chmod(0o755)
        self.logger.info(f"Created git pre-commit hook: {pre_commit_hook}")


def main():
    parser = argparse.ArgumentParser(description="ATOM Project File Organizer")
    parser.add_argument(
        "--organize", action="store_true", help="Organize files according to rules"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate current structure against rules",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be organized without making changes",
    )
    parser.add_argument(
        "--create-hook", action="store_true", help="Create git pre-commit hook"
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Project root directory (default: current directory)",
    )

    args = parser.parse_args()

    try:
        organizer = FileOrganizer(args.project_root)

        if args.create_hook:
            organizer.create_git_hook()

        if args.validate:
            results = organizer.validate_structure()
            print(f"Validation Results:")
            print(f"Files in root: {results['total_files_in_root']}")
            print(f"Violations: {results['violation_count']}")

            if results["violation_count"] > 0:
                print("\nViolations found:")
                for violation in results["violations"]:
                    if violation["rule_applied"]:
                        print(
                            f"  {violation['file']} -> should be in {violation['expected_location']}/"
                        )
                    else:
                        print(f"  {violation['file']} -> no rule defined")
                return 1  # Exit with error code for CI/CD
            else:
                print("✓ Project structure is clean!")
                return 0

        if args.organize or args.dry_run:
            results = organizer.organize_all(dry_run=args.dry_run)
            print(f"Organization Results:")
            print(f"Total files scanned: {results['total_files']}")
            print(f"Files organized: {results['organized']}")
            print(f"Files skipped: {results['skipped']}")
            print(f"Files failed: {results['failed']}")

            if args.dry_run:
                print("\nFiles that would be organized:")
                for detail in results["details"]:
                    if detail["action"] == "would_move":
                        print(f"  {detail['file']}")

        if not any([args.organize, args.validate, args.create_hook, args.dry_run]):
            parser.print_help()

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
