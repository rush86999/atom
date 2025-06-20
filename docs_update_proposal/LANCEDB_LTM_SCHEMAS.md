```markdown
# LanceDB Long-Term Memory (LTM) Schemas

This document defines the schemas for tables to be created in LanceDB for the agent's long-term memory.

## 1. `user_profiles` Table

Stores user-specific information, preferences, and summaries of past interactions.

-   **`user_id`**: `string` (Primary Key) - Unique identifier for the user.
-   **`preferences`**: `object` - JSON object to store user preferences (e.g., timezone, communication style, notification settings).
    -   Example: `{"timezone": "America/New_York", "preferred_contact_method": "email"}`
-   **`interaction_summary_embeddings`**: `vector` - Embedding of a concise summary of all past interactions with the user. Used for high-level similarity matching of user profiles or finding users with similar interaction patterns.
-   **`interaction_history_embeddings`**: `vector` (Stored in a linked table or handled carefully if directly in this record, due to potential for multiple embeddings per user) - Embeddings of individual significant past interactions or conversation summaries.
    *   *Consideration*: This might be better as a separate table `user_interaction_history (user_id, interaction_id, summary_text, summary_embedding, timestamp)` to allow multiple historical entries per user. For now, defining as a single vector placeholder, to be refined during LanceDB integration.
-   **`interaction_summaries`**: `list<string>` - Textual summaries of significant past interactions or conversations.
-   **`created_at`**: `timestamp` - Timestamp of when the user profile was created.
-   **`updated_at`**: `timestamp` - Timestamp of the last update to the user profile.

## 2. `knowledge_base` Table

Stores general knowledge, facts, concepts, and learned information.

-   **`fact_id`**: `string` (Primary Key) - Unique identifier for the knowledge fact.
-   **`text_content`**: `string` - The textual representation of the knowledge (e.g., "The capital of France is Paris.").
-   **`text_content_embedding`**: `vector` - Embedding of `text_content` for similarity search.
-   **`source`**: `string` - Origin of the information (e.g., "user_interaction_X", "research_agent_Y", "manual_entry").
-   **`metadata`**: `object` - JSON object for additional information like tags, categories, confidence score, relationships to other facts.
    -   Example: `{"tags": ["geography", "capitals"], "confidence": 0.95, "related_facts": ["fact_id_france_population"]}`
-   **`created_at`**: `timestamp` - Timestamp of when the fact was added.
-   **`updated_at`**: `timestamp` - Timestamp of the last update to the fact.

## 3. `research_findings` Table

Stores outcomes from research tasks, typically managed by `research_agent.py`.

-   **`finding_id`**: `string` (Primary Key) - Unique identifier for the research finding.
-   **`query`**: `string` - The original query that initiated the research.
-   **`query_embedding`**: `vector` - Embedding of the `query` for finding similar past research.
-   **`summary`**: `string` - A concise summary of the research findings.
-   **`summary_embedding`**: `vector` - Embedding of the `summary`.
-   **`details_text`**: `string` - Detailed findings, potentially including extracted text, key points. (Formerly `details` as object, simplified to text for broader compatibility, raw data can be JSON stringified if needed).
-   **`source_references`**: `list<string>` - List of URLs or identifiers for the sources used in the research.
-   **`project_page_id`**: `string` (Optional) - Link to Notion page ID if `research_agent.py` uses Notion.
-   **`created_at`**: `timestamp` - Timestamp of when the research finding was stored.
-   **`updated_at`**: `timestamp` - Timestamp of the last update.

## Vector Dimensionality

The dimensionality of the `vector` fields will depend on the chosen embedding model (e.g., Sentence-BERT models often use 384 or 768 dimensions, OpenAI Ada-002 uses 1536). This needs to be consistent across all tables and embedding generation processes.
```
