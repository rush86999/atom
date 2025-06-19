import os
import openai
import json
from serpapi import GoogleSearch, SerpApiClientException # Import SerpApi parts
from project.functions import note_utils
# Removed requests import as it's no longer used by python_search_web

def decompose_query_into_tasks_llm(user_query: str, openai_api_key: str) -> list[str]:
    try:
        client = openai.OpenAI(api_key=openai_api_key)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo-1106",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You are a research assistant. Given the user's research query, break it down into 3 to 5 specific, actionable sub-queries that can be independently searched on a web search engine. Each sub-query should be a concise string. Respond ONLY with a valid JSON object containing a single key 'tasks' which is a list of these string sub-queries. For example: {\\\"tasks\\\": [\\\"search query 1\\\", \\\"search query 2\\\", \\\"search query 3\\\"]}"},
                {"role": "user", "content": user_query}
            ],
            temperature=0.2
        )
        response_content = response.choices[0].message.content
        if response_content:
            data = json.loads(response_content)
            if isinstance(data.get("tasks"), list):
                return [str(task) for task in data["tasks"] if isinstance(task, str)]
        print("LLM response for task decomposition did not yield a valid task list.")
        return []
    except Exception as e:
        print(f"Error decomposing query with LLM: {e}")
        return []

def initiate_research_project(user_query: str, user_id: str, project_db_id: str, task_db_id: str, openai_api_key: str) -> dict:
    if not note_utils.notion:
        return {"status": "error", "message": "Notion client not initialized in note_utils."}

    original_notes_db_id = note_utils.NOTION_NOTES_DATABASE_ID
    project_page_id = None
    try:
        task_descriptions = decompose_query_into_tasks_llm(user_query, openai_api_key)
        if not task_descriptions:
            return {"status": "error", "message": "Failed to decompose query into tasks."}

        note_utils.NOTION_NOTES_DATABASE_ID = project_db_id
        project_page_title = f"Research Project: {user_query[:100]}"
        project_content = f"Original Query: {user_query}\\nUser ID: {user_id}\\nStatus: Pending"
        project_page_id = note_utils.create_notion_note(title=project_page_title, content=project_content, source="research_agent")

        if not project_page_id:
            return {"status": "error", "message": f"Failed to create project page in Notion DB {project_db_id}."}

        created_task_page_ids = []
        note_utils.NOTION_NOTES_DATABASE_ID = task_db_id
        for desc in task_descriptions:
            task_page_title = f"Task: {desc[:100]}"
            task_page_id = note_utils.create_notion_note(title=task_page_title, content=desc, source="research_agent_task", linked_event_id=project_page_id)
            if task_page_id:
                created_task_page_ids.append(task_page_id)
            else:
                print(f"Warning: Failed to create task page for '{desc}' in DB {task_db_id}.")
        return {"status": "success", "project_page_id": project_page_id, "task_page_ids": created_task_page_ids}
    finally:
        note_utils.NOTION_NOTES_DATABASE_ID = original_notes_db_id


