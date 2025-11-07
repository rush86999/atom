"""
Quick syntax fix for phase2_day2_integration.py
"""

import re

# Read the file
with open('phase2_day2_integration.py', 'r') as f:
    content = f.read()

# Fix the syntax error on line 390
content = re.sub(
    r'sum\(1 for r in framework_result\.values\(\) if r\.success if hasattr\(r, [\'"]\w+[\'"\]\) else True\)',
    r'sum(1 for r in framework_result.values() if r.success if hasattr(r, "success") else True)',
    content
)

# Write the fixed file
with open('phase2_day2_integration.py', 'w') as f:
    f.write(content)

print("✅ Syntax error fixed in phase2_day2_integration.py")