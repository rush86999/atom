# Strict production web type checking

Executed source: 01eb3a8321ef3f00eb35c2b62dae9ca37b9b5a95.

The actual full Next.js 16.2.2 production build exited 0 on Node 20.20.2 with TypeScript checking enabled. Its log records TypeScript validation, rather than skipping it. No runtime signing key was supplied. Generated build output was removed afterward.

Two independent native compiler controls passed: the project configuration rejects an injected type error, and the valid fixture builds. Fixture filesystem tracing roots are bounded to the owned project; package, filesystem, and configuration failures cannot count as the expected type refusal. The tests use the caller Node executable and the existing external resource gate.

This does not qualify lint, browser journeys, live identity providers, deployment, or mobile. Existing middleware/Browserslist/tracing warnings remain visible in the build log. Earlier filesystem-fixture failure informed the tracing repair and was not counted as passing evidence. Depends on the unchanged proxy and production-cookie work submitted in PRs 804 and 806.
