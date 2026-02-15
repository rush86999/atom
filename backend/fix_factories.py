#!/usr/bin/env python3
import re

with open('tests/integration/test_multi_agent_coordination.py', 'r') as f:
    content = f.read()

# Remove db_session.add_all() calls first
content = re.sub(r'\s*db_session\.add_all\([^)]*\)\s*\n', '\n', content)

# Fix AgentFactory calls to add _session parameter if not already present
def fix_factory(match):
    factory_type = match.group(1)
    args = match.group(2)
    if '_session' not in args:
        if args.strip():  # If there are arguments
            return '{}({}, _session=db_session)'.format(factory_type, args)
        else:  # If no arguments
            return '{}(_session=db_session)'.format(factory_type)
    return match.group(0)

# Pattern to match all factory types
pattern = r'(AutonomousAgentFactory|StudentAgentFactory|InternAgentFactory|SupervisedAgentFactory|AgentFactory)\(([^)]*?)\)'
content = re.sub(pattern, fix_factory, content)

with open('tests/integration/test_multi_agent_coordination.py', 'w') as f:
    f.write(content)

print('Fixed all factory calls and removed add_all')
