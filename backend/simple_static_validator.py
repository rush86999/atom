# -*- coding: utf-8 -*-
"""
Simple Static AI Validation System
Analyzes code structure and identifies bugs/gaps without requiring running servers
"""

import os
import ast
import json
import logging
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SimpleCodeValidator:
    """Simple static code analyzer"""

    def __init__(self):
        self.backend_dir = Path(__file__).parent
        self.issues = []
        self.recommendations = []

    def run_analysis(self):
        """Run the complete analysis"""
        print("Starting Static AI Validation System")
        print("=" * 60)

        # Analyze integrations
        self._check_integrations()

        # Analyze core files
        self._check_core_files()

        # Analyze main API
        self._check_main_api()

        # Analyze OAuth files
        self._check_oauth_files()

        # Print results
        self._print_results()

        # Save report
        self._save_report()

    def _check_integrations(self):
        """Check integration files for issues"""
        print("Analyzing integrations...")

        integrations_dir = self.backend_dir / "integrations"
        if not integrations_dir.exists():
            self.issues.append("Integrations directory not found")
            return

        integration_files = []
        for file_path in integrations_dir.glob("*.py"):
            if not file_path.name.startswith("test_") and not file_path.name.startswith("__"):
                integration_files.append(file_path)

        print(f"   Found {len(integration_files)} integration files")

        for file_path in integration_files:
            issues = self._analyze_file(file_path)
            for issue in issues:
                self.issues.append(f"{file_path.name}: {issue}")

    def _check_core_files(self):
        """Check core files for issues"""
        print("🔍 Analyzing core files...")

        core_dir = self.backend_dir / "core"
        if not core_dir.exists():
            self.issues.append("Core directory not found")
            return

        critical_files = ["config.py", "integration_loader.py"]
        for critical_file in critical_files:
            file_path = core_dir / critical_file
            if not file_path.exists():
                self.issues.append(f"Missing critical core file: {critical_file}")
            else:
                issues = self._analyze_file(file_path)
                for issue in issues:
                    self.issues.append(f"core/{critical_file}: {issue}")

    def _check_main_api(self):
        """Check main API file"""
        print("🔍 Analyzing main API...")

        main_api_file = self.backend_dir / "main_api_app.py"
        if not main_api_file.exists():
            self.issues.append("Main API file not found")
            return

        try:
            with open(main_api_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Check for integration loader usage
            if "integration_loader" not in content:
                self.issues.append("Main API doesn't use integration loader")

            # Check for route registration
            if "APIRouter" not in content:
                self.issues.append("No APIRouter imports found in main API")

            print("   Main API file analyzed successfully")

        except Exception as e:
            self.issues.append(f"Error analyzing main API: {e}")

    def _check_oauth_files(self):
        """Check OAuth implementations"""
        print("🔍 Analyzing OAuth files...")

        oauth_files = []
        for file_path in self.backend_dir.glob("**/*.py"):
            if any(pattern in file_path.name.lower() for pattern in ["oauth", "auth"]):
                oauth_files.append(file_path)

        print(f"   Found {len(oauth_files)} OAuth-related files")

        for file_path in oauth_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Security checks
                if "token" in content.lower() and "encrypt" not in content.lower():
                    self.issues.append(f"{file_path.name}: Token encryption not implemented")

                if "state" not in content.lower() and "oauth" in content.lower():
                    self.issues.append(f"{file_path.name}: Missing OAuth state parameter")

            except Exception as e:
                self.issues.append(f"Error analyzing {file_path.name}: {e}")

    def _analyze_file(self, file_path):
        """Analyze a single file for issues"""
        issues = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Syntax check
            try:
                ast.parse(content)
            except SyntaxError as e:
                issues.append(f"Syntax error: {e}")
                return issues

            # Basic code quality checks
            if '"""' not in content and "'''" not in content:
                issues.append("Missing module docstring")

            if "import logging" not in content and "logger" not in content:
                issues.append("Missing logging")

            if "try:" not in content:
                issues.append("Missing error handling")

            # Check for router pattern in route files
            if "routes" in file_path.name.lower() and "APIRouter" not in content:
                issues.append("Missing APIRouter import/usage")

        except Exception as e:
            issues.append(f"File read error: {e}")

        return issues

    def _print_results(self):
        """Print analysis results"""
        print("\n📊 ANALYSIS RESULTS:")
        print(f"   Total Issues Found: {len(self.issues)}")

        if len(self.issues) == 0:
            print("   ✅ No issues found!")
            return

        # Count severity
        high_priority = [i for i in self.issues if "critical" in i.lower() or "missing" in i.lower() or "error" in i.lower()]

        print(f"   High Priority Issues: {len(high_priority)}")

        if high_priority:
            print(f"\n🚨 HIGH PRIORITY ISSUES:")
            for issue in high_priority[:5]:
                print(f"   ❌ {issue}")

        print(f"\n💡 RECOMMENDATIONS:")
        if high_priority:
            self.recommendations.append("Fix high-priority issues first")

        if len(self.issues) > 10:
            self.recommendations.append("Consider code cleanup to reduce technical debt")

        if not any("integration_loader" in i for i in self.issues):
            self.recommendations.append("Architecture looks good - integration loader being used")

        for rec in self.recommendations:
            print(f"   • {rec}")

        # Health score
        health_score = max(0, 100 - (len(self.issues) * 5))
        print(f"\n🏥 System Health Score: {health_score}/100")

        if health_score > 80:
            print("   Status: ✅ HEALTHY")
        elif health_score > 60:
            print("   Status: ⚠️ NEEDS IMPROVEMENT")
        else:
            print("   Status: 🚨 CRITICAL")

    def _save_report(self):
        """Save detailed report to file"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_issues": len(self.issues),
            "issues": self.issues,
            "recommendations": self.recommendations,
            "health_score": max(0, 100 - (len(self.issues) * 5))
        }

        report_file = f"static_validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)

        print(f"\n📋 Detailed report saved to: {report_file}")
        print("=" * 60)

def main():
    """Main function"""
    validator = SimpleCodeValidator()
    validator.run_analysis()

if __name__ == "__main__":
    main()