def python_search_web(query: str, api_key: str) -> dict:
    """
    Performs a web search using SerpApi.

    Args:
        query: The search query string.
        api_key: The SerpApi API key.

    Returns:
        A dictionary with 'status' and either 'data' (list of results) or 'message'/'details' (on error).
        Each result in 'data' is a dict with 'title', 'link', and 'snippet'.
    """
    if not api_key:
        # This should ideally be caught before calling, but as a safeguard:
        return {"status": "error", "message": "Search API key is missing.", "code": "CONFIG_ERROR"}

    params = {
        "q": query,
        "api_key": api_key,
        "engine": "google",  # Default engine
        # "num": 10, # Number of results
    }
    search_results = []
    try:
        search = GoogleSearch(params)
        results_data = search.get_dict() # Returns a dict

        if results_data.get("error"):
            error_message = results_data["error"]
            code = "SEARCH_API_ERROR"
            if "invalid api key" in error_message.lower() or \
               "authorization" in error_message.lower() or \
               "forbidden" in error_message.lower():
                code = "SEARCH_API_AUTH_ERROR"
            return {"status": "error", "message": f"SerpApi error: {error_message}", "code": code, "details": results_data}

        organic_results = results_data.get("organic_results", [])
        if not organic_results and "knowledge_graph" in results_data: # Fallback for some queries
            kg = results_data["knowledge_graph"]
            if kg.get("title") and kg.get("source", {}).get("link"): # Ensure basic fields exist
                 search_results.append({
                    "title": kg.get("title", "Knowledge Graph Result"),
                    "link": kg.get("source", {}).get("link", "#"),
                    "snippet": kg.get("description", kg.get("snippet", "No snippet available from Knowledge Graph."))
                })

        for item in organic_results:
            search_results.append({
                "title": item.get("title", "No title"),
                "link": item.get("link", "#"),
                "snippet": item.get("snippet", "No snippet available.")
            })

        if not search_results and not results_data.get("error"):
            # No organic results and no explicit error from SerpApi
            # This could be a valid case (no results for query) or an unexpected response
            print(f"No organic results found by SerpApi for query: {query}. Full response: {results_data.get('search_information', {}).get('organic_results_state', 'N/A')}")
            # Let's not treat "no results" as an error, but return empty data.
            # If it's truly an unexpected format, other checks might catch it or it'll result in empty.

        return {"status": "success", "data": search_results}

    except SerpApiClientException as e:
        # Handles API client-specific errors (e.g., auth, bad request to SerpApi endpoint)
        # This exception's message often contains useful info from SerpApi.
        message = str(e)
        code = "SEARCH_API_ERROR"
        if "API_KEY_INVALID" in message or "forbidden" in message.lower() or "authorization" in message.lower():
            code = "SEARCH_API_AUTH_ERROR"
        elif "Request timed out" in message: # Example for network-like issue
            code = "NETWORK_ERROR"
        return {"status": "error", "message": f"SerpApi client error: {message}", "code": code, "details": str(e)}
    except Exception as e:
        # Catch-all for other unexpected errors (e.g., network issues not caught by SerpApiClientException, bugs)
        print(f"Unexpected error during web search with SerpApi for query '{query}': {e}")
        return {"status": "error", "message": f"Unexpected error during web search: {str(e)}", "code": "UNKNOWN_SEARCH_ERROR", "details": str(e)}


def execute_research_task(task_page_id: str, search_api_key: str) -> dict:
    """
    Executes a single research task: retrieves task details from Notion,
    performs a web search, and updates the Notion page with results.
    """
    if not note_utils.notion:
        return {"status": "error", "message": "Notion client not initialized."}
    if not search_api_key: # Check for API key at the beginning
        return {"status": "error", "message": "Search API key not provided to execute_research_task.", "code": "CONFIG_ERROR"}


    original_notes_db_id = note_utils.NOTION_NOTES_DATABASE_ID
    task_details = None
    try:
        task_details = note_utils.get_notion_note(page_id=task_page_id)
        if not task_details:
            return {"status": "error", "message": f"Could not retrieve task details for page ID: {task_page_id}"}

        search_query = task_details.get("content", "").strip()
        if not search_query:
            search_query = task_details.get("title", "").replace("Task: ", "").strip()
            if not search_query:
                return {"status": "error", "message": f"Search query not found for page ID: {task_page_id}"}

        print(f"Executing task {task_page_id}: Searching for '{search_query}'")

        search_response = python_search_web(query=search_query, api_key=search_api_key)
        results_string = f"\n\n--- Search Task: {search_query} ---\n"

        if search_response["status"] == "success":
            search_results = search_response["data"]
            if search_results:
                for res in search_results:
                    results_string += f"Title: {res['title']}\nLink: {res['link']}\nSnippet: {res['snippet']}\n---\n"
            else:
                results_string += "No results found for this query.\n"
        else: # Search failed
            error_info = search_response
            results_string += (f"Search failed: {error_info.get('message', 'Unknown error')}\n"
                               f"Error Code: {error_info.get('code', 'N/A')}\n"
                               f"Details: {error_info.get('details', 'N/A')}\n---\n")

        updated_content = task_details.get("content", "") + results_string
        # Using linked_task_id to store status. Could also be a dedicated 'Status' property.
        # If search failed, task is still marked "COMPLETED" to avoid re-processing, but contains error info.
        success = note_utils.update_notion_note(page_id=task_page_id, content=updated_content, linked_task_id="COMPLETED")

        if success:
            return {"status": "success", "message": f"Task {task_page_id} processed. Results/errors saved to Notion."}
        else:
            return {"status": "error", "message": f"Failed to update task {task_page_id} in Notion after search."}

    except Exception as e:
        print(f"Error executing research task {task_page_id}: {e}")
        # Attempt to update Notion page with error if possible
        if task_details and task_page_id:
            try:
                error_update_content = task_details.get("content", "") + f"\n\n--- ERROR DURING TASK EXECUTION ---\n{str(e)}\n---"
                note_utils.update_notion_note(page_id=task_page_id, content=error_update_content, linked_task_id="ERROR_STATE")
            except Exception as notion_update_err:
                print(f"Additionally failed to update Notion page {task_page_id} with execution error: {notion_update_err}")
        return {"status": "error", "message": f"Error executing research task {task_page_id}: {str(e)}"}
    finally:
        if original_notes_db_id:
             note_utils.NOTION_NOTES_DATABASE_ID = original_notes_db_id


