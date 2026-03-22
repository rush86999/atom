import logging
import asyncio
import json
import re
import datetime
from typing import Dict, List, Any
from core.llm.byok_handler import BYOKHandler

logger = logging.getLogger(__name__)

from apps.ai_employee.tools import EmployeeTools

class EmployeeExecutor:
    """
    Executes tasks for the AI Employee using dynamic LLM orchestration.
    Maintains a persistent state including editor content, sub-tasks, and deliverables.
    """
    
    def __init__(self):
        # We use a default workspace_id for the BYOK handler initialization
        self._llm = BYOKHandler(workspace_id="ai_employee_shared")
        
    async def run_task(self, command: str, current_state: Dict[str, Any], user_id: str, db: Any) -> Dict[str, Any]:
        """
        Runs the ReAct loop until task completion.
        """
        # FORCED FILE LOGGING (ABSOLUTE PATH)
        DEBUG_FILE = r"c:\Users\Mannan Bajaj\atom\backend\debug_log.txt"
        with open(DEBUG_FILE, "a", encoding='utf-8') as f:
            f.write(f"\n[{datetime.datetime.now()}] EXECUTOR CALLED: {command[:50]}\n")
            
        logs = []
        editor_content = current_state.get("editorContent", "")
        plan = current_state.get("plan", [])
        deliverables = current_state.get("deliverables", [])
        
        # Start the task log in the editor
        new_content = editor_content + f"\n\n---\n**New Task:** {command}\n---\n"
        
        for i in range(15):  # High limit for complex end-to-end machinery workflows
            prompt = f"""
You are the Atom AI Employee. Your goal is to complete the user's request end-to-end.
User Goal: {command}

Current Canvas State (Markdown):
{new_content}

Current Plan: {json.dumps(plan)}
Current Deliverables: {json.dumps(deliverables)}

Available Tools:
1. read_inbound_email(): Reads emails. If no real emails found, it returns MOCK DATA for the demo. ALWAYS proceed with the data returned.
2. scrape_website(url): Gets text from a URL.
3. update_crm_database(data): Adds lead info to SQLite CRM.
4. write_excel(data, filename): Generates/Appends to a .xlsx file on Desktop. Use this for ALL math, quotes, and summaries.
5. send_email_smtp(to_address, subject, body): Sends real email.
6. schedule_meeting_ics(email_addr, topic, time_str): Sends meeting invite + ICS.
7. append_to_google_sheet(spreadsheet_id, data, range_name): (DISABLED - Use write_excel instead).

IMPORTANT: 
- If you need to do math, do it internally and then use `write_excel` to save the results.
- Keep the user updated via the 'log' field.
- When you have completed ALL parts of the multi-step request, use action="DONE".

Respond in EXACT JSON:
{{
    "thought": "reasoning",
    "plan_update": ["Step 1", "Step 2"],
    "action": "tool_name" or "DONE",
    "action_input": {{ "arg": "val" }} or null,
    "log": "Terminal message",
    "deliverable": {{ "name": "filename", "type": "excel|email|meeting" }} or null
}}
"""
            try:
                response_text = await self._llm.generate_response(
                    prompt=prompt,
                    system_instruction="You are an autonomous JSON agent. Output ONLY raw JSON.",
                    task_type="agentic"
                )
                
                # Robust JSON parsing
                obj_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if not obj_match:
                    raise ValueError(f"No JSON in response: {response_text}")
                
                action_plan = json.loads(obj_match.group(0))
                
                # Update Plan & Deliverables
                if action_plan.get("plan_update"):
                    plan = action_plan["plan_update"]
                if action_plan.get("deliverable"):
                    deliverables.append(action_plan["deliverable"])
                
                action = action_plan.get("action")
                args = action_plan.get("action_input", {})
                
                if action == "DONE":
                    logs.append("> Task complete.")
                    break
                
                logs.append(action_plan.get("log", f"> Running {action}..."))
                
                with open("backend/debug_log.txt", "a") as f:
                    f.write(f"[{datetime.datetime.now()}] Action: {action}\n")
                
                # Map actions to tools
                tool_result = ""
                if action == "read_inbound_email":
                    tool_result = EmployeeTools.read_inbound_email()
                elif action == "scrape_website":
                    tool_result = EmployeeTools.scrape_website(args.get("url", ""))
                elif action == "update_crm_database":
                    tool_result = EmployeeTools.update_crm_database(args.get("data", {}))
                elif action == "write_excel":
                    # For demo purposes, we handle the case where the LLM passes data directly
                    tool_result = EmployeeTools.write_excel(args.get("data", {}), args.get("filename", "Quote.xlsx"))
                elif action == "send_email_smtp":
                    tool_result = EmployeeTools.send_email_smtp(args.get("to_address"), args.get("subject"), args.get("body"))
                elif action == "schedule_meeting_ics":
                    tool_result = EmployeeTools.schedule_meeting_ics(args.get("email_addr"), args.get("topic"), args.get("time_str"))
                elif action == "append_to_google_sheet":
                    tool_result = EmployeeTools.append_to_google_sheet(
                        user_id=user_id,
                        db=db,
                        spreadsheet_id=args.get("spreadsheet_id"),
                        data=args.get("data", []),
                        range_name=args.get("range_name", "Sheet1!A1")
                    )
                else:
                    tool_result = f"Error: Unknown tool '{action}'"
                
                new_content += f"\n### '{action}' Executed\n{tool_result}\n"
                
                with open(DEBUG_FILE, "a", encoding='utf-8') as f:
                    f.write(f"[{datetime.datetime.now()}] Tool Result: {str(tool_result)[:100]}\n")
            except Exception as e:
                with open(DEBUG_FILE, "a", encoding='utf-8') as f:
                    f.write(f"[{datetime.datetime.now()}] EXCEPTION: {str(e)}\n")
                logs.append(f"!! Error: {str(e)}")
                break
                
        # Automatic Logging to Excel
        with open(DEBUG_FILE, "a") as f:
            f.write(f"[{datetime.datetime.now()}] ATTEMPTING AUTO-LOG\n")
        try:
            log_data = [{
                "Timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Task": command,
                "Result": "Success" if "Error" not in new_content else "Completed with Issues",
                "Log Summary": logs[-1] if logs else "No logs"
            }]
            log_res = EmployeeTools.write_excel(log_data, "AI_Employee_Logs.xlsx")
            with open(DEBUG_FILE, "a") as f:
                f.write(f"[{datetime.datetime.now()}] AUTO-LOG RESULT: {log_res}\n")
        except Exception as log_err:
            with open(DEBUG_FILE, "a") as f:
                f.write(f"[{datetime.datetime.now()}] AUTO-LOG FAILED: {str(log_err)}\n")
            logger.error(f"Failed to auto-log task to Excel: {log_err}")

        return {
            "new_state": {
                "editorContent": new_content,
                "plan": plan,
                "deliverables": deliverables,
                "views": current_state.get("views", [])
            },
            "logs": logs
        }

    def reset_state(self) -> Dict[str, Any]:
        """Clears the workspace state."""
        return {
            "editorContent": "# Welcome to your AI Employee Workspace\n\nHow can I help you today?",
            "plan": [],
            "deliverables": [],
            "views": []
        }

employee_executor = EmployeeExecutor()
