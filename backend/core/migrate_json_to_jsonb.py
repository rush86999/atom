import os
import re
import logging
from sqlalchemy import text
from core.database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Whitelist for SQL identifiers — prevents injection if this script is ever
# refactored to accept external input.
_IDENT_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def _validate_identifier(name: str) -> str:
    """Raise ValueError if the identifier contains non-alphanumeric characters."""
    if not _IDENT_RE.match(name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    return name


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
            # SECURITY: validate identifiers before interpolation into DDL.
            _validate_identifier(table)
            _validate_identifier(column)
            logger.info(f"Migrating {table}.{column} to JSONB...")
            try:
                # Check if column exists — use bound parameters for the lookup
                check_sql = text(
                    "SELECT data_type FROM information_schema.columns "
                    "WHERE table_name = :t AND column_name = :c"
                ).bindparams(t=table, c=column)
                result = connection.execute(check_sql).fetchone()

                if not result:
                    logger.warning(f"Column {table}.{column} does not exist. Skipping.")
                    continue

                current_type = result[0].lower()
                if current_type == 'jsonb':
                    logger.info(f"Column {table}.{column} is already JSONB.")
                    continue

                # Perform the migration — identifiers validated above
                migrate_sql = text(
                    f"ALTER TABLE {table} ALTER COLUMN {column} "
                    f"TYPE JSONB USING {column}::jsonb;"
                )
                connection.execute(migrate_sql)
                connection.commit()
                logger.info(f"Successfully migrated {table}.{column} to JSONB.")
            except ValueError:
                raise  # Don't swallow identifier validation failures
            except Exception as e:
                logger.error(f"Failed to migrate {table}.{column}: {e}")
                connection.rollback()

if __name__ == "__main__":
    migrate()
