#!/usr/bin/env python3
"""
ATOM UI Availability Verification Script
Comprehensive verification of UI components for all 43 features
across web app and desktop app, including settings and dead code detection.
"""

import json
import os
from pathlib import Path
import sys
from typing import Dict, List, Set, Tuple


class UIVerification:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.frontend_path = self.project_root / "frontend-nextjs"
        self.desktop_path = self.project_root / "desktop" / "tauri" / "src"

        # Define all 43 features from README verification
        self.features = {
            "core_features": [
                "Unified calendar view for personal and work calendars",
                "Smart scheduling with conflict detection",
                "Meeting transcription and summarization",
                "Unified communication hub (email, chat)",
                "Task and project management",
                "Voice-powered productivity",
                "Automated workflows across platforms",
                "Financial insights and bank integration",
                "Unified cross-platform search",
                "Semantic understanding search",
            ],
            "multi_agent_system": [
                "Multi-agent system with specialized agents",
                "Wake word detection for hands-free operation",
                "Proactive autopilot assistant",
                "Automation engine for workflow automation",
                "Cross-platform orchestration",
                "Automated weekly reports",
            ],
            "integrations": [
                "Communication integrations (Gmail, Outlook, Slack, Teams, Discord)",
                "Scheduling integrations (Google Calendar, Outlook Calendar, Calendly, Zoom)",
                "Task management integrations (Notion, Trello, Asana, Jira)",
                "File storage integrations (Google Drive, Dropbox, OneDrive, Box)",
                "Finance integrations (Plaid, Quickbooks, Xero, Stripe)",
                "CRM integrations (Salesforce, HubSpot)",
            ],
            "agent_skills": [
                "Individual calendar management",
                "Email integration and search",
                "Contact management",
                "Basic task syncing across platforms",
                "Meeting notes with templates",
                "Reminder setup based on deadlines",
                "Workflow automation",
                "Web project setup",
                "Data collection and API retrieval",
                "Report generation",
                "Template-based content creation",
                "Financial data access",
                "Project tracking",
                "Information gathering and research",
                "Simple sales tracking",
                "Basic social media management",
                "Cross-platform data sync",
                "GitHub integration",
            ],
            "frontend_desktop": [
                "Frontend web application",
                "Desktop application",
                "Responsive user interface",
            ],
        }

        # Map features to expected UI components
        self.feature_to_ui_map = {
            # Core Features
            "Unified calendar view for personal and work calendars": [
                "calendar",
                "events",
                "scheduling",
            ],
            "Smart scheduling with conflict detection": [
                "calendar",
                "scheduling",
                "conflict",
            ],
            "Meeting transcription and summarization": [
                "meeting",
                "transcription",
                "audio",
                "summary",
            ],
            "Unified communication hub (email, chat)": [
                "chat",
                "messages",
                "email",
                "communication",
            ],
            "Task and project management": ["tasks", "projects", "todo", "kanban"],
            "Voice-powered productivity": ["voice", "audio", "speech", "wake-word"],
            "Automated workflows across platforms": [
                "automation",
                "workflows",
                "orchestration",
            ],
            "Financial insights and bank integration": [
                "finance",
                "banking",
                "transactions",
                "budget",
            ],
            "Unified cross-platform search": [
                "search",
                "unified-search",
                "smart-search",
            ],
            "Semantic understanding search": ["search", "semantic", "smart-search"],
            # Multi-Agent System
            "Multi-agent system with specialized agents": [
                "agents",
                "multi-agent",
                "orchestration",
            ],
            "Wake word detection for hands-free operation": [
                "wake-word",
                "voice",
                "audio",
            ],
            "Proactive autopilot assistant": ["autopilot", "proactive", "assistant"],
            "Automation engine for workflow automation": [
                "automation",
                "workflows",
                "engine",
            ],
            "Cross-platform orchestration": [
                "orchestration",
                "integration",
                "cross-platform",
            ],
            "Automated weekly reports": ["reports", "analytics", "dashboard"],
            # Integrations (Settings/Configuration)
            "Communication integrations (Gmail, Outlook, Slack, Teams, Discord)": [
                "settings",
                "integrations",
                "oauth",
            ],
            "Scheduling integrations (Google Calendar, Outlook Calendar, Calendly, Zoom)": [
                "settings",
                "integrations",
                "calendar",
            ],
            "Task management integrations (Notion, Trello, Asana, Jira)": [
                "settings",
                "integrations",
                "tasks",
            ],
            "File storage integrations (Google Drive, Dropbox, OneDrive, Box)": [
                "settings",
                "integrations",
                "files",
            ],
            "Finance integrations (Plaid, Quickbooks, Xero, Stripe)": [
                "settings",
                "integrations",
                "finance",
            ],
            "CRM integrations (Salesforce, HubSpot)": [
                "settings",
                "integrations",
                "crm",
            ],
            # Agent Skills
            "Individual calendar management": ["calendar", "events", "management"],
            "Email integration and search": ["email", "messages", "search"],
            "Contact management": ["contacts", "people", "address-book"],
            "Basic task syncing across platforms": ["tasks", "sync", "integration"],
            "Meeting notes with templates": ["meeting", "notes", "templates"],
            "Reminder setup based on deadlines": [
                "reminders",
                "alerts",
                "notifications",
            ],
            "Workflow automation": ["automation", "workflows"],
            "Web project setup": ["projects", "web", "setup"],
            "Data collection and API retrieval": ["data", "api", "collection"],
            "Report generation": ["reports", "analytics", "dashboard"],
            "Template-based content creation": ["templates", "content", "creation"],
            "Financial data access": ["finance", "data", "transactions"],
            "Project tracking": ["projects", "tracking", "progress"],
            "Information gathering and research": [
                "research",
                "information",
                "gathering",
            ],
            "Simple sales tracking": ["sales", "tracking", "crm"],
            "Basic social media management": ["social", "media", "posts"],
            "Cross-platform data sync": ["sync", "integration", "data"],
            "GitHub integration": ["github", "code", "repositories"],
            # Frontend & Desktop
            "Frontend web application": ["frontend", "web", "browser"],
            "Desktop application": ["desktop", "tauri", "native"],
            "Responsive user interface": ["responsive", "ui", "layout"],
        }

    def verify_frontend_structure(self) -> Dict:
        """Verify frontend Next.js application structure"""
        print("🔍 Verifying Frontend Next.js Application Structure...")

        frontend_checks = {
            "pages": {
                "required": ["index.tsx", "api/"],
                "optional": ["Assist/", "Automations/", "User/"],
            },
            "components": {
                "required": ["Dashboard.tsx", "Settings/"],
                "optional": ["Audio/", "Search/", "chat/"],
            },
            "settings": {
                "required": ["Settings components"],
                "optional": ["Integration configuration"],
            },
        }

        results = {}

        # Check pages directory
        pages_path = self.frontend_path / "pages"
        if pages_path.exists():
            pages_files = list(pages_path.rglob("*"))
            results["pages"] = {
                "exists": True,
                "files": [
                    str(f.relative_to(pages_path)) for f in pages_files if f.is_file()
                ],
                "directories": [
                    str(f.relative_to(pages_path)) for f in pages_files if f.is_dir()
                ],
            }
        else:
            results["pages"] = {"exists": False, "files": [], "directories": []}

        # Check components directory
        components_path = self.frontend_path / "components"
        if components_path.exists():
            components_files = list(components_path.rglob("*"))
            results["components"] = {
                "exists": True,
                "files": [
                    str(f.relative_to(components_path))
                    for f in components_files
                    if f.is_file()
                ],
                "directories": [
                    str(f.relative_to(components_path))
                    for f in components_files
                    if f.is_dir()
                ],
            }
        else:
            results["components"] = {"exists": False, "files": [], "directories": []}

        return results

    def verify_desktop_structure(self) -> Dict:
        """Verify desktop Tauri application structure"""
        print("🔍 Verifying Desktop Tauri Application Structure...")

        desktop_checks = {
            "main_components": {
                "required": ["App.tsx", "Dashboard.tsx", "Settings.tsx"],
                "optional": [
                    "Chat.tsx",
                    "Automations.tsx",
                    "Finance.tsx",
                    "Projects.tsx",
                ],
            },
            "feature_pages": {
                "required": ["Settings"],
                "optional": ["Chat", "Automations", "Finance", "Projects", "Research"],
            },
        }

        results = {}

        # Check main source files
        if self.desktop_path.exists():
            desktop_files = list(self.desktop_path.glob("*.tsx")) + list(
                self.desktop_path.glob("*.ts")
            )
            results["main_components"] = {
                "exists": True,
                "files": [f.name for f in desktop_files],
            }

            # Check for components directory
            components_path = self.desktop_path / "components"
            if components_path.exists():
                components_files = list(components_path.rglob("*"))
                results["components"] = {
                    "exists": True,
                    "files": [
                        str(f.relative_to(components_path))
                        for f in components_files
                        if f.is_file()
                    ],
                }
            else:
                results["components"] = {"exists": False, "files": []}
        else:
            results["main_components"] = {"exists": False, "files": []}
            results["components"] = {"exists": False, "files": []}

        return results

    def scan_for_dead_code(self) -> Dict:
        """Scan for potentially dead code and unused files"""
        print("🔍 Scanning for Dead Code...")

        dead_code_candidates = {"frontend": [], "desktop": [], "backend": []}

        # Check frontend for potentially unused files
        frontend_path = self.frontend_path
        if frontend_path.exists():
            # Look for files that might be unused
            potential_dead_files = [
                "components/ExampleSharedUsage.tsx",  # Might be example code
                "pages/index-dev.tsx",  # Development version
            ]

            for file_path in potential_dead_files:
                full_path = frontend_path / file_path
                if full_path.exists():
                    dead_code_candidates["frontend"].append(str(full_path))

        # Check desktop for potentially unused files
        desktop_path = self.desktop_path
        if desktop_path.exists():
            potential_dead_files = [
                "ExampleSharedUsage.tsx",  # Example code
                "web-dev-service.ts",  # Development service
            ]

            for file_path in potential_dead_files:
                full_path = desktop_path / file_path
                if full_path.exists():
                    dead_code_candidates["desktop"].append(str(full_path))

        # Check backend for potentially unused handlers
        backend_path = self.project_root / "backend" / "python-api-service"
        if backend_path.exists():
            # Look for handlers without corresponding service implementations
            handler_files = list(backend_path.glob("*_handler*.py"))
            service_files = list(backend_path.glob("*_service*.py"))

            handler_names = {f.stem.replace("_handler", "") for f in handler_files}
            service_names = {f.stem.replace("_service", "") for f in service_files}

            # Find handlers without services
            handlers_without_services = handler_names - service_names
            for handler in handlers_without_services:
                dead_code_candidates["backend"].append(f"{handler}_handler.py")

        return dead_code_candidates

    def verify_feature_ui_coverage(self) -> Dict:
        """Verify UI coverage for each of the 43 features"""
        print("🔍 Verifying Feature UI Coverage...")

        feature_coverage = {}

        # Scan frontend files for feature-related content
        frontend_files = []
        if self.frontend_path.exists():
            frontend_files = list(self.frontend_path.rglob("*.tsx")) + list(
                self.frontend_path.rglob("*.ts")
            )

        # Scan desktop files for feature-related content
        desktop_files = []
        if self.desktop_path.exists():
            desktop_files = list(self.desktop_path.rglob("*.tsx")) + list(
                self.desktop_path.rglob("*.ts")
            )

        # Filter out node_modules and other dependency directories
        def is_app_code(file_path):
            path_str = str(file_path)
            return (
                "node_modules" not in path_str
                and ".next" not in path_str
                and "target" not in path_str
                and ".pytest_cache" not in path_str
            )

        frontend_files = [f for f in frontend_files if is_app_code(f)]
        desktop_files = [f for f in desktop_files if is_app_code(f)]
        all_files = frontend_files + desktop_files

        for category, features in self.features.items():
            feature_coverage[category] = {}

            for feature in features:
                # Get search terms for this feature
                search_terms = self.feature_to_ui_map.get(
                    feature, [feature.lower().split()[0]]
                )

                # Check for UI components related to this feature
                ui_found = []
                for file_path in all_files:
                    file_content = self.read_file_safe(file_path)
                    if file_content:
                        # Check if any search terms appear in the file
                        for term in search_terms:
                            if term.lower() in file_content.lower():
                                ui_found.append(
                                    {
                                        "file": str(
                                            file_path.relative_to(self.project_root)
                                        ),
                                        "term": term,
                                    }
                                )
                                break

                # Only count as UI found if we have actual app code matches (not just node_modules)
                actual_ui_found = [
                    comp
                    for comp in ui_found
                    if "node_modules" not in comp["file"]
                    and ".next" not in comp["file"]
                    and "target" not in comp["file"]
                ]

                feature_coverage[category][feature] = {
                    "ui_found": len(actual_ui_found) > 0,
                    "components_found": actual_ui_found,
                    "search_terms": search_terms,
                    "total_matches": len(ui_found),
                    "app_matches": len(actual_ui_found),
                }

        return feature_coverage

    def read_file_safe(self, file_path: Path) -> str:
        """Safely read file content with error handling"""
        try:
            if file_path.exists() and file_path.is_file():
                return file_path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"⚠️  Warning: Could not read {file_path}: {e}")
        return ""

    def generate_report(self) -> Dict:
        """Generate comprehensive UI verification report"""
        print("🚀 Starting Comprehensive UI Availability Verification...")
        print("=" * 60)

        report = {
            "frontend_structure": self.verify_frontend_structure(),
            "desktop_structure": self.verify_desktop_structure(),
            "feature_ui_coverage": self.verify_feature_ui_coverage(),
            "dead_code_candidates": self.scan_for_dead_code(),
            "summary": {},
        }

        # Calculate summary statistics
        total_features = sum(len(features) for features in self.features.values())
        features_with_ui = 0

        for category, features in report["feature_ui_coverage"].items():
            for feature, coverage in features.items():
                if coverage["ui_found"]:
                    features_with_ui += 1

        report["summary"] = {
            "total_features": total_features,
            "features_with_ui": features_with_ui,
            "ui_coverage_percentage": round(
                (features_with_ui / total_features) * 100, 1
            )
            if total_features > 0
            else 0,
            "frontend_components_found": len(
                report["frontend_structure"].get("components", {}).get("files", [])
            ),
            "desktop_components_found": len(
                report["desktop_structure"].get("main_components", {}).get("files", [])
            ),
            "dead_code_candidates_found": sum(
                len(candidates)
                for candidates in report["dead_code_candidates"].values()
            ),
        }

        return report

    def print_report(self, report: Dict):
        """Print formatted verification report"""
        print("\n" + "=" * 60)
        print("🎯 ATOM UI AVAILABILITY VERIFICATION REPORT")
        print("=" * 60)

        # Summary
        summary = report["summary"]
        print(f"\n📊 SUMMARY")
        print(f"   Total Features: {summary['total_features']}")
        print(f"   Features with UI: {summary['features_with_ui']}")
        print(f"   UI Coverage: {summary['ui_coverage_percentage']}%")
        print(f"   Frontend Components: {summary['frontend_components_found']}")
        print(f"   Desktop Components: {summary['desktop_components_found']}")
        print(f"   Dead Code Candidates: {summary['dead_code_candidates_found']}")

        # Feature Coverage Details
        print(f"\n🎯 FEATURE UI COVERAGE")
        for category, features in report["feature_ui_coverage"].items():
            print(f"\n   {category.upper().replace('_', ' ')}:")
            for feature, coverage in features.items():
                status = "✅" if coverage["ui_found"] else "❌"
                print(f"     {status} {feature}")
                if coverage["ui_found"] and coverage["components_found"]:
                    for component in coverage["components_found"][
                        :2
                    ]:  # Show first 2 matches
                        print(f"        📁 {component['file']}")

        # Dead Code Analysis
        dead_code = report["dead_code_candidates"]
        if any(dead_code.values()):
            print(f"\n⚠️  DEAD CODE CANDIDATES")
            for area, files in dead_code.items():
                if files:
                    print(f"\n   {area.upper()}:")
                    for file in files:
                        print(f"     🗑️  {file}")

        # Recommendations
        print(f"\n💡 RECOMMENDATIONS")
        coverage = summary["ui_coverage_percentage"]
        if coverage >= 90:
            print(
                "   ✅ Excellent UI coverage! Focus on polishing existing components."
            )
        elif coverage >= 70:
            print("   📈 Good UI coverage. Consider adding missing feature interfaces.")
        elif coverage >= 50:
            print("   ⚠️  Moderate UI coverage. Prioritize high-impact feature UIs.")
        else:
            print(
                "   🚨 Low UI coverage. Significant development needed for feature interfaces."
            )

        if summary["dead_code_candidates_found"] > 0:
            print("   🧹 Consider removing identified dead code candidates.")

        print(f"\n🎯 NEXT STEPS")
        print("   1. Review feature UI coverage and prioritize missing interfaces")
        print("   2. Remove identified dead code candidates")
        print("   3. Enhance settings pages for integration configuration")
        print("   4. Test UI components with real backend integrations")

        print(f"\n✅ UI Verification Completed!")


def main():
    """Main execution function"""
    verifier = UIVerification()
    report = verifier.generate_report()
    verifier.print_report(report)


if __name__ == "__main__":
    main()
