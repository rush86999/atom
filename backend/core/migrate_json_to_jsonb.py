import os
import logging
from sqlalchemy import text
from core.database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    tables_to_migrate = [
        ("graph_nodes", "properties"),
        ("graph_edges", "properties"),
        ("graph_communities", "keywords"),
        ("agent_episodes", "metadata_json"),
        ("episode_access_logs", "metadata_json"),
        ("entity_type_definitions", "json_schema"),
    ]

    with engine.connect() as connection:
        for table, column in tables_to_migrate:
            logger.info(f"Migrating {table}.{column} to JSONB...")
            try:
                # Check if column exists first to avoid crashing
                check_sql = text(f"SELECT data_type FROM information_schema.columns WHERE table_name = '{table}' AND column_name = '{column}';")
                result = connection.execute(check_sql).fetchone()
                
                if not result:
                    logger.warning(f"Column {table}.{column} does not exist. Skipping.")
                    continue
                
                current_type = result[0].lower()
                if current_type == 'jsonb':
                    logger.info(f"Column {table}.{column} is already JSONB.")
                    continue

                # Perform the migration
                # We use ALTER TABLE ... TYPE JSONB USING column::jsonb
                migrate_sql = text(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE JSONB USING {column}::jsonb;")
                connection.execute(migrate_sql)
                connection.commit()
                logger.info(f"Successfully migrated {table}.{column} to JSONB.")
            except Exception as e:
                logger.error(f"Failed to migrate {table}.{column}: {e}")
                connection.rollback()

if __name__ == "__main__":
    migrate()
