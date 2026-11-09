# Generic presentation workspace fixture correction

Frozen executed source: `00c1293b110e1c859278f2ca27b93f7c64bba82b`. Hosted PR800 c32da8185 Oracle selection passed796/797; the one failing registered Markdown consumer reproduced locally. Its shared scratch fixture created a real-scoped User with workspace_id=ws-1 but no authoritative Workspace row. The production presenter correctly refused.

The fixture now seeds that active matching row. Existing consumer assertions additionally require the real Canvas row and exact tenant/workspace/owner/content. A new missing-workspace twin refutes verification and publishes zero rows/frames. All original30 method identities remain; one negative is added.

Frozen source neighborhood:60 passed (generic expectations, mini-app host mutations and immutable CI lane guard). No production runtime, scope guard, route, credential, model/provider, browser or deployment change. Wider hosted checks on the new head remain required. Earlier browser/presentation/evidence identities remain unchanged.
