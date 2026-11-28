# Workflow event renewal successor

This work order continues whole-app completion; it does not replace that finish line with the workflow slice. See [whole-app requirements](../../acceptance/WHOLE_APP_COMPLETION_2026-10-27.md).

## Retained checkpoint

PR #1082 remains draft at `23bedf1255faa9c2e204abc284f477f037a818ae`. On November28 the remote readback showed all17 hosted checks successful at that exact head, including every backend lane, aggregate backend-tests, e2e, frontend, bootstrap, quickstart, Docker and GitGuardian. This does not certify renewal or whole-app readiness.

The committed scoped-refresh evidence records the exact Python3.11 gate282 passed, unchanged625 shell cases deselected, existing generic consumers72 passed and picker/sidebar35 passed. The controlled browser evidence certifies editing/enrolling/saving/reopening a seeded rule under full profile, core refusal, and a real durable notification through mounted workflow/profile routers. Authentication/Graph transport are controlled; this is not full-main or live-provider acceptance.

The previous temporary checkout and local handoffs were partly removed by temporary-file cleanup. Code and committed evidence are intact. Use a durable isolated worktree and retain tested checkpoints remotely. Do not reset or stage the owner's dirty checkout. Push tested runtime and evidence together between coherent phases, then observe CI on that exact head while doing independent work. A successor head never inherits green checks.

## Next complete engineering boundary

Implement callable subscription renewal through the existing registry, AuditLog and TaskOperationRecord arbiter. Preserve original enrollment operation, prepared time, request digest and provider receipt. Persist one frozen pending renewal intent before dispatch; do not recompute expiry on retries. Use exact current owner/authority/connection/document claims and exact-document CAS. The existing transition_effect hook can commit a winning local target, safe audit and operation receipt together.

Use native PATCH of the exact original subscription, with prior material verification and independent readback of the exact new expiry/resource/callback/id. An uncertain request reconciles by GET only; never repeat PATCH or silently POST a replacement. Missing/corrupt proof is unavailable/refuted. Verify the current lease's separate receipt while retaining the original enrollment proof. Old documents must remain valid for their original semantics. Preserve all public safety and permission contracts.

First qualify this callable with real scratch storage and controlled provider transport: success/replay, competing callers, timeout then readback recovery, wrong target/expiry readback, actor/target races, atomic audit rollback and corrupt proof. Integrate only a qualified callable into the existing worker; do not add another runner or queue.

## Remaining finish line

Still required: proactive token/subscription maintenance, reauthorization, missed-event recovery/backfill, safe expired-initial-setup recovery after days, fresh browser-created rules and full-main browser operation, another domain source, scoped native forwarding and applicable PostgreSQL/multi-worker qualification. Passing one callable must not close these claims. Keep accepted lanes and original negative evidence intact.

