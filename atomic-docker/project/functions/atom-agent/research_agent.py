import os
import openai
import json
from project.functions import note_utils
import requests # Add requests import

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
    if not note_utils.notion: # Checks if the Notion client in note_utils is initialized
        return {"status": "error", "message": "Notion client not initialized in note_utils. Potentially missing NOTION_API_TOKEN."}

    original_notes_db_id = note_utils.NOTION_NOTES_DATABASE_ID # Store original

    project_page_id = None # Define project_page_id to ensure it's available in all paths
    try:
        task_descriptions = decompose_query_into_tasks_llm(user_query, openai_api_key)
        if not task_descriptions:
            return {"status": "error", "message": "Failed to decompose query into tasks (no tasks returned)."}

        # Create Project Page
        note_utils.NOTION_NOTES_DATABASE_ID = project_db_id
        project_page_title = f"Research Project: {user_query[:100]}"
        project_content = f"Original Query: {user_query}\\nUser ID: {user_id}\\nStatus: Pending"
        project_page_id = note_utils.create_notion_note(title=project_page_title, content=project_content, source="research_agent")

        if not project_page_id:
            return {"status": "error", "message": f"Failed to create project page in Notion DB {project_db_id}."}

        created_task_page_ids = []
        # Create Task Pages
        note_utils.NOTION_NOTES_DATABASE_ID = task_db_id
        for desc in task_descriptions:
            task_page_title = f"Task: {desc[:100]}"
            # Using linked_event_id to store project_page_id.
            task_page_id = note_utils.create_notion_note(title=task_page_title, content=desc, source="research_agent_task", linked_event_id=project_page_id)
            if task_page_id:
                created_task_page_ids.append(task_page_id)
            else:
                print(f"Warning: Failed to create task page for description '{desc}' in Notion DB {task_db_id}.")

        return {"status": "success", "project_page_id": project_page_id, "task_page_ids": created_task_page_ids}
    finally:
        # Ensure original_notes_db_id is restored even if errors occur after it's changed
        note_utils.NOTION_NOTES_DATABASE_ID = original_notes_db_id

import requests # Add requests import

def python_search_web(query: str, api_key: str) -> list[dict]:
    search_api_url = "https://api.exampleSearchEngine.com/search" # Placeholder URL
    results = []
    try:
        response = requests.get(search_api_url, params={"q": query, "key": api_key})
        response.raise_for_status() # Raises an HTTPError for bad responses (4XX or 5XX)
        data = response.json()
        if data and isinstance(data.get("items"), list):
            for item in data["items"]:
                results.append({
                    "title": item.get("title", "No title"),
                    "link": item.get("link", "#"),
                    "snippet": item.get("snippet", "No snippet available.")
                })
        else:
            print(f"Web search API response format unexpected: {data}")
    except requests.exceptions.RequestException as e:
        print(f"Error during web search API call: {e}")
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from web search API: {e}")
    return results

def execute_research_task(task_page_id: str, search_api_key: str) -> dict:
    if not note_utils.notion:
        return {"status": "error", "message": "Notion client not initialized."}

    original_notes_db_id = note_utils.NOTION_NOTES_DATABASE_ID # Store original
    task_details = None
    try:
        # Assuming task pages are in the main NOTION_NOTES_DATABASE_ID or their specific DB ID needs to be set.
        # For this function, we assume the task_page_id is globally unique and get_notion_note can fetch it.
        # If tasks are in a specific DB, note_utils.NOTION_NOTES_DATABASE_ID would need to be set to task_db_id here.
        task_details = note_utils.get_notion_note(page_id=task_page_id)
        if not task_details:
            return {"status": "error", "message": f"Could not retrieve task details for page ID: {task_page_id}"}

        search_query = task_details.get("content", "").strip() # Assume query is in the main content
        if not search_query:
            # Try title if content is empty, removing common prefixes
            search_query = task_details.get("title", "").replace("Task: ", "").strip()
            if not search_query:
                return {"status": "error", "message": f"Search query not found in task content or title for page ID: {task_page_id}"}

        print(f"Executing task {task_page_id}: Searching for '{search_query}'")
        search_results = python_search_web(query=search_query, api_key=search_api_key)

        results_string = "\n\n--- Search Results ---\n"
        if search_results:
            for res in search_results:
                results_string += f"Title: {res['title']}\nLink: {res['link']}\nSnippet: {res['snippet']}\n---\n"
        else:
            results_string += "No results found or search failed.\n"

        # Update the task page with results and new status
        # The task page's DB ID must be active in note_utils.NOTION_NOTES_DATABASE_ID for update_notion_note
        # This is a simplification; a robust solution would pass the task's DB ID or have note_utils handle it.
        updated_content = task_details.get("content", "") + results_string
        success = note_utils.update_notion_note(page_id=task_page_id, content=updated_content, linked_task_id="COMPLETED") # Using linked_task_id for status

        if success:
            return {"status": "success", "message": f"Task {task_page_id} completed. Results saved to Notion."}
        else:
            return {"status": "error", "message": f"Failed to update task {task_page_id} in Notion after search."}

    except Exception as e:
        print(f"Error executing research task {task_page_id}: {e}")
        return {"status": "error", "message": f"Error executing research task {task_page_id}: {str(e)}"}
    finally:
        if original_notes_db_id: # Ensure it was captured
             note_utils.NOTION_NOTES_DATABASE_ID = original_notes_db_id

