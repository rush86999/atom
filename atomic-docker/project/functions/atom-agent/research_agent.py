import openai # os is not directly needed here anymore for env vars
import json
from serpapi import GoogleSearch, SerpApiClientException
from project.functions import note_utils


def decompose_query_into_tasks_llm(user_query: str, openai_api_key: str) -> list[str]:
    """Decomposes a user query into actionable sub-tasks using an LLM."""
    if not openai_api_key:
        print("Error: OpenAI API key not provided for task decomposition.")
        # Returning empty list, caller should handle this as a failure to decompose.
        return []
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
    """
    Initiates a research project by decomposing the query into tasks and creating corresponding Notion pages.
    Assumes Notion client (note_utils.notion) is already initialized by the caller.
    """
    if not openai_api_key:
        return {"status": "error", "message": "OpenAI API key not provided.", "code": "CONFIG_ERROR_OPENAI"}

    if not note_utils.notion:
        return {"status": "error", "message": "Notion client not initialized in note_utils.", "code": "NOTION_CLIENT_ERROR"}

    original_notes_db_id = note_utils.NOTION_NOTES_DATABASE_ID
    project_page_id = None
    try:
        task_descriptions = decompose_query_into_tasks_llm(user_query, openai_api_key)
        if not task_descriptions:
            return {"status": "error", "message": "Failed to decompose query into tasks (no tasks returned by LLM).", "code": "LLM_DECOMPOSITION_FAILED"}

        note_utils.NOTION_NOTES_DATABASE_ID = project_db_id
        project_page_title = f"Research Project: {user_query[:100]}"
        project_content = f"Original Query: {user_query}\nUser ID: {user_id}\nStatus: Pending"

        project_creation_response = note_utils.create_notion_note(title=project_page_title, content=project_content, source="research_agent")

        if project_creation_response["status"] != "success":
            return {"status": "error", "message": f"Failed to create project page in Notion DB {project_db_id}. Details: {project_creation_response.get('message')}", "code": "NOTION_PAGE_CREATION_FAILED"}
        project_page_id = project_creation_response["data"] # Expects page_id here

        created_task_page_ids = []
        note_utils.NOTION_NOTES_DATABASE_ID = task_db_id
        for desc in task_descriptions:
            task_page_title = f"Task: {desc[:100]}"
            task_creation_response = note_utils.create_notion_note(title=task_page_title, content=desc, source="research_agent_task", linked_event_id=project_page_id)
            if task_creation_response["status"] == "success":
                created_task_page_ids.append(task_creation_response["data"]) # Expects page_id
            else:
                print(f"Warning: Failed to create task page for description '{desc}' in Notion DB {task_db_id}. Details: {task_creation_response.get('message')}")

        return {"status": "success", "data": {"project_page_id": project_page_id, "task_page_ids": created_task_page_ids}}
    except Exception as e:
        print(f"Unexpected error in initiate_research_project: {e}")
        return {"status": "error", "message": f"Unexpected error: {str(e)}", "code": "UNEXPECTED_ERROR_INITIATE_RESEARCH"}
    finally:
        if original_notes_db_id is not None : # Ensure it was set before trying to restore
            note_utils.NOTION_NOTES_DATABASE_ID = original_notes_db_id


