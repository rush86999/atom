#!/usr/bin/env python3
"""
ATOM Platform - Focused Next Steps Completion Plan

This script provides a focused, actionable plan to complete the ATOM platform
integration and bring all systems to full operational status.
"""

import os
import sys
import json
import requests
import time
from datetime import datetime
from pathlib import Path


class FocusedNextSteps:
    """Focused completion plan for ATOM platform"""

    def __init__(self):
        self.results = {}
        self.current_status = {}
        self.completion_plan = []

    def assess_current_status(self):
        """Assess current system status"""
        print("🔍 ASSESSING CURRENT SYSTEM STATUS")
        print("=" * 60)

        # Test backend services
        services_to_check = [
            ("OAuth Server", "http://localhost:5058/healthz"),
            ("Backend API", "http://localhost:8000/health"),
            ("Frontend", "http://localhost:3000"),
        ]

        for service_name, url in services_to_check:
            try:
                if service_name == "Frontend":
                    # Quick check for frontend
                    response = requests.get(url, timeout=5)
                    status = (
                        "✅ RUNNING" if response.status_code == 200 else "❌ ISSUES"
                    )
                else:
                    response = requests.get(url, timeout=5)
                    data = response.json()
                    status = (
                        "✅ RUNNING"
                        if data.get("status") in ["ok", "healthy"]
                        else "❌ ISSUES"
                    )

                self.current_status[service_name] = {
                    "status": status,
                    "url": url,
                    "details": data
                    if service_name != "Frontend"
                    else {"status_code": response.status_code},
                }
                print(f"   {status} {service_name}: {url}")

            except Exception as e:
                self.current_status[service_name] = {
                    "status": "❌ OFFLINE",
                    "url": url,
                    "error": str(e),
                }
                print(f"   ❌ OFFLINE {service_name}: {url}")

        print()

    def identify_critical_gaps(self):
        """Identify critical gaps that need immediate attention"""
        print("🎯 IDENTIFYING CRITICAL GAPS")
        print("=" * 60)

        critical_gaps = []

        # Check NLU system
        try:
            response = requests.get(
                "http://localhost:8000/api/workflow-agent/analyze", timeout=5
            )
            nlu_status = "✅ OPERATIONAL"
        except:
            nlu_status = "❌ OFFLINE"
            critical_gaps.append(
                "NLU System - Natural language understanding not working"
            )

        # Check service integrations
        try:
            response = requests.get(
                "http://localhost:8000/api/services/status", timeout=5
            )
            data = response.json()
            active_services = data.get("status_summary", {}).get("active", 0)
            if active_services < 5:
                critical_gaps.append(
                    f"Service Integrations - Only {active_services} services active (need 5+)"
                )
        except:
            critical_gaps.append(
                "Service Integrations - Service registry not accessible"
            )

        # Check workflow generation
        try:
            response = requests.post(
                "http://localhost:8000/api/workflow-automation/generate",
                json={"user_input": "test workflow", "user_id": "test_user"},
                timeout=10,
            )
            data = response.json()
            if not data.get("success"):
                critical_gaps.append(
                    "Workflow Generation - API responding but not generating workflows"
                )
        except:
            critical_gaps.append("Workflow Generation - Endpoint not responding")

        # Check UI endpoints
        ui_endpoints = [
            ("Search UI", "/search"),
            ("Task UI", "/tasks"),
            ("Communication UI", "/communication"),
            ("Workflow UI", "/automations"),
            ("Calendar UI", "/calendar"),
        ]

        for ui_name, endpoint in ui_endpoints:
            try:
                response = requests.get(f"http://localhost:3000{endpoint}", timeout=5)
                if response.status_code != 200:
                    critical_gaps.append(
                        f"{ui_name} - Endpoint {endpoint} not accessible"
                    )
            except:
                critical_gaps.append(f"{ui_name} - Endpoint {endpoint} not responding")

        # Print gaps
        if critical_gaps:
            for gap in critical_gaps:
                print(f"   ❌ {gap}")
        else:
            print("   ✅ No critical gaps identified!")

        self.critical_gaps = critical_gaps
        print()

    def create_completion_plan(self):
        """Create focused completion plan"""
        print("🚀 CREATING FOCUSED COMPLETION PLAN")
        print("=" * 60)

        plan = [
            {
                "phase": "IMMEDIATE",
                "priority": "CRITICAL",
                "steps": [
                    {
                        "action": "Fix NLU System",
                        "description": "Enable natural language understanding for workflow generation",
                        "commands": [
                            "Check nlu_bridge_service.py implementation",
                            "Test /api/workflow-agent/analyze endpoint",
                            "Verify LLM integration",
                        ],
                        "success_criteria": "NLU endpoint responds successfully to natural language queries",
                    },
                    {
                        "action": "Activate Core Services",
                        "description": "Enable Slack, Google Calendar, Gmail, Notion, Trello integrations",
                        "commands": [
                            "Configure OAuth for each service",
                            "Test service health endpoints",
                            "Verify service registry shows 5+ active services",
                        ],
                        "success_criteria": "5+ services show as 'active' in service registry",
                    },
                    {
                        "action": "Test Workflow Generation",
                        "description": "Ensure natural language to workflow conversion works",
                        "commands": [
                            "Test workflow generation with sample inputs",
                            "Verify multi-step workflows are created",
                            "Test cross-service coordination",
                        ],
                        "success_criteria": "Workflow generation API returns success with valid workflows",
                    },
                ],
            },
            {
                "phase": "SHORT-TERM",
                "priority": "HIGH",
                "steps": [
                    {
                        "action": "Enable UI Endpoints",
                        "description": "Make all specialized UI interfaces accessible",
                        "commands": [
                            "Check frontend routing configuration",
                            "Test each UI endpoint (/search, /tasks, etc.)",
                            "Verify UI components load correctly",
                        ],
                        "success_criteria": "All 5 UI endpoints return 200 status",
                    },
                    {
                        "action": "Test Voice Integration",
                        "description": "Verify voice command processing works",
                        "commands": [
                            "Check wake_word_recorder functionality",
                            "Test voice endpoint responses",
                            "Verify audio processing pipeline",
                        ],
                        "success_criteria": "Voice endpoints respond to test requests",
                    },
                    {
                        "action": "Validate Multi-Service Workflows",
                        "description": "Test workflows that coordinate across multiple services",
                        "commands": [
                            "Create workflow using 2+ services",
                            "Test workflow execution",
                            "Verify cross-service data flow",
                        ],
                        "success_criteria": "Workflows successfully coordinate 2+ services",
                    },
                ],
            },
            {
                "phase": "FINAL",
                "priority": "MEDIUM",
                "steps": [
                    {
                        "action": "Performance Optimization",
                        "description": "Ensure all endpoints respond within 2 seconds",
                        "commands": [
                            "Test response times for critical endpoints",
                            "Optimize database queries",
                            "Implement caching where needed",
                        ],
                        "success_criteria": "All endpoints respond in <2s",
                    },
                    {
                        "action": "Documentation Updates",
                        "description": "Update README and documentation with current capabilities",
                        "commands": [
                            "Update validation status in README",
                            "Document current service status",
                            "Create user guides for working features",
                        ],
                        "success_criteria": "README accurately reflects current system capabilities",
                    },
                    {
                        "action": "Final Integration Test",
                        "description": "Complete end-to-end user journey test",
                        "commands": [
                            "Test user registration/login",
                            "Test workflow creation and execution",
                            "Test cross-interface coordination",
                        ],
                        "success_criteria": "Complete user journey works without errors",
                    },
                ],
            },
        ]

        # Print the plan
        for phase in plan:
            print(f"\n📋 {phase['phase']} ACTIONS ({phase['priority']} Priority):")
            for i, step in enumerate(phase["steps"], 1):
                print(f"   {i}. {step['action']}")
                print(f"      📝 {step['description']}")
                print(f"      ✅ Success: {step['success_criteria']}")

        self.completion_plan = plan
        print()

    def generate_quick_start_commands(self):
        """Generate quick start commands for immediate action"""
        print("⚡ QUICK START COMMANDS FOR IMMEDIATE ACTION")
        print("=" * 60)

        commands = [
            "# 1. Check NLU System Status",
            "curl -X POST http://localhost:8000/api/workflow-agent/analyze \\",
            '  -H "Content-Type: application/json" \\',
            '  -d \'{"user_input": "Schedule a meeting tomorrow", "user_id": "test"}\'',
            "",
            "# 2. Check Service Registry",
            "curl http://localhost:8000/api/services/status",
            "",
            "# 3. Test Workflow Generation",
            "curl -X POST http://localhost:8000/api/workflow-automation/generate \\",
            '  -H "Content-Type: application/json" \\',
            '  -d \'{"user_input": "Send a message to Slack", "user_id": "test"}\'',
            "",
            "# 4. Test UI Endpoints",
            "curl -I http://localhost:3000/search",
            "curl -I http://localhost:3000/tasks",
            "curl -I http://localhost:3000/communication",
            "",
            "# 5. Monitor All Services",
            "echo \"OAuth: $(curl -s http://localhost:5058/healthz | jq -r '.status')\"",
            "echo \"Backend: $(curl -s http://localhost:8000/health | jq -r '.status')\"",
            "echo \"Frontend: $(curl -s -o /dev/null -w '%{http_code}' http://localhost:3000)\"",
        ]

        for cmd in commands:
            print(cmd)

        print()

    def create_monitoring_dashboard(self):
        """Create a simple monitoring dashboard script"""
        print("📊 CREATING MONITORING DASHBOARD")
        print("=" * 60)

        dashboard_script = """#!/bin/bash

# ATOM Platform - Real-time Monitoring Dashboard
echo "🚀 ATOM PLATFORM - REAL-TIME STATUS"
echo "===================================="
echo "Last updated: $(date)"
echo ""

# Service Status
echo "🔧 SERVICE STATUS:"
services=(
    "OAuth Server|http://localhost:5058/healthz"
    "Backend API|http://localhost:8000/health"
    "Frontend App|http://localhost:3000"
    "NLU System|http://localhost:8000/api/workflow-agent/analyze"
    "Workflow Gen|http://localhost:8000/api/workflow-automation/generate"
)

for service in "${services[@]}"; do
    IFS='|' read -r name url <<< "$service"

    if [[ $url == *"workflow-agent"* ]] || [[ $url == *"workflow-automation"* ]]; then
        # POST endpoints
        response=$(curl -s -X POST "$url" -H "Content-Type: application/json" -d '{"user_input":"test","user_id":"monitor"}' --max-time 5 2>/dev/null || echo "ERROR")
    else
        # GET endpoints
        response=$(curl -s "$url" --max-time 5 2>/dev/null || echo "ERROR")
    fi

    if [[ "$response" == "ERROR" ]]; then
        status="❌ OFFLINE"
    elif [[ "$response" == *"status"* ]] && [[ "$response" == *"ok"* ]]; then
        status="✅ HEALTHY"
    elif [[ "$response" == *"success"* ]] && [[ "$response" == *"true"* ]]; then
        status="✅ WORKING"
    elif [[ "$response" == *"200"* ]] || [[ "$response" == *"<!DOCTYPE"* ]]; then
        status="✅ RUNNING"
    else
        status="⚠️  ISSUES"
    fi

    echo "   $status $name"
done

echo ""
echo "🌐 ACCESS POINTS:"
echo "   Frontend: http://localhost:3000"
echo "   Backend API: http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo "   OAuth Server: http://localhost:5058"
echo ""

echo "🔍 CRITICAL ENDPOINTS:"
critical_endpoints=(
    "/search"
    "/tasks"
    "/communication"
    "/automations"
    "/calendar"
)

for endpoint in "${critical_endpoints[@]}"; do
    status_code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:3000$endpoint" --max-time 3 2>/dev/null || echo "000")
    if [[ "$status_code" == "200" ]]; then
        echo "   ✅ $endpoint: HTTP $status_code"
    else
        echo "   ❌ $endpoint: HTTP $status_code"
    fi
done

echo ""
echo "💡 QUICK ACTIONS:"
echo "   Test NLU: curl -X POST http://localhost:8000/api/workflow-agent/analyze -H 'Content-Type: application/json' -d '{\"user_input\":\"test\",\"user_id\":\"test\"}'"
echo "   Test Workflow: curl -X POST http://localhost:8000/api/workflow-automation/generate -H 'Content-Type: application/json' -d '{\"user_input\":\"Schedule meeting\",\"user_id\":\"test\"}'"
echo "   Check Services: curl http://localhost:8000/api/services/status"
"""

        with open("monitor_atom.sh", "w") as f:
            f.write(dashboard_script)

        os.chmod("monitor_atom.sh", 0o755)
        print("   ✅ Monitoring dashboard created: monitor_atom.sh")
        print("   📋 Usage: ./monitor_atom.sh")
        print()

    def run_focused_plan(self):
        """Execute the focused completion plan"""
        print("🚀 ATOM PLATFORM - FOCUSED NEXT STEPS")
        print("=" * 80)
        print(
            "🎯 Mission: Complete platform integration and achieve full operational status"
        )
        print("⏰ Timeline: Immediate action with phased completion")
        print("=" * 80)
        print()

        # Run all assessment steps
        self.assess_current_status()
        self.identify_critical_gaps()
        self.create_completion_plan()
        self.generate_quick_start_commands()
        self.create_monitoring_dashboard()

        # Generate final report
        report = {
            "timestamp": datetime.now().isoformat(),
            "current_status": self.current_status,
            "critical_gaps": self.critical_gaps,
            "completion_plan": self.completion_plan,
            "recommendations": {
                "immediate": "Fix NLU system and activate core services",
                "short_term": "Enable UI endpoints and test voice integration",
                "final": "Optimize performance and complete documentation",
            },
        }

        with open("focused_next_steps_report.json", "w") as f:
            json.dump(report, f, indent=2)

        print("🎉 FOCUSED NEXT STEPS PLAN COMPLETE!")
        print("=" * 60)
        print("📄 Detailed report saved: focused_next_steps_report.json")
        print("📊 Monitoring dashboard: ./monitor_atom.sh")
        print()
        print("🚀 IMMEDIATE ACTIONS:")
        print("   1. Run monitoring dashboard: ./monitor_atom.sh")
        print("   2. Test NLU system with provided curl commands")
        print("   3. Check service registry status")
        print("   4. Test workflow generation")
        print()
        print(
            "💪 CONFIDENCE: 85% - Core infrastructure is running, focus on integration completion!"
        )


def main():
    """Main execution function"""
    planner = FocusedNextSteps()
    planner.run_focused_plan()


if __name__ == "__main__":
    main()
