import os
import glob
import json

files = glob.glob("logs/traces/*.json")
if not files:
    print("No traces found.")
else:
    latest_file = max(files, key=os.path.getctime)
    print(f"Latest Trace File: {latest_file}")
    with open(latest_file, 'r') as f:
        print(json.dumps(json.load(f), indent=2))
