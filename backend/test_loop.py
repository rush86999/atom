import asyncio
import json
import os
import sys

sys.path.append(os.getcwd())

from dotenv import load_dotenv
load_dotenv(override=True)

from apps.ai_employee.executor import employee_executor

async def run():
    print("Running executor loop manually to trace Qwen rationale...")
    res = await employee_executor.run_task(
        "Check my inbox for urgent machinery quote requests. Request vendor pricing for the machine, add $2000 for freight, and calculate a 30% margin. Put the math in an Excel file. Scrape the client website (brennan.ca) and add their summary to our CRM database. Finally, email the client the final loaded quote and attach a calendar invite for a meeting tomorrow.",
        {"editorContent": ""}
    )
    print("\n!!! FINAL OUTPUT !!!\n")
    print(json.dumps(res, indent=2))

asyncio.run(run())
