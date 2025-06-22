# LTM Embedding and Cross-Language Storage/Retrieval Testing Guide

This guide outlines the steps to test and validate the Long-Term Memory (LTM) functionality, specifically focusing on embedding generation and the ability for Python components to store data that TypeScript components can retrieve, and vice-versa. This ensures that the vector dimension change to 1536 (OpenAI `text-embedding-ada-002`) is correctly implemented and that cross-language LTM access works as expected.

## 1. Prerequisites

Before starting the tests, ensure the following conditions are met:

*   **Valid `OPENAI_API_KEY`:**
    *   The API key must be correctly set as an environment variable for both the Node.js/TypeScript environment (e.g., in a `.env` file loaded by `dotenv` for `memoryManager.ts`) and the Python environment (e.g., in a `.env` file loaded by `python-dotenv` for `research_agent.py`).
*   **Clear LanceDB Directory:**
    *   Delete any existing LanceDB database directories to ensure tables are recreated with the new 1536 vector dimensions. The typical paths are:
        *   `./lance_db/` (relative to `atomic-docker/project/functions/` if `lanceDBManager.ts` is run from there or its CWD is `functions`)
        *   `../../lance_db/` (relative to `atomic-docker/project/functions/atom-agent/` if `research_agent.py` is run from there).
    *   The key is to find where `ltm_agent_data.lance` (or `ltm_agent_data_ts.lance`) is being created by `lanceDBManager.ts` and `research_agent.py` and remove it. Consistent DB path configuration is crucial.
*   **Install Dependencies:**
    *   For TypeScript: Navigate to `atomic-docker/project/functions/` and run `pnpm install` (or `npm install`).
    *   For Python: Ensure your Python environment has access to the packages in `atomic-docker/project/functions/requirements.txt`. Install them using `pip install -r atomic-docker/project/functions/requirements.txt`.

## 2. Test Data Examples

### Python Storage (Research Findings)

1.  **Query:** "Future of Renewable Energy"
    **Summary:** "Renewable energy sources like solar and wind are projected to dominate future energy landscapes, driven by technological advancements and climate change concerns."
    **Details:** "Extensive report detailing solar panel efficiency improvements, wind turbine cost reductions, grid storage solutions, and policy incentives promoting renewable adoption. Discusses challenges like intermittency and material sourcing."
2.  **Query:** "Impact of AI on Healthcare"
    **Summary:** "AI is revolutionizing healthcare through improved diagnostics, personalized medicine, and streamlined administrative processes, though ethical considerations remain."
    **Details:** "Covers AI applications in medical imaging, drug discovery, patient risk stratification, virtual health assistants, and potential biases in AI algorithms. Ethical guidelines and data privacy are key discussion points."

### TypeScript Storage (Conversation Summaries for Knowledge Base)

1.  **User Interaction leading to:** "User expressed strong interest in learning advanced JavaScript programming techniques, specifically async/await and functional programming."
    **User ID:** `user_ts_001`
    **User Goal (optional):** "Improve JavaScript skills"
2.  **User Interaction leading to:** "Agent provided detailed steps on how to brew a perfect cup of V60 coffee, including grind size, water temperature, and pouring method."
    **User ID:** `user_ts_002`
    **User Goal (optional):** "Learn coffee brewing"

## 3. Testing Procedure - Python Stores, TypeScript Retrieves

### 3.1. Store Data using Python (`research_agent.py`)

Modify `research_agent.py` or create a separate test script that uses its functions to store one of the "Research Findings" samples.

