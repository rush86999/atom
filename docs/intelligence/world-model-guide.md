# AI World Model Retrieval & Governance

This document outlines how the Atom AI agents retrieve, filter, and use past "experiences" to improve decision-making over time. This architecture ensures agents learn from success, avoid repeating failures, and respect human oversight.

## 1. The Storage Mechanism (`AgentExperience`)

The core storage logic resides in `core.agent_world_model`.

Every time an agent completes a task (whether successful or not), it records an **Experience** object in the `agent_experience` vector table. This object contains:

*   **Vector Embedding**: A semantic representation of the `Task`, `Input`, `Outcome`, and `Learnings` text. This allows for concept-based retrieval ("process bill" finds "pay invoice").
*   **Metadata**:
    *   `agent_role`: (e.g., "Finance", "Sales") for scope isolation.
    *   `outcome`: "Success" or "Failure".
    *   `confidence_score`: A float (0.0 - 1.0) indicating how trusted this pattern is.
    *   `trace`: Execution details for debugging.

    *   `trace`: Execution details for debugging.

**Storage Technology**: PostgreSQL (Relational Graph Tables: `graph_nodes`, `graph_edges`) + Upstash Redis (Job Queue).
Traversal is handled via SQL Recursive CTEs for stateless efficient lookup.
Community Detection (clustering) is handled by a background worker using NetworkX + Leiden Algorithm.

## 2. The Retrieval Pipeline (`recall_experiences`)

When an agent faces a new task `T`, the system calls `WorldModelService.recall_experiences(T)`. This triggers a multi-step retrieval process:

### Step 1: Graph Neighborhood Search
The system queries the PostgreSQL Map using **Recursive CTEs** to find the neighborhood of the relevant entity (Person, Project, Document).
This retrieves specific, connected context (Relationships) rather than just semantic similarity.

### Step 2: Role Scoping
Results are filtered by `agent_role`.
*   A **Sales Agent** will primarily retrieve experiences created by other Sales agents.
*   It generally will *not* retrieve DevOps or HR experiences, unless they are marked as `general_knowledge`.

### Step 3: Quality Gating
The system applies filters to prevent "learning bad habits":
*   **Success Prioritization**: Only experiences with `outcome="Success"` are aggressively retrieved.
*   **Confidence Threshold**: Failures are generally ignored unless they have a very high confidence score (indicating a verified "warning" or "what NOT to do" lesson).

### Step 4: Context Assembly
The retrieved experiences are combined with:
*   **Verified Business Facts**: Hard constraints stored in the `business_facts` table (e.g., "PO required for >$5k").
*   **Relevant Formulas**: Mathematical logic patterns used successfully in the past.

## 3. The Governance Gate (`GovernanceEngine`)

Retrieval feeds into the **Governance Engine** (`core.governance_engine`), which decides if the agent acts autonomously or pauses for approval.

### Confidence Scoring
The system calculates a `confidence` score for the proposed action based on the retrieval results:
$$ Score = \frac{ \text{Similar Approved Actions} }{ \text{Total Similar Actions} } $$

### The "Learning Phase"
*   **Learning Phase**: When a workspace is new, agents are cautious. Most actions require Human-in-the-Loop (HITL) approval unless confidence is extremely high (>0.9).
*   **Autonomy**: Once a workspace "graduates" (via setting `learning_phase_completed`), agents act autonomously for tasks with high confidence.

### Feedback Loop
When a human approves or rejects an action:
1.  The `confidence_score` of the recalled experience is updated.
2.  A new experience is recorded with the result of the human intervention.
3.  This immediately influences the retrieval ranking for future similar tasks.

## Summary Flow

```mermaid
graph TD
    A[New Task] --> B[Map Search (Postgres Graph)]
    B --> C{Filter Results}
    C -->|Role Mismatch| D[Discard]
    C -->|Low Quality| D
    C -->|High Confidence| E[Inject into Context]
    E --> F[AI Plans Action]
    F --> G{Governance Check}
    G -->|High Confidence| H[Execute]
    G -->|Low Confidence| I[Pause for HITL]
    I -->|User Approves| H
    I -->|User Rejects| J[Record Failure]
    H --> K[Record Success]
```
