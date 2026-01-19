
import sys

# Force utf-8 output if possible, or just replace errors
sys.stdout.reconfigure(encoding='utf-8')

try:
    with open("server.log", "rb") as f:
        # Try decode utf-16le (powershell default)
        content = f.read().decode("utf-16-le", errors="replace")
        print(content)
except Exception as e:
    print(f"Error reading log: {e}")
