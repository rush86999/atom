import sys
import os
from sqlalchemy import text

# Add backend to path
sys.path.append(os.getcwd())

from core.database import SessionLocal

def apply_gin_indices():
    session = SessionLocal()
    try:
        print("Applying GIN indexes to GraphRAG and Episodic Memory tables...")
        
        indices = [
            ("ix_graph_nodes_properties_gin", "graph_nodes", "properties"),
            ("ix_graph_edges_properties_gin", "graph_edges", "properties"),
            ("ix_graph_communities_keywords_gin", "graph_communities", "keywords"),
            ("ix_agent_episodes_metadata_gin", "agent_episodes", "metadata_json"),
            ("ix_agent_episodes_topics_gin", "agent_episodes", "topics"),
            ("ix_agent_episodes_entities_gin", "agent_episodes", "entities")
        ]
        
        for name, table, col in indices:
            print(f"Creating index {name} on {table}({col})...")
            # Upgrade columns to JSONB first just in case
            session.execute(text(f"ALTER TABLE {table} ALTER COLUMN {col} TYPE JSONB USING {col}::jsonb;"))
            session.execute(text(f"CREATE INDEX IF NOT EXISTS {name} ON {table} USING GIN ({col});"))
            
        session.commit()
        print("✓ All GIN indexes applied successfully.")
        
    except Exception as e:
        session.rollback()
        print(f"✗ Failed to apply GIN indexes: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    apply_gin_indices()
