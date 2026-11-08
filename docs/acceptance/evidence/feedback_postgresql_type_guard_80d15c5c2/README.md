# PostgreSQL business-feedback exact JSON binding type

Runtime repair: 80d15c5c287be3e7c7047206e0ef2ced8715cc47. This successor retains the earlier bdd48960b portable JSON-access repair and its original evidence; it does not relabel those older executions.

## Actual independent negative and valid twin

At 54dafd988, the real record_attempt_evaluation producer accepted a stored JSON numeric workspace_id 123 for expected opaque string "123" on PostgreSQL: 1 failed / 1 passed. The positive string-valued twin passed. The same two exact controls passed on main-equivalent SQLite 27a1830a2 (backend equal 8ded00232), proving the dialect difference. A bounded GLM packet review suggested this conditional concern; root reproduced it using the real writer, real ORM rows and an actual private PostgreSQL cluster before assigning the repair. Review output itself is not a test or approval.

## Repair and actual verification

The Python business binding precheck requires stored workspace, provider, capability profile and version to be JSON strings. The PostgreSQL CAS also requires jsonb_typeof(key) = 'string' atomically with the existing exact value/revision/quality/generation predicates. This prevents a concurrent string-to-number rewrite from being authorized through ->> text coercion. SQLite typed json_extract and the legacy grounding/fabrication writer remain intact. No new feedback store, router, schema or global JSONColumn change.

Frozen source 80d15c5c2:

- PostgreSQL selection: **49 passed**. This is 20 real PostgreSQL DB controls (10 forced interleavings, eight field/type twins and two independent workspace twins), 24 pure Python wrong-type checks, and five SQL-dialect compile/refusal checks. Do not describe all 49 as DB races.
- SQLite affected selection: **71 passed**. It includes overlapping existing business-feedback, shared-writer/interleaving, new type and dialect controls plus the two root twins; do not sum it with 49 as unique capabilities.
- Both provider transport and application business decisions in the existing feedback tests are doubled. No live model/provider/user account was used.

Each PostgreSQL run initialized a new private installed PostgreSQL14.24 cluster, bound Unix socket only, verified its exact data directory and inet_server_addr NULL, created all 376 registered ORM tables, and gracefully stopped its owned process with exit0. A synthetic scratch SQLite URL protected incidental imports. initdb --no-sync means these runs do not qualify crash durability. They do not qualify Alembic migration, operator databases, all PostgreSQL app routes, multi-worker/soak or universal model judgment.

The external root wrappers are retained verbatim, with absolute paths to the actual executed checkout. They are harness artifacts, not files claimed committed at the runtime source. postgresql-fixture-and-tests.py imports the retained original fixture module, the committed forced-interleaving test functions, the new exact-type functions and the independent probe. Run them only against a new isolated cluster; never point their environment at an operator database.

A separate conditional review concern about malformed revision casts is not claimed repaired or reproduced here. _persist_feedback catches exceptions and returns truthful error, so a reviewer prediction of an uncaught writer crash is not established. Existing revision semantics were not changed to make that prediction pass.

## Attribution and CI

Source hashes bind the executed runtime 80d15c5c2. Artifacts bind committed Git bytes. Source-based manifests and previous negatives are preserved. The later ordinary merge of PR758 supplies only the already-qualified Goal utility test synchronization and its evidence; backend bytes remain exact. Current-head hosted checks must finish; no older green check or code-owner approval is inherited. No merge/deployment is performed by this packet.

The original negative private cluster was fully byte-verified into a retained cold archive after graceful exit. Its raw test log was copied and hash-compared before archival. The original source/result identities remain in negative-pg-result.json. No negative was regenerated to fit a manifest.

Primary references:
- https://docs.sqlalchemy.org/en/20/core/type_basics.html#sqlalchemy.types.JSON.Comparator.as_string
- https://www.postgresql.org/docs/14/functions-json.html (JSON scalar extraction and jsonb_typeof)

Whole-app ORACLE, general adaptive judgment and broad PostgreSQL qualification remain open.