```python
# Example: test_python_storage.py (place in atomic-docker/project/functions/atom-agent/ or adjust imports)
import os
import sys
from datetime import datetime, timezone
import uuid

# Adjust path to import research_agent modules
# This assumes you run this script from the 'functions' directory or have configured PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.'))) # For atom-agent
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) # For project.functions

from research_agent import (
    get_lance_db_connection,
    generate_embedding_py,
    store_research_findings_in_ltm, # Or call the components of it directly
    log # Use the log from research_agent
)

# Ensure OPENAI_API_KEY is loaded via .env by research_agent's load_dotenv()

def store_sample_python_finding():
    db = get_lance_db_connection()
    if not db:
        log("Failed to connect to LanceDB from Python test script.", level="ERROR")
        return

    log("Python test script: Storing sample research finding...")

    sample_query = "Future of Renewable Energy"
    sample_summary = "Renewable energy sources like solar and wind are projected to dominate future energy landscapes, driven by technological advancements and climate change concerns."
    sample_details_list = [
        "Extensive report detailing solar panel efficiency improvements.",
        "Wind turbine cost reductions and grid storage solutions discussed.",
        "Policy incentives promoting renewable adoption are key."
    ]
    project_page_id = "notion_project_py_001" # Mock Notion ID

    # Call the existing function if it suits, or replicate parts of its logic
    # store_research_findings_in_ltm expects completed_task_findings as a list of strings
    store_research_findings_in_ltm(db, project_page_id, sample_query, sample_summary, sample_details_list)

    # --- Alternative: Manual data construction and addition (closer to store_research_findings_in_ltm logic) ---
    # finding_id = str(uuid.uuid4())
    # query_embedding = generate_embedding_py(sample_query)
    # summary_embedding = generate_embedding_py(sample_summary)
    # details_text = "\n\n---\n\n".join(sample_details_list)
    # source_references = ["http://example.com/solar_report", "http://example.com/wind_study"] # Example
    # current_time_iso = datetime.now(timezone.utc).isoformat()

    # if query_embedding is None or summary_embedding is None:
    #     log("Failed to generate embeddings for Python test data. Aborting storage.", level="ERROR")
    #     return

    # data_to_store = {
    #     "finding_id": finding_id, "query": sample_query, "query_embedding": query_embedding,
    #     "summary": sample_summary, "summary_embedding": summary_embedding,
    #     "details_text": details_text, "source_references": source_references,
    #     "project_page_id": project_page_id,
    #     "created_at": current_time_iso, "updated_at": current_time_iso
    # }
    # try:
    #     research_table = db.open_table("research_findings")
    #     research_table.add([data_to_store])
    #     log(f"Test finding {finding_id} added by Python script.")
    # except Exception as e:
    #     log(f"Error adding test finding from Python: {e}", level="ERROR")

if __name__ == "__main__":
    # This part of research_agent.py initializes the OpenAI client using its global key
    # Ensure that OPENAI_API_KEY is available in the environment.
    # research_agent.OPENAI_API_KEY_GLOBAL must be set, or adapt to use openai_client_py directly
    if not os.getenv("OPENAI_API_KEY"):
        print("CRITICAL: OPENAI_API_KEY not set in environment. Python test script cannot run effectively.")
    else:
        store_sample_python_finding()
```
*   Run this script (e.g., `python atomic-docker/project/functions/atom-agent/test_python_storage.py`).
*   Verify logs for successful connection, embedding generation (real, not dummy if key is set), and data addition.

### 3.2. Retrieve Data using TypeScript (`memoryManager.ts`)

Create a temporary test script or use an existing entry point for TypeScript execution.

```typescript
// Example: test_ts_retrieval.ts (place in atomic-docker/project/functions/ and compile/run)
// Ensure paths to modules are correct based on your project structure and how you run it.
// You might need to compile this to JS first (e.g. using tsc)
import { initializeDB } from './lanceDBManager'; // Adjust path if needed
import { retrieveRelevantLTM } from './atom-agent/memoryManager'; // Adjust path
import * as lancedb from '@lancedb/lancedb'; // For lancedb.Connection type

async function testRetrieveFromPython() {
  console.log("TypeScript test: Attempting to retrieve data stored by Python...");
  // Ensure DB name matches what Python side would connect to if they are to share the same DB.
  // lanceDBManager.ts uses "ltm_agent_data" by default.
  // research_agent.py uses LANCEDB_URI which might point to "ltm_agent_data.lance"
  const db: lancedb.Connection | null = await initializeDB("ltm_agent_data");

  if (db) {
    const query = "renewable energy future"; // Should be semantically similar to what Python stored
    const results = await retrieveRelevantLTM(query, null, db, { table: "research_findings" });

    console.log(`TypeScript retrieved ${results.length} items for query "${query}":`);
    results.forEach((result, index) => {
      console.log(`Result ${index + 1}:`, {
        id: result.id,
        text_snippet: result.text.substring(0, 200) + "...",
        score: result.score,
        table: result.table,
        metadata: result.metadata
      });
    });
  } else {
    console.error("TypeScript test: Failed to connect to LanceDB.");
  }
}

testRetrieveFromPython().catch(console.error);
```
*   Compile and run this TypeScript script (e.g., `npx ts-node test_ts_retrieval.ts` if you have `ts-node` and paths are set up, or compile first then run with `node`).
*   **Expected Outcome:** The console output should show the "Future of Renewable Energy" finding(s) stored by Python, demonstrating successful cross-language retrieval and semantic search.

## 4. Testing Procedure - TypeScript Stores, Python Retrieves

### 4.1. Store Data using TypeScript (`memoryManager.ts`)

Use a test script to invoke `processSTMToLTM`.

