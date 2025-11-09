#!/usr/bin/env python3
"""
Comprehensive Integration Analysis
Analyze all ATOM integrations and provide enhancement roadmap
"""

import os
import json
import sys
import glob
from datetime import datetime
from typing import Dict, List, Tuple

class IntegrationAnalyzer:
    """Analyze integration completeness and provide enhancement roadmap"""
    
    def __init__(self, base_path: str):
        self.base_path = base_path
        self.backend_path = os.path.join(base_path, "backend/python-api-service")
        self.frontend_path = os.path.join(base_path, "frontend-nextjs")
        self.integrations = {}
        self.analysis_results = {}
        
    def analyze_all_integrations(self) -> Dict[str, Dict]:
        """Analyze all integrations comprehensively"""
        print("🔍 Analyzing all ATOM integrations...")
        
        # Define all integrations to analyze
        integration_configs = {
            "slack": {
                "name": "Slack",
                "category": "Communication",
                "files": {
                    "auth": ["auth_handler_slack.py", "auth_handler_slack_complete.py", "auth_handler_slack_new.py"],
                    "db": ["db_oauth_slack.py"],
                    "api": ["slack_enhanced_api.py", "slack_enhanced_api_complete.py"],
                    "service": ["slack_enhanced_service.py", "slack_enhanced_service_complete.py"],
                    "events": ["slack_events_handler.py"]
                },
                "frontend": "slack.tsx",
                "frontend_api": "slack"
            },
            "github": {
                "name": "GitHub",
                "category": "Development",
                "files": {
                    "auth": ["auth_handler_github.py", "auth_handler_github_complete.py", "auth_handler_github_new.py"],
                    "db": ["db_oauth_github.py", "db_oauth_github_complete.py"],
                    "api": ["github_enhanced_api.py"],
                    "service": ["github_service.py", "github_enhanced_service.py"]
                },
                "frontend": "github.tsx",
                "frontend_api": "github"
            },
            "gitlab": {
                "name": "GitLab",
                "category": "Development",
                "files": {
                    "auth": ["auth_handler_gitlab.py"],
                    "db": ["db_oauth_gitlab.py"],
                    "api": ["gitlab_enhanced_api.py"],
                    "service": ["gitlab_enhanced_service.py"]
                },
                "frontend": "gitlab.tsx",
                "frontend_api": "gitlab"
            },
            "jira": {
                "name": "Jira",
                "category": "Project Management",
                "files": {
                    "auth": ["auth_handler_jira.py"],
                    "db": ["db_oauth_jira.py"],
                    "api": ["jira_enhanced_api.py"],
                    "service": ["jira_enhanced_service.py"]
                },
                "frontend": "jira.tsx",
                "frontend_api": "jira"
            },
            "asana": {
                "name": "Asana",
                "category": "Project Management",
                "files": {
                    "auth": ["auth_handler_asana.py"],
                    "db": ["db_oauth_asana.py"],
                    "api": ["asana_enhanced_api.py"],
                    "service": ["asana_enhanced_service.py"]
                },
                "frontend": "asana.tsx",
                "frontend_api": "asana"
            },
            "trello": {
                "name": "Trello",
                "category": "Project Management",
                "files": {
                    "auth": ["auth_handler_trello.py"],
                    "db": ["db_oauth_trello.py"],
                    "api": ["trello_enhanced_api.py"],
                    "service": ["trello_enhanced_service.py"]
                },
                "frontend": "trello.tsx",
                "frontend_api": "trello"
            },
            "notion": {
                "name": "Notion",
                "category": "Productivity",
                "files": {
                    "auth": ["auth_handler_notion.py"],
                    "db": ["db_oauth_notion.py"],
                    "api": ["notion_enhanced_api.py"],
                    "service": ["notion_enhanced_service.py"]
                },
                "frontend": "notion.tsx",
                "frontend_api": "notion"
            },
            "figma": {
                "name": "Figma",
                "category": "Design",
                "files": {
                    "auth": ["auth_handler_figma.py"],
                    "db": ["db_oauth_figma.py"],
                    "api": ["figma_enhanced_api.py"],
                    "service": ["figma_enhanced_service.py"]
                },
                "frontend": "figma.tsx",
                "frontend_api": "figma"
            },
            "linear": {
                "name": "Linear",
                "category": "Project Management",
                "files": {
                    "auth": ["auth_handler_linear.py"],
                    "db": ["db_oauth_linear.py"],
                    "api": ["linear_enhanced_api.py"],
                    "service": ["linear_enhanced_service.py"]
                },
                "frontend": "linear.tsx",
                "frontend_api": "linear"
            },
            "discord": {
                "name": "Discord",
                "category": "Communication",
                "files": {
                    "auth": ["auth_handler_discord_complete.py"],
                    "db": ["db_oauth_discord_complete.py"],
                    "api": ["discord_enhanced_api.py"],
                    "service": ["discord_enhanced_service.py"]
                },
                "frontend": "discord.tsx" if os.path.exists(os.path.join(self.frontend_path, "pages/integrations/discord.tsx")) else None,
                "frontend_api": "discord"
            },
            "google": {
                "name": "Google Workspace",
                "category": "Productivity",
                "files": {
                    "auth": ["auth_handler_gdrive.py", "auth_handler_gmail.py"],
                    "db": ["db_oauth_gdrive.py", "db_oauth_gmail.py"],
                    "api": ["google_enhanced_api.py", "gmail_enhanced_api.py", "calendar_enhanced_api.py"],
                    "service": ["google_services_enhanced.py", "gmail_enhanced_service.py"]
                },
                "frontend": ["gdrive.tsx", "gmail.tsx", "google-workspace.tsx"],
                "frontend_api": ["gdrive", "gmail", "google-workspace"]
            },
            "microsoft": {
                "name": "Microsoft 365",
                "category": "Productivity",
                "files": {
                    "auth": ["auth_handler_outlook.py", "auth_handler_teams.py", "auth_handler_onedrive.py"],
                    "db": ["db_oauth_outlook.py", "db_oauth_teams.py"],
                    "api": ["outlook_enhanced_api.py", "teams_enhanced_api.py", "microsoft_enhanced_api.py"],
                    "service": ["microsoft_services_enhanced.py", "teams_enhanced_service.py"]
                },
                "frontend": ["outlook.tsx", "teams.tsx", "onedrive.tsx", "microsoft365.tsx"],
                "frontend_api": ["outlook", "teams", "onedrive", "microsoft365"]
            },
            "stripe": {
                "name": "Stripe",
                "category": "Payments",
                "files": {
                    "auth": ["auth_handler_stripe.py"],
                    "db": ["db_oauth_stripe.py"],
                    "api": ["stripe_enhanced_api.py"],
                    "service": ["stripe_enhanced_service.py"]
                },
                "frontend": "stripe.tsx",
                "frontend_api": "stripe"
            },
            "shopify": {
                "name": "Shopify",
                "category": "E-commerce",
                "files": {
                    "auth": ["auth_handler_shopify.py"],
                    "db": ["db_oauth_shopify.py"],
                    "api": ["shopify_enhanced_api.py"],
                    "service": ["shopify_enhanced_service.py"]
                },
                "frontend": "shopify.tsx",
                "frontend_api": "shopify"
            },
            "salesforce": {
                "name": "Salesforce",
                "category": "CRM",
                "files": {
                    "auth": ["auth_handler_salesforce.py"],
                    "db": ["db_oauth_salesforce.py"],
                    "api": ["salesforce_enhanced_api.py"],
                    "service": ["salesforce_enhanced_service.py"]
                },
                "frontend": "salesforce.tsx",
                "frontend_api": "salesforce"
            },
            "xero": {
                "name": "Xero",
                "category": "Accounting",
                "files": {
                    "auth": ["auth_handler_xero.py"],
                    "db": ["db_oauth_xero.py"],
                    "api": ["xero_enhanced_api.py"],
                    "service": ["xero_enhanced_service.py"]
                },
                "frontend": "xero.tsx",
                "frontend_api": "xero"
            },
            "zoom": {
                "name": "Zoom",
                "category": "Communication",
                "files": {
                    "auth": ["auth_handler_zoom.py"],
                    "db": ["db_oauth_zoom.py"],
                    "api": ["zoom_enhanced_api.py"],
                    "service": ["zoom_enhanced_service.py"]
                },
                "frontend": "zoom.tsx",
                "frontend_api": "zoom"
            },
            "box": {
                "name": "Box",
                "category": "Storage",
                "files": {
                    "auth": ["auth_handler_box.py", "auth_handler_box_real.py"],
                    "db": ["db_oauth_box.py"],
                    "api": ["box_enhanced_api.py"],
                    "service": ["box_services_enhanced.py"]
                },
                "frontend": "box.tsx",
                "frontend_api": "box"
            },
            "dropbox": {
                "name": "Dropbox",
                "category": "Storage",
                "files": {
                    "auth": ["auth_handler_dropbox.py"],
                    "db": ["db_oauth_dropbox.py"],
                    "api": ["dropbox_enhanced_api.py"],
                    "service": ["dropbox_services_enhanced.py"]
                },
                "frontend": "dropbox.tsx" if os.path.exists(os.path.join(self.frontend_path, "pages/integrations/dropbox.tsx")) else None,
                "frontend_api": "dropbox"
            },
            "hubspot": {
                "name": "HubSpot",
                "category": "CRM",
                "files": {
                    "auth": ["auth_handler_hubspot.py"],
                    "db": ["db_oauth_hubspot.py"],
                    "api": ["hubspot_enhanced_api.py"],
                    "service": ["hubspot_enhanced_service.py"]
                },
                "frontend": "hubspot.tsx",
                "frontend_api": "hubspot"
            }
        }
        
        # Analyze each integration
        for key, config in integration_configs.items():
            print(f"  📊 Analyzing {config['name']}...")
            self.analyze_integration(key, config)
        
        return self.analysis_results
    
    def analyze_integration(self, key: str, config: Dict):
        """Analyze individual integration"""
        backend_files = config.get("files", {})
        
        # Check backend components
        auth_complete = self.check_files_exist(backend_files.get("auth", []))
        db_complete = self.check_files_exist(backend_files.get("db", []))
        api_complete = self.check_files_exist(backend_files.get("api", []))
        service_complete = self.check_files_exist(backend_files.get("service", []))
        events_complete = self.check_files_exist(backend_files.get("events", []))
        
        # Check frontend components
        frontend_file = config.get("frontend")
        frontend_api = config.get("frontend_api")
        
        if isinstance(frontend_file, list):
            frontend_complete = all(os.path.exists(os.path.join(self.frontend_path, "pages/integrations", f)) for f in frontend_file)
        else:
            frontend_complete = os.path.exists(os.path.join(self.frontend_path, "pages/integrations", frontend_file)) if frontend_file else False
        
        if isinstance(frontend_api, list):
            frontend_api_complete = all(os.path.exists(os.path.join(self.frontend_path, "pages/api/integrations", f"{api}/health.ts")) for api in frontend_api)
        else:
            frontend_api_complete = os.path.exists(os.path.join(self.frontend_path, "pages/api/integrations", frontend_api)) if frontend_api else False
        
        # Calculate completion percentages
        backend_score = (
            (auth_complete * 20) +
            (db_complete * 20) +
            (api_complete * 25) +
            (service_complete * 25) +
            (events_complete * 10)
        )
        
        frontend_score = (
            (frontend_complete * 50) +
            (frontend_api_complete * 50)
        )
        
        overall_score = (backend_score + frontend_score) / 2
        
        # Determine status
        if overall_score >= 90:
            status = "COMPLETE"
            priority = "LOW"
        elif overall_score >= 70:
            status = "GOOD"
            priority = "MEDIUM"
        elif overall_score >= 50:
            status = "PARTIAL"
            priority = "HIGH"
        else:
            status = "INCOMPLETE"
            priority = "CRITICAL"
        
        # Store results
        self.analysis_results[key] = {
            "name": config["name"],
            "category": config["category"],
            "status": status,
            "priority": priority,
            "overall_score": round(overall_score, 1),
            "backend_score": round(backend_score, 1),
            "frontend_score": round(frontend_score, 1),
            "components": {
                "authentication": auth_complete,
                "database": db_complete,
                "api": api_complete,
                "service": service_complete,
                "events": events_complete,
                "frontend": frontend_complete,
                "frontend_api": frontend_api_complete
            },
            "gaps": self.identify_gaps(key, config)
        }
    
    def check_files_exist(self, file_list: List[str]) -> float:
        """Check if files exist and return completion percentage"""
        if not file_list:
            return 1.0  # Not required
        
        existing_count = 0
        for filename in file_list:
            if os.path.exists(os.path.join(self.backend_path, filename)):
                existing_count += 1
        
        return existing_count / len(file_list)
    
    def identify_gaps(self, key: str, config: Dict) -> List[str]:
        """Identify specific gaps in integration"""
        gaps = []
        results = self.analysis_results.get(key, {}).get("components", {})
        
        # Check backend gaps
        if not results.get("authentication", False):
            gaps.append("Missing OAuth authentication")
        
        if not results.get("database", False):
            gaps.append("Missing database operations")
        
        if not results.get("api", False):
            gaps.append("Missing API endpoints")
        
        if not results.get("service", False):
            gaps.append("Missing service layer")
        
        if not results.get("events", False) and key in ["slack", "discord"]:
            gaps.append("Missing real-time events")
        
        # Check frontend gaps
        if not results.get("frontend", False):
            gaps.append("Missing frontend UI")
        
        if not results.get("frontend_api", False):
            gaps.append("Missing frontend API endpoints")
        
        return gaps
    
    def generate_enhancement_roadmap(self) -> Dict:
        """Generate enhancement roadmap based on analysis"""
        # Sort integrations by priority and score
        integrations_by_priority = {
            "CRITICAL": [],
            "HIGH": [],
            "MEDIUM": [],
            "LOW": []
        }
        
        for key, results in self.analysis_results.items():
            priority = results["priority"]
            integrations_by_priority[priority].append((key, results))
        
        # Generate enhancement plans
        roadmap = {
            "summary": {
                "total_integrations": len(self.analysis_results),
                "complete": len([r for r in self.analysis_results.values() if r["status"] == "COMPLETE"]),
                "good": len([r for r in self.analysis_results.values() if r["status"] == "GOOD"]),
                "partial": len([r for r in self.analysis_results.values() if r["status"] == "PARTIAL"]),
                "incomplete": len([r for r in self.analysis_results.values() if r["status"] == "INCOMPLETE"])
            },
            "enhancement_roadmap": {}
        }
        
        for priority, integrations in integrations_by_priority.items():
            roadmap["enhancement_roadmap"][priority] = []
            
            for key, results in integrations:
                enhancement_plan = {
                    "key": key,
                    "name": results["name"],
                    "category": results["category"],
                    "current_score": results["overall_score"],
                    "target_score": 100,
                    "improvement_needed": 100 - results["overall_score"],
                    "gaps": results["gaps"],
                    "enhancement_steps": self.generate_enhancement_steps(key, results),
                    "estimated_effort": self.estimate_effort(results),
                    "dependencies": self.identify_dependencies(key)
                }
                roadmap["enhancement_roadmap"][priority].append(enhancement_plan)
        
        return roadmap
    
    def generate_enhancement_steps(self, key: str, results: Dict) -> List[str]:
        """Generate specific enhancement steps for integration"""
        steps = []
        gaps = results["gaps"]
        
        # Generic enhancement steps based on gaps
        for gap in gaps:
            if "OAuth" in gap:
                steps.append("Implement OAuth 2.0 authentication flow")
                steps.append("Add token storage and refresh mechanisms")
            elif "database" in gap:
                steps.append("Create database schema for tokens")
                steps.append("Implement CRUD operations for user data")
            elif "API" in gap:
                steps.append("Build comprehensive API endpoints")
                steps.append("Add error handling and rate limiting")
            elif "service" in gap:
                steps.append("Create service layer for business logic")
                steps.append("Add caching and optimization")
            elif "frontend" in gap:
                steps.append("Build React UI components")
                steps.append("Add real-time updates and interactions")
            elif "events" in gap:
                steps.append("Implement webhook handlers")
                steps.append("Add real-time event processing")
        
        # Integration-specific steps
        if key == "slack":
            if results["overall_score"] < 100:
                steps.append("Add advanced file operations")
                steps.append("Implement message threading")
                steps.append("Add presence and status management")
        elif key in ["github", "gitlab"]:
            steps.append("Add repository management")
            steps.append("Implement CI/CD integration")
            steps.append("Add pull request management")
        elif key in ["jira", "asana", "trello"]:
            steps.append("Add project management features")
            steps.append("Implement task automation")
            steps.append("Add reporting and analytics")
        elif key == "notion":
            steps.append("Add database management")
            steps.append("Implement page editing")
            steps.append("Add block operations")
        
        return list(set(steps))  # Remove duplicates
    
    def estimate_effort(self, results: Dict) -> str:
        """Estimate development effort based on gaps"""
        score = results["overall_score"]
        gaps_count = len(results["gaps"])
        
        if score >= 90:
            return "LOW (1-2 days)"
        elif score >= 70:
            return "MEDIUM (3-5 days)"
        elif score >= 50:
            return "HIGH (1-2 weeks)"
        else:
            return "CRITICAL (2-4 weeks)"
    
    def identify_dependencies(self, key: str) -> List[str]:
        """Identify dependencies for integration enhancement"""
        common_deps = [
            "Database connection (PostgreSQL)",
            "Redis for caching",
            "Authentication service",
            "API gateway",
            "Error logging service"
        ]
        
        specific_deps = {
            "slack": ["Slack API access", "Webhook configuration"],
            "github": ["GitHub App registration", "SSH keys"],
            "gitlab": ["GitLab access token", "Runner configuration"],
            "google": ["Google Cloud project", "API keys"],
            "microsoft": ["Azure AD app", "API permissions"],
            "stripe": ["Stripe account", "Webhook endpoints"],
            "salesforce": ["Salesforce org", "API credentials"]
        }
        
        return common_deps + specific_deps.get(key, [])
    
    def generate_report(self) -> Dict:
        """Generate comprehensive analysis report"""
        # Run analysis
        self.analyze_all_integrations()
        
        # Generate roadmap
        roadmap = self.generate_enhancement_roadmap()
        
        # Create final report
        report = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "analyzer": "Comprehensive Integration Analyzer v1.0",
                "total_integrations_analyzed": len(self.analysis_results)
            },
            "executive_summary": self.generate_executive_summary(roadmap),
            "detailed_analysis": self.analysis_results,
            "enhancement_roadmap": roadmap,
            "recommendations": self.generate_recommendations(),
            "implementation_timeline": self.generate_timeline()
        }
        
        return report
    
    def generate_executive_summary(self, roadmap: Dict) -> Dict:
        """Generate executive summary of analysis"""
        summary = roadmap["summary"]
        
        return {
            "total_integrations": summary["total_integrations"],
            "production_ready": summary["complete"],
            "nearly_production_ready": summary["good"],
            "requires_enhancement": summary["partial"],
            "needs_major_work": summary["incomplete"],
            "overall_health_score": round(
                (summary["complete"] * 100 + summary["good"] * 75 + summary["partial"] * 50 + summary["incomplete"] * 25) / summary["total_integrations"], 1
            ),
            "critical_priorities": len(roadmap["enhancement_roadmap"]["CRITICAL"]),
            "high_priorities": len(roadmap["enhancement_roadmap"]["HIGH"]),
            "estimated_total_effort": self.calculate_total_effort(roadmap)
        }
    
    def calculate_total_effort(self, roadmap: Dict) -> str:
        """Calculate total effort across all integrations"""
        critical_days = len(roadmap["enhancement_roadmap"]["CRITICAL"]) * 10  # 2 weeks average
        high_days = len(roadmap["enhancement_roadmap"]["HIGH"]) * 5  # 1 week average
        medium_days = len(roadmap["enhancement_roadmap"]["MEDIUM"]) * 4  # 3-5 days average
        low_days = len(roadmap["enhancement_roadmap"]["LOW"]) * 1.5  # 1-2 days average
        
        total_days = critical_days + high_days + medium_days + low_days
        
        return f"{total_days:.0f} days ({total_days/5:.0f} weeks with parallel development)"
    
    def generate_recommendations(self) -> Dict:
        """Generate strategic recommendations"""
        return {
            "immediate_actions": [
                "Focus on CRITICAL and HIGH priority integrations first",
                "Establish standard integration architecture patterns",
                "Create reusable components for common features",
                "Set up comprehensive testing framework"
            ],
            "architectural_improvements": [
                "Standardize OAuth authentication patterns",
                "Implement unified error handling",
                "Create consistent API response formats",
                "Add comprehensive logging and monitoring"
            ],
            "development_priorities": [
                "Complete authentication flows for all integrations",
                "Build robust database operations",
                "Create modern React UI components",
                "Add real-time capabilities where needed"
            ],
            "quality_assurance": [
                "Implement automated testing for all integrations",
                "Add integration testing with actual services",
                "Create performance monitoring",
                "Add security vulnerability scanning"
            ]
        }
    
    def generate_timeline(self) -> Dict:
        """Generate implementation timeline"""
        return {
            "phase_1": {
                "name": "Critical Foundation (Week 1-2)",
                "focus": "Complete authentication and database operations",
                "integrations": ["CRITICAL priority"],
                "deliverables": [
                    "All OAuth flows implemented",
                    "Database schemas created",
                    "Basic API endpoints functional"
                ]
            },
            "phase_2": {
                "name": "Feature Enhancement (Week 3-4)",
                "focus": "Complete API services and frontend components",
                "integrations": ["HIGH priority"],
                "deliverables": [
                    "Full API coverage",
                    "React UI components",
                    "Integration testing"
                ]
            },
            "phase_3": {
                "name": "Polish & Optimization (Week 5-6)",
                "focus": "Enhance user experience and performance",
                "integrations": ["MEDIUM priority"],
                "deliverables": [
                    "Advanced features",
                    "Performance optimization",
                    "Documentation completion"
                ]
            },
            "phase_4": {
                "name": "Final Touches (Week 7-8)",
                "focus": "Complete remaining features and testing",
                "integrations": ["LOW priority"],
                "deliverables": [
                    "All features implemented",
                    "Comprehensive testing",
                    "Production deployment ready"
                ]
            }
        }

