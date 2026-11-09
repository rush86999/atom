# Localized presentation workspace setup

Frozen source: `89e40d3212e87f48179e9fd64c23ad711dc99593`. The previous shared fixture seed at66619bbba fixed the presentation case but collided with budget consumers that deliberately create their own workspace. Hosted exact-step result:114 passed/28 duplicate-workspace failures. The extracted failure identities retain that negative scope.

Workspace creation now belongs only to the existing registered-presentation test. The shared mini-app fixture is byte-identical to c32da8185. The missing-workspace zero-effect twin and exact Canvas/receipt readback remain. All consumer test identities remain; production guards and immutable workflow commands are unchanged.

The frozen205-control gate includes every direct shared-fixture consumer, the exact MCP/budget step, reconciliation and CI-preservation controls:205 passed. No production, model/provider, browser, sandbox, credential or deployment change. Earlier60-control and browser evidence remains historical at its actual source; this packet does not relabel it as broad acceptance. New exact-head hosted checks are required.
