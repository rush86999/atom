import os
from flask import Blueprint, request, jsonify
from notion_client import Client as NotionClient # Official client
from datetime import datetime, timezone, timedelta # Added timedelta
from typing import Optional, Tuple # For type hinting _resolve_date_query

# It's good practice to handle API keys and DB IDs via environment variables
# These will be fetched within each route as needed.
# NOTION_API_TOKEN = os.environ.get("ATOM_NOTION_API_TOKEN")
# NOTION_TASKS_DB_ID = os.environ.get("ATOM_NOTION_TASKS_DATABASE_ID")

task_bp = Blueprint('task_bp', __name__)

# Helper function to initialize Notion client (optional, can also do in each route)
# def get_notion_client():
#     token = os.environ.get("ATOM_NOTION_API_TOKEN")
#     if not token:
#         raise ValueError("ATOM_NOTION_API_TOKEN environment variable not set.")
#     return NotionClient(auth=token)

# Routes will be added here in subsequent steps:
# @task_bp.route('/create-notion-task', methods=['POST'])
# def create_notion_task_route():
#     # Implementation will go here
#     pass

@task_bp.route('/create-notion-task', methods=['POST'])
def create_notion_task_route():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": {"code": "INVALID_PAYLOAD", "message": "Request must be JSON."}}), 400

        # --- Configuration ---
        notion_api_token = os.environ.get("ATOM_NOTION_API_TOKEN")
        # notion_db_id can come from payload (e.g. params.notionTasksDbId) or fallback to env var
        # The TypeScript skill sends `notion_db_id` in payload, which is params.notionTasksDbId or ATOM_NOTION_TASKS_DATABASE_ID
        notion_db_id = data.get("notion_db_id") # This is the resolved DB ID from the skill

        if not notion_api_token:
            return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Notion API token not configured."}}), 500
        if not notion_db_id:
            return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Notion Tasks Database ID not provided or configured."}}), 400

        # --- Extract Task Details ---
        description = data.get("description")
        if not description:
            return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "Task description is required."}}), 400

        due_date_str = data.get("dueDate") # Expected as ISO string or YYYY-MM-DD by Notion
        status = data.get("status", "To Do") # Default status
        priority = data.get("priority")
        list_name = data.get("listName")
        task_notes_content = data.get("notes") # Content for the page body

        # --- Initialize Notion Client ---
        notion = NotionClient(auth=notion_api_token)

        # --- Construct Notion Page Properties ---
        page_properties = {
            # Assumes Notion DB has a "Task Description" property of type "Title"
            "Task Description": {"title": [{"type": "text", "text": {"content": description}}]}
        }
        if due_date_str:
            # Validate or ensure due_date_str is in ISO 8601 format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ)
            # For simplicity, we assume the client sends a format Notion accepts for Date type.
            # If it includes time: {"date": {"start": "YYYY-MM-DDTHH:MM:SSZ", "time_zone": "Etc/UTC"}}
            # If it's just a date: {"date": {"start": "YYYY-MM-DD"}}
            # The Notion client SDK handles this well if the string is standard.
            page_properties["Due Date"] = {"date": {"start": due_date_str}}

        # Assumes "Status" is a Select property
        page_properties["Status"] = {"select": {"name": status}}

        if priority: # Assumes "Priority" is a Select property
            page_properties["Priority"] = {"select": {"name": priority}}

        if list_name: # Assumes "List Name" is a Text (rich_text) property or Select
             # If Text (rich_text):
            page_properties["List Name"] = {"rich_text": [{"type": "text", "text": {"content": list_name}}]}
            # If Select:
            # page_properties["List Name"] = {"select": {"name": list_name}}
            # For this implementation, let's assume "List Name" is a Text property.

        # --- Construct Page Content (for notes) ---
        page_children = []
        if task_notes_content:
            page_children.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": task_notes_content}}]
                }
            })

        # --- Create Notion Page ---
        new_page = notion.pages.create(
            parent={"database_id": notion_db_id},
            properties=page_properties,
            children=page_children if page_children else None
        )

        return jsonify({
            "ok": True,
            "data": {
                "taskId": new_page["id"],
                "taskUrl": new_page.get("url"),
                "message": "Task created successfully in Notion."
            }
        }), 201 # HTTP 201 Created

    except Exception as e:
        # Log the full error for debugging on the server
        print(f"Error creating Notion task: {str(e)}")
        # Consider specific error handling for NotionAPIError if needed
        # from notion_client import APIResponseError
        # if isinstance(e, APIResponseError):
        #    return jsonify({"ok": False, "error": {"code": "NOTION_API_ERROR", "message": str(e)}}), e.status
        return jsonify({"ok": False, "error": {"code": "INTERNAL_SERVER_ERROR", "message": f"An unexpected error occurred: {str(e)}" }}), 500

