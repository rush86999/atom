#!/usr/bin/env python3
"""
ATOM Dependency Audit and Cleanup Script
Identifies and removes unused dependencies across the platform
"""

import json
import os
import subprocess
import sys
from typing import Dict, List, Set, Tuple

from path import Path


class DependencyAuditor:
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.unused_dependencies = {
            "frontend": set(),
            "backend": set(),
            "shared": set(),
        }
        self.used_dependencies = {"frontend": set(), "backend": set(), "shared": set()}

    def analyze_frontend_dependencies(self) -> Dict:
        """Analyze frontend dependencies and identify unused packages"""
        frontend_path = self.project_root / "frontend-nextjs"
        package_json_path = frontend_path / "package.json"

        if not package_json_path.exists():
            return {"error": "package.json not found"}

        with open(package_json_path, "r") as f:
            package_data = json.load(f)

        dependencies = set(package_data.get("dependencies", {}).keys())
        dev_dependencies = set(package_data.get("devDependencies", {}).keys())
        all_dependencies = dependencies.union(dev_dependencies)

        # Scan for used imports
        used_imports = self._scan_typescript_imports(frontend_path)

        # Identify unused dependencies
        unused = all_dependencies - used_imports
        self.unused_dependencies["frontend"] = unused
        self.used_dependencies["frontend"] = used_imports

        return {
            "total_dependencies": len(all_dependencies),
            "used_dependencies": len(used_imports),
            "unused_dependencies": len(unused),
            "unused_list": sorted(list(unused)),
        }

    def _scan_typescript_imports(self, directory: Path) -> Set[str]:
        """Scan TypeScript/JavaScript files for import statements"""
        used_imports = set()

        # Common import patterns
        import_patterns = [
            r"import\s+.*\s+from\s+['\"]([^'\"]+)['\"]",
            r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)",
            r"import\s*\(\s*['\"]([^'\"]+)['\"]\s*\)",
        ]

        for file_path in directory.walkfiles("*.ts"):
            if "node_modules" in file_path or ".next" in file_path:
                continue

            try:
                content = file_path.read_text(encoding="utf-8")
                for pattern in import_patterns:
                    import re

                    matches = re.findall(pattern, content)
                    for match in matches:
                        # Extract package name (remove relative paths and file extensions)
                        if not match.startswith(".") and not match.startswith("/"):
                            pkg_name = match.split("/")[0]
                            used_imports.add(pkg_name)
            except Exception as e:
                print(f"Warning: Could not read {file_path}: {e}")

        return used_imports

    def analyze_backend_dependencies(self) -> Dict:
        """Analyze Python backend dependencies"""
        backend_path = self.project_root / "backend"

        # Get installed packages
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "list", "--format=json"],
                capture_output=True,
                text=True,
                cwd=backend_path,
            )
            installed_packages = {
                pkg["name"].lower() for pkg in json.loads(result.stdout)
            }
        except:
            installed_packages = set()

        # Scan for used imports
        used_imports = self._scan_python_imports(backend_path)

        # Identify unused packages
        unused = installed_packages - used_imports
        self.unused_dependencies["backend"] = unused
        self.used_dependencies["backend"] = used_imports

        return {
            "total_dependencies": len(installed_packages),
            "used_dependencies": len(used_imports),
            "unused_dependencies": len(unused),
            "unused_list": sorted(list(unused)),
        }

    def _scan_python_imports(self, directory: Path) -> Set[str]:
        """Scan Python files for import statements"""
        used_imports = set()

        for file_path in directory.walkfiles("*.py"):
            if "__pycache__" in file_path or "venv" in file_path:
                continue

            try:
                content = file_path.read_text(encoding="utf-8")
                lines = content.split("\n")

                for line in lines:
                    line = line.strip()
                    if line.startswith("import ") or line.startswith("from "):
                        # Extract package name
                        if line.startswith("import "):
                            pkg_name = line.split()[1].split(".")[0]
                        else:  # from statement
                            pkg_name = line.split()[1].split(".")[0]

                        used_imports.add(pkg_name.lower())
            except Exception as e:
                print(f"Warning: Could not read {file_path}: {e}")

        return used_imports

    def generate_cleanup_report(self) -> Dict:
        """Generate comprehensive cleanup report"""
        frontend_analysis = self.analyze_frontend_dependencies()
        backend_analysis = self.analyze_backend_dependencies()

        total_unused = len(self.unused_dependencies["frontend"]) + len(
            self.unused_dependencies["backend"]
        )

        return {
            "frontend": frontend_analysis,
            "backend": backend_analysis,
            "summary": {
                "total_unused_dependencies": total_unused,
                "estimated_bundle_reduction": f"~{len(self.unused_dependencies['frontend']) * 100}KB",
                "security_risk_reduction": "High" if total_unused > 10 else "Medium",
            },
        }

    def create_cleanup_script(self) -> str:
        """Generate cleanup script for removing unused dependencies"""
        script_lines = [
            "#!/bin/bash",
            "# ATOM Dependency Cleanup Script",
            "# Generated automatically - review before running",
            "",
            "echo '🔍 Starting ATOM dependency cleanup...'",
            "",
        ]

        # Frontend cleanup commands
        if self.unused_dependencies["frontend"]:
            script_lines.extend(
                [
                    "# Frontend dependency cleanup",
                    "cd frontend-nextjs",
                ]
            )

            for pkg in sorted(self.unused_dependencies["frontend"]):
                script_lines.append(f"npm uninstall {pkg}")

            script_lines.extend(["cd ..", ""])

        # Backend cleanup commands
        if self.unused_dependencies["backend"]:
            script_lines.extend(
                [
                    "# Backend dependency cleanup",
                    "cd backend",
                ]
            )

            for pkg in sorted(self.unused_dependencies["backend"]):
                script_lines.append(f"pip uninstall -y {pkg}")

            script_lines.extend(["cd ..", ""])

        script_lines.extend(
            [
                "echo '✅ Dependency cleanup completed!'",
                "echo '📊 Summary:'",
                f"echo '  - Frontend packages removed: {len(self.unused_dependencies['frontend'])}'",
                f"echo '  - Backend packages removed: {len(self.unused_dependencies['backend'])}'",
                "echo '🚀 Consider running tests to ensure functionality is preserved'",
            ]
        )

        return "\n".join(script_lines)

    def run_audit(self) -> None:
        """Run comprehensive dependency audit"""
        print("🔍 Starting ATOM Dependency Audit...")
        print("=" * 50)

        report = self.generate_cleanup_report()

        # Print frontend results
        print("\n📦 FRONTEND DEPENDENCIES")
        print("-" * 30)
        print(f"Total dependencies: {report['frontend']['total_dependencies']}")
        print(f"Used dependencies: {report['frontend']['used_dependencies']}")
        print(f"Unused dependencies: {report['frontend']['unused_dependencies']}")

        if report["frontend"]["unused_list"]:
            print("\nUnused frontend packages:")
            for pkg in report["frontend"]["unused_list"]:
                print(f"  - {pkg}")

        # Print backend results
        print("\n🐍 BACKEND DEPENDENCIES")
        print("-" * 30)
        print(f"Total dependencies: {report['backend']['total_dependencies']}")
        print(f"Used dependencies: {report['backend']['used_dependencies']}")
        print(f"Unused dependencies: {report['backend']['unused_dependencies']}")

        if report["backend"]["unused_list"]:
            print("\nUnused backend packages:")
            for pkg in report["backend"]["unused_list"]:
                print(f"  - {pkg}")

        # Print summary
        print("\n📊 SUMMARY")
        print("-" * 30)
        print(
            f"Total unused dependencies: {report['summary']['total_unused_dependencies']}"
        )
        print(
            f"Estimated bundle reduction: {report['summary']['estimated_bundle_reduction']}"
        )
        print(
            f"Security risk reduction: {report['summary']['security_risk_reduction']}"
        )

        # Generate cleanup script
        cleanup_script = self.create_cleanup_script()
        script_path = self.project_root / "cleanup_dependencies.sh"

        with open(script_path, "w") as f:
            f.write(cleanup_script)

        os.chmod(script_path, 0o755)
        print(f"\n📝 Cleanup script generated: {script_path}")
        print("⚠️  Review the script before running it!")


def main():
    """Main execution function"""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    auditor = DependencyAuditor(project_root)
    auditor.run_audit()


if __name__ == "__main__":
    main()
