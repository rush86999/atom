from .celery_app import celery_app
from . import database, models
from sqlalchemy.orm import Session
import json
import time
from collections import defaultdict
import os
import notion_client

# --- Node Execution Functions ---

import requests

def execute_gmail_trigger(node_config, input_data, user_id):
    print("Executing Gmail Trigger...")
    query = node_config.get("query", "is:unread")
    max_results = node_config.get("maxResults", 10)

    if not user_id:
        print("Error: userId is not configured for Gmail Trigger.")
        return []

    try:
        response = requests.post(
            "http://functions:3000/gmail-integration/search-user-gmail",
            json={
                "session_variables": {"x-hasura-user-id": str(user_id)},
                "input": {"query": query, "maxResults": max_results},
            },
        )
        response.raise_for_status()
        data = response.json()
        return data.get("results", [])
    except requests.exceptions.RequestException as e:
        print(f"    Error calling functions service: {e}")
        return []

import openai

def execute_ai_task(node_config, input_data):
    print("Executing AI Task...")
    prompt = node_config.get("prompt", "")
    openai.api_key = os.environ.get("OPENAI_API_KEY")

    if not prompt or not openai.api_key:
        print("Error: OpenAI API key or prompt is not configured.")
        return []

    output = []
    for item in input_data:
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": str(item)}
                ]
            )
            result = response.choices[0].message.content
            output.append(result)
        except Exception as e:
            print(f"    Error calling OpenAI API: {e}")
            output.append(f"Error processing item: {item}")

    return output

def flatten_list(node_config, input_data):
    print("Executing Flatten List...")
    return [item for sublist in input_data for item in sublist]

from notion_client import APIResponseError

def execute_notion_action(node_config, input_data, user_id):
    print("Executing Notion Action...")
    database_id = node_config.get("databaseId")
    properties = node_config.get("properties", {})

    if not database_id:
        print("Error: Notion database ID is not configured.")
        return []

    for item in input_data:
        try:
            description = str(item)
            response = requests.post(
                "http://functions:3000/notion/create-task",
                json={
                    "session_variables": {"x-hasura-user-id": str(user_id)},
                    "input": {
                        "notion_db_id": database_id,
                        "description": description,
                        "properties": properties,
                    },
                },
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"    Error calling functions service: {e}")

    return [] # Notion action is a sink, it doesn't return data

def execute_google_calendar_create_event(node_config, input_data, user_id):
    print("Executing Google Calendar Create Event...")
    calendar_id = node_config.get("calendarId", "primary")
    summary = node_config.get("summary", "")
    start_time = node_config.get("startTime", "")
    end_time = node_config.get("endTime", "")
    timezone = node_config.get("timezone", "UTC")

    if not all([summary, start_time, end_time, timezone]):
        print("Error: Missing required config for Google Calendar Create Event.")
        return []

    try:
        response = requests.post(
            "http://functions:3000/google-calendar-sync/create-event",
            json={
                "session_variables": {"x-hasura-user-id": str(user_id)},
                "input": {
                    "calendarId": calendar_id,
                    "summary": summary,
                    "startTime": start_time,
                    "endTime": end_time,
                    "timezone": timezone,
                },
            },
        )
        response.raise_for_status()
        data = response.json()
        return [data]
    except requests.exceptions.RequestException as e:
        print(f"    Error calling functions service: {e}")
        return []

import time

def execute_delay_node(node_config, input_data):
    duration = node_config.get("duration", 60)  # in seconds
    print(f"Delaying workflow for {duration} seconds...")
    time.sleep(duration)
    print("Delay finished.")
    return input_data

import openai

def execute_llm_filter_node(node_config, input_data):
    condition = node_config.get("condition", "")
    openai.api_key = os.environ.get("OPENAI_API_KEY")

    if not condition or not openai.api_key:
        print("Error: OpenAI API key or condition is not configured.")
        return []

    output = []
    for item in input_data:
        try:
            prompt = f"You are a filtering assistant. Given an item and a condition, you must determine if the item satisfies the condition. Respond with only 'true' or 'false'.\n\nItem: {str(item)}\nCondition: {condition}\n\nDoes the item satisfy the condition?"
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a filtering assistant. Your only job is to determine if an item satisfies a condition. Respond with only 'true' or 'false'."},
                    {"role": "user", "content": f"Item: {str(item)}\nCondition: {condition}"}
                ]
            )
            result = response.choices[0].message.content.lower().strip()
            if result == 'true':
                output.append(item)
        except Exception as e:
            print(f"    Error calling OpenAI API: {e}")

    return output

def execute_reduce_node(node_config, input_data):
    return input_data