# @task_bp.route('/query-notion-tasks', methods=['POST'])
# def query_notion_tasks_route():
#     # Implementation will go here
#     pass

# Helper function for dateQuery (can be inside the route or outside)
def _resolve_date_query(date_query_str: str) -> Tuple[Optional[str], Optional[str]]:
    # Returns (start_date_iso, end_date_iso) or (None, None)
    # This is a simplified resolver. A more robust one would use a date parsing library.
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    if date_query_str == "today":
        return today.isoformat(), today.isoformat()
    elif date_query_str == "tomorrow":
        tomorrow = today + timedelta(days=1)
        return tomorrow.isoformat(), tomorrow.isoformat()
    elif date_query_str == "yesterday":
        yesterday = today - timedelta(days=1)
        return yesterday.isoformat(), yesterday.isoformat()
    elif date_query_str == "this week": # Assuming week starts on Monday
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        return start_of_week.isoformat(), end_of_week.isoformat()
    elif date_query_str == "next week":
        start_of_next_week = today - timedelta(days=today.weekday()) + timedelta(weeks=1)
        end_of_next_week = start_of_next_week + timedelta(days=6)
        return start_of_next_week.isoformat(), end_of_next_week.isoformat()
    return None, None

@task_bp.route('/query-notion-tasks', methods=['POST'])
def query_notion_tasks_route():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": {"code": "INVALID_PAYLOAD", "message": "Request must be JSON."}}), 400

        # --- Configuration ---
        notion_api_token = os.environ.get("ATOM_NOTION_API_TOKEN")
        notion_db_id = data.get("notion_db_id") # Resolved DB ID from skill

        if not notion_api_token:
            return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Notion API token not configured."}}), 500
        if not notion_db_id:
            return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Notion Tasks Database ID not provided."}}), 400

        # --- Extract Query Parameters ---
        status_filter = data.get("status")
        priority_filter = data.get("priority")
        due_date_before_str = data.get("dueDateBefore")
        due_date_after_str = data.get("dueDateAfter")
        date_query_str = data.get("dateQuery")
        list_name_filter = data.get("listName")
        description_contains_filter = data.get("descriptionContains")
        limit = data.get("limit", 25)

        # --- Initialize Notion Client ---
        notion = NotionClient(auth=notion_api_token)

        # --- Construct Notion Filter Object ---
        filters = []

        if status_filter:
            if isinstance(status_filter, list):
                if status_filter:
                    status_conditions = [{"property": "Status", "select": {"equals": s}} for s in status_filter]
                    filters.append({"or": status_conditions})
            elif isinstance(status_filter, str):
                filters.append({"property": "Status", "select": {"equals": status_filter}})

        if priority_filter:
            filters.append({"property": "Priority", "select": {"equals": priority_filter}})

        resolved_start_date, resolved_end_date = None, None
        if date_query_str:
            resolved_start_date, resolved_end_date = _resolve_date_query(date_query_str)

        if resolved_start_date and resolved_end_date:
            if resolved_start_date == resolved_end_date:
                filters.append({"property": "Due Date", "date": {"equals": resolved_start_date.split('T')[0]}})
            else:
                filters.append({"property": "Due Date", "date": {"on_or_after": resolved_start_date.split('T')[0]}})
                filters.append({"property": "Due Date", "date": {"on_or_before": resolved_end_date.split('T')[0]}})
        else:
            if due_date_after_str:
                filters.append({"property": "Due Date", "date": {"on_or_after": due_date_after_str}})
            if due_date_before_str:
                filters.append({"property": "Due Date", "date": {"on_or_before": due_date_before_str}})

        if list_name_filter:
            filters.append({"property": "List Name", "rich_text": {"contains": list_name_filter}})

        if description_contains_filter:
            filters.append({"property": "Task Description", "title": {"contains": description_contains_filter}})

        final_filter = None
        if len(filters) > 1:
            final_filter = {"and": filters}
        elif len(filters) == 1:
            final_filter = filters[0]

        query_params = {"database_id": notion_db_id, "page_size": min(limit, 100)}
        if final_filter:
            query_params["filter"] = final_filter

        response = notion.databases.query(**query_params)

        tasks_list = []
        for page in response.get("results", []):
            props = page.get("properties", {})

            def get_prop_value(prop_name, prop_type):
                prop = props.get(prop_name)
                if not prop: return None
                if prop_type == "title": return prop.get("title", [{}])[0].get("plain_text") if prop.get("title") else None
                if prop_type == "rich_text": return prop.get("rich_text", [{}])[0].get("plain_text") if prop.get("rich_text") else None
                if prop_type == "select": return prop.get("select", {}).get("name") if prop.get("select") else None
                if prop_type == "date": return prop.get("date", {}).get("start") if prop.get("date") else None
                return None

            tasks_list.append({
                "id": page.get("id"),
                "description": get_prop_value("Task Description", "title"),
                "dueDate": get_prop_value("Due Date", "date"),
                "status": get_prop_value("Status", "select"),
                "priority": get_prop_value("Priority", "select"),
                "listName": get_prop_value("List Name", "rich_text"),
                "createdDate": page.get("created_time"),
                "url": page.get("url"),
            })

        return jsonify({
            "ok": True,
            "data": tasks_list,
            "message": f"Retrieved {len(tasks_list)} tasks."
        }), 200

    except Exception as e:
        print(f"Error querying Notion tasks: {str(e)}")
        return jsonify({"ok": False, "error": {"code": "INTERNAL_SERVER_ERROR", "message": f"An unexpected error occurred: {str(e)}" }}), 500

