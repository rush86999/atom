"""
Static AI Validation System
Analyzes code structure and identifies bugs/gaps without requiring running servers
"""

import os
import ast
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class StaticCodeValidator:
    """Static code analyzer with AI validation capabilities"""

    def __init__(self):
        self.backend_dir = Path(__file__).parent
        self.issues = []
        self.recommendations = []
        self.validation_results = {}

    def analyze_code_structure(self):
        """Analyze the codebase structure and identify issues"""
        logger.info("Starting static code analysis...")

        # Analyze integrations
        integration_analysis = self._analyze_integrations()

        # Analyze core modules
        core_analysis = self._analyze_core_modules()

        # Analyze API endpoints
        api_analysis = self._analyze_api_endpoints()

        # Analyze OAuth implementations
        oauth_analysis = self._analyze_oauth_implementations()

        # Analyze configuration and setup
        config_analysis = self._analyze_configuration()

        # Generate AI insights
        ai_insights = self._generate_ai_insights()

        return {
            "timestamp": datetime.now().isoformat(),
            "integration_analysis": integration_analysis,
            "core_analysis": core_analysis,
            "api_analysis": api_analysis,
            "oauth_analysis": oauth_analysis,
            "configuration_analysis": config_analysis,
            "ai_insights": ai_insights,
            "critical_issues": self.issues,
            "recommendations": self.recommendations
        }

    def _analyze_integrations(self):
        """Analyze integration services"""
        integrations_dir = self.backend_dir / "integrations"
        analysis = {
            "total_integration_files": 0,
            "services_found": [],
            "missing_services": [],
            "duplicate_files": [],
            "import_issues": []
        }

        if not integrations_dir.exists():
            self.issues.append({
                "category": "structure",
                "issue": "Integrations directory not found",
                "severity": "high"
            })
            return analysis

        # Find all integration files
        integration_files = []
        for file_path in integrations_dir.glob("*.py"):
            if not file_path.name.startswith("test_"):
                integration_files.append(file_path)
                analysis["total_integration_files"] += 1

        # Identify services
        for file_path in integration_files:
            service_name = file_path.stem.replace("_routes", "").replace("_service", "")
            analysis["services_found"].append(service_name)

            # Check for potential issues in each file
            issues = self._analyze_integration_file(file_path)
            analysis["import_issues"].extend(issues)

        # Check for duplicates
        service_names = [os.path.basename(f).replace("_routes.py", "").replace("_service.py", "")
                        for f in integration_files]
        duplicates = [name for name in service_names if service_names.count(name) > 1]
        analysis["duplicate_files"] = list(set(duplicates))

        if duplicates:
            self.issues.append({
                "category": "duplicates",
                "issue": f"Duplicate integration files found: {', '.join(duplicates)}",
                "severity": "medium"
            })

        return analysis

    def _analyze_integration_file(self, file_path: Path) -> List[str]:
        """Analyze a single integration file for issues"""
        issues = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Parse AST
            try:
                tree = ast.parse(content)
            except SyntaxError as e:
                issues.append(f"Syntax error in {file_path.name}: {e}")
                self.issues.append({
                    "category": "syntax",
                    "issue": f"Syntax error in {file_path.name}: {e}",
                    "severity": "high",
                    "file": str(file_path)
                })
                return issues

            # Check imports
            imports = self._extract_imports(tree)

            # Check for common patterns
            self._check_integration_patterns(content, file_path, issues)

        except Exception as e:
            issues.append(f"Error analyzing {file_path.name}: {e}")

        return issues

    def _analyze_core_modules(self) -> Dict[str, Any]:
        """Analyze core modules"""
        core_dir = self.backend_dir / "core"
        analysis = {
            "core_files_found": [],
            "missing_critical_files": [],
            "import_circular_deps": [],
            "configuration_issues": []
        }

        if not core_dir.exists():
            self.issues.append({
                "category": "structure",
                "issue": "Core directory not found",
                "severity": "high"
            })
            return analysis

        # Critical core files that should exist
        critical_files = [
            "config.py",
            "integration_loader.py",
            "token_storage.py"
        ]

        for file_path in core_dir.glob("*.py"):
            analysis["core_files_found"].append(file_path.name)

        # Check for missing critical files
        for critical_file in critical_files:
            if critical_file not in analysis["core_files_found"]:
                analysis["missing_critical_files"].append(critical_file)
                self.issues.append({
                    "category": "missing_files",
                    "issue": f"Missing critical core file: {critical_file}",
                    "severity": "high"
                })

        return analysis

    def _analyze_api_endpoints(self) -> Dict[str, Any]:
        """Analyze API endpoints"""
        analysis = {
            "total_routes": 0,
            "route_files": [],
            "missing_health_endpoints": [],
            "inconsistent_patterns": []
        }

        # Find route files
        for file_path in self.backend_dir.glob("**/*routes*.py"):
            if file_path.is_file():
                analysis["route_files"].append(str(file_path))
                analysis["total_routes"] += 1

                # Check for health endpoints
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    if "health" not in content.lower():
                        analysis["missing_health_endpoints"].append(file_path.name)
                except Exception as e:
                    logger.warning(f"Could not analyze {file_path}: {e}")

        # Check main API app
        main_api_file = self.backend_dir / "main_api_app.py"
        if main_api_file.exists():
            try:
                with open(main_api_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Check for route registration
                if "integration_loader" in content:
                    analysis["has_integration_loader"] = True
                else:
                    analysis["has_integration_loader"] = False
                    self.issues.append({
                        "category": "architecture",
                        "issue": "Main API app doesn't use integration loader",
                        "severity": "medium"
                    })

            except Exception as e:
                logger.warning(f"Could not analyze main API app: {e}")

        return analysis

    def _analyze_oauth_implementations(self) -> Dict[str, Any]:
        """Analyze OAuth implementations"""
        analysis = {
            "oauth_files": [],
            "missing_oauth_components": [],
            "security_issues": []
        }

        # Look for OAuth related files
        oauth_patterns = ["oauth", "auth", "callback"]

        for file_path in self.backend_dir.glob("**/*.py"):
            if any(pattern in file_path.name.lower() for pattern in oauth_patterns):
                analysis["oauth_files"].append(str(file_path))

                # Check for security best practices
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # Check for security patterns
                    if "state" not in content and "csrf" not in content.lower():
                        analysis["security_issues"].append(f"{file_path.name}: Missing CSRF protection")

                    if "token" in content.lower() and "encrypt" not in content.lower():
                        analysis["security_issues"].append(f"{file_path.name}: Token storage might not be encrypted")

                except Exception as e:
                    logger.warning(f"Could not analyze OAuth file {file_path}: {e}")

        return analysis

    def _analyze_configuration(self) -> Dict[str, Any]:
        """Analyze configuration and setup"""
        analysis = {
            "env_file_exists": False,
            "requirements_file_exists": False,
            "docker_files": [],
            "configuration_issues": []
        }

        # Check for .env file
        env_file = self.backend_dir / ".env"
        analysis["env_file_exists"] = env_file.exists()

        # Check for requirements
        req_file = self.backend_dir / "requirements.txt"
        analysis["requirements_file_exists"] = req_file.exists()

        # Check for virtual environment
        venv_dir = self.backend_dir / "venv"
        if venv_dir.exists():
            analysis["has_virtual_env"] = True
        else:
            analysis["has_virtual_env"] = False
            self.issues.append({
                "category": "setup",
                "issue": "No virtual environment found",
                "severity": "medium"
            })

        return analysis

    def _extract_imports(self, tree: ast.AST) -> List[str]:
        """Extract imports from AST"""
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append(f"{module}.{alias.name}")
        return imports

    def _check_integration_patterns(self, content: str, file_path: Path, issues: List[str]):
        """Check for common integration patterns"""
        filename = file_path.name.lower()

        # Check for router pattern
        if "routes" in filename and "APIRouter" not in content:
            issues.append(f"{file_path.name}: Missing APIRouter import/usage")

        # Check for error handling
        if "try:" not in content:
            issues.append(f"{file_path.name}: Missing error handling")

        # Check for logging
        if "logger" not in content and "logging" not in content:
            issues.append(f"{file_path.name}: Missing logging")

        # Check for docstrings
        if '"""' not in content and "'''" not in content:
            issues.append(f"{file_path.name}: Missing module docstring")

    def _generate_ai_insights(self) -> Dict[str, Any]:
        """Generate AI-powered insights from the analysis"""
        total_issues = len(self.issues)
        severity_counts = {"high": 0, "medium": 0, "low": 0}

        for issue in self.issues:
            severity_counts[issue.get("severity", "medium")] += 1

        # Generate recommendations
        if severity_counts["high"] > 0:
            self.recommendations.append("Fix high-priority issues immediately")

        if severity_counts["medium"] > 5:
            self.recommendations.append("Address medium-priority issues for better stability")

        # Calculate health score
        max_issues = 20  # Arbitrary threshold for "perfect" system
        health_score = max(0, 100 - (total_issues * 5))

        return {
            "total_issues_found": total_issues,
            "severity_breakdown": severity_counts,
            "health_score": health_score,
            "overall_status": "healthy" if health_score > 80 else "needs_improvement" if health_score > 60 else "critical",
            "primary_focus_areas": self._get_focus_areas()
        }

    def _get_focus_areas(self) -> List[str]:
        """Get primary focus areas based on issues"""
        focus_areas = []
        categories = [issue.get("category", "unknown") for issue in self.issues]

        category_counts = {}
        for category in categories:
            category_counts[category] = category_counts.get(category, 0) + 1

        # Sort by count and take top 3
        sorted_categories = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
        focus_areas = [cat[0] for cat in sorted_categories[:3]]

        return focus_areas

    def generate_fix_recommendations(self) -> List[Dict[str, Any]]:
        """Generate specific fix recommendations"""
        fixes = []

        for issue in self.issues:
            fix = {
                "issue": issue["issue"],
                "category": issue["category"],
                "severity": issue["severity"],
                "recommended_action": self._get_fix_action(issue),
                "estimated_effort": self._estimate_effort(issue)
            }
            fixes.append(fix)

        return fixes

    def _get_fix_action(self, issue: Dict[str, Any]) -> str:
        """Get specific fix action for an issue"""
        category = issue.get("category", "")

        if category == "syntax":
            return "Fix syntax errors in the affected file"
        elif category == "missing_files":
            return "Create the missing core files or adjust the architecture"
        elif category == "duplicates":
            return "Consolidate duplicate integration files"
        elif category == "security":
            return "Implement proper security measures (CSRF protection, encryption, etc.)"
        elif category == "architecture":
            return "Review and update the application architecture"
        elif category == "setup":
            return "Set up proper development environment (virtual environment, etc.)"
        else:
            return "Review and fix the identified issue"

    def _estimate_effort(self, issue: Dict[str, Any]) -> str:
        """Estimate effort to fix an issue"""
        severity = issue.get("severity", "medium")

        if severity == "high":
            return "High - requires immediate attention"
        elif severity == "medium":
            return "Medium - can be addressed in next iteration"
        else:
            return "Low - quick fix"

def main():
    """Main function to run static AI validation"""
    validator = StaticCodeValidator()

    print("🤖 Starting Static AI Validation System")
    print("=" * 60)

    # Run analysis
    results = validator.analyze_code_structure()

    # Generate fix recommendations
    fix_recommendations = validator.generate_fix_recommendations()

    # Print summary
    print("\n📊 ANALYSIS RESULTS:")
    print(f"   Total Issues Found: {len(validator.issues)}")
    print(f"   Health Score: {results['ai_insights']['health_score']}/100")
    print(f"   Overall Status: {results['ai_insights']['overall_status'].upper()}")

    print(f"\n🎯 FOCUS AREAS:")
    for area in results['ai_insights']['primary_focus_areas']:
        print(f"   • {area}")

    print(f"\n🚨 CRITICAL ISSUES ({len([i for i in validator.issues if i['severity'] == 'high'])}):")
    high_priority_issues = [i for i in validator.issues if i['severity'] == 'high'][:5]
    for issue in high_priority_issues:
        print(f"   ❌ {issue['issue']}")

    print(f"\n💡 RECOMMENDATIONS:")
    for rec in validator.recommendations[:5]:
        print(f"   • {rec}")

    # Save detailed report
    report_file = f"static_ai_validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    full_report = {
        **results,
        "fix_recommendations": fix_recommendations
    }

    with open(report_file, "w") as f:
        json.dump(full_report, f, indent=2)

    print(f"\n📋 Detailed report saved to: {report_file}")
    print("=" * 60)

if __name__ == "__main__":
    main()