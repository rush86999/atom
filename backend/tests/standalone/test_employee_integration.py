import asyncio
import json
import os
import sys

# Add backend to path
sys.path.append(os.getcwd())

from apps.ai_employee.executor import employee_executor
from apps.ai_employee.tools import EmployeeTools

async def verify_task():
    print("STARTING: AI Employee REAL Integration Test (no mocks)...")
    
    command = "Check my inbox for urgent machinery quote requests. Request vendor pricing for the machine, add $2,000 for freight, and calculate a 30% margin. Put the math in an Excel file. Scrape the client's website (brennan.ca) and add their summary to our CRM database. Finally, email the client the final loaded quote and attach a calendar invite for a meeting tomorrow"
    
    current_state = {
        "editorContent": "# Welcome to your AI Employee Workspace\n\nHow can I help you today?",
        "plan": [],
        "deliverables": [],
        "views": []
    }
    
    # NO MOCKS — run with real tools
    result = await employee_executor.run_task(
        command=command,
        current_state=current_state,
        user_id="test_user",
        db=None
    )
    
    print("\nEXECUTION RESULT:")
    print(f"Deliverables Found: {len(result['new_state']['deliverables'])}")
    
    print("\nFINAL LOGS:")
    for log in result['logs']:
        print(log)
    
    # Check if email was attempted by looking at debug log
    try:
        with open("debug_log.txt", "r") as f:
            content = f.read()
            if "SMTP Transmitted successfully" in content:
                print("\n✅ SUCCESS: Real email was SENT!")
            elif "send_email_smtp" in content:
                print("\n⚠️ Email tool was called but may have had issues.")
            else:
                print("\n❌ FAILURE: Email tool was never reached.")
    except FileNotFoundError:
        print("\n⚠️ Could not read debug log.")

if __name__ == "__main__":
    asyncio.run(verify_task())
