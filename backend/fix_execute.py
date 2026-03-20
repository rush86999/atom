#!/usr/bin/env python3
"""Fix SQLAlchemy 2.0 text() wrapper in test files."""

import re

def fix_sqlalchemy_text_calls(content: str) -> str:
    """Fix db.execute() calls to use text() wrapper for SQLAlchemy 2.0+."""

    # Step 1: Add text to imports
    content = content.replace(
        'from sqlalchemy import create_engine',
        'from sqlalchemy import create_engine, text'
    )

    # Step 2: Find all execute("""...""") patterns and wrap with text()
    # We need to handle both simple and parameterized calls

    # Pattern for simple calls: db.execute("""SQL""")
    # Pattern for parameterized: db.execute("""SQL""", params)

    lines = content.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]

        # Check for execute(""" pattern
        if re.search(r'\w+\.execute\("""', line):
            # Add text( wrapper
            line = re.sub(r'(\w+\.execute)\("""', r'\1(text("""', line)
            lines[i] = line

            # Find the closing
            j = i + 1
            while j < len(lines):
                current_line = lines[j]

                # Check for parameterized closing: """, {params})
                # For parameterized calls, we don't add extra ) after """
                # The structure is: execute(text("""SQL"""), params)
                # So we keep: """), and add ) after params
                # We need to find the line with the closing ) for params
                if '{"' in current_line and '""",' in current_line:
                    # Just replace """, with """),  (no extra paren)
                    current_line = current_line.replace('""",', '"""),')
                    lines[j] = current_line
                    # Now we need to add the extra ) after the params dict
                    # Find the closing ) for the dict
                    if '})' in current_line:
                        # Replace }) with })),
                        current_line = current_line.replace('})', '}))')
                        lines[j] = current_line
                    print(f"Line {j+1}: Fixed parameterized closing")
                    break

                # Also check if next line starts with { (multiline parameterized call)
                if j + 1 < len(lines) and '""",' in current_line and lines[j + 1].strip().startswith('{'):
                    # Just replace """, with """),  (no extra paren yet)
                    current_line = current_line.replace('""",', '"""),')
                    lines[j] = current_line
                    # Find the line with }) to add extra paren
                    k = j + 1
                    while k < len(lines):
                        if '})' in lines[k]:
                            lines[k] = lines[k].replace('})', '}))')
                            print(f"Line {k+1}: Added extra closing paren")
                            break
                        k += 1
                    print(f"Line {j+1}: Fixed multiline parameterized closing")
                    break

                # Check for simple closing: """)
                elif '""")' in current_line and current_line.strip().endswith('""")'):
                    # Replace with """))
                    current_line = current_line.replace('""")', '"""))')
                    lines[j] = current_line
                    print(f"Line {j+1}: Fixed simple closing")
                    break

                j += 1

            i = j  # Skip to after this block
        else:
            i += 1

    return '\n'.join(lines)


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        filepath = sys.argv[1]
    else:
        filepath = 'tests/api/test_admin_routes.py'

    print(f"Fixing {filepath}...")

    with open(filepath, 'r') as f:
        content = f.read()

    fixed_content = fix_sqlalchemy_text_calls(content)

    with open(filepath, 'w') as f:
        f.write(fixed_content)

    print(f"✓ Fixed {filepath}")
