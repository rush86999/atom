import sqlite3
import sys

try:
    conn = sqlite3.connect('dev.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM analytics_workflow_logs ORDER BY created_at DESC LIMIT 5")
    rows = cursor.fetchall()
    
    if not rows:
        print("No rows found in analytics_workflow_logs.")
    else:
        print(f"Found {len(rows)} rows:")
        for row in rows:
            print(row)
            
    conn.close()
except Exception as e:
    print(f"Error: {e}")
