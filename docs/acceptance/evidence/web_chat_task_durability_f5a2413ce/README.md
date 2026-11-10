# Durable local task consumers

Executed source: `f5a2413ce07bfd180b64ca58d861f9b9898cb9a5` on `codex/chat-task-durability-20261109`. This packet is evidence for that source, not a claim that its code is already merged to main.

The ordinary task API and both chat task consumers now share the existing UserTask SQL mechanism. Production MagicMock identity and memory-only chat success are removed. The service resolves the active canonical user, claims exact current authority in the write transaction, validates project/workspace, and confirms the durable task. User-scoped idempotency compares complete normalized creation material and current stored material. An omitted deadline remains absent, so replay does not invent a different deadline. Unspecified platform is local; a product name in a title does not select a provider. Explicit unsupported providers refuse rather than silently creating locally. Deferred Tasks UI is not force-enabled.

Root independently ran 28 controls under normal repository conftest and three original consumer probes. Both actual exits were zero. The original provider-word probe at predecessor3ae had one failure and two passes; that negative remains attributed to its source. The worker also reported242 affected passes; that broad number is not presented as root's independent run.

Scope includes real scratch SQL rows, authenticated public ASGI task reads, fresh sessions and a child Python-process read in the normal suite. It does not establish a complete main-app browser task journey, a live connected-provider task operation, full mutation ORACLE, or model judgment. No new task store/schema/review engine was introduced. The local single-tenant deployment remains primary.

Reproduce using Python3.11 and installed repository dependencies, TESTING=1, a unique private scratch DATABASE_URL/data root, and the existing bounded test gate. command.json records the executed arguments. The independent probe imports fixtures from the exact source test module. Raw logs, auth tokens, environments and databases remain private. No live provider/model/account, send/spend, deployment or credential action was used.
