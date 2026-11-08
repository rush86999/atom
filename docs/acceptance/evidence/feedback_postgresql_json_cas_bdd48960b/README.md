# PostgreSQL feedback CAS JSON accessor repair

Executed repair source:`bdd48960b34c48b45756ae30f288a62cb94953c9`. Main-equivalent negative source:`27a1830a27e73ed30124a82d01bb710e26bc7113` (its learning router/models/test blobs equal main8ded). The original accepted SQLite lane remains preserved; this is new PostgreSQL runtime scope, not retrospective relabelling.

## Real failure and narrow repair

The shared business/legacy CAS called PostgreSQL-specific `.astext` on actual `JSONColumn(TypeDecorator(JSON))`. Real private PostgreSQL14.24 execution returns annotation `error`: the comparator has no astext attribute. All9 existing forced-interleaving controls fail. Replace only those two PostgreSQL expressions with portable `.as_string()`; receipt, scope, quality snapshot, revision, bounded reload/precedence and one shared CAS are unchanged. No global JSON type, SQLite branch, model schema, authority or evaluator semantics changes.

Primary SQLAlchemy documentation supports portable JSON scalar casters: https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#sqlalchemy.dialects.postgresql.JSON.Comparator.astext and https://docs.sqlalchemy.org/en/20/core/type_basics.html#sqlalchemy.types.JSON.Comparator.as_string . This is an existing-mechanism correction, not a new persistence engine.

## Results

- New private PG14.24 cluster, Unix socket only,0700root,noTCP/operatorDB. Actual376 ORM tables created. Exact runtime data_directory/inet_server_addr verified before each fixture. Native shared CAS and real DB sessions are used; no DB persistence double.
- Before:9 failed. After:9 real interleaving controls +5 dialect controls =14 passed. Covers stale positive/pending vs stronger failure, legacy/business cross-writer precedence, duplicate stable incident identity and changed workspace binding refusal.
- Same frozen repair source, SQLite consumer/business/interleaving +dialect selection:36 passed. Its5 dialect controls overlap the14 and are not counted twice as a unique total.
- Cluster process exits0 in both attempts; no live model/provider/browser/transport call. Synthetic generation rows/scopes are explicit fixtures. `initdb --no-sync` means crash durability is NOT qualified. No migration, whole PostgreSQL compatibility, multi-worker app, soak or universal model-quality claim.

Actual original controls are imported from source-bound tests; the external PostgreSQL fixture overrides only the database fixture and seeds required real FK tenant rows. Session cleanup is explicit. Source/route/quality evaluators and verdict precedence remain the real implementations. Executed absolute paths/runners are retained, not regenerated to fit hashes. A first resource-gate attempt returned75 NOT DISPATCHED before cluster creation; it is not a test failure or hidden model retry.

CI successor adds these36 SQLite/dialect controls to the existing backend selection. That configuration successor is not relabelled as the executed bdd source. Hosted PostgreSQL is not claimed: local PG runtime proof and ordinary dialect compile regression are separate. Private cluster directories/logs stay retained outside Git; no operator account/secret is used.

Raw pytest logs retain their original trailing whitespace. Whole-packet git diff --check therefore reports those evidence lines; they are not rewritten to make a cosmetic check pass. Product/test/CI source whitespace is checked separately.
