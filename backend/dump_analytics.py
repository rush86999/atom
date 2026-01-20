import sqlite3

try:
    conn = sqlite3.connect('dev.db')
    cursor = conn.cursor()
    cursor.execute("SELECT workflow_id, step_id, duration_ms, status FROM analytics_workflow_logs ORDER BY created_at DESC LIMIT 10")
    rows = cursor.fetchall()
    
    with open('analytics_debug.txt', 'w') as f:
        for row in rows:
            f.write(f"Workflow: {row[0]} | Step: {row[1]} | Dur: {row[2]} | Stat: {row[3]}\n")
            
    conn.close()
    print("Dumped to analytics_debug.txt")
except Exception as e:
    print(f"Error: {e}")
