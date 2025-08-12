from .celery_app import celery_app
from . import database, models
from sqlalchemy.orm import Session
import json
import time
from collections import defaultdict
import os
import notion_client

# --- Node Execution Functions ---

def execute_gmail_trigger(node_config, input_data):
    print("Executing Gmail Trigger...")
    return [
        {"email_body": "This is a test email. Please send me the report by Friday."},
        {"email_body": "Another email with an action: follow up with John."},
    ]

def execute_ai_task(node_config, input_data):
    print("Executing AI Task...")
    prompt = node_config.get("prompt", "")
    if not prompt:
        print("Warning: No prompt provided for AI Task node.")
        return []

    output = []
    for item in input_data:
        # In a real implementation, this would call an LLM with the prompt and item
        print(f"  - Simulating LLM call with prompt: '{prompt}' and input: '{item}'")
        # Placeholder logic
        if "summarize" in prompt.lower():
            output.append(f"Summary of {item}")
        else:
            output.append(f"Result of '{prompt}' on '{item}'")
    return output

def flatten_list(node_config, input_data):
    print("Executing Flatten List...")
    return [item for sublist in input_data for item in sublist]

from notion_client import APIResponseError

def execute_notion_action(node_config, input_data):
    print("Executing Notion Action...")
    action_items = input_data
    database_id = node_config.get("databaseId")
    notion_api_key = os.environ.get("NOTION_API_KEY")

    if not database_id or not notion_api_key:
        print("Error: Notion database ID or API key is not configured.")
        return []

    notion = notion_client.Client(auth=notion_api_key)

    for item in action_items:
        print(f"  - Creating Notion task: {item}")
        try:
            notion.pages.create(
                parent={"database_id": database_id},
                properties={
                    "Name": {
                        "title": [
                            {
                                "text": {
                                    "content": str(item) # Ensure item is a string
                                }
                            }
                        ]
                    }
                }
            )
        except APIResponseError as e:
            print(f"    Error creating Notion page: {e.body}")
        except Exception as e:
            print(f"    An unexpected error occurred: {e}")

    return [] # Notion action is a sink, it doesn't return data

NODE_EXECUTION_MAP = {
    "gmailTrigger": execute_gmail_trigger,
    "aiTask": execute_ai_task,
    "notionAction": execute_notion_action,
    "flatten": flatten_list,
}

# --- Topological Sort ---

def topological_sort(nodes, edges):
    adj = defaultdict(list)
    in_degree = {node['id']: 0 for node in nodes}
    node_map = {node['id']: node for node in nodes}

    for edge in edges:
        source_id = edge['source']
        target_id = edge['target']
        adj[source_id].append(target_id)
        in_degree[target_id] += 1

    queue = [node['id'] for node in nodes if in_degree[node['id']] == 0]
    sorted_order = []

    while queue:
        u = queue.pop(0)
        sorted_order.append(node_map[u])
        for v_id in adj[u]:
            in_degree[v_id] -= 1
            if in_degree[v_id] == 0:
                queue.append(v_id)

    if len(sorted_order) == len(nodes):
        return sorted_order
    else:
        raise Exception("Workflow contains a cycle")


@celery_app.task
def execute_workflow(workflow_id: str):
    db: Session = next(database.get_db())
    workflow = db.query(models.Workflow).filter(models.Workflow.id == workflow_id).first()
    if not workflow:
        print(f"Workflow with id {workflow_id} not found")
        return

    print(f"Executing workflow: {workflow.name}")
    definition = workflow.definition
    nodes = definition.get("nodes", [])
    edges = definition.get("edges", [])

    if not nodes:
        print("Workflow has no nodes to execute.")
        return

    try:
        sorted_nodes = topological_sort(nodes, edges)
    except Exception as e:
        print(f"Error sorting workflow nodes: {e}")
        return

    node_outputs = {}

    for node in sorted_nodes:
        node_id = node['id']
        node_type = node.get('type')

        input_data = []
        for edge in edges:
            if edge['target'] == node_id:
                source_id = edge['source']
                if source_id in node_outputs:
                    input_data.extend(node_outputs[source_id])

        if node_type in NODE_EXECUTION_MAP:
            print(f"--- Executing node {node_id} ({node_type}) ---")
            execution_func = NODE_EXECUTION_MAP[node_type]
            output_data = execution_func(node.get('data', {}), input_data)
            node_outputs[node_id] = output_data
            print(f"--- Finished node {node_id}. Output: {output_data} ---")
        else:
            print(f"Warning: No execution function found for node type '{node_type}'")

    print(f"Workflow {workflow.name} executed successfully")