Microsoft documents subscription renewal and lifecycle loss separately from OAuth token refresh: [update subscription](https://learn.microsoft.com/en-us/graph/api/subscription-update?view=graph-rest-1.0), [lifecycle events](https://learn.microsoft.com/en-us/graph/change-notifications-lifecycle-events), [webhook delivery](https://learn.microsoft.com/en-us/graph/change-notifications-delivery-webhooks). Renewing/reauthorizing with a PATCH is a different operation from obtaining a fresh access token. Provider retry windows do not prove recovery after days offline.

## Worker and resource boundaries

Prefer the requested free OpenCode models when available. Use public-source-only bounded packets and independently verify proposed patches. Do not expose private handoffs, credentials or raw logs. A model/configuration failure is not a completed worker task; no paid fallback or unbounded retry is implied. CLI availability must be revalidated after cleanup or reset windows. Keep root as verifier and coordinator.

The owner explicitly requires remote checkpoints. Routine CI observation can be delegated; it grants no merge/deployment authority to the worker. This work order starts no deployment, live account/provider campaign, credential rotation, spend or send operation.

## Callable checkpoint and next maintenance boundary

The internal renewal callable now uses full-document audit proof, one frozen pending lease, exact authority/credential/document claims before PATCH, and atomic current-lease/audit/operation receipt commit. Original enrollment fields remain unchanged. Enrollment replay and callback consumers explicitly verify current lease proof before using its expiry. The native adapter alone remains bound to its original enrollment semantics by default. Qualification results belong to the new evidence bundle; do not infer hosted or whole-app acceptance from local tests.

A single bounded OpenCode Go DeepSeek proposal completed on November28 (CLI reported cost0); the free endpoint returned429. Root corrected the proposal rather than applying it wholesale. No worker tool execution, paid fallback or live application provider campaign occurred.

Next: use the existing workflow_event_worker_loop for periodic lease maintenance, with bounded/fair source traversal and restart tests. OAuth renewal and Graph subscription authorization must both be covered. Microsoft documents separate lifecycle challenges, lost notifications and removal; one PATCH may renew and reauthorize together, and rapid parallel reauthorization/update calls can cause inconsistent state. Lifecycle notification URLs must be registered, authenticated against durable receiver state, persisted before acknowledgment and consumed by the existing worker. Missed/removed events need durable delta recovery and safe subscription succession, not repeated creation after uncertainty. See [Microsoft lifecycle guidance](https://learn.microsoft.com/en-us/graph/change-notifications-lifecycle-events).

Retain the unresolved boundaries: no live-provider qualification, PostgreSQL/soak or multi-worker claim; no full-main/fresh-created-rule browser proof; no days-offline/backfill claim. Do not broaden marketing claims from the callable checkpoint.

## Existing-worker maintenance checkpoint

Periodic maintenance now belongs to the existing event worker lifecycle. It scans bounded keyset pages using actual hashed registry keys, skips malformed/disabled rows, and passes each valid source to the qualified renewal callable. Per-source timeout leaves ambiguous PATCH state durable; later scans reconcile by GET. Source network waits run in one owned maintenance task while event polling continues. Shutdown and parent cancellation cancel/await that owned task; restart scans from the beginning safely through durable operation receipts. Cursor progress is per completed finite page, not a timed batch that repeatedly abandons the same first rows.

This only schedules due lease renewal. At this checkpoint enrollment lacked lifecycleNotificationUrl; the successor below adds it for new registrations. Missed-event delta recovery, safe removed/expired subscription succession and days-offline acceptance remain required. Controlled time advancing across several lease generations is not a live days-long soak.

## Authenticated lifecycle / reauthorization successor

New source preparations freeze adapter-owned lifecycle capability in the audited document. Native enrollment explicitly registers the same callback as lifecycleNotificationUrl, and provider readback must match it. Old documents keep their original four-field plan and receipt; replay does not upgrade or recreate them. Microsoft requires a new subscription to add lifecycle support to an existing subscription, so safe legacy succession remains a separate requirement.

Lifecycle intake proves the original private receiver state and exact durable subscription/scope/lease, then claims current authority and records the full updated source document plus audit before202. It performs no provider I/O before acknowledgment. The existing worker refreshes scoped credentials and verifies the target before one renewing/reauthorizing PATCH. Reauthorization can run before the usual24-hour renewal threshold; duplicates coalesce, timeout reconciles by GET, and a challenge received during an already-prepared renewal is satisfied by that same PATCH. Identical old/new expiry is deferred until readback can distinguish the operation. Missing credentials retain the durable request until restored.

Missed and removed reports are persisted as pending reports, not certified recovery. Delta/backfill, removed/expired-source succession, registered-source refusal resumption (successor below), legacy lifecycle enablement and days-offline qualification remain open. Original unknown operations must never be blindly repeated. Full-main/fresh-rule browser, another native domain, PostgreSQL/multi-worker/soak and whole-app finish-line claims remain open.

References: [Graph lifecycle events](https://learn.microsoft.com/en-us/graph/change-notifications-lifecycle-events) documents subscription capability and combined renewing/reauthorizing PATCH; [webhook delivery](https://learn.microsoft.com/en-us/graph/change-notifications-delivery-webhooks) recommends validated durable persistence followed by202 when processing cannot finish promptly. This implementation reuses the existing source ledger and worker rather than adding a queue/runner.

The shared registry writer also now validates strict JSON material and claims the actual observed storage bytes. A public lifecycle callback reproduced a false stale503 after equivalent JSON whitespace reformatting; the repaired valid twin and actor/target/original-receipt stale negatives pass. This affects both renewal and lifecycle writes; it does not relax material comparisons. The original development failure log is retained with provenance, not relabeled as a remote baseline.

## Relevant-input resumption successor

A pending registered-source renewal may now be superseded only when its exact old operation is stillCLAIMED (never dispatched) or FAILED_BEFORE_EFFECT with no receipt, and permitted current authority or encrypted-grant commitment changed. Clock changes and last_login do not create new attempts. Raw actor/connection tenant/workspace/id/source must stay exact; an effective default alias cannot adopt changed raw scope. Current active manage/run authority remains required.

The old status guard, exact source CAS, fresh pending intent and full-document audit commit through the existing transition_effect transaction. The server issues a new UUID linked to the exact retired operation/hash. Original identity/payload/result remain; uncertainty is never reset. At most one supersession occurs per invocation. Credentials are read again after replacement so a concurrent reconnect cannot send the stale grant. Fresh readback also verifies the retired ledger entry's scope/action/id/hash/no-receipt/no-effect status.

Independent failure-first sourcec536a2003 records4failed relevant-input positives and5passing protections. Expanded controls cover peer dispatch winning the CAS, audit rollback, simultaneous resumption, contradictory receipt, corrupted retired proof, raw-scope alias, credential wait and a new OS process. The development alias negative is retained separately; it is not labeled as the original Git-bound baseline.

This completes only registered-source lease refusal resumption. Initial enrollment/expired/removed/legacy-source succession and durable delta/backfill still need implementation and qualification, along with the wider browser/provider/second-domain/PostgreSQL/soak finish line. No uncertain request may be blindly repeated to make recovery appear complete.

Design reference: [AWS Builders Library: safe idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/) distinguishes request identity from a new intent and describes atomic token/effect recording. Atom reuses its existing arbiter for that local atomicity. The external Graph call cannot share that database transaction, so uncertain writes remain GET-only; this change does not adopt a generic retry-until-success policy.

The remaining product acceptance also needs explicit observable waiting/recovery/expired status and a supported owner action when a source needs credentials. A private pending receipt alone is not a complete user journey; do not turn this internal resumption gate into a broad readiness claim.


## Delta prerequisites: activation and native pages

The real public create/revision-bound save now stamps server-owned per-binding activation cutoffs inside the catalog mutation. Unchanged active binding and owner scope preserve the cutoff; disabling/removing a binding clears it, and re-enabling/rebinding starts a fresh window. Caller timestamps cannot backdate it. Legacy rows without a valid binding-matched, timezone-aware cutoff have no inferred historical entitlement. This metadata alone admits no event.

The existing Outlook adapter now resolves the current delegated user and Inbox IDs, checks them before every delta page, and reads a bounded created-message delta page. Continuations must be exact Graph v1.0 HTTPS user/folder/message-delta targets; opaque URLs are followed unchanged. Empty next pages continue, terminal delta links complete, malformed pages refuse, and provider reset responses are typed. Transport errors expose fixed safe text and cancellation propagates. No cursor persistence, source binding migration, full catch-up, or recovery completion is claimed here.

Microsoft's [message delta guide](https://learn.microsoft.com/en-us/graph/delta-query-messages) documents folder-scoped initial synchronization, created filtering and opaque continuations. Its [delta overview](https://learn.microsoft.com/en-us/graph/delta-query-overview) documents empty next pages, replay and invalid-token resets. The Outlook implementation deliberately does not borrow the Entra-only `$deltatoken=latest` shortcut. Future consumer work must pin provider identity durably, retain activation/coverage proof, and commit existing event reservations before cursor advancement. Reconnecting to another mailbox cannot adopt a previous cursor.


## Provider identity binding before enrollment

New native enrollments resolve the current delegated mailbox and Inbox before the first durable source intent. Exact raw authority, encrypted grant and expiry are claimed in the same preparation transaction as the private provider binding and audit. New subscription material names those explicit provider IDs. Reconnect/authority changes during the GETs refuse preparation; a reconnect after preparation cannot dispatch an unchecked grant. Existing prepared/registered/unknown source documents retain their original plan, operation and receipt, without silently upgrading `/me` intent material.

The existing source credential entry point validates current mailbox/Inbox against the frozen binding for subsequent provider reads, renewals and callbacks. A different mailbox cannot certify the original source. The shared private credential commitment preserves the exact established renewal algorithm, and the conditional claim preserves unrelated timestamps. No decrypted credential or provider binding appears in public registration output or audit metadata.

The source-bound original eight probes at a54c39d1a record seven failures and one legacy-preservation pass. Expanded controls cover raw-scope/grant/expiry/authority peers, malformed/plaintext/expired credentials, expiry during provider lookup, missing credentials, unchanged commitment and legacy unknown receipts. Existing pre-dispatch control now explicitly permits only the four required mailbox-proof GETs, while still forbidding enrollment/content/subscription I/O after authority loss. The renewal target-read negative still fails its subscription GET after successful identity proof.

References: [Outlook resource paths](https://learn.microsoft.com/en-us/graph/outlook-change-notifications-overview) recommends an unambiguous object-ID mailbox; [Graph delta](https://learn.microsoft.com/en-us/graph/delta-query-messages) remains folder-specific. [Immutable Outlook IDs](https://learn.microsoft.com/en-us/graph/outlook-immutable-id) are also required for consistent webhook/delta identity across moves; that header/succession qualification remains open. This binding checkpoint does not store a cursor, perform catch-up or certify days-offline operation.


Confirmation also uses a freshly provider-verified grant after the external effect, then claims that exact grant through activation and independent registry readback. Three additional development probes reproduced a reconnect after POST, after subscription GET, and after local activation returning false registered success; the original logs are retained explicitly as an uncommitted development negative, not the Git-bound eight-probe baseline. Those paths now retain the original successful operation receipt and report committed_unverified, never overwrite a reconnect or repeat POST. A new grant for the same mailbox is a valid confirmation twin; restoring the original mailbox later reconciles the same committed receipt. The two existing fresh-OS-process transports now answer the required exact identity GETs as well as subscription reads; GET-only reconciliation and one-PATCH resumption remain enforced.


## Stable native message identity

New registrations freeze adapter-owned source_options with message_id_type=immutable into the original private audited source document. The native plan and operation payload bind this mode. Subscription POST, message-content GET and every delta-page GET send the exact static Prefer: IdType="ImmutableId" header through the existing Microsoft service. Profile/Inbox resolution, subscription GET and expiry-only renewal PATCH do not change identity mode. Strict boolean transport flags cannot override Authorization or inject arbitrary headers.

New-mode message reads target the explicit frozen mailbox. Their provider event key namespaces the immutable message ID by provider principal, excluding mutable subject/body, folder and source generation; the existing reservation key still supplies workflow/connection/source/application scope. This is a created-message identity, not a new event for each folder move. Legacy source documents without the option keep original subscription plans, /me reads and provider event IDs. Changing adapter defaults cannot rewrite an existing receipt or silently upgrade old subscriptions.

The existing real callback passes the verified document to native content normalization. HTTP doubles accept the new option without bypassing the native adapter/service; low-level tests inspect the actual emitted aiohttp headers and unchanged payload. The shared development mock log now retains method/path while omitting opaque query state. No new logging engine or provider eligibility change.

Reference: [Microsoft immutable Outlook identifiers](https://learn.microsoft.com/en-us/graph/outlook-immutable-id). Container IDs are already stable; immutable message IDs survive moves within the same mailbox, but not archive-mailbox moves or export/reimport. Existing subscriptions require explicit recreation to change ID mode. Subscription GET does not expose an id-type field: the local receipt proves frozen requested transport material, not an invented provider readback field or live provider qualification. Encrypted canonical-event/cursor storage, coverage/reset, legacy succession and days-offline acceptance remain open.


## Exact original-enrollment receipt proof

Failure-first source27c5990fb records7failed/5passed: wrong original tenant/action/run/idempotency/payload values could certify a registered source while status/result digest still matched. A changed payload hash also allowed renewal and public callback admission. The shared source verifier now reconstructs the original adapter plan and exact operation hash from frozen source/actor material and validates the complete six-field target receipt.

All original scope, kind, run/key, payload, status and receipt fields are read as fresh scalar columns in the caller transaction, with a row lock where supported and a conditional no-op claim over the observed record and raw JSON storage text. Semantic JSON is checked first, preserving valid equivalent formatting without rewriting history. The claim preserves timestamps and never inserts, repairs, commits or rolls back its caller. This uses the existing operation ledger only.

The same verifier guards callback/readback, activation, registry lease/lifecycle writes and renewal dispatch. Source-row then original-operation lock order is consistent. Preparation still returns an audited source snapshot, not effect certification; enrollment separately verifies the original operation before invoking the generic arbiter and preserves committed_unverified/effect_unknown/conflict responses. A moved pending source UUID/slot cannot be silently adopted or reallocated. Dispatch and uncertain reconciliation recheck exact metadata before status transition. A refusal reports effect=none only when the original operation is still provably CLAIMED with no receipt; otherwise it remains unknown.

Additional controls cover a peer winning the receipt/payload/status/scope claim, an ORM identity-map stale row, equivalent JSON spacing, caller-owned edits, missing rows, moved pending/unknown scopes, dispatch/reconciliation races and no duplicate allocation after a registered receipt disappears. The initial focused37-control development run exposed three response-compatibility regressions; these were fixed without weakening controls, and the expanded52-control selection passes. Original logs remain retained.

The generic cold-resume loader retains its broader compatibility contract; this source-specific verifier uses the existing registered adapter mechanism to reconstruct exact source material rather than adding another ledger or changing every generic consumer. References: [SQLAlchemy CAST](https://docs.sqlalchemy.org/en/20/core/sqlelement.html#sqlalchemy.sql.expression.cast) and [row locking](https://docs.sqlalchemy.org/en/20/core/selectable.html#sqlalchemy.sql.expression.GenerativeSelect.with_for_update). Actual PostgreSQL concurrency remains unqualified. Canonical payload/cursor storage and source succession are still unfinished.


Three more development probes exposed scope movement during successful/refused/timed-out provider attempts. Acknowledgement persistence now uses the same exact pending-row proof before recording success, confirmed refusal or uncertainty. A failed no-effect persistence is not reported as a verified refusal. The peer-moved row remains unchanged and the response retains original identities with effect_unknown/do_not_repeat. Original development logs and measured hashes are retained separately from the Git-bound baseline. The earlier485-control gate passed before adding these persistence twins; final acceptance uses the expanded selection.


The final transaction join also covers admission. Three expanded development probes reproduced receipt, registration or grant changes during real content fetch still reserving an execution. The callback now captures the checked read grant and passes a server-owned source guard through existing intake authority/reservation hooks. SQLAlchemy AsyncSession.run_sync reuses the same synchronous source verifier inside that exact async transaction; it opens no second store or runner. The guard repeats for receipt-only checks and actual insertion, so a change after preliminary verification still rolls back the reservation. An unverified duplicate neither acknowledges nor replaces its original execution.

Source delivery retains its existing WORKFLOW_RUN permission; source setup/lease management still require WORKFLOW_MANAGE. A private typed snapshot mode reuses the existing authority resolver and raw grant claim without promoting member roles. The positive member-delivery/forbidden-enrollment twin and repeat-at-insert control pass. Original development evidence is labeled separately; the retained admission negative is the expanded three-case rerun, not the preliminary two-case output. Reference: [SQLAlchemy synchronous ORM inside AsyncSession](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#running-synchronous-methods-and-functions-under-asyncio). The six focused admission controls and20-control callback neighborhood pass before the final expanded gate.


### Renewal operation transition proof follow-through (2026-11-28)

Original enrollment proof checkpoint `c13c5c535` / evidence `fdc1288bb`
is retained (494 controls +18 subtests). Its success does not certify the
renewal operation's own metadata across asynchronous provider reads/writes.
The next Git-bound baseline `4208c35b2` reproduces 24 failures and one valid
renewal twin: tenant/workspace/operation/action/run/idempotency changes during
preflight, successful PATCH, confirmed refusal and lost confirmation.

The same existing source-operation scalar/raw-JSON no-op claim is now reused
for renewal; generic arbiter semantics remain unchanged. Source proof and
exact operation inspection occur inside the allocation transaction, and exact
pending-row proof occurs before each dispatch/acknowledgement/status transition.
A separate development negative also reproduced a new-row allocation after a
workspace move between preliminary inspection and generic claim. That log is
labeled working-tree evidence, not a second Git baseline. Restoration permits
GET-only reconciliation of the same identity; no new PATCH or operation is
inferred from a moved row. No-effect supersession retains its existing exact
old/new authority and audit contract. Whole source catch-up acceptance remains
open: canonical event observations, encrypted durable cursor, activation
coverage, safe source succession and owner-visible recovery are not supplied
by this receipt repair.