def python_search_web(query: str, api_key: str) -> dict:
    """
    Performs a web search using SerpApi.
    """
    if not api_key:
        return {"status": "error", "message": "Search API key is missing.", "code": "CONFIG_ERROR_SEARCH_KEY"}

    params = { "q": query, "api_key": api_key, "engine": "google" }
    search_results = []
    try:
        search = GoogleSearch(params)
        results_data = search.get_dict()

        if results_data.get("error"):
            error_message = results_data["error"]
            code = "SEARCH_API_ERROR"
            if "invalid api key" in error_message.lower() or "authorization" in error_message.lower() or "forbidden" in error_message.lower():
                code = "SEARCH_API_AUTH_ERROR"
            return {"status": "error", "message": f"SerpApi error: {error_message}", "code": code, "details": results_data.get("search_parameters", {})}

        organic_results = results_data.get("organic_results", [])
        if not organic_results and "knowledge_graph" in results_data:
            kg = results_data["knowledge_graph"]
            if kg.get("title") and kg.get("source", {}).get("link"):
                 search_results.append({
                    "title": kg.get("title", "Knowledge Graph Result"),
                    "link": kg.get("source", {}).get("link", "#"),
                    "snippet": kg.get("description", kg.get("snippet", "No snippet available from Knowledge Graph."))
                })

        for item in organic_results:
            search_results.append({
                "title": item.get("title", "No title"), "link": item.get("link", "#"),
                "snippet": item.get("snippet", "No snippet available.")
            })

        if not search_results and not results_data.get("error"):
            print(f"No organic results by SerpApi for query: {query}. State: {results_data.get('search_information', {}).get('organic_results_state', 'N/A')}")

        return {"status": "success", "data": search_results}

    except SerpApiClientException as e:
        message = str(e)
        code = "SEARCH_API_ERROR"
        if "API_KEY_INVALID" in message or "forbidden" in message.lower() or "authorization" in message.lower():
            code = "SEARCH_API_AUTH_ERROR"
        elif "Request timed out" in message: code = "NETWORK_ERROR"
        return {"status": "error", "message": f"SerpApi client error: {message}", "code": code, "details": str(e)}
    except Exception as e:
        print(f"Unexpected error during web search (SerpApi query '{query}'): {e}")
        return {"status": "error", "message": f"Unexpected error during web search: {str(e)}", "code": "UNKNOWN_SEARCH_ERROR", "details": str(e)}


def execute_research_task(task_page_id: str, search_api_key: str) -> dict:
    """
    Executes a single research task. Assumes Notion client is initialized.
    """
    if not note_utils.notion:
        return {"status": "error", "message": "Notion client not initialized.", "code": "NOTION_CLIENT_ERROR"}
    if not search_api_key:
        return {"status": "error", "message": "Search API key not provided.", "code": "CONFIG_ERROR_SEARCH_KEY"}

    original_notes_db_id = note_utils.NOTION_NOTES_DATABASE_ID
    task_details_response = note_utils.get_notion_note(page_id=task_page_id) # Returns dict

    if task_details_response["status"] != "success":
        return {"status": "error", "message": f"Could not retrieve task details for page ID: {task_page_id}. Details: {task_details_response.get('message')}", "code": "NOTION_PAGE_RETRIEVAL_FAILED"}
    task_details = task_details_response["data"] # page object

    try:
        search_query = task_details.get("content", "").strip()
        if not search_query:
            search_query = task_details.get("title", "").replace("Task: ", "").strip()
            if not search_query:
                return {"status": "error", "message": f"Search query not found for page ID: {task_page_id}", "code": "QUERY_NOT_FOUND"}

        print(f"Executing task {task_page_id}: Searching for '{search_query}'")
        search_response = python_search_web(query=search_query, api_key=search_api_key)

        results_log_string = f"\n\n--- Search Task: {search_query} ---\n"
        if search_response["status"] == "success":
            search_results = search_response["data"]
            if search_results:
                for res in search_results: results_log_string += f"Title: {res['title']}\nLink: {res['link']}\nSnippet: {res['snippet']}\n---\n"
            else: results_log_string += "No results found for this query.\n"
        else:
            error_info = search_response
            results_log_string += (f"Search failed: {error_info.get('message', 'Unknown error')}\n"
                                   f"Error Code: {error_info.get('code', 'N/A')}\n"
                                   f"Details: {str(error_info.get('details', 'N/A'))}\n---\n")

        current_content = task_details.get("content", "")
        updated_content = current_content + results_log_string

        update_response = note_utils.update_notion_note(page_id=task_page_id, content=updated_content, linked_task_id="COMPLETED")

        if update_response["status"] == "success":
            return {"status": "success", "message": f"Task {task_page_id} processed. Results/errors saved."}
        else:
            return {"status": "error", "message": f"Failed to update task {task_page_id} in Notion. Details: {update_response.get('message')}", "code": "NOTION_PAGE_UPDATE_FAILED"}

    except Exception as e:
        print(f"Unexpected error executing research task {task_page_id}: {e}")
        if task_page_id:
            try:
                # task_details might be None if error occurred before it was fetched
                current_content_for_error = task_details.get("content", "Content not available.") if task_details else "Content not available."
                error_update_content = current_content_for_error + f"\n\n--- ERROR DURING TASK EXECUTION ---\n{str(e)}\n---"
                note_utils.update_notion_note(page_id=task_page_id, content=error_update_content, linked_task_id="ERROR_STATE")
            except Exception as notion_update_err:
                print(f"Additionally failed to update Notion page {task_page_id} with execution error: {notion_update_err}")
        return {"status": "error", "message": f"Unexpected error executing task {task_page_id}: {str(e)}", "code": "UNEXPECTED_TASK_EXECUTION_ERROR"}
    finally:
        if original_notes_db_id is not None:
             note_utils.NOTION_NOTES_DATABASE_ID = original_notes_db_id


