# Shared Python constants for various function services

import os

# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_LIVE_MEETING_TOPIC = "atom_live_meeting_tasks"

# LanceDB Configuration
LANCEDB_URI = os.environ.get("LANCEDB_URI", "/data/lancedb_store") # Example local path

# Other shared constants can be added here
# For example, default API keys if not passed directly (though direct passing is preferred for handlers)
# DEFAULT_OPENAI_API_KEY = os.environ.get("DEFAULT_OPENAI_API_KEY")
# DEFAULT_NOTION_API_TOKEN = os.environ.get("DEFAULT_NOTION_API_TOKEN")

[end of atomic-docker/project/functions/_utils/constants.py]
