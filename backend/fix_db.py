
from core.database import engine
from sqlalchemy import text

def reset_analytics_table():
    print("Dropping analytics_workflow_logs table...")
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS analytics_workflow_logs"))
        conn.commit()
    print("Table dropped.")

if __name__ == "__main__":
    reset_analytics_table()