def monitor_and_execute_tasks(task_db_id: str, search_api_key: str, project_db_id: str, openai_api_key: str) -> dict:
    if not note_utils.notion:
        return {"status": "error", "message": "Notion client not initialized."}
    if not search_api_key: # Check for API key at the beginning
        return {"status": "error", "message": "Search API key not provided to monitor_and_execute_tasks.", "code": "CONFIG_ERROR"}
    if not openai_api_key:
         return {"status": "error", "message": "OpenAI API key not provided to monitor_and_execute_tasks.", "code": "CONFIG_ERROR"}


    print(f"Checking for pending tasks in database: {task_db_id}")
    original_notes_db_id = note_utils.NOTION_NOTES_DATABASE_ID
    processed_tasks = 0
    failed_tasks = 0
    try:
        note_utils.NOTION_NOTES_DATABASE_ID = task_db_id
        all_tasks_in_db = note_utils.search_notion_notes(query="", source="research_agent_task")
        pending_tasks = [
            task for task in all_tasks_in_db
            if task.get("source") == "research_agent_task" and
               task.get("linked_task_id") not in ["COMPLETED", "ERROR_STATE"] # Avoid reprocessing completed or error-state tasks
        ]

        if not pending_tasks:
            print("No pending research tasks found.")
        else:
            print(f"Found {len(pending_tasks)} pending tasks to process.")
            for task_summary in pending_tasks:
                task_page_id = task_summary["id"]
                result = execute_research_task(task_page_id=task_page_id, search_api_key=search_api_key)
                if result.get("status") == "success":
                    processed_tasks += 1
                else:
                    failed_tasks += 1
                    print(f"Failed to process task {task_page_id}: {result.get('message')}")
    except Exception as e:
        print(f"Error during task monitoring and execution: {e}")
    finally:
        note_utils.NOTION_NOTES_DATABASE_ID = original_notes_db_id

    print("Proceeding to check for project completion and synthesis.")
    check_projects_for_completion_and_synthesize(
        project_db_id=project_db_id,
        task_db_id=task_db_id,
        openai_api_key=openai_api_key
    )
    return {"status": "success", "message": f"Task cycle finished. Processed: {processed_tasks}, Failed: {failed_tasks}.", "processed_tasks": processed_tasks, "failed_tasks": failed_tasks}