def monitor_and_execute_tasks(task_db_id: str, project_db_id: str, search_api_key: str, openai_api_key: str) -> dict:
    """
    Monitors Notion for pending tasks, executes them, and triggers synthesis.
    Assumes Notion client is initialized.
    """
    if not search_api_key: return {"status": "error", "message": "Search API key not provided.", "code": "CONFIG_ERROR_SEARCH_KEY"}
    if not openai_api_key: return {"status": "error", "message": "OpenAI API key not provided.", "code": "CONFIG_ERROR_OPENAI"}
    if not note_utils.notion: return {"status": "error", "message": "Notion client not initialized.", "code": "NOTION_CLIENT_ERROR"}

    print(f"Checking for pending tasks in database: {task_db_id}")
    original_notes_db_id = note_utils.NOTION_NOTES_DATABASE_ID
    processed_tasks_count = 0; failed_tasks_count = 0
    try:
        note_utils.NOTION_NOTES_DATABASE_ID = task_db_id
        all_tasks_response = note_utils.search_notion_notes(query="", source="research_agent_task")

        if all_tasks_response["status"] != "success":
            return {"status": "error", "message": "Failed to retrieve tasks from Notion.", "code": "NOTION_SEARCH_FAILED", "details": all_tasks_response.get("message")}

        all_tasks_in_db = all_tasks_response["data"]
        pending_tasks = [t for t in all_tasks_in_db if t.get("source") == "research_agent_task" and t.get("linked_task_id") not in ["COMPLETED", "ERROR_STATE"]]

        if not pending_tasks: print("No pending research tasks found.")
        else:
            print(f"Found {len(pending_tasks)} pending tasks to process.")
            for task_summary in pending_tasks:
                task_page_id = task_summary["id"]
                result = execute_research_task(task_page_id=task_page_id, search_api_key=search_api_key)
                if result.get("status") == "success": processed_tasks_count += 1
                else: failed_tasks_count += 1; print(f"Failed task {task_page_id}: {result.get('message')}")
    except Exception as e:
        print(f"Error during task monitoring/execution: {e}")
        return {"status": "error", "message": f"Error in task monitoring loop: {str(e)}", "code": "TASK_MONITORING_ERROR"}
    finally:
        if original_notes_db_id is not None: note_utils.NOTION_NOTES_DATABASE_ID = original_notes_db_id

    print("Proceeding to check for project completion and synthesis.")
    synthesis_result = check_projects_for_completion_and_synthesize(project_db_id=project_db_id, task_db_id=task_db_id, openai_api_key=openai_api_key)

    return {"status": "success", "data": {
            "message": f"Task cycle finished. Processed: {processed_tasks_count}, Failed: {failed_tasks_count}.",
            "processed_tasks": processed_tasks_count, "failed_tasks": failed_tasks_count,
            "synthesis_outcome": synthesis_result }}


def synthesize_research_findings_llm(findings: list[str], original_query: str, openai_api_key: str) -> str:
    """Synthesizes research findings using an LLM."""
    if not openai_api_key: return "Error: OpenAI API key not provided for synthesis."
    try:
        client = openai.OpenAI(api_key=openai_api_key)
        MAX_FINDINGS_LENGTH = 15000
        concatenated_findings = "\n\n---\n\n".join(findings)
        if len(concatenated_findings) > MAX_FINDINGS_LENGTH:
            concatenated_findings = concatenated_findings[:MAX_FINDINGS_LENGTH] + "... (truncated)"

        system_prompt = ("You are a research analyst. Based on the collected information and original query, synthesize a comprehensive report. "
                         "Focus on addressing the query directly, using only the provided information. State if information is insufficient.")
        user_message = f"Original Query: {original_query}\n\nCollected Information:\n{concatenated_findings}"

        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[ {"role": "system", "content": system_prompt}, {"role": "user", "content": user_message} ],
            temperature=0.5 )
        report = response.choices[0].message.content
        return report if report else "Synthesis LLM returned empty content."
    except Exception as e:
        print(f"Error synthesizing research findings with LLM: {e}")
        return f"Error during synthesis: {str(e)}"