```typescript
// Example: test_ts_storage.ts (place in atomic-docker/project/functions/ and compile/run)
import { initializeDB } from './lanceDBManager'; // Adjust path
import { processSTMToLTM } from './atom-agent/memoryManager'; // Adjust path
import { ConversationState } from './atom-agent/conversationState'; // Adjust path
import * as lancedb from '@lancedb/lancedb';

async function testStoreTypeScriptData() {
  console.log("TypeScript test: Storing sample conversation summary...");
  const db: lancedb.Connection | null = await initializeDB("ltm_agent_data");

  if (db) {
    const mockConversationState: ConversationState = {
      isActive: true,
      isAgentResponding: false,
      lastInteractionTime: Date.now(),
      conversationHistory: [], // Can be empty for this test
      idleTimer: null,
      currentIntent: "DiscussTopic",
      identifiedEntities: { topic: "JavaScript" },
      userGoal: "Improve JavaScript skills",
      turnHistory: [
        { userInput: "Tell me about async/await.", agentResponse: {text: "Async/await simplifies asynchronous code..."}, timestamp: Date.now() - 10000 },
        { userInput: "What about functional programming?", agentResponse: {text: "Functional programming emphasizes pure functions..."}, timestamp: Date.now() }
      ],
      ltmContext: null, // Initialize as per interface
    };

    await processSTMToLTM("user_ts_001", mockConversationState, db);
    console.log("TypeScript data stored for JavaScript programming discussion.");
  } else {
    console.error("TypeScript test: Failed to connect to LanceDB for storing data.");
  }
}

testStoreTypeScriptData().catch(console.error);
```
*   Compile and run this script.
*   Verify logs for successful connection, embedding generation, and data addition to the `knowledge_base` table.

### 4.2. Retrieve Data using Python (`research_agent.py`)

Modify `research_agent.py` or create a separate test script.

```python
# Example: test_python_retrieval.py (place in atomic-docker/project/functions/atom-agent/ or adjust imports)
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from research_agent import get_lance_db_connection, generate_embedding_py, log

def retrieve_sample_ts_finding():
    db = get_lance_db_connection()
    if not db:
        log("Failed to connect to LanceDB from Python retrieval test script.", level="ERROR")
        return

    log("Python test script: Retrieving data stored by TypeScript...")

    query_text = "JavaScript async/await and functional programming" # Semantically similar to what TS stored
    query_embedding = generate_embedding_py(query_text)

    if query_embedding:
        try:
            kb_table = db.open_table("knowledge_base")
            # Ensure 'text_content_embedding' is the correct vector column name in knowledge_base
            results = kb_table.search(query_embedding, vector_column_name='text_content_embedding') \
                                .limit(3) \
                                .to_list()

            log(f"Python retrieved {len(results)} items from knowledge_base for query '{query_text}':")
            for i, res in enumerate(results):
                log(f"Result {i+1}:")
                log(f"  ID: {res.get('fact_id', 'N/A')}")
                log(f"  Text: {res.get('text_content', '')[:200]}...")
                log(f"  Score (Distance): {res.get('_distance', 'N/A')}") # LanceDB search results include _distance
                log(f"  Metadata: {res.get('metadata', '{}')}")
        except Exception as e:
            log(f"Error querying knowledge_base from Python: {e}", level="ERROR")
    else:
        log(f"Could not generate embedding for Python query: '{query_text}'. Skipping retrieval.", level="WARNING")

if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        print("CRITICAL: OPENAI_API_KEY not set. Python retrieval test may not work as expected if embeddings are crucial.")
    else:
        retrieve_sample_ts_finding()
```
*   Run this script.
*   **Expected Outcome:** The console output should show the "JavaScript programming techniques" summary stored by TypeScript, demonstrating successful retrieval.

## 5. Validation Checks

During and after these tests, validate the following:

*   **Semantic Relevance:** Are the search results semantically related to the queries?
    *   The dummy embedding functions will *not* provide semantic relevance. This check is primarily for when real OpenAI embeddings are enabled. With dummy embeddings, you are mostly checking if the data can be written and read back, and if the vector search executes without error.
*   **Vector Dimensions:**
    *   If possible, use a LanceDB inspection tool or log table schemas (e.g., `db.open_table(name).schema` in Python, or equivalent in TS) to confirm that vector fields are indeed 1536 dimensions.
    *   Both `generateEmbedding` (TS) and `generate_embedding_py` (Python) should log warnings if the embedding dimension from OpenAI does not match the configured `DEFAULT_VECTOR_DIMENSION` (1536).
*   **No Errors:**
    *   Check console logs from both Python and TypeScript scripts for any errors during embedding generation, DB connection, table operations (add, search), or data parsing.
*   **API Key Handling:**
    *   Temporarily unset or use an invalid `OPENAI_API_KEY`.
    *   Confirm that both `generateEmbedding` (TS) and `generate_embedding_py` (Python) handle this gracefully by returning `null`/`None` for embeddings and logging an appropriate error, rather than crashing. Subsequent operations that depend on embeddings should also handle these null values (e.g., by skipping storage of that field or skipping the search).

This comprehensive testing will provide confidence in the LTM's core functionality related to embeddings and cross-language data exchange.
