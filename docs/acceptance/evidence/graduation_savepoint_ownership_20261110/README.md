# Caller-owned work across SAVEPOINT boundaries

The original frozen graduation probe failed two negative controls and passed two valid twins: ending a nested transaction erased the outer write marker, allowing promotion to commit unrelated caller work. The repair tracks write ownership by the real SQLAlchemy transaction and transfers committed nested writes to their parent. Rollback/close discards only nested ownership; only the outermost end clears the complete marker.

Repaired source: `918e7a17c`. The unchanged public-service probe passes 4/4; the permanent graduation, assessment, notification, CI-preservation and transaction matrix passes 110/110. Both captures verify source-before/source-after equality and actual test exit zero. Earlier sandbox socket setup failures are retained in scratch and are not product test results.

Independent native review and broader shared-consumer regression remain pending. No full-app, PostgreSQL, model-competence or browser-on-this-successor claim follows. The ordinary graduation browser worker remains bound to its earlier frozen source.

Primary references: [SQLAlchemy transaction lifecycle](https://docs.sqlalchemy.org/en/20/orm/events.html#sqlalchemy.orm.SessionEvents.after_transaction_end), [SAVEPOINT semantics](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#using-savepoint).

The additional shared-consumer selection initially returned 163 passed and 11 failed. Seven are the already reproduced main training baseline. The remaining four also fail on frozen pre-SAVEPOINT graduation source6da: two old route controls omit qualification and two manual-exam mocks assume the retired direct-history writer. Their predecessor failures are preserved separately. Test migration is being verified with explicit exact-agent owner policy for receipt/CAS-only positives, shared-writer adapter assertions, and two added missing-qualification refusals; production policy is unchanged.

Migrating those controls exposed a separate real promotion-replay mismatch: the initial commit digest includes last_exam_id and promotion_count, but generic replay compared only the older agent fields. The adapted six-case run retained one failure/five passes. The successor now shares exact promotion result material between commit and replay; changed receipt/count negatives are being verified. This is not dismissed as fixture-only and the prior source remains unchanged.

Final combined permanent gate:121 passed, actual exit0 and unchanged recorded source hashes. Includes13 real Session lifecycle controls,8 promotion/refusal/replay controls, qualification/assessment/notification controls and CI-preservation checks. Prior follow-through21 passed assertions but source changed while queued, so it is supporting only; final121 is the authoritative frozen-file gate. Ordinary graduation UI remains incomplete after valid receipt/no enabled promotion button, on original6da, separate from this backend successor.
