import os

# Read the existing file
with open('backend/ai/automation_engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Check if method already exists
if 'execute_workflow_definition' in content:
    print("Method already exists!")
else:
    # Read the new method
    with open('backend/workflow_execution_method.py', 'r', encoding='utf-8') as f:
        method_content = f.read()
    
    # Find the last line (it's the main example code)
    # We want to add before the example code
    lines = content.split('\n')
    
    # Find where to insert (before __main__ or at end of class)
    insert_index = -1
    for i, line in enumerate(lines):
        if 'if __name__ ==' in line:
            insert_index = i
            break
    
    if insert_index == -1:
        # No main block, append at end
        new_content = content + '\n\n' + method_content.replace('# This method should be added to the AutomationEngine class in automation_engine.py\n# Add this as a method after the execute_workflow method\n\n', '')
    else:
        # Insert before main block
        method_lines = method_content.replace('# This method should be added to the AutomationEngine class in automation_engine.py\n# Add this as a method after the execute_workflow method\n\n', '').split('\n')
        # Add proper indentation (4 spaces for class method)
        indented_method = '\n'.join(['    ' + line if line.strip() else line for line in method_lines])
        
        lines.insert(insert_index - 1, indented_method)
        new_content = '\n'.join(lines)
    
    # Write back
    with open('backend/ai/automation_engine.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("Method added successfully!")