def monitor_and_execute_tasks(task_db_id: str, search_api_key: str, project_db_id: str, openai_api_key: str) -> dict:
    if not note_utils.notion:
        return {"status": "error", "message": "Notion client not initialized."}

    print(f"Checking for pending tasks in database: {task_db_id}")
    original_notes_db_id = note_utils.NOTION_NOTES_DATABASE_ID
    processed_tasks = 0
    failed_tasks = 0
    try:
        note_utils.NOTION_NOTES_DATABASE_ID = task_db_id
        all_tasks_in_db = note_utils.search_notion_notes(query="", source="research_agent_task") # Gets all tasks by source
        pending_tasks = []
        for task in all_tasks_in_db:
            if task.get("source") == "research_agent_task" and task.get("linked_task_id") != "COMPLETED":
                pending_tasks.append(task)

        if not pending_tasks:
            print("No pending research tasks found.")
            # Still proceed to check for synthesis, as tasks might have been completed in a previous run
        else:
            print(f"Found {len(pending_tasks)} pending tasks to process.")
            for task_summary in pending_tasks:
                task_page_id = task_summary["id"]
                # Ensure correct DB context for execute_research_task if it manipulates note_utils.NOTION_NOTES_DATABASE_ID
                # execute_research_task already handles its own DB context setting and restoration for the task page.
                result = execute_research_task(task_page_id=task_page_id, search_api_key=search_api_key)
                if result.get("status") == "success":
                    processed_tasks += 1
                else:
                    failed_tasks += 1
                    print(f"Failed to process task {task_page_id}: {result.get('message')}")

    except Exception as e:
        print(f"Error during task monitoring and execution: {e}")
        # Do not return yet, allow synthesis check to run
    finally:
        note_utils.NOTION_NOTES_DATABASE_ID = original_notes_db_id

    # After task execution cycle, check for project completion and synthesis
    print("Proceeding to check for project completion and synthesis.")
    # Ensure that openai_api_key is available here. It's now a parameter.
    check_projects_for_completion_and_synthesize(
        project_db_id=project_db_id,
        task_db_id=task_db_id, # Pass task_db_id again as it's needed by the synthesis function
        openai_api_key=openai_api_key
    )

    return {"status": "success", "message": f"Task execution and synthesis check cycle completed. Processed tasks: {processed_tasks}, Failed tasks: {failed_tasks}.\", \"processed_tasks\": processed_tasks, \"failed_tasks\": failed_tasks}


def synthesize_research_findings_llm(findings: list[str], original_query: str, openai_api_key: str) -> str:
    try:
        client = openai.OpenAI(api_key=openai_api_key)
        # Concatenate findings into a single string, ensure it's not excessively long for the context window
        # Basic concatenation, could be smarter (e.g., summarize each first if too many)
        MAX_FINDINGS_LENGTH = 15000 # Rough character limit for context, adjust as needed
        concatenated_findings = "\n\n---\n\n".join(findings)
        if len(concatenated_findings) > MAX_FINDINGS_LENGTH:
            # Simple truncation, ideally summarize if too long
            concatenated_findings = concatenated_findings[:MAX_FINDINGS_LENGTH] + "... (truncated)"

        system_prompt = ("You are a research analyst. Based on the following collected information (from multiple search tasks) \n"
                         "and the original research query, synthesize a comprehensive report. \n"
                         "The report should directly address the original query, be well-organized, coherent, and based SOLELY on the provided information. \n"
                         "Do not add external knowledge. If the information is insufficient, state that. \n"
                         "Original Research Query: {}".format(original_query))

        user_message = f"Collected Information:\n{concatenated_findings}"

        response = client.chat.completions.create(
            model="gpt-4-turbo-preview", # Or gpt-3.5-turbo if preferred, but gpt-4 might be better for synthesis
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.5 # Allow some creativity for synthesis but not too much
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

    print(f"Checking for completable projects in database: {project_db_id}")
    original_notes_db_id = note_utils.NOTION_NOTES_DATABASE_ID
    updated_projects_count = 0

    try:
        # 1. Find 'Pending' projects
        note_utils.NOTION_NOTES_DATABASE_ID = project_db_id
        # Simplification: Search for projects by source, then filter by status locally.
        # Assumes project status is stored in 'content' or a specific field we can check.
        # For now, let's assume 'Status: Pending' is in the content.
        all_projects_in_db = note_utils.search_notion_notes(query="Status: Pending", source="research_agent")
        pending_projects = [p for p in all_projects_in_db if "Status: Pending" in p.get("content","")]

        if not pending_projects:
            print("No pending research projects found requiring synthesis.")
            return

        print(f"Found {len(pending_projects)} pending projects. Checking task completion...")

        for project in pending_projects:
            project_page_id = project["id"]
            original_query = project.get("content","").split("\n")[0].replace("Original Query: ","").strip()
            print(f"Checking project: {project_page_id} - {project.get('title')}")

            # 2. For each pending project, find its tasks using linked_event_id
            note_utils.NOTION_NOTES_DATABASE_ID = task_db_id
            # This search is a simplification. It gets ALL tasks and filters locally.
            # A more efficient way would be a direct Notion API query with a filter if note_utils supported it.
            all_tasks_in_task_db = note_utils.search_notion_notes(query="", source="research_agent_task")
            project_tasks = [t for t in all_tasks_in_task_db if t.get("linked_event_id") == project_page_id]

            if not project_tasks:
                print(f"No tasks found for project {project_page_id}. Skipping synthesis.")
                continue

            # 3. Check if all tasks for this project are 'COMPLETED'
            all_tasks_completed = True
            completed_task_findings = []
            for task in project_tasks:
                # Status is in 'linked_task_id' field as per execute_research_task
                if task.get("linked_task_id") == "COMPLETED":
                    completed_task_findings.append(task.get("content", ""))
                else:
                    all_tasks_completed = False
                    break # Not all tasks are done for this project

            if all_tasks_completed:
                print(f"All tasks for project {project_page_id} are completed. Synthesizing report...")
                if not completed_task_findings:
                    print(f"No findings from tasks for project {project_page_id}. Marking as completed with note.")
                    synthesized_report = "No specific findings were extracted from research tasks."
                else:
                    synthesized_report = synthesize_research_findings_llm(completed_task_findings, original_query, openai_api_key)

                # 4. Update project page with report and 'Completed' status
                note_utils.NOTION_NOTES_DATABASE_ID = project_db_id
                project_current_content = project.get("content","")
                # Replace 'Status: Pending' with 'Status: Completed' and append report
                updated_project_content = project_current_content.replace("Status: Pending", "Status: Completed")
                updated_project_content += f"\n\n--- Synthesized Report ---\n{synthesized_report}"

                # Using linked_task_id for project status as well, for consistency with tasks.
                # Or, if a 'Status' property exists and note_utils.update_notion_note can update it, use that.
                update_success = note_utils.update_notion_note(page_id=project_page_id, content=updated_project_content, linked_task_id="COMPLETED_PROJECT")

                if update_success:
                    print(f"Project {project_page_id} successfully updated with synthesized report and status 'Completed'.")
                    updated_projects_count += 1
                else:
                    print(f"Failed to update project {project_page_id} with report.")
            else:
                print(f"Project {project_page_id} still has pending tasks. Not synthesizing yet.")

    except Exception as e:
        print(f"Error during project completion check and synthesis: {e}")
    finally:
        note_utils.NOTION_NOTES_DATABASE_ID = original_notes_db_id

    print(f"Project synthesis check finished. Updated projects: {updated_projects_count}")

# Modify monitor_and_execute_tasks to call check_projects_for_completion_and_synthesize at the end
# This requires finding the original definition of monitor_and_execute_tasks and adding a call.
# For this subtask, we'll assume this is done by providing the full modified function if needed,
# or just the new function and a note to integrate it.
# Given the subtask system, it's better to append the new function and then in a separate step (or thought) explain how to integrate.
# For now, just add the new function. Integration will be handled in the next thought/subtask if needed.
