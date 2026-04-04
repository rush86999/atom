import os
import sys
import logging

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from apps.ai_employee.tools import EmployeeTools

logging.basicConfig(level=logging.INFO)

test_data = [{"Timestamp": "2026-03-20 16:30:00", "Task": "Test Task", "Result": "Success", "Log Summary": "Testing write_excel"}]

print("Attempting to write test Excel file...")
result = EmployeeTools.write_excel(test_data, "AI_Employee_Test.xlsx")
print(f"Result: {result}")

desktop_path = os.path.join(os.path.expanduser('~'), 'OneDrive', 'Desktop', 'AI_Employee_Test.xlsx')
if os.path.exists(desktop_path):
    print(f"Verified! File exists at: {desktop_path}")
else:
    print(f"Failure! File NOT found at expected path: {desktop_path}")
