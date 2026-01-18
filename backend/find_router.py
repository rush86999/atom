
filename = r"c:\Users\Mannan Bajaj\atom\backend\integrations\workflow_automation_routes.py"
with open(filename, "r", encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        if "router =" in line or "router=" in line:
            print(f"{i}: {line.strip()}")
