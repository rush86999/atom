```markdown
# LanceDB Long-Term Memory (LTM) Schemas

This document defines the schemas for tables to be created in LanceDB for the agent's long-term memory.

## 1. `user_profiles` Table

Stores user-specific information, preferences, and summaries of past interactions.

-   **`user_id`**: `string` (Primary Key) - Unique identifier for the user.
-   **`preferences`**: `object` - JSON object to store user preferences (e.g., timezone, communication style, notification settings).
    -   Example: `{"timezone": "America/New_York", "preferred_contact_method": "email"}`
-   **`interaction_summary_embeddings`**: `vector` - Embedding of a concise, holistic summary representing all past interactions with the user. Used for high-level similarity matching of user profiles or finding users with broadly similar interaction patterns.
-   **`interaction_summaries`**: `list<string>` - A curated list of key textual summaries from past interactions or conversations. This is distinct from the comprehensive log of interaction summaries stored in the `knowledge_base` table.
-   **`created_at`**: `timestamp` - Timestamp of when the user profile was created.
-   **`updated_at`**: `timestamp` - Timestamp of the last update to the user profile.

    *Note on Interaction History:* Individual user interaction summaries and their embeddings are stored in the `knowledge_base` table, identifiable by `source: 'user_interaction_<USER_ID>'` and/or `metadata.userId: '<USER_ID>'`. This approach provides a scalable way to record and query the history of interactions. The `user_profiles` table focuses on holistic summaries and curated information related to the user.

## 2. `knowledge_base` Table

Stores general knowledge, facts, concepts, learned information, and individual user interaction summaries.

-   **`fact_id`**: `string` (Primary Key) - Unique identifier for the knowledge fact or interaction record.
-   **`text_content`**: `string` - The textual representation of the knowledge (e.g., "The capital of France is Paris.") or the summary of a user interaction.
-   **`text_content_embedding`**: `vector` - Embedding of `text_content` for similarity search.
-   **`source`**: `string` - Origin of the information (e.g., `"user_interaction_<USER_ID>"`, `"research_agent_Y"`, `"manual_entry"`). This field is crucial for distinguishing user interaction logs.
-   **`metadata`**: `object` - JSON object for additional information.
    -   For general facts: `{"tags": ["geography", "capitals"], "confidence": 0.95}`
    -   For user interactions: `{"type": "user_interaction_summary", "userId": "<USER_ID>", "goal": "...", "turnCount": X, "timestamp": "..."}`
-   **`created_at`**: `timestamp` - Timestamp of when the record was added.
-   **`updated_at`**: `timestamp` - Timestamp of the last update to the record.
-   **`feedback_status`**: `string` (nullable) - Status of feedback on this record (e.g., `verified`, `unreviewed`, `flagged_inaccurate`, `flagged_outdated`).
-   **`feedback_notes`**: `string` (nullable) - Optional textual notes related to feedback.

## 3. `research_findings` Table

Stores outcomes from research tasks, typically managed by `research_agent.py`.

-   **`finding_id`**: `string` (Primary Key) - Unique identifier for the research finding.
-   **`query`**: `string` - The original query that initiated the research.
-   **`query_embedding`**: `vector` - Embedding of the `query` for finding similar past research.
-   **`summary`**: `string` - A concise summary of the research findings.
-   **`summary_embedding`**: `vector` - Embedding of the `summary`.
-   **`details_text`**: `string` - Detailed findings, potentially including extracted text, key points.
-   **`source_references`**: `list<string>` - List of URLs or identifiers for the sources used in the research.
-   **`project_page_id`**: `string` (Optional) - Link to Notion page ID if `research_agent.py` uses Notion.
-   **`created_at`**: `timestamp` - Timestamp of when the research finding was stored.
-   **`updated_at`**: `timestamp` - Timestamp of the last update.
-   **`feedback_status`**: `string` (nullable) - Status of feedback on this finding.
-   **`feedback_notes`**: `string` (nullable) - Optional textual notes related to feedback.

## Vector Dimensionality

The dimensionality of the `vector` fields will depend on the chosen embedding model (e.g., Sentence-BERT models often use 384 or 768 dimensions, OpenAI Ada-002 uses 1536). This needs to be consistent across all tables and embedding generation processes.
```
