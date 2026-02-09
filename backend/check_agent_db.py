import sys
import os
from sqlalchemy import create_engine, inspect, text

# Add parent directory to path to import core
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import engine, SessionLocal
from core.models import AgentRegistry

def check_db():
    print("Checking database...")
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"Tables found: {tables}")
    
    if "agent_registry" in tables:
        print("agent_registry table exists.")
        with SessionLocal() as db:
            count = db.query(AgentRegistry).count()
            print(f"AgentRegistry count: {count}")
            agents = db.query(AgentRegistry).all()
            for agent in agents:
                print(f" - {agent.name} ({agent.status})")
    else:
        print("ERROR: agent_registry table MISSING!")

    if "agent_jobs" in tables:
        print("agent_jobs table exists.")
    else:
        print("ERROR: agent_jobs table MISSING!")

if __name__ == "__main__":
    check_db()
