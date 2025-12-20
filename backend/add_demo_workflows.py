#!/usr/bin/env python3
"""
Add demo workflows to workflows.json for testing.
"""
import json
import os
import sys

WORKFLOWS_FILE = os.path.join(os.path.dirname(__file__), "workflows.json")

def load_workflows():
    if not os.path.exists(WORKFLOWS_FILE):
        return []
    with open(WORKFLOWS_FILE, 'r') as f:
        return json.load(f)

def save_workflows(workflows):
    with open(WORKFLOWS_FILE, 'w') as f:
        json.dump(workflows, f, indent=2)

def add_demo_workflows():
    workflows = load_workflows()
    existing_ids = set()
    for w in workflows:
        if 'id' in w:
            existing_ids.add(w['id'])
        if 'workflow_id' in w:
            existing_ids.add(w['workflow_id'])

    demo_workflows = [
        {
            "id": "demo-project-management",
            "name": "Demo Project Management Workflow",
            "description": "Demo workflow for project management",
            "version": "1.0.0",
            "nodes": [
                {
                    "id": "node_1",
                    "type": "action",
                    "title": "Create Project",
                    "description": "Create a new project",
                    "position": {"x": 100, "y": 100},
                    "config": {
                        "service": "asana",
                        "action": "create_project",
                        "parameters": {}
                    },
                    "connections": []
                }
            ],
            "connections": [],
            "triggers": ["manual"],
            "enabled": True,
            "createdAt": "2025-12-13T00:00:00Z",
            "updatedAt": "2025-12-13T00:00:00Z"
        },
        {
            "id": "demo-customer-support",
            "name": "Demo Customer Support Workflow",
            "description": "Demo workflow for customer support",
            "version": "1.0.0",
            "nodes": [
                {
                    "id": "node_1",
                    "type": "action",
                    "title": "Create Ticket",
                    "description": "Create a support ticket",
                    "position": {"x": 100, "y": 100},
                    "config": {
                        "service": "zendesk",
                        "action": "create_ticket",
                        "parameters": {}
                    },
                    "connections": []
                }
            ],
            "connections": [],
            "triggers": ["manual"],
            "enabled": True,
            "createdAt": "2025-12-13T00:00:00Z",
            "updatedAt": "2025-12-13T00:00:00Z"
        },
        {
            "id": "demo-sales-lead",
            "name": "Demo Sales Lead Workflow",
            "description": "Demo workflow for sales lead processing",
            "version": "1.0.0",
            "nodes": [
                {
                    "id": "node_1",
                    "type": "action",
                    "title": "Create Lead",
                    "description": "Create a new lead in CRM",
                    "position": {"x": 100, "y": 100},
                    "config": {
                        "service": "salesforce",
                        "action": "create_lead",
                        "parameters": {}
                    },
                    "connections": []
                }
            ],
            "connections": [],
            "triggers": ["manual"],
            "enabled": True,
            "createdAt": "2025-12-13T00:00:00Z",
            "updatedAt": "2025-12-13T00:00:00Z"
        }
    ]

    added = 0
    for demo in demo_workflows:
        if demo['id'] not in existing_ids:
            workflows.append(demo)
            added += 1
            print("Added demo workflow: " + demo['id'])
        else:
            print("Demo workflow " + demo['id'] + " already exists")

    if added > 0:
        save_workflows(workflows)
        print("Successfully added " + str(added) + " demo workflows")
    else:
        print("No new demo workflows added")

if __name__ == "__main__":
    add_demo_workflows()