def main():
    """Main analysis runner"""
    base_path = "/Users/rushiparikh/projects/atom/atom"
    
    print("🚀 COMPREHENSIVE INTEGRATION ANALYSIS")
    print("=" * 60)
    
    analyzer = IntegrationAnalyzer(base_path)
    report = analyzer.generate_report()
    
    # Save report
    report_file = os.path.join(base_path, "INTEGRATION_ANALYSIS_REPORT.json")
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    # Print summary
    print("\n📊 EXECUTIVE SUMMARY")
    print("=" * 40)
    exec_summary = report["executive_summary"]
    print(f"Total Integrations: {exec_summary['total_integrations']}")
    print(f"Production Ready: {exec_summary['production_ready']}")
    print(f"Nearly Production Ready: {exec_summary['nearly_production_ready']}")
    print(f"Requires Enhancement: {exec_summary['requires_enhancement']}")
    print(f"Needs Major Work: {exec_summary['needs_major_work']}")
    print(f"Overall Health Score: {exec_summary['overall_health_score']}/100")
    print(f"Critical Priorities: {exec_summary['critical_priorities']}")
    print(f"High Priorities: {exec_summary['high_priorities']}")
    print(f"Estimated Total Effort: {exec_summary['estimated_total_effort']}")
    
    # Print detailed roadmap
    print(f"\n🗺️  ENHANCEMENT ROADMAP")
    print("=" * 40)
    roadmap = report["enhancement_roadmap"]
    
    for priority in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        integrations = roadmap.get(priority, [])
        if integrations:
            print(f"\n{priority} PRIORITY ({len(integrations)} integrations):")
            for integration in integrations:
                print(f"  • {integration['name']} - Score: {integration['current_score']} - Effort: {integration['estimated_effort']}")
                print(f"    Gaps: {', '.join(integration['gaps'][:2])}")
    
    print(f"\n📄 Full report saved to: {report_file}")
    print(f"🎯 Ready for enhancement implementation!")
    
    return report

if __name__ == "__main__":
    main()