def check_projects_for_completion_and_synthesize(project_db_id: str, task_db_id: str, openai_api_key: str) -> dict:
    """
    Checks research projects for completion and triggers synthesis. Assumes Notion client initialized.
    """
    if not note_utils.notion: return {"status": "error", "message": "Notion client not initialized.", "code": "NOTION_CLIENT_ERROR"}
    if not openai_api_key: return {"status": "error", "message": "OpenAI API key not provided for synthesis.", "code": "CONFIG_ERROR_OPENAI"}

    print(f"Checking completable projects in DB: {project_db_id}")
    original_notes_db_id = note_utils.NOTION_NOTES_DATABASE_ID
    synthesis_attempts = 0; successful_synthesis_updates = 0
    try:
        note_utils.NOTION_NOTES_DATABASE_ID = project_db_id
        projects_response = note_utils.search_notion_notes(query="Status: Pending", source="research_agent") # Expects dict

        if projects_response["status"] != "success":
            return {"status": "error", "message": f"Failed to search pending projects: {projects_response.get('message')}", "code": "NOTION_SEARCH_FAILED"}

        pending_projects = [p for p in projects_response["data"] if "Status: Pending" in p.get("content","")]
        if not pending_projects:
            return {"status": "success", "data": {"message": "No pending projects for synthesis.", "updated_projects": 0}}

        synthesis_attempts = len(pending_projects)
        print(f"Found {synthesis_attempts} pending projects for synthesis check.")

        for project in pending_projects:
            project_page_id = project["id"]
            original_query_match = [line for line in project.get("content","").split("\n") if line.startswith("Original Query: ")]
            original_query = original_query_match[0].replace("Original Query: ","").strip() if original_query_match else "Unknown Original Query"

            note_utils.NOTION_NOTES_DATABASE_ID = task_db_id
            tasks_response = note_utils.search_notion_notes(query="", source="research_agent_task") # Expects dict
            if tasks_response["status"] != "success":
                print(f"Failed to retrieve tasks for project {project_page_id}: {tasks_response.get('message')}")
                continue

            project_tasks = [t for t in tasks_response["data"] if t.get("linked_event_id") == project_page_id]
            if not project_tasks: print(f"No tasks for project {project_page_id}."); continue

            all_tasks_processed = True; completed_task_findings = []
            for task in project_tasks:
                task_status = task.get("linked_task_id")
                if task_status == "COMPLETED": completed_task_findings.append(task.get("content", ""))
                elif task_status == "ERROR_STATE": completed_task_findings.append(f"Note: Task '{task.get('title')}' error. Content: {task.get('content', '')}")
                else: all_tasks_processed = False; break

            if all_tasks_processed:
                print(f"All tasks for project {project_page_id} processed. Synthesizing report...")
                report_content = synthesize_research_findings_llm(completed_task_findings, original_query, openai_api_key) if completed_task_findings else "No findings from tasks."

                note_utils.NOTION_NOTES_DATABASE_ID = project_db_id
                project_current_content = project.get("content","")
                updated_project_content = project_current_content.replace("Status: Pending", "Status: Completed")
                updated_project_content += f"\n\n--- Synthesized Report ---\n{report_content}"

                update_response = note_utils.update_notion_note(page_id=project_page_id, content=updated_project_content, linked_task_id="COMPLETED_PROJECT") # Expects dict
                if update_response["status"] == "success": successful_synthesis_updates +=1
                else: print(f"Failed to update project {project_page_id}. Details: {update_response.get('message')}")
            else: print(f"Project {project_page_id} has unprocessed tasks.")
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error during synthesis check: {str(e)}", "code": "SYNTHESIS_CHECK_ERROR"}
    finally:
        if original_notes_db_id is not None: note_utils.NOTION_NOTES_DATABASE_ID = original_notes_db_id

    return {"status": "success", "data": {"message": f"Synthesis check finished. Attempted: {synthesis_attempts}, Succeeded: {successful_synthesis_updates}",
                                          "attempted_synthesis": synthesis_attempts, "successful_synthesis_updates": successful_synthesis_updates}}

[end of atomic-docker/project/functions/atom-agent/research_agent.py]
