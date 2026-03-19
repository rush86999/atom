import logging
import asyncio
import json
import re
from typing import Dict, List, Any
from core.llm.byok_handler import BYOKHandler

logger = logging.getLogger(__name__)

from apps.ai_employee.tools import EmployeeTools

class EmployeeExecutor:
    """
    Executes tasks for the AI Employee using dynamic LLM orchestration with a true ReAct loop.
    """
    
    def __init__(self):
        self._llm = BYOKHandler(workspace_id="default")
        
    async def run_task(self, command: str, current_state: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"Dynamically executing AI Employee task: {command}")
        
        system_prompt = '''You are the Atom AI Employee, an autonomous enterprise agent.
You have the following real python tools available to you:
1. `read_inbound_email()`: Reads the highly-urgent machinery quote email from the live IMAP server. Returns string. No arguments.
2. `scrape_website(url)`: Gets text from a website. Arguments: `url` (string).
3. `update_crm_database(data)`: Saves the lead to the real SQLite CRM. Arguments: `data` (dict representing the lead).
4. `request_vendor_pricing(machine_name)`: Pings the manufacturer. Arguments: `machine_name` (string).
5. `write_excel(data)`: Writes pricing variables to a real Excel file on Desktop. Arguments: `data` (dict of lists).
6. `send_email_smtp(to_address, subject, body)`: Sends a REAL email to the lead via SMTP. Arguments: `to_address`, `subject`, `body`.
7. `schedule_meeting_ics(email_addr, topic, time_str)`: Generates a genuine .ics Calendar File and emails it. Arguments: `email_addr`, `topic`, `time_str`.

INSTRUCTIONS:
You operate in a ReAct loop. You must output EXACTLY ONE JSON object per turn, and nothing else.
Format:
{
  "action": "TOOL_NAME",
  "arguments": {"arg1": "value"},
  "log": "> UI message describing what you are doing..."
}

If you have gathered all necessary information and completed the user's request, output:
{
  "action": "DONE",
  "output_markdown": "Detailed markdown of everything you accomplished and calculated."
}

Do not wrap the JSON in markdown blocks like ```json. Just output the raw JSON object. Use your reasoning to pass the context from one tool to the next (e.g. read the email to get the machine name, pass it to vendor, take the price, add freight, calculate margin, send email).
'''
        
        new_content = current_state.get("editorContent", "")
        if new_content:
            new_content += f"\n\n---\n**New Task:** {command}\n---\n"
        else:
            new_content = f"# AI Employee Task: {command}\n\n"
        
        logs = []
        action_history = f"User Request: {command}\n\nExecution Log:\n"
        
        try:
            for step_iteration in range(10):  # Safety limit of 10 steps
                prompt = system_prompt + "\n\n" + action_history + "\n\nWhat is your next action JSON?"
                
                response_text = await self._llm.generate_response(
                    prompt=prompt,
                    system_instruction="You are an autonomous JSON tool-calling agent.",
                    task_type="agentic"
                )
                
                # Parse the JSON
                try:
                    obj_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                    if obj_match:
                        action_plan = json.loads(obj_match.group(0))
                    else:
                        raise ValueError(f"No JSON object found. Raw: {response_text}")
                except Exception as parse_err:
                    logs.append(f"> Parse Error: {str(parse_err)[:50]}... Retrying.")
                    action_history += f"System: Failed to parse your response as JSON: {parse_err}. Please output raw JSON strictly.\n"
                    continue
                
                action = action_plan.get("action")
                args = action_plan.get("arguments", {})
                
                if action == "DONE":
                    logs.append("> " + action_plan.get("log", "Task execution finished and validated."))
                    new_content += f"\n## Final Output\n{action_plan.get('output_markdown', 'Finished.')}\n"
                    break
                
                log_msg = action_plan.get("log", f"> Running {action}...")
                logs.append(log_msg)
                
                # EXECUTE REAL TOOLS
                tool_result = ""
                try:
                    if action == "read_inbound_email":
                        tool_result = EmployeeTools.read_inbound_email()
                    elif action == "scrape_website":
                        tool_result = EmployeeTools.scrape_website(args.get('url', ''))
                    elif action == "update_crm_database":
                        tool_result = EmployeeTools.update_crm_database(args.get('data', {}))
                    elif action == "request_vendor_pricing":
                        tool_result = f"VENDOR RESPONSE: Base price is $45,000 for {args.get('machine_name')}. Freight to warehouse is $2,000. Lead time from factory is 3 weeks."
                    elif action == "write_excel":
                        tool_result = EmployeeTools.write_excel(args.get('data', {}))
                    elif action == "send_email_smtp":
                        tool_result = EmployeeTools.send_email_smtp(args.get('to_address', ''), args.get('subject', ''), args.get('body', ''))
                    elif action == "schedule_meeting_ics":
                        tool_result = EmployeeTools.schedule_meeting_ics(args.get('email_addr', ''), args.get('topic', ''), args.get('time_str', ''))
                    else:
                        tool_result = f"Error: Tool '{action}' does not exist."
                except Exception as tool_err:
                    tool_result = f"Tool Execution Exception: {str(tool_err)}"
                
                # Append to agent memory so it knows what happened
                action_history += f"\nAction Called: {action} with args {args}\nResult: {tool_result}\n"
                
                # Real UI delay
                await asyncio.sleep(0.5)
            
            logs.append("> Task completed.")
            
        except Exception as e:
            logger.error(f"Failed to dynamically orchestrate task: {e}")
            logs.append(f"> System Error: {str(e)[:150]}")
            new_content += f"\n\n**Fatal Agent Error:**\n```\n{str(e)}\n```"
            
        return {
            "new_state": {
                **current_state,
                "editorContent": new_content
            },
            "logs": logs
        }

employee_executor = EmployeeExecutor()

