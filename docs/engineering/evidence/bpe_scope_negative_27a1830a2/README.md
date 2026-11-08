# BPE scope negative — source-bound root findings

Executed checkout27a1830a27e73ed30124a82d01bb710e26bc7113 has the exact backend tree of main8ded00232c30961a990e675e06ec672ef6a43910. These are negative controls, not repair acceptance, model qualification or browser evidence.

## Mounted public RPC: 1 failed / 1 passed

Two real active User rows share the single tenant but have different authoritative workspaces. Through the real mounted POST /api/rpc/workspace.note route, action registry and handler, workspaceA buffers one note; workspaceB's FIRST note reports buffered2. The shared resolver used default/atom_main/empty-scope for both, so a foreign workspace appended the peer buffer. The same-user positive twin deliberately adds two notes and receives counts1then2.

The authentication dependency is injected with actual freshly read User rows; this does not qualify normal JWT/login. SQLite FK checks are enabled; BPE storage is rebound to the scratch fixture. No operator DB, model, provider or server was used.

The first root RPC harness unpacked buffered at the outer wrapper instead of data.buffered. Its2KeyErrors were harness errors, not product failures. That original private file/log remain retained at /private/tmp/test_root_bpe_rpc_scope.py and /private/tmp/root-bpe-rpc-scope-main27a.*. The corrected v2 and decisive1fail1pass are committed here unchanged.

## Actual Generic step consumer: 2 failed / 5 passed / 5 skipped

The action really appends a note, then the default Oracle consumer marks it uncertain because it has no registered postcondition verifier. An empty pre-effect refusal is also recast uncertain. Five positive/mechanism checks pass; five explicit pre-fix diagnostic cases were skipped, never counted as passes. This controlled slice invokes the real step consumer with pre_approved=True and a scratch operation store, not the whole governed app episode. Its actor is not qualified as an authenticated normal-run actor.

The author-only header in the retained probe describes its state when authored. Root subsequently executed those exact bytes, as the source-bound log/spec/exit prove; the historical header was not rewritten. The test's proposed close-out branch is not reached after its first failure, so this packet DOES NOT claim a full run demonstrated note loss or consolidation. Code tracing shows the episode close-out chooses consolidate versus drain based on run status; a separate valid-authority whole-consumer test is still needed.

## Product/engineering priority

Phase1 fixes authoritative current-principal namespace isolation in the existing shared resolver across all four BPE actions/RPC/MCP/Generic callers. Keep legitimate same-user and PersonalNULL/default behavior, refuse forged/absent/inactive authority, and never assign ambiguous old global state to a user. Do not relabel writes read-only or remove legitimate functions just to pass.

Phase2 remains open: classify or verify internal harness state truthfully without awarding business completion, and establish appropriate producer identity/durability using existing mechanisms. Do not use buffer count/content presence as proof of a new durable effect. Current execution memory versus long-term memory is a design distinction, not an excuse to bypass authorization or invent receipts. Durable-state guidance research: https://github.com/langchain-ai/docs/blob/main/src/oss/langgraph/persistence.mdx (thread checkpoints and stores). Repo adaptation remains an engineering inference, not external proof.

No new source/runtime behavior is introduced by this evidence packet. The original143-claim denominator and historical scores remain unchanged; whole-app ORACLE and general judgment stay open.