def execute_reminder_node(node_config, input_data, user_id):
    summary = node_config.get("summary", "")
    date_time = node_config.get("dateTime", "")
    minutes_before = node_config.get("minutesBefore", 10)

    if not all([summary, date_time]):
        print("Error: Missing required config for Reminder Node.")
        return []

    try:
        response = requests.post(
            "http://functions:3000/google-calendar-sync/create-reminder",
            json={
                "session_variables": {"x-hasura-user-id": str(user_id)},
                "input": {
                    "summary": summary,
                    "dateTime": date_time,
                    "minutesBefore": minutes_before,
                },
            },
        )
        response.raise_for_status()
        data = response.json()
        return [data]
    except requests.exceptions.RequestException as e:
        print(f"    Error calling functions service: {e}")
        return []

def execute_slack_send_message_node(node_config, input_data, user_id):
    channel_id = node_config.get("channelId", "")
    text = node_config.get("text", "")

    if not all([channel_id, text]):
        print("Error: Missing required config for Slack Send Message Node.")
        return []

    try:
        response = requests.post(
            "http://functions:3000/slack-service/send-message",
            json={
                "session_variables": {"x-hasura-user-id": str(user_id)},
                "input": {
                    "channelId": channel_id,
                    "text": text,
                },
            },
        )
        response.raise_for_status()
        data = response.json()
        return [data]
    except requests.exceptions.RequestException as e:
        print(f"    Error calling functions service: {e}")
        return []

def execute_branch_node(node_config, input_data):
    return input_data

def execute_send_email_node(node_config, input_data, user_id):
    to = node_config.get("to", "")
    subject = node_config.get("subject", "")
    body = node_config.get("body", "")

    if not all([to, subject, body]):
        print("Error: Missing required config for Send Email Node.")
        return []

    try:
        response = requests.post(
            "http://functions:3000/gmail-service/send-email",
            json={
                "session_variables": {"x-hasura-user-id": str(user_id)},
                "input": {
                    "to": to,
                    "subject": subject,
                    "body": body,
                },
            },
        )
        response.raise_for_status()
        data = response.json()
        return [data]
    except requests.exceptions.RequestException as e:
        print(f"    Error calling functions service: {e}")
        return []

def execute_trello_create_card_node(node_config, input_data, user_id):
    list_id = node_config.get("listId", "")
    card_name = node_config.get("cardName", "")

    if not all([list_id, card_name]):
        print("Error: Missing required config for Trello Create Card Node.")
        return []

    try:
        response = requests.post(
            "http://functions:3000/trello/create-card",
            json={
                "session_variables": {"x-hasura-user-id": str(user_id)},
                "input": {
                    "list_id": list_id,
                    "card_name": card_name,
                },
            },
        )
        response.raise_for_status()
        data = response.json()
        return [data]
    except requests.exceptions.RequestException as e:
        print(f"    Error calling functions service: {e}")
        return []

def execute_asana_create_task_node(node_config, input_data, user_id):
    project_id = node_config.get("projectId", "")
    task_name = node_config.get("taskName", "")

    if not all([project_id, task_name]):
        print("Error: Missing required config for Asana Create Task Node.")
        return []

    try:
        response = requests.post(
            "http://functions:3000/asana/create-task",
            json={
                "session_variables": {"x-hasura-user-id": str(user_id)},
                "input": {
                    "project_id": project_id,
                    "task_name": task_name,
                },
            },
        )
        response.raise_for_status()
        data = response.json()
        return [data]
    except requests.exceptions.RequestException as e:
        print(f"    Error calling functions service: {e}")
        return []

NODE_EXECUTION_MAP = {
    "gmailTrigger": execute_gmail_trigger,
    "aiTask": execute_ai_task,
    "notionAction": execute_notion_action,
    "flatten": flatten_list,
    "googleCalendarCreateEvent": execute_google_calendar_create_event,
    "delay": execute_delay_node,
    "llmFilter": execute_llm_filter_node,
    "reduce": execute_reduce_node,
    "reminder": execute_reminder_node,
    "slackSendMessage": execute_slack_send_message_node,
    "branch": execute_branch_node,
    "sendEmail": execute_send_email_node,
    "trelloCreateCard": execute_trello_create_card_node,
    "asanaCreateTask": execute_asana_create_task_node,
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
            if node_type in ["gmailTrigger", "reminder", "slackSendMessage", "sendEmail", "trelloCreateCard", "asanaCreateTask", "notionAction"]:
                output_data = execution_func(node.get('data', {}), input_data, workflow.user_id)
            else:
                output_data = execution_func(node.get('data', {}), input_data)
            node_outputs[node_id] = output_data
            print(f"--- Finished node {node_id}. Output: {output_data} ---")
        else:
            print(f"Warning: No execution function found for node type '{node_type}'")

    print(f"Workflow {workflow.name} executed successfully")
