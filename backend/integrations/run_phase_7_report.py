import subprocess
import sys

# Run the final Phase 7 success report
try:
    result = subprocess.run([sys.executable, '/Users/rushiparikh/projects/atom/atom/backend/integrations/final_additional_platforms_phase_7_report.py'], 
                          capture_output=True, text=True, cwd='/Users/rushiparikh/projects/atom/atom/backend/integrations')
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
except Exception as e:
    print(f"Error running report: {e}")