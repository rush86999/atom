# Caller-owned work across SAVEPOINT boundaries

The original frozen graduation probe failed two negative controls and passed two valid twins: ending a nested transaction erased the outer write marker, allowing promotion to commit unrelated caller work. The repair tracks write ownership by the real SQLAlchemy transaction and transfers committed nested writes to their parent. Rollback/close discards only nested ownership; only the outermost end clears the complete marker.

Repaired source: `918e7a17c`. The unchanged public-service probe passes 4/4; the permanent graduation, assessment, notification, CI-preservation and transaction matrix passes 110/110. Both captures verify source-before/source-after equality and actual test exit zero. Earlier sandbox socket setup failures are retained in scratch and are not product test results.

Independent native review and broader shared-consumer regression remain pending. No full-app, PostgreSQL, model-competence or browser-on-this-successor claim follows. The ordinary graduation browser worker remains bound to its earlier frozen source.

Primary references: [SQLAlchemy transaction lifecycle](https://docs.sqlalchemy.org/en/20/orm/events.html#sqlalchemy.orm.SessionEvents.after_transaction_end), [SAVEPOINT semantics](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#using-savepoint).
