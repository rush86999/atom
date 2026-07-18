#!/usr/bin/env python3
"""
ATOM Test Coverage Enhancement Script
Automatically identifies test gaps and generates missing test cases
"""

import ast
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


class TestCoverageEnhancer:
    """Enhances test coverage by analyzing code and generating missing tests"""

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.coverage_data = {}
        self.untested_functions = defaultdict(list)
        self.untested_classes = defaultdict(list)
        self.missing_test_files = set()

    def analyze_coverage(self) -> Dict[str, Any]:
        """Analyze current test coverage and identify gaps"""
        print("🔍 Analyzing current test coverage...")

        # Run coverage analysis for backend
        backend_coverage = self._analyze_backend_coverage()

        # Analyze frontend test coverage
        frontend_coverage = self._analyze_frontend_coverage()

        # Identify untested code
        self._identify_untested_functions()
        self._identify_missing_test_files()

        return {
            "backend": backend_coverage,
            "frontend": frontend_coverage,
            "untested_functions": dict(self.untested_functions),
            "untested_classes": dict(self.untested_classes),
            "missing_test_files": list(self.missing_test_files),
        }

    def _analyze_backend_coverage(self) -> Dict[str, Any]:
        """Analyze Python backend test coverage"""
        backend_path = self.project_root / "backend"

        try:
            # Run pytest with coverage
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "--cov=.",
                    "--cov-report=json",
                    "--cov-report=term-missing",
                    str(backend_path),
                ],
                capture_output=True,
                text=True,
                cwd=backend_path,
            )

            if result.returncode == 0 and os.path.exists(
                backend_path / "coverage.json"
            ):
                with open(backend_path / "coverage.json", "r") as f:
                    coverage_data = json.load(f)
                    return self._parse_backend_coverage(coverage_data)

        except Exception as e:
            print(f"⚠️  Could not run backend coverage: {e}")

        return {"total_coverage": 0, "files": {}}

    def _parse_backend_coverage(self, coverage_data: Dict) -> Dict[str, Any]:
        """Parse backend coverage data"""
        files_coverage = {}
        total_covered = 0
        total_statements = 0

        for file_path, file_data in coverage_data["files"].items():
            if "backend" in file_path:
                covered = file_data["summary"]["covered_lines"]
                total = file_data["summary"]["num_statements"]
                coverage_pct = (covered / total * 100) if total > 0 else 0

                files_coverage[file_path] = {
                    "coverage": coverage_pct,
                    "covered_lines": covered,
                    "total_lines": total,
                    "missing_lines": file_data.get("missing_lines", []),
                }

                total_covered += covered
                total_statements += total

        overall_coverage = (
            (total_covered / total_statements * 100) if total_statements > 0 else 0
        )

        return {"total_coverage": overall_coverage, "files": files_coverage}

    def _analyze_frontend_coverage(self) -> Dict[str, Any]:
        """Analyze frontend test coverage"""
        frontend_path = self.project_root / "frontend-nextjs"

        try:
            # Run Jest with coverage
            result = subprocess.run(
                ["npm", "test", "--", "--coverage", "--json"],
                capture_output=True,
                text=True,
                cwd=frontend_path,
            )

            if result.returncode == 0:
                coverage_data = json.loads(result.stdout)
                return self._parse_frontend_coverage(coverage_data)

        except Exception as e:
            print(f"⚠️  Could not run frontend coverage: {e}")

        return {"total_coverage": 0, "files": {}}

    def _parse_frontend_coverage(self, coverage_data: Dict) -> Dict[str, Any]:
        """Parse frontend coverage data"""
        files_coverage = {}

        if "coverageMap" in coverage_data:
            for file_path, file_data in coverage_data["coverageMap"].items():
                if "frontend-nextjs" in file_path:
                    statement_coverage = file_data.get("s", {})
                    covered = sum(1 for v in statement_coverage.values() if v > 0)
                    total = len(statement_coverage)
                    coverage_pct = (covered / total * 100) if total > 0 else 0

                    files_coverage[file_path] = {
                        "coverage": coverage_pct,
                        "covered_statements": covered,
                        "total_statements": total,
                    }

        return {
            "total_coverage": coverage_data.get("numPassedTests", 0),
            "files": files_coverage,
        }

    def _identify_untested_functions(self):
        """Identify functions and classes without tests"""
        print("📊 Identifying untested functions...")

        # Analyze backend Python files
        backend_path = self.project_root / "backend"
        for py_file in backend_path.rglob("*.py"):
            if "test" in py_file.name or "__pycache__" in str(py_file):
                continue

            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    tree = ast.parse(content)

                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef):
                            function_name = node.name
                            if not self._has_test_for_function(
                                str(py_file), function_name
                            ):
                                self.untested_functions[str(py_file)].append(
                                    function_name
                                )

                        elif isinstance(node, ast.ClassDef):
                            class_name = node.name
                            if not self._has_test_for_class(str(py_file), class_name):
                                self.untested_classes[str(py_file)].append(class_name)

            except Exception as e:
                print(f"⚠️  Could not analyze {py_file}: {e}")

    def _has_test_for_function(self, file_path: str, function_name: str) -> bool:
        """Check if a function has corresponding tests"""
        test_file = self._get_test_file_path(file_path)
        if not test_file.exists():
            return False

        # Simple pattern matching for test functions
        test_patterns = [
            f"test.*{function_name}",
            f"test_{function_name}",
            f"{function_name}.*test",
        ]

        try:
            with open(test_file, "r") as f:
                content = f.read()
                return any(
                    re.search(pattern, content, re.IGNORECASE)
                    for pattern in test_patterns
                )
        except:
            return False

    def _has_test_for_class(self, file_path: str, class_name: str) -> bool:
        """Check if a class has corresponding tests"""
        test_file = self._get_test_file_path(file_path)
        if not test_file.exists():
            return False

        # Look for test classes or test methods for this class
        test_patterns = [
            f"Test{class_name}",
            f"test.*{class_name}",
            f"{class_name}.*test",
        ]

        try:
            with open(test_file, "r") as f:
                content = f.read()
                return any(
                    re.search(pattern, content, re.IGNORECASE)
                    for pattern in test_patterns
                )
        except:
            return False

    def _get_test_file_path(self, file_path: str) -> Path:
        """Get corresponding test file path"""
        path = Path(file_path)
        test_dir = path.parent / "tests"
        test_file = test_dir / f"test_{path.name}"

        # If no test directory, check for test_ prefixed files in same directory
        if not test_dir.exists():
            test_file = path.parent / f"test_{path.name}"

        return test_file

    def _identify_missing_test_files(self):
        """Identify Python files without corresponding test files"""
        backend_path = self.project_root / "backend"

        for py_file in backend_path.rglob("*.py"):
            if "test" in py_file.name or "__pycache__" in str(py_file):
                continue

            test_file = self._get_test_file_path(str(py_file))
            if not test_file.exists():
                self.missing_test_files.add(str(py_file))

    def generate_missing_tests(self):
        """Generate missing test cases"""
        print("🛠️ Generating missing test cases...")

        generated_tests = []

        # Generate tests for untested functions
        for file_path, functions in self.untested_functions.items():
            test_file = self._generate_function_tests(file_path, functions)
            if test_file:
                generated_tests.append(test_file)

        # Generate tests for missing test files
        for file_path in self.missing_test_files:
            test_file = self._generate_basic_test_file(file_path)
            if test_file:
                generated_tests.append(test_file)

        return generated_tests

    def _generate_function_tests(self, file_path: str, functions: List[str]) -> str:
        """Generate test cases for specific functions"""
        path = Path(file_path)
        module_name = path.stem
        module_path = (
            str(path.relative_to(self.project_root / "backend"))
            .replace("/", ".")
            .replace(".py", "")
        )

        test_content = [
            "#!/usr/bin/env python3",
            f'"""Test cases for {module_name} module"""',
            "",
            "import pytest",
            "import sys",
            "import os",
            "",
            "# Add backend to path",
            "sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))",
            "",
            f"from {module_path} import *",
            "",
            "class TestGenerated:",
            '    """Automatically generated test cases"""',
            "",
        ]

        for function in functions:
            test_content.extend(
                [
                    f"    def test_{function}(self):",
                    f'        """Test {function} function"""',
                    f"        # TODO: Implement test for {function}",
                    f"        # Example test structure:",
                    f"        # result = {function}()",
                    f"        # assert result is not None",
                    f"        pass",
                    "",
                ]
            )

        test_file = self._get_test_file_path(file_path)
        test_file.parent.mkdir(parents=True, exist_ok=True)

        with open(test_file, "w") as f:
            f.write("\n".join(test_content))

        print(f"✅ Generated test file: {test_file}")
        return str(test_file)

    def _generate_basic_test_file(self, file_path: str) -> str:
        """Generate basic test file for modules without tests"""
        path = Path(file_path)
        module_name = path.stem
        module_path = (
            str(path.relative_to(self.project_root / "backend"))
            .replace("/", ".")
            .replace(".py", "")
        )

        test_content = [
            "#!/usr/bin/env python3",
            f'"""Basic test cases for {module_name} module"""',
            "",
            "import pytest",
            "import sys",
            "import os",
            "",
            "# Add backend to path",
            "sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))",
            "",
            f"import {module_path}",
            "",
            "class TestBasic:",
            '    """Basic test cases for module import and structure"""',
            "",
            "    def test_module_import(self):",
            f'        """Test that {module_name} module can be imported"""',
            f"        assert {module_path} is not None",
            "",
            "    def test_module_has_expected_attributes(self):",
            f'        """Test that {module_name} module has expected attributes"""',
            "        # Check for common attributes or functions",
            "        assert hasattr(sys.modules[__name__], '__file__')",
            "",
        ]

        test_file = self._get_test_file_path(file_path)
        test_file.parent.mkdir(parents=True, exist_ok=True)

        with open(test_file, "w") as f:
            f.write("\n".join(test_content))

        print(f"✅ Generated basic test file: {test_file}")
        return str(test_file)

    def create_coverage_improvement_plan(self) -> Dict[str, Any]:
        """Create a comprehensive plan for improving test coverage"""
        analysis = self.analyze_coverage()
        generated_tests = self.generate_missing_tests()

        improvement_plan = {
            "current_state": analysis,
            "generated_tests": generated_tests,
            "recommendations": self._generate_recommendations(analysis),
            "targets": self._set_coverage_targets(analysis),
        }

        return improvement_plan

    def _generate_recommendations(self, analysis: Dict) -> List[str]:
        """Generate specific recommendations for improving coverage"""
        recommendations = []

        backend_coverage = analysis["backend"]["total_coverage"]
        frontend_coverage = analysis["frontend"]["total_coverage"]

        if backend_coverage < 80:
            recommendations.append(
                f"🚨 Backend coverage is {backend_coverage:.1f}% - target 80%"
            )

        if frontend_coverage < 70:
            recommendations.append(
                f"🚨 Frontend coverage is {frontend_coverage:.1f}% - target 70%"
            )

        if self.untested_functions:
            total_untested = sum(
                len(funcs) for funcs in self.untested_functions.values()
            )
            recommendations.append(f"📝 {total_untested} functions need test coverage")

        if self.missing_test_files:
            recommendations.append(
                f"📁 {len(self.missing_test_files)} files missing test files"
            )

        recommendations.extend(
            [
                "🔧 Run generated test templates and implement actual test logic",
                "📊 Integrate coverage reporting into CI/CD pipeline",
                "🎯 Focus on critical path and integration tests",
                "🔄 Establish test coverage gates for new code",
            ]
        )

        return recommendations

    def _set_coverage_targets(self, analysis: Dict) -> Dict[str, Any]:
        """Set realistic coverage improvement targets"""
        backend_current = analysis["backend"]["total_coverage"]
        frontend_current = analysis["frontend"]["total_coverage"]

        return {
            "backend": {
                "current": backend_current,
                "target_1_week": min(backend_current + 10, 80),
                "target_1_month": min(backend_current + 20, 90),
                "target_3_months": 95,
            },
            "frontend": {
                "current": frontend_current,
                "target_1_week": min(frontend_current + 5, 70),
                "target_1_month": min(frontend_current + 15, 80),
                "target_3_months": 85,
            },
        }

    def run_enhancement_pipeline(self):
        """Run complete enhancement pipeline"""
        print("🚀 Starting ATOM Test Coverage Enhancement Pipeline")
        print("=" * 60)

        improvement_plan = self.create_coverage_improvement_plan()

        # Print summary
        print("\n📊 COVERAGE SUMMARY")
        print("-" * 30)
        print(
            f"Backend Coverage: {improvement_plan['current_state']['backend']['total_coverage']:.1f}%"
        )
        print(
            f"Frontend Coverage: {improvement_plan['current_state']['frontend']['total_coverage']:.1f}%"
        )
        print(
            f"Untested Functions: {sum(len(funcs) for funcs in improvement_plan['current_state']['untested_functions'].values())}"
        )
        print(
            f"Missing Test Files: {len(improvement_plan['current_state']['missing_test_files'])}"
        )
        print(f"Generated Tests: {len(improvement_plan['generated_tests'])}")

        print("\n🎯 RECOMMENDATIONS")
        print("-" * 30)
        for recommendation in improvement_plan["recommendations"]:
            print(f"• {recommendation}")

        print("\n📈 IMPROVEMENT TARGETS")
        print("-" * 30)
        targets = improvement_plan["targets"]
        print("Backend:")
        print(f"  • 1 week: {targets['backend']['target_1_week']}%")
        print(f"  • 1 month: {targets['backend']['target_1_month']}%")
        print(f"  • 3 months: {targets['backend']['target_3_months']}%")

        print("Frontend:")
        print(f"  • 1 week: {targets['frontend']['target_1_week']}%")
        print(f"  • 1 month: {targets['frontend']['target_1_month']}%")
        print(f"  • 3 months: {targets['frontend']['target_3_months']}%")

        # Save improvement plan
        plan_path = self.project_root / "test_coverage_improvement_plan.json"
        with open(plan_path, "w") as f:
            json.dump(improvement_plan, f, indent=2)

        print(f"\n📝 Improvement plan saved to: {plan_path}")
        print("✅ Enhancement pipeline completed!")


def main():
    """Main execution function"""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    enhancer = TestCoverageEnhancer(project_root)
    enhancer.run_enhancement_pipeline()


if __name__ == "__main__":
    main()
