#!/usr/bin/env python3
"""
Enhanced ATOM UI Availability Verification Script
Comprehensive verification of UI components with functional analysis
across web app and desktop app, including settings and dead code detection.
"""

import os
import sys
import json
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional


class EnhancedUIVerification:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.frontend_path = self.project_root / "frontend-nextjs"
        self.desktop_path = self.project_root / "desktop" / "tauri" / "src"
        self.backend_path = self.project_root / "backend" / "python-api-service"

        # Define all features with detailed UI component expectations
        self.features = {
            "core_ui_components": [
                "Dashboard with calendar, tasks, and messages",
                "Calendar management interface",
                "Task management interface",
                "Communication hub (email/chat)",
                "Search functionality",
                "Settings and configuration",
                "Voice/audio controls",
                "Automation workflows",
                "Financial dashboard",
                "Project tracking",
            ],
            "integration_ui": [
                "Integration settings for Gmail/Outlook",
                "Integration settings for Slack/Teams/Discord",
                "Integration settings for Google Calendar/Outlook Calendar",
                "Integration settings for Notion/Trello/Asana/Jira",
                "Integration settings for Google Drive/Dropbox/OneDrive/Box",
                "Integration settings for Plaid/Quickbooks/Xero/Stripe",
                "Integration settings for Salesforce/HubSpot",
                "Integration settings for GitHub",
            ],
            "desktop_specific": [
                "Desktop chat interface",
                "Sales management dashboard",
                "Project management interface",
                "Support ticket system",
                "Research tools",
                "Social media management",
                "Content creation tools",
                "Shopping assistant",
                "Financial analysis",
                "Competitor analysis",
                "Learning assistant",
                "Project health monitoring",
            ],
            "advanced_features": [
                "Wake word detection UI",
                "Multi-agent system interface",
                "Cross-platform orchestration",
                "Automated reporting",
                "Template-based content creation",
                "Data collection and API management",
                "Meeting transcription interface",
                "Reminder and notification system",
            ],
        }

        # Map features to specific UI component patterns and requirements
        self.feature_requirements = {
            # Core UI Components
            "Dashboard with calendar, tasks, and messages": {
                "components": ["Dashboard", "Calendar", "TaskList", "MessageList"],
                "required_elements": [
                    "calendar events",
                    "task list",
                    "message preview",
                ],
                "interaction": ["refresh", "complete task", "mark as read"],
            },
            "Calendar management interface": {
                "components": ["Calendar", "EventForm", "Scheduler"],
                "required_elements": [
                    "event creation",
                    "time slots",
                    "conflict detection",
                ],
                "interaction": ["create event", "edit event", "delete event"],
            },
            "Task management interface": {
                "components": ["TaskList", "TaskForm", "ProjectBoard"],
                "required_elements": ["task creation", "priority setting", "due dates"],
                "interaction": ["add task", "complete task", "filter tasks"],
            },
            "Communication hub (email/chat)": {
                "components": ["MessageList", "ChatInterface", "EmailComposer"],
                "required_elements": [
                    "message threads",
                    "compose area",
                    "platform indicators",
                ],
                "interaction": ["send message", "reply", "mark unread"],
            },
            "Search functionality": {
                "components": ["SearchBar", "SmartSearch", "SearchResults"],
                "required_elements": ["search input", "results display", "filters"],
                "interaction": ["search", "filter results", "clear search"],
            },
            "Settings and configuration": {
                "components": ["Settings", "IntegrationSettings", "VoiceSettings"],
                "required_elements": [
                    "api key inputs",
                    "toggle switches",
                    "save buttons",
                ],
                "interaction": ["save settings", "test connection", "reset"],
            },
            "Voice/audio controls": {
                "components": ["AudioRecorder", "VoiceSettings", "WakeWordDetector"],
                "required_elements": [
                    "record button",
                    "audio visualization",
                    "settings",
                ],
                "interaction": ["start recording", "stop recording", "configure"],
            },
            "Automation workflows": {
                "components": ["Automations", "WorkflowEditor", "TriggerSettings"],
                "required_elements": [
                    "workflow list",
                    "trigger configuration",
                    "action setup",
                ],
                "interaction": ["create workflow", "toggle status", "run manually"],
            },
            "Financial dashboard": {
                "components": ["FinanceDashboard", "TransactionList", "BudgetView"],
                "required_elements": [
                    "transaction history",
                    "budget overview",
                    "charts",
                ],
                "interaction": ["filter transactions", "view details", "export"],
            },
            "Project tracking": {
                "components": ["Projects", "ProjectHealth", "ProgressTracker"],
                "required_elements": [
                    "project list",
                    "status indicators",
                    "progress bars",
                ],
                "interaction": ["view project", "update status", "add milestone"],
            },
            # Integration UI
            "Integration settings for Gmail/Outlook": {
                "components": ["EmailIntegration", "OAuthSettings"],
                "required_elements": [
                    "api key input",
                    "connect button",
                    "status indicator",
                ],
                "interaction": ["connect account", "disconnect", "test connection"],
            },
            "Integration settings for Slack/Teams/Discord": {
                "components": ["ChatIntegration", "ChannelSettings"],
                "required_elements": [
                    "webhook url",
                    "channel selection",
                    "permissions",
                ],
                "interaction": ["connect", "configure channels", "test message"],
            },
            "Integration settings for Google Calendar/Outlook Calendar": {
                "components": ["CalendarIntegration", "EventSyncSettings"],
                "required_elements": [
                    "calendar selection",
                    "sync options",
                    "conflict resolution",
                ],
                "interaction": ["sync calendars", "set preferences", "manual sync"],
            },
            "Integration settings for Notion/Trello/Asana/Jira": {
                "components": ["TaskIntegration", "BoardSettings"],
                "required_elements": [
                    "api key",
                    "workspace selection",
                    "board mapping",
                ],
                "interaction": ["connect", "select boards", "sync tasks"],
            },
            "Integration settings for Google Drive/Dropbox/OneDrive/Box": {
                "components": ["FileIntegration", "FolderSettings"],
                "required_elements": [
                    "folder selection",
                    "sync options",
                    "permissions",
                ],
                "interaction": ["connect", "select folders", "set sync frequency"],
            },
            "Integration settings for Plaid/Quickbooks/Xero/Stripe": {
                "components": ["FinanceIntegration", "AccountSettings"],
                "required_elements": [
                    "bank connection",
                    "account selection",
                    "transaction settings",
                ],
                "interaction": ["connect bank", "select accounts", "set categories"],
            },
            "Integration settings for Salesforce/HubSpot": {
                "components": ["CRMIntegration", "LeadSettings"],
                "required_elements": [
                    "api credentials",
                    "object mapping",
                    "sync rules",
                ],
                "interaction": ["connect crm", "map fields", "test sync"],
            },
            "Integration settings for GitHub": {
                "components": ["GitHubIntegration", "RepositorySettings"],
                "required_elements": [
                    "personal token",
                    "repo selection",
                    "webhook setup",
                ],
                "interaction": ["connect", "select repos", "configure webhooks"],
            },
            # Desktop Specific
            "Desktop chat interface": {
                "components": ["Chat", "MessageInput", "ConversationList"],
                "required_elements": ["message history", "input field", "send button"],
                "interaction": ["send message", "view history", "clear chat"],
            },
            "Sales management dashboard": {
                "components": ["Sales", "LeadList", "PipelineView"],
                "required_elements": [
                    "lead list",
                    "pipeline stages",
                    "conversion metrics",
                ],
                "interaction": ["add lead", "update status", "view details"],
            },
            "Project management interface": {
                "components": ["Projects", "TaskBoard", "TeamView"],
                "required_elements": [
                    "project overview",
                    "task assignments",
                    "timeline",
                ],
                "interaction": ["create project", "assign tasks", "update progress"],
            },
            "Support ticket system": {
                "components": ["Support", "TicketList", "ResponseTemplates"],
                "required_elements": [
                    "ticket queue",
                    "customer info",
                    "response history",
                ],
                "interaction": ["view ticket", "respond", "escalate"],
            },
            "Research tools": {
                "components": ["Research", "SearchPanel", "ResultsView"],
                "required_elements": [
                    "search interface",
                    "results organization",
                    "saving options",
                ],
                "interaction": ["search", "save results", "export findings"],
            },
            "Social media management": {
                "components": ["Social", "PostComposer", "ScheduleView"],
                "required_elements": [
                    "platform selection",
                    "content editor",
                    "scheduling",
                ],
                "interaction": ["create post", "schedule", "analyze performance"],
            },
            "Content creation tools": {
                "components": ["Content", "Editor", "TemplateGallery"],
                "required_elements": [
                    "content editor",
                    "template selection",
                    "preview",
                ],
                "interaction": ["create content", "apply template", "publish"],
            },
            "Shopping assistant": {
                "components": ["Shopping", "ProductSearch", "ListManager"],
                "required_elements": [
                    "product search",
                    "price comparison",
                    "shopping lists",
                ],
                "interaction": ["search products", "add to list", "compare prices"],
            },
            "Financial analysis": {
                "components": ["Finance", "ChartView", "ReportGenerator"],
                "required_elements": [
                    "financial charts",
                    "data tables",
                    "export options",
                ],
                "interaction": ["view reports", "filter data", "export"],
            },
            "Competitor analysis": {
                "components": [
                    "CompetitorAnalysis",
                    "ComparisonView",
                    "MetricsDashboard",
                ],
                "required_elements": [
                    "competitor list",
                    "metric comparison",
                    "trend analysis",
                ],
                "interaction": ["add competitor", "compare metrics", "view trends"],
            },
            "Learning assistant": {
                "components": ["LearningAssistant", "StudyPlan", "ProgressTracker"],
                "required_elements": [
                    "learning goals",
                    "study materials",
                    "progress tracking",
                ],
                "interaction": ["set goals", "track progress", "review materials"],
            },
            "Project health monitoring": {
                "components": ["ProjectHealth", "MetricsView", "AlertSettings"],
                "required_elements": ["health metrics", "trend indicators", "alerts"],
                "interaction": ["view metrics", "set alerts", "export report"],
            },
            # Advanced Features
            "Wake word detection UI": {
                "components": [
                    "WakeWordDetector",
                    "AudioSettings",
                    "TrainingInterface",
                ],
                "required_elements": [
                    "detection status",
                    "sensitivity controls",
                    "training",
                ],
                "interaction": ["enable/disable", "train model", "test detection"],
            },
            "Multi-agent system interface": {
                "components": ["AgentManager", "RoleSettings", "CoordinationView"],
                "required_elements": [
                    "agent status",
                    "role assignments",
                    "coordination logs",
                ],
                "interaction": ["assign roles", "view logs", "configure agents"],
            },
            "Cross-platform orchestration": {
                "components": ["Orchestration", "WorkflowView", "IntegrationStatus"],
                "required_elements": [
                    "workflow visualization",
                    "integration status",
                    "execution logs",
                ],
                "interaction": ["view workflows", "monitor status", "troubleshoot"],
            },
            "Automated reporting": {
                "components": [
                    "ReportGenerator",
                    "ScheduleSettings",
                    "TemplateManager",
                ],
                "required_elements": [
                    "report templates",
                    "scheduling options",
                    "delivery settings",
                ],
                "interaction": ["generate report", "schedule", "customize template"],
            },
            "Template-based content creation": {
                "components": ["TemplateManager", "ContentEditor", "PreviewPanel"],
                "required_elements": ["template gallery", "content editor", "preview"],
                "interaction": ["select template", "edit content", "preview"],
            },
            "Data collection and API management": {
                "components": ["DataCollector", "APIManager", "DataSourceSettings"],
                "required_elements": [
                    "data sources",
                    "collection settings",
                    "api endpoints",
                ],
                "interaction": ["add source", "configure collection", "test api"],
            },
            "Meeting transcription interface": {
                "components": ["Transcription", "AudioPlayer", "SummaryView"],
                "required_elements": [
                    "audio controls",
                    "transcript display",
                    "summary generation",
                ],
                "interaction": ["upload audio", "transcribe", "generate summary"],
            },
            "Reminder and notification system": {
                "components": ["Reminders", "NotificationSettings", "AlertManager"],
                "required_elements": [
                    "reminder list",
                    "notification preferences",
                    "delivery methods",
                ],
                "interaction": ["set reminder", "configure notifications", "snooze"],
            },
        }

    def analyze_component_functionality(
        self, file_path: Path, component_name: str
    ) -> Dict:
        """Analyze a component file for functional completeness"""
        try:
            content = file_path.read_text(encoding="utf-8")

            analysis = {
                "file": str(file_path.relative_to(self.project_root)),
                "component_name": component_name,
                "has_imports": bool(re.search(r"import\s+.*from|import\s+.*", content)),
                "has_exports": bool(
                    re.search(r"export\s+(default\s+)?(class|function|const)", content)
                ),
                "has_state": bool(
                    re.search(r"useState|useReducer|this\.state", content)
                ),
                "has_effects": bool(re.search(r"useEffect", content)),
                "has_event_handlers": bool(
                    re.search(r"onClick|onChange|onSubmit|handle[A-Z]", content)
                ),
                "has_api_calls": bool(
                    re.search(r"fetch|axios|\.get\(|\.post\(", content)
                ),
                "has_conditional_rendering": bool(
                    re.search(r"&&|\?|if\s*\(|switch", content)
                ),
                "has_jsx_elements": bool(re.search(r"<[A-Z]|</[A-Z]", content)),
                "line_count": len(content.splitlines()),
                "is_empty": len(content.strip()) == 0,
            }

            return analysis
        except Exception as e:
            return {
                "file": str(file_path.relative_to(self.project_root)),
                "component_name": component_name,
                "error": str(e),
                "is_empty": True,
            }

    def scan_ui_components(self) -> Dict:
        """Scan for all UI components across frontend and desktop"""
        print("🔍 Scanning UI Components...")

        components = {
            "frontend": {"pages": {}, "components": {}},
            "desktop": {"pages": {}, "components": {}},
        }

        # Scan frontend pages
        pages_path = self.frontend_path / "pages"
        if pages_path.exists():
            for page_file in pages_path.rglob("*.tsx"):
                if self._is_app_code(page_file):
                    component_name = page_file.stem
                    if page_file.parent != pages_path:
                        component_name = f"{page_file.parent.name}/{component_name}"
                    analysis = self.analyze_component_functionality(
                        page_file, component_name
                    )
                    components["frontend"]["pages"][
                        str(page_file.relative_to(pages_path))
                    ] = analysis

        # Scan frontend components
        components_path = self.frontend_path / "components"
        if components_path.exists():
            for comp_file in components_path.rglob("*.tsx"):
                if self._is_app_code(comp_file):
                    component_name = comp_file.stem
                    if comp_file.parent != components_path:
                        component_name = f"{comp_file.parent.name}/{component_name}"
                    analysis = self.analyze_component_functionality(
                        comp_file, component_name
                    )
                    components["frontend"]["components"][
                        str(comp_file.relative_to(components_path))
                    ] = analysis

        # Scan desktop components
        if self.desktop_path.exists():
            for desktop_file in self.desktop_path.rglob("*.tsx"):
                if self._is_app_code(desktop_file):
                    component_name = desktop_file.stem
                    analysis = self.analyze_component_functionality(
                        desktop_file, component_name
                    )
                    components["desktop"]["pages"][component_name] = analysis

            # Scan desktop components directory
            desktop_components_path = self.desktop_path / "components"
            if desktop_components_path.exists():
                for comp_file in desktop_components_path.rglob("*.tsx"):
                    if self._is_app_code(comp_file):
                        component_name = comp_file.stem
                        if comp_file.parent != desktop_components_path:
                            component_name = f"{comp_file.parent.name}/{component_name}"
                        analysis = self.analyze_component_functionality(
                            comp_file, component_name
                        )
                        components["desktop"]["components"][
                            str(comp_file.relative_to(desktop_components_path))
                        ] = analysis

        return components

    def verify_feature_coverage(self, components: Dict) -> Dict:
        """Verify feature coverage with functional analysis"""
        print("🔍 Verifying Feature Coverage...")

        feature_coverage = {}

        for category, features in self.features.items():
            feature_coverage[category] = {}

            for feature in features:
                requirements = self.feature_requirements.get(feature, {})
                expected_components = requirements.get("components", [])
                expected_elements = requirements.get("required_elements", [])
                expected_interactions = requirements.get("interaction", [])

                # Find matching components
                matching_components = self._find_matching_components(
                    components, expected_components
                )

                # Analyze functional completeness
                functional_analysis = self._analyze_functional_completeness(
                    matching_components
                )

                feature_coverage[category][feature] = {
                    "expected_components": expected_components,
                    "expected_elements": expected_elements,
                    "expected_interactions": expected_interactions,
                    "matching_components": matching_components,
                    "functional_analysis": functional_analysis,
                    "coverage_score": self._calculate_coverage_score(
                        functional_analysis, len(expected_components)
                    ),
                    "status": self._get_feature_status(
                        functional_analysis, len(expected_components)
                    ),
                }

        return feature_coverage

    def _find_matching_components(
        self, components: Dict, expected_components: List[str]
    ) -> List[Dict]:
        """Find components that match expected component names"""
        matching = []

        # Search in frontend pages
        for page_path, analysis in components["frontend"]["pages"].items():
            component_name = analysis["component_name"].lower()
            for expected in expected_components:
                if expected.lower() in component_name:
                    matching.append(analysis)
                    break

        # Search in frontend components
        for comp_path, analysis in components["frontend"]["components"].items():
            component_name = analysis["component_name"].lower()
            for expected in expected_components:
                if expected.lower() in component_name:
                    matching.append(analysis)
                    break

        # Search in desktop pages
        for page_name, analysis in components["desktop"]["pages"].items():
            component_name = analysis["component_name"].lower()
            for expected in expected_components:
                if expected.lower() in component_name:
                    matching.append(analysis)
                    break

        # Search in desktop components
        for comp_path, analysis in components["desktop"]["components"].items():
            component_name = analysis["component_name"].lower()
            for expected in expected_components:
                if expected.lower() in component_name:
                    matching.append(analysis)
                    break

        return matching

    def _analyze_functional_completeness(self, components: List[Dict]) -> Dict:
        """Analyze functional completeness of components"""
        if not components:
            return {
                "total_components": 0,
                "functional_components": 0,
                "has_state": False,
                "has_effects": False,
                "has_event_handlers": False,
                "has_api_calls": False,
                "has_conditional_rendering": False,
                "has_jsx_elements": False,
                "average_line_count": 0,
            }

        stats = {
            "total_components": len(components),
            "functional_components": 0,
            "has_state": 0,
            "has_effects": 0,
            "has_event_handlers": 0,
            "has_api_calls": 0,
            "has_conditional_rendering": 0,
            "has_jsx_elements": 0,
            "total_line_count": 0,
        }

        for comp in components:
            if not comp.get("is_empty", True):
                stats["functional_components"] += 1
                if comp.get("has_state", False):
                    stats["has_state"] += 1
                if comp.get("has_effects", False):
                    stats["has_effects"] += 1
                if comp.get("has_event_handlers", False):
                    stats["has_event_handlers"] += 1
                if comp.get("has_api_calls", False):
                    stats["has_api_calls"] += 1
                if comp.get("has_conditional_rendering", False):
                    stats["has_conditional_rendering"] += 1
                if comp.get("has_jsx_elements", False):
                    stats["has_jsx_elements"] += 1
                stats["total_line_count"] += comp.get("line_count", 0)

        return {
            "total_components": stats["total_components"],
            "functional_components": stats["functional_components"],
            "has_state": stats["has_state"] > 0,
            "has_effects": stats["has_effects"] > 0,
            "has_event_handlers": stats["has_event_handlers"] > 0,
            "has_api_calls": stats["has_api_calls"] > 0,
            "has_conditional_rendering": stats["has_conditional_rendering"] > 0,
            "has_jsx_elements": stats["has_jsx_elements"] > 0,
            "average_line_count": stats["total_line_count"]
            / max(1, stats["functional_components"]),
        }

    def _calculate_coverage_score(self, analysis: Dict, expected_count: int) -> float:
        """Calculate coverage score for a feature"""
        if expected_count == 0:
            return 0.0

        component_score = min(analysis["functional_components"] / expected_count, 1.0)

        # Weight different aspects of functionality
        functionality_weights = {
            "has_state": 0.15,
            "has_effects": 0.15,
            "has_event_handlers": 0.20,
            "has_api_calls": 0.20,
            "has_conditional_rendering": 0.15,
            "has_jsx_elements": 0.15,
        }

        functionality_score = sum(
            weight * (1.0 if analysis[key] else 0.0)
            for key, weight in functionality_weights.items()
        )

        # Combine component count and functionality
        return (component_score * 0.6) + (functionality_score * 0.4)

    def _get_feature_status(self, analysis: Dict, expected_count: int) -> str:
        """Get feature status based on analysis"""
        coverage_score = self._calculate_coverage_score(analysis, expected_count)

        if coverage_score >= 0.8:
            return "✅ Complete"
        elif coverage_score >= 0.5:
            return "🟡 Partial"
        elif coverage_score >= 0.2:
            return "🟠 Basic"
        else:
            return "❌ Missing"

    def _is_app_code(self, file_path: Path) -> bool:
        """Check if file is application code (not dependencies)"""
        path_str = str(file_path)
        return (
            "node_modules" not in path_str
            and ".next" not in path_str
            and "target" not in path_str
            and ".pytest_cache" not in path_str
        )

    def scan_dead_code(self) -> Dict:
        """Scan for potentially dead code"""
        print("🔍 Scanning for Dead Code...")

        dead_code_candidates = {"frontend": [], "desktop": [], "backend_handlers": []}

        # Check backend handlers without services
        if self.backend_path.exists():
            handler_files = list(self.backend_path.glob("*_handler*.py"))
            service_files = list(self.backend_path.glob("*_service*.py"))

            handler_names = {f.stem.replace("_handler", "") for f in handler_files}
            service_names = {f.stem.replace("_service", "") for f in service_files}

            # Find handlers without services
            handlers_without_services = handler_names - service_names
            for handler in handlers_without_services:
                dead_code_candidates["backend_handlers"].append(f"{handler}_handler.py")

        # Check for empty or minimal components
        components = self.scan_ui_components()

        for area in ["frontend", "desktop"]:
            for section in ["pages", "components"]:
                for comp_path, analysis in components[area][section].items():
                    if (
                        analysis.get("is_empty", True)
                        or analysis.get("line_count", 0) < 10
                    ):
                        dead_code_candidates[area].append(
                            f"{comp_path} (minimal/empty)"
                        )

        return dead_code_candidates

    def generate_report(self) -> Dict:
        """Generate comprehensive enhanced UI verification report"""
        print("🚀 Starting Enhanced UI Availability Verification...")
        print("=" * 60)

        # Scan components
        components = self.scan_ui_components()

        # Verify feature coverage
        feature_coverage = self.verify_feature_coverage(components)

        # Scan for dead code
        dead_code = self.scan_dead_code()

        # Calculate summary statistics
        total_features = sum(len(features) for features in self.features.values())
        complete_features = 0
        partial_features = 0
        basic_features = 0
        missing_features = 0

        for category, features in feature_coverage.items():
            for feature, coverage in features.items():
                status = coverage["status"]
                if "Complete" in status:
                    complete_features += 1
                elif "Partial" in status:
                    partial_features += 1
                elif "Basic" in status:
                    basic_features += 1
                else:
                    missing_features += 1

        report = {
            "components": components,
            "feature_coverage": feature_coverage,
            "dead_code_candidates": dead_code,
            "summary": {
                "total_features": total_features,
                "complete_features": complete_features,
                "partial_features": partial_features,
                "basic_features": basic_features,
                "missing_features": missing_features,
                "overall_coverage_percentage": round(
                    (complete_features + partial_features * 0.7 + basic_features * 0.3)
                    / total_features
                    * 100,
                    1,
                ),
                "total_components_found": len(components["frontend"]["pages"])
                + len(components["frontend"]["components"])
                + len(components["desktop"]["pages"])
                + len(components["desktop"]["components"]),
                "dead_code_candidates_found": sum(
                    len(candidates) for candidates in dead_code.values()
                ),
            },
        }

        return report

    def print_report(self, report: Dict):
        """Print formatted enhanced verification report"""
        print("\n" + "=" * 60)
        print("🎯 ENHANCED ATOM UI AVAILABILITY VERIFICATION REPORT")
        print("=" * 60)

        # Summary
        summary = report["summary"]
        print(f"\n📊 SUMMARY")
        print(f"   Total Features: {summary['total_features']}")
        print(f"   ✅ Complete: {summary['complete_features']}")
        print(f"   🟡 Partial: {summary['partial_features']}")
        print(f"   🟠 Basic: {summary['basic_features']}")
        print(f"   ❌ Missing: {summary['missing_features']}")
        print(f"   Overall Coverage: {summary['overall_coverage_percentage']}%")
        print(f"   Total Components: {summary['total_components_found']}")
        print(f"   Dead Code Candidates: {summary['dead_code_candidates_found']}")

        # Feature Coverage Details
        print(f"\n🎯 FEATURE COVERAGE ANALYSIS")
        for category, features in report["feature_coverage"].items():
            print(f"\n   {category.upper().replace('_', ' ')}:")
            for feature, coverage in features.items():
                status = coverage["status"]
                score = coverage["coverage_score"]
                matching_count = len(coverage["matching_components"])
                expected_count = len(coverage["expected_components"])

                print(f"     {status} {feature}")
                print(
                    f"        📊 Coverage: {score:.1%} ({matching_count}/{expected_count} components)"
                )

                # Show functional analysis
                func = coverage["functional_analysis"]
                if func["functional_components"] > 0:
                    print(
                        f"        🔧 Functional: {func['functional_components']} components"
                    )
                    if func["has_state"]:
                        print(f"        📱 State management")
                    if func["has_effects"]:
                        print(f"        🔄 Side effects")
                    if func["has_event_handlers"]:
                        print(f"        🖱️  Event handlers")
                    if func["has_api_calls"]:
                        print(f"        🌐 API integration")
                    if func["has_conditional_rendering"]:
                        print(f"        🎨 Conditional UI")

                # Show matching components
                if coverage["matching_components"]:
                    for comp in coverage["matching_components"][:2]:  # Show first 2
                        print(f"        📁 {comp['file']}")

        # Dead Code Analysis
        dead_code = report["dead_code_candidates"]
        if any(dead_code.values()):
            print(f"\n⚠️  DEAD CODE CANDIDATES")
            for area, files in dead_code.items():
                if files:
                    print(f"\n   {area.upper()}:")
                    for file in files[:10]:  # Show first 10
                        print(f"     🗑️  {file}")

        # Recommendations
        print(f"\n💡 RECOMMENDATIONS")
        coverage = summary["overall_coverage_percentage"]
        if coverage >= 90:
            print(
                "   ✅ Excellent UI coverage! Focus on polishing existing components."
            )
        elif coverage >= 70:
            print("   📈 Good UI coverage. Consider enhancing partial implementations.")
        elif coverage >= 50:
            print(
                "   ⚠️  Moderate UI coverage. Prioritize high-impact feature development."
            )
        else:
            print(
                "   🚨 Low UI coverage. Significant development needed for core features."
            )

        if summary["dead_code_candidates_found"] > 0:
            print("   🧹 Consider removing identified dead code candidates.")

        print(f"\n🎯 NEXT STEPS")
        print("   1. Review feature coverage and prioritize missing interfaces")
        print("   2. Remove identified dead code candidates")
        print("   3. Enhance settings pages for integration configuration")
        print("   4. Test UI components with real backend integrations")
        print("   5. Focus on completing partial implementations")

        print(f"\n✅ Enhanced UI Verification Completed!")


def main():
    """Main execution function"""
    verifier = EnhancedUIVerification()
    report = verifier.generate_report()
    verifier.print_report(report)


if __name__ == "__main__":
    main()
