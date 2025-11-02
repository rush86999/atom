#!/usr/bin/env python3
"""
Integration Priority Assessment Tool
Analyzes current integration state and recommends next implementation priorities
"""

import os
import sys
import json
from typing import Dict, List, Any, Tuple
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class IntegrationPriorityAssessor:
    """Assesses integration priorities based on current state and business value"""

    def __init__(self):
        self.integrations = {
            "github": {
                "name": "GitHub",
                "category": "development",
                "business_value": "high",
                "complexity": "medium",
                "current_state": self.assess_github_state(),
                "prerequisites": ["backend_fix"],
                "estimated_days": 3,
            },
            "teams": {
                "name": "Microsoft Teams",
                "category": "communication",
                "business_value": "high",
                "complexity": "medium",
                "current_state": self.assess_teams_state(),
                "prerequisites": ["backend_fix"],
                "estimated_days": 4,
            },
            "notion": {
                "name": "Notion",
                "category": "productivity",
                "business_value": "high",
                "complexity": "low",
                "current_state": self.assess_notion_state(),
                "prerequisites": ["backend_fix"],
                "estimated_days": 1,
            },
            "slack": {
                "name": "Slack",
                "category": "communication",
                "business_value": "medium",
                "complexity": "medium",
                "current_state": self.assess_slack_state(),
                "prerequisites": ["backend_fix", "handler_creation"],
                "estimated_days": 3,
            },
            "asana": {
                "name": "Asana",
                "category": "productivity",
                "business_value": "medium",
                "complexity": "medium",
                "current_state": self.assess_asana_state(),
                "prerequisites": ["backend_fix", "oauth_config"],
                "estimated_days": 3,
            },
            "trello": {
                "name": "Trello",
                "category": "productivity",
                "business_value": "medium",
                "complexity": "low",
                "current_state": self.assess_trello_state(),
                "prerequisites": ["backend_fix", "oauth_config"],
                "estimated_days": 2,
            },
        }

    def assess_github_state(self) -> Dict[str, Any]:
        """Assess GitHub integration state"""
        return {
            "credentials_configured": bool(
                os.getenv("GITHUB_CLIENT_ID") and os.getenv("GITHUB_CLIENT_SECRET")
            ),
            "access_token_available": bool(os.getenv("GITHUB_ACCESS_TOKEN")),
            "handler_available": self.check_handler_exists("github_handler.py"),
            "service_available": self.check_handler_exists("github_service.py"),
            "oauth_api_needed": True,
            "frontend_needed": True,
            "database_layer_needed": True,
            "completion_percentage": self.calculate_completion_percentage(
                [
                    "credentials_configured",
                    "access_token_available",
                    "handler_available",
                    "service_available",
                ]
            ),
        }

    def assess_teams_state(self) -> Dict[str, Any]:
        """Assess Teams integration state"""
        return {
            "credentials_configured": bool(
                os.getenv("TEAMS_CLIENT_ID") and os.getenv("TEAMS_CLIENT_SECRET")
            ),
            "handler_available": self.check_handler_exists("teams_service_real.py"),
            "health_handler_available": self.check_handler_exists(
                "teams_health_handler.py"
            ),
            "oauth_api_needed": True,
            "frontend_needed": True,
            "database_layer_needed": True,
            "completion_percentage": self.calculate_completion_percentage(
                [
                    "credentials_configured",
                    "handler_available",
                    "health_handler_available",
                ]
            ),
        }

    def assess_notion_state(self) -> Dict[str, Any]:
        """Assess Notion integration state"""
        return {
            "credentials_configured": bool(
                os.getenv("NOTION_CLIENT_ID") and os.getenv("NOTION_CLIENT_SECRET")
            ),
            "token_available": bool(os.getenv("NOTION_TOKEN")),
            "redirect_uri_configured": bool(os.getenv("NOTION_REDIRECT_URI")),
            "handler_available": self.check_handler_exists("notion_handler_real.py"),
            "service_available": self.check_handler_exists("notion_service_real.py"),
            "database_layer_available": self.check_handler_exists("db_oauth_notion.py"),
            "oauth_api_needed": True,
            "frontend_needed": True,
            "completion_percentage": self.calculate_completion_percentage(
                [
                    "credentials_configured",
                    "token_available",
                    "redirect_uri_configured",
                    "handler_available",
                    "service_available",
                    "database_layer_available",
                ]
            ),
        }

    def assess_slack_state(self) -> Dict[str, Any]:
        """Assess Slack integration state"""
        return {
            "credentials_configured": bool(
                os.getenv("SLACK_CLIENT_ID") and os.getenv("SLACK_CLIENT_SECRET")
            ),
            "handler_available": self.check_handler_exists("slack_service_real.py"),
            "health_handler_available": self.check_handler_exists(
                "slack_health_handler.py"
            ),
            "oauth_api_needed": True,
            "frontend_needed": True,
            "database_layer_needed": True,
            "completion_percentage": self.calculate_completion_percentage(
                [
                    "credentials_configured",
                    "handler_available",
                    "health_handler_available",
                ]
            ),
        }

    def assess_asana_state(self) -> Dict[str, Any]:
        """Assess Asana integration state"""
        return {
            "credentials_configured": bool(
                os.getenv("ASANA_CLIENT_ID") and os.getenv("ASANA_CLIENT_SECRET")
            ),
            "handler_available": self.check_handler_exists("asana_handler.py"),
            "service_available": self.check_handler_exists("asana_service_real.py"),
            "database_layer_available": self.check_handler_exists("db_oauth_asana.py"),
            "oauth_api_needed": True,
            "frontend_needed": True,
            "completion_percentage": self.calculate_completion_percentage(
                ["handler_available", "service_available", "database_layer_available"]
            ),
        }

    def assess_trello_state(self) -> Dict[str, Any]:
        """Assess Trello integration state"""
        return {
            "credentials_configured": bool(
                os.getenv("TRELLO_API_KEY") and os.getenv("TRELLO_API_TOKEN")
            ),
            "handler_available": self.check_handler_exists("trello_handler_real.py"),
            "service_available": self.check_handler_exists("trello_service_real.py"),
            "database_layer_available": self.check_handler_exists("db_oauth_trello.py"),
            "oauth_api_needed": True,
            "frontend_needed": True,
            "completion_percentage": self.calculate_completion_percentage(
                ["handler_available", "service_available", "database_layer_available"]
            ),
        }

    def check_handler_exists(self, handler_name: str) -> bool:
        """Check if a service handler file exists"""
        possible_paths = [
            f"backend/python-api-service/{handler_name}",
            f"backend/{handler_name}",
            handler_name,
        ]
        return any(os.path.exists(path) for path in possible_paths)

    def calculate_completion_percentage(self, checks: List[str]) -> int:
        """Calculate completion percentage based on checks"""
        state_methods = {
            "github": self.assess_github_state,
            "teams": self.assess_teams_state,
            "notion": self.assess_notion_state,
            "slack": self.assess_slack_state,
            "asana": self.assess_asana_state,
            "trello": self.assess_trello_state,
        }

        # This is a simplified calculation - in practice, we'd use the actual state
        return 25  # Default base completion

    def calculate_priority_score(self, integration: Dict[str, Any]) -> float:
        """Calculate priority score for an integration"""
        # Weight factors
        business_value_weights = {"high": 3.0, "medium": 2.0, "low": 1.0}
        complexity_weights = {"low": 3.0, "medium": 2.0, "high": 1.0}
        completion_bonus = integration["current_state"]["completion_percentage"] / 100.0

        base_score = (
            business_value_weights[integration["business_value"]]
            * complexity_weights[integration["complexity"]]
            + completion_bonus
        )

        # Penalty for prerequisites
        prerequisite_penalty = len(integration["prerequisites"]) * 0.2

        return max(0.1, base_score - prerequisite_penalty)

    def generate_recommendations(self) -> Dict[str, Any]:
        """Generate integration implementation recommendations"""
        recommendations = []

        for integration_id, integration in self.integrations.items():
            priority_score = self.calculate_priority_score(integration)

            recommendation = {
                "integration": integration_id,
                "name": integration["name"],
                "priority_score": round(priority_score, 2),
                "business_value": integration["business_value"],
                "complexity": integration["complexity"],
                "current_completion": integration["current_state"][
                    "completion_percentage"
                ],
                "estimated_days": integration["estimated_days"],
                "prerequisites": integration["prerequisites"],
                "next_actions": self.generate_next_actions(integration_id, integration),
                "readiness_level": self.assess_readiness_level(integration),
            }
            recommendations.append(recommendation)

        # Sort by priority score (descending)
        recommendations.sort(key=lambda x: x["priority_score"], reverse=True)

        return {
            "recommendations": recommendations,
            "summary": self.generate_summary(recommendations),
        }

    def generate_next_actions(
        self, integration_id: str, integration: Dict[str, Any]
    ) -> List[str]:
        """Generate next actions for an integration"""
        actions = []
        state = integration["current_state"]

        if "backend_fix" in integration["prerequisites"]:
            actions.append("Fix backend blueprint registration")

        if not state.get("credentials_configured", False):
            actions.append(f"Configure {integration['name']} OAuth credentials")

        if not state.get("handler_available", False):
            actions.append(f"Create {integration['name']} service handler")

        if state.get("oauth_api_needed", False):
            actions.append(f"Implement {integration['name']} OAuth API")

        if state.get("database_layer_needed", False):
            actions.append(f"Create {integration['name']} database layer")

        if state.get("frontend_needed", False):
            actions.append(f"Build {integration['name']} frontend components")

        return actions

    def assess_readiness_level(self, integration: Dict[str, Any]) -> str:
        """Assess implementation readiness level"""
        completion = integration["current_state"]["completion_percentage"]

        if completion >= 80:
            return "ready"
        elif completion >= 50:
            return "partial"
        elif completion >= 20:
            return "foundation"
        else:
            return "planning"

    def generate_summary(self, recommendations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate summary statistics"""
        total_estimated_days = sum(rec["estimated_days"] for rec in recommendations)
        ready_integrations = [
            rec for rec in recommendations if rec["readiness_level"] == "ready"
        ]
        high_value_integrations = [
            rec for rec in recommendations if rec["business_value"] == "high"
        ]

        return {
            "total_integrations_assessed": len(recommendations),
            "ready_for_implementation": len(ready_integrations),
            "high_business_value": len(high_value_integrations),
            "total_estimated_effort_days": total_estimated_days,
            "immediate_opportunities": [rec["name"] for rec in recommendations[:3]],
            "critical_prerequisites": [
                "Fix backend blueprint registration"
            ],  # Common prerequisite
        }

    def print_recommendations(self, recommendations: Dict[str, Any]):
        """Print formatted recommendations"""
        print("\n" + "=" * 80)
        print("🎯 INTEGRATION PRIORITY ASSESSMENT")
        print("=" * 80)

        print(f"\n📊 Summary:")
        summary = recommendations["summary"]
        print(
            f"   Total Integrations Assessed: {summary['total_integrations_assessed']}"
        )
        print(f"   Ready for Implementation: {summary['ready_for_implementation']}")
        print(f"   High Business Value: {summary['high_business_value']}")
        print(
            f"   Total Estimated Effort: {summary['total_estimated_effort_days']} days"
        )
        print(
            f"   Immediate Opportunities: {', '.join(summary['immediate_opportunities'])}"
        )
        print(
            f"   Critical Prerequisites: {', '.join(summary['critical_prerequisites'])}"
        )

        print(f"\n🏆 Priority Recommendations:")
        print("=" * 80)

        for i, rec in enumerate(recommendations["recommendations"], 1):
            print(f"\n{i}. {rec['name']} (Score: {rec['priority_score']})")
            print(f"   📈 Business Value: {rec['business_value'].upper()}")
            print(f"   ⚙️  Complexity: {rec['complexity'].upper()}")
            print(f"   📊 Completion: {rec['current_completion']}%")
            print(f"   ⏱️  Estimated: {rec['estimated_days']} days")
            print(f"   🚦 Readiness: {rec['readiness_level'].upper()}")

            print(f"   📋 Next Actions:")
            for action in rec["next_actions"][:3]:  # Show top 3 actions
                print(f"      • {action}")

            if len(rec["next_actions"]) > 3:
                print(f"      • ... and {len(rec['next_actions']) - 3} more")

        print(f"\n" + "=" * 80)
        print("💡 Implementation Strategy:")
        print("=" * 80)

        top_3 = recommendations["recommendations"][:3]
        print(f"\n🎯 Focus on these 3 integrations first:")
        for i, rec in enumerate(top_3, 1):
            print(f"   {i}. {rec['name']} - {rec['estimated_days']} days")

        print(f"\n🚀 Quick Wins (after backend fix):")
        quick_wins = [
            rec
            for rec in recommendations["recommendations"]
            if rec["readiness_level"] in ["ready", "partial"]
        ]
        for win in quick_wins[:2]:
            print(f"   • {win['name']} - {win['estimated_days']} days")


def main():
    """Main assessment function"""
    print("🔍 Assessing integration priorities...")

    assessor = IntegrationPriorityAssessor()
    recommendations = assessor.generate_recommendations()

    assessor.print_recommendations(recommendations)

    # Save detailed report
    report_file = "integration_priority_report.json"
    with open(report_file, "w") as f:
        json.dump(recommendations, f, indent=2)
    print(f"\n📄 Detailed report saved to: {report_file}")


if __name__ == "__main__":
    main()
