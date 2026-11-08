# Isolated normal-application restore/read/restart

Executed source: `bb60d53d6a2e3d9725a18c18b346febc64c51176`. Restore product implementation remains `22f501599`; subsequent changes prepare/fix the harness, helper tests and existing CI selection. All earlier negative packets remain unchanged.

Root executed existing release-kit backup/restore once into a fresh scratch target, renamed the old source to a preserved unavailable location, then started the real main_api_app twice. Normal public login and exact actor/scope readback passed in both processes. Canvas/Goal reads, exact current office binding, authenticated DOCX download hash/content, SQL document/Parquet managed files and every original audit column were checked. One new restore-owned event carries honest provenance without historical approval/operation authority.

Result: 38 outer named checks; readback before restart 73 checks; after restart 74 checks. These overlap and are not a unique total. Distinct child PIDs 49134 and 49210 used the same target DB and frozen revision. Both stopped gracefully. Original source path stayed absent; preserved source was not used by readback. Product-model fixtures are synthetic, not actual agent/business work. No model/provider inference, send or external network operation is claimed. Memory is excluded: no LanceDB or public document-search qualification. No UI/browser claim.

Parent TESTING=1; seed/application child explicitly TESTING=0 with fresh scratch DATABASE_URL/data/office/Lance/output/BYOK paths and no provider keys. This uses the authorized explicit-scratch-DB exception, not a claim that the child ran in test-DB mode. Seatbelt restricts network to loopback. Login/startup bookkeeping is disclosed. No business mutation follows restore; normal login may update authentication state. Original operator DB was never used.

## Retained failures and helper provenance

- f6ec: worker advanced HEAD during startup; strict identity check refused, child stopped. No pass inferred.
- 5ad: first readback failed on an undefined audit-checker variable; child stopped. Fixed at 0e152 with real SQLite positive/extra-effect twins.
- 0e152: all readback checks except canvas_success passed; projection omitted the actual success field. Fixed at bb60 with true/false/missing controls.
- Helper candidate gate: 20 passed before the bb60 commit; its actual harness/test bytes equal bb60. The log's source field names prior HEAD 0e152 because these were then uncommitted harness changes. It is not a clean-tree test run. Earlier 15-pass helper log was accidentally replaced by a subsequent 17-pass run under the same prefix; the 15-pass stdout exists only in tool history, so it is not submitted as an independent artifact. Child negative worlds/logs were not overwritten.

Raw backend logs, scratch databases, password, keys and private world stay outside Git. Committed JSON contains safe identities, paths and token-presence booleans, never token/password values. No deployment or general recovery acceptance is claimed. Whole-app goals remain open; root observed this bounded episode and submits it for independent review.
