"""
Fix workflow data to match the new data model requirements
Add missing fields: nodes, connections, enabled
"""

import json
import os
from datetime import datetime
from pathlib import Path

# Path to workflows file
WORKFLOWS_FILE = Path(__file__).parent.parent / "workflows.json"

def fix_workflow_data():
    """Fix existing workflow data to match the new schema"""

    if not WORKFLOWS_FILE.exists():
        print("No workflows file found - creating empty one")
        with open(WORKFLOWS_FILE, 'w') as f:
            json.dump([], f)
        return

    # Load existing workflows
    try:
        with open(WORKFLOWS_FILE, 'r') as f:
            workflows = json.load(f)
    except Exception as e:
        print(f"Error loading workflows: {e}")
        workflows = []

    # Fix each workflow
    fixed_workflows = []
    for workflow in workflows:
        # Create a fixed version
        fixed_workflow = workflow.copy()

        # Ensure required fields exist
        if 'nodes' not in fixed_workflow:
            # Create a default node if missing
            if 'steps' in fixed_workflow:
                # Convert old steps format to nodes
                nodes = []
                for i, step in enumerate(fixed_workflow['steps']):
                    node = {
                        "id": step.get('step_id', f"node_{i}"),
                        "type": step.get('step_type', 'default'),
                        "title": step.get('description', f'Step {i+1}'),
                        "description": step.get('description', ''),
                        "position": {"x": i * 200, "y": 100},
                        "config": step.get('parameters', {}),
                        "connections": step.get('next_steps', [])
                    }
                    nodes.append(node)
                fixed_workflow['nodes'] = nodes
            else:
                # Create a single default node
                fixed_workflow['nodes'] = [{
                    "id": "default_node",
                    "type": "process",
                    "title": "Default Node",
                    "description": "Default workflow node",
                    "position": {"x": 0, "y": 0},
                    "config": {},
                    "connections": []
                }]

        if 'connections' not in fixed_workflow:
            # Create default connections if missing
            nodes = fixed_workflow['nodes']
            connections = []

            # Connect nodes sequentially if there are multiple
            for i in range(len(nodes) - 1):
                connection = {
                    "id": f"conn_{i}_{i+1}",
                    "source": nodes[i]["id"],
                    "target": nodes[i+1]["id"],
                    "condition": None
                }
                connections.append(connection)

            fixed_workflow['connections'] = connections

        if 'enabled' not in fixed_workflow:
            fixed_workflow['enabled'] = True

        # Ensure version exists
        if 'version' not in fixed_workflow:
            fixed_workflow['version'] = '1.0'

        # Ensure timestamps
        if 'createdAt' not in fixed_workflow:
            fixed_workflow['createdAt'] = datetime.now().isoformat()

        if 'updatedAt' not in fixed_workflow:
            fixed_workflow['updatedAt'] = datetime.now().isoformat()

        fixed_workflows.append(fixed_workflow)

    # Save fixed workflows
    try:
        with open(WORKFLOWS_FILE, 'w') as f:
            json.dump(fixed_workflows, f, indent=2)
        print(f"Fixed {len(fixed_workflows)} workflows")
        return True
    except Exception as e:
        print(f"Error saving fixed workflows: {e}")
        return False

def main():
    print("Fixing workflow data model...")
    success = fix_workflow_data()

    if success:
        print("✅ Workflow data fixed successfully!")
    else:
        print("❌ Failed to fix workflow data")

if __name__ == "__main__":
    main()