def synthesize_research_findings_llm(findings: list[str], original_query: str, openai_api_key: str) -> str:
    try:
        client = openai.OpenAI(api_key=openai_api_key)
        MAX_FINDINGS_LENGTH = 15000
        concatenated_findings = "\n\n---\n\n".join(findings)
        if len(concatenated_findings) > MAX_FINDINGS_LENGTH:
            concatenated_findings = concatenated_findings[:MAX_FINDINGS_LENGTH] + "... (truncated)"
        system_prompt = ("You are a research analyst. Based on the following collected information (from multiple search tasks) \n"
                         "and the original research query, synthesize a comprehensive report. \n"
                         "The report should directly address the original query, be well-organized, coherent, and based SOLELY on the provided information. \n"
                         "Do not add external knowledge. If the information is insufficient, state that. \n"
                         "Original Research Query: {}".format(original_query))
        user_message = f"Collected Information:\n{concatenated_findings}"
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[ {"role": "system", "content": system_prompt}, {"role": "user", "content": user_message} ],
            temperature=0.5
        )
        report = response.choices[0].message.content
        return report if report else "Synthesis failed or returned empty."
    except Exception as e:
        print(f"Error synthesizing research findings with LLM: {e}")
        return f"Error during synthesis: {str(e)}"

def check_projects_for_completion_and_synthesize(project_db_id: str, task_db_id: str, openai_api_key: str):
    if not note_utils.notion:
        print("Notion client not initialized. Cannot check projects.")
        return
    if not openai_api_key: # Check for API key
        print("OpenAI API key not provided. Cannot synthesize.")
        return

    print(f"Checking for completable projects in database: {project_db_id}")
    original_notes_db_id = note_utils.NOTION_NOTES_DATABASE_ID
    updated_projects_count = 0
    try:
        note_utils.NOTION_NOTES_DATABASE_ID = project_db_id
        all_projects_in_db = note_utils.search_notion_notes(query="Status: Pending", source="research_agent")
        pending_projects = [p for p in all_projects_in_db if "Status: Pending" in p.get("content","")]

        if not pending_projects:
            print("No pending research projects found requiring synthesis.")
            return
        print(f"Found {len(pending_projects)} pending projects for synthesis check.")

        for project in pending_projects:
            project_page_id = project["id"]
            original_query = project.get("content","").split("\n")[0].replace("Original Query: ","").strip()
            print(f"Checking project: {project_page_id} - {project.get('title')}")

            note_utils.NOTION_NOTES_DATABASE_ID = task_db_id
            all_tasks_in_task_db = note_utils.search_notion_notes(query="", source="research_agent_task")
            project_tasks = [t for t in all_tasks_in_task_db if t.get("linked_event_id") == project_page_id]

            if not project_tasks:
                print(f"No tasks found for project {project_page_id}. Skipping.")
                continue

            all_tasks_completed = True
            completed_task_findings = []
            for task in project_tasks:
                if task.get("linked_task_id") == "COMPLETED": # Status is in 'linked_task_id'
                    completed_task_findings.append(task.get("content", ""))
                elif task.get("linked_task_id") == "ERROR_STATE": # Task had an error during execution
                    completed_task_findings.append(f"Note: Task '{task.get('title')}' encountered an error during execution. Content: {task.get('content', '')}")
                else: # Task not completed or in error state
                    all_tasks_completed = False
                    break

            if all_tasks_completed:
                print(f"All tasks for project {project_page_id} are processed. Synthesizing report...")
                if not completed_task_findings:
                    synthesized_report = "No specific findings were extracted from research tasks, or tasks encountered issues."
                else:
                    synthesized_report = synthesize_research_findings_llm(completed_task_findings, original_query, openai_api_key)

                note_utils.NOTION_NOTES_DATABASE_ID = project_db_id
                project_current_content = project.get("content","")
                updated_project_content = project_current_content.replace("Status: Pending", "Status: Completed")
                updated_project_content += f"\n\n--- Synthesized Report ---\n{synthesized_report}"
                update_success = note_utils.update_notion_note(page_id=project_page_id, content=updated_project_content, linked_task_id="COMPLETED_PROJECT")

                if update_success:
                    print(f"Project {project_page_id} updated with report and status 'Completed'.")
                    updated_projects_count += 1
                else:
                    print(f"Failed to update project {project_page_id} with report.")
            else:
                print(f"Project {project_page_id} still has pending tasks. Not synthesizing.")
    except Exception as e:
        print(f"Error during project completion check: {e}")
    finally:
        note_utils.NOTION_NOTES_DATABASE_ID = original_notes_db_id
    print(f"Project synthesis check finished. Updated projects: {updated_projects_count}")

[end of atomic-docker/project/functions/atom-agent/research_agent.py]