# @task_bp.route('/update-notion-task', methods=['POST'])
# def update_notion_task_route():
#     # Implementation will go here
#     pass

@task_bp.route('/update-notion-task', methods=['POST'])
def update_notion_task_route():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": {"code": "INVALID_PAYLOAD", "message": "Request must be JSON."}}), 400

        # --- Configuration ---
        notion_api_token = os.environ.get("ATOM_NOTION_API_TOKEN")
        if not notion_api_token:
            return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Notion API token not configured."}}), 500

        # --- Extract Task ID and Updateable Fields ---
        task_id = data.get("taskId") # Notion Page ID
        if not task_id:
            return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "Task ID (taskId) is required."}}), 400

        properties_to_update = {}
        updated_keys = [] # To report back which fields were actually updated

        # Description (Title property)
        if "description" in data and data["description"] is not None:
            properties_to_update["Task Description"] = {"title": [{"type": "text", "text": {"content": data["description"]}}]}
            updated_keys.append("description")

        # Due Date (Date property)
        if "dueDate" in data:
            due_date_str = data["dueDate"]
            if due_date_str is None:
                properties_to_update["Due Date"] = {"date": None}
            else:
                properties_to_update["Due Date"] = {"date": {"start": due_date_str}}
            updated_keys.append("dueDate")

        # Status (Select property)
        if "status" in data and data["status"] is not None:
            properties_to_update["Status"] = {"select": {"name": data["status"]}}
            updated_keys.append("status")

        # Priority (Select property)
        if "priority" in data:
            priority_val = data["priority"]
            if priority_val is not None:
                properties_to_update["Priority"] = {"select": {"name": priority_val}}
                updated_keys.append("priority")
            # Note: Notion typically doesn't allow clearing a select to null via API in the same way as a date.
            # If priority_val is None, we simply don't add it to properties_to_update.
            # The skill/NLU should send a specific value if a change is intended.

        # List Name (Rich Text property)
        if "listName" in data:
            list_name_val = data["listName"]
            if list_name_val is None: # Clear the rich text
                properties_to_update["List Name"] = {"rich_text": []}
            else: # Set or update rich text
                properties_to_update["List Name"] = {"rich_text": [{"type": "text", "text": {"content": list_name_val}}]}
            updated_keys.append("listName")

        if "notes" in data and data["notes"] is not None:
            print(f"Info: 'notes' field was provided for task {task_id} but page content update is not implemented in this endpoint version.")
            # If we were to update notes (page content), it would be a separate block operation.
            # updated_keys.append("notes") # Only add if actually updated

        if not properties_to_update:
            return jsonify({
                "ok": True,
                "data": {
                    "taskId": task_id,
                    "updatedProperties": [],
                    "message": "No updateable fields provided or no changes detected."
                }
            }), 200

        # --- Initialize Notion Client ---
        notion = NotionClient(auth=notion_api_token)

        # --- Update Notion Page ---
        notion.pages.update(
            page_id=task_id,
            properties=properties_to_update
        )

        return jsonify({
            "ok": True,
            "data": {
                "taskId": task_id,
                "updatedProperties": updated_keys,
                "message": "Task updated successfully in Notion."
            }
        }), 200

    except Exception as e:
        print(f"Error updating Notion task {data.get('taskId', 'Unknown_ID') if 'data' in locals() else 'Unknown_ID'}: {str(e)}")
        # from notion_client import APIResponseError
        # if isinstance(e, APIResponseError):
        #    return jsonify({"ok": False, "error": {"code": "NOTION_API_ERROR", "message": str(e)}}), e.status
        return jsonify({"ok": False, "error": {"code": "INTERNAL_SERVER_ERROR", "message": f"An unexpected error occurred: {str(e)}" }}), 500

# Example of how this blueprint might be used (for context, not part of this file):
# app = Flask(__name__)
# app.register_blueprint(task_bp, url_prefix='/api/tasks')
