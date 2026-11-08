# Benchmark integration on accepted main

Frozen source ff457e05caff260db38d605e359a097ba2ccfbfe integrates accepted main ac2b73778 and the published governance README. The CI overlap preserves both the mandatory Python matrix contract and the independent bounded benchmark gate. Shared worker regression wiring remains present.

83 controls passed on Python3.11 and3.14:37 benchmark contracts,27 CI-preservation controls,14 supported-Python matrix controls and5 version-guard controls. Exact commands, source tree, source hashes and actual exits are retained. Fresh hosted checks are required on the next submitted head; earlier green is not inherited.

The benchmark loader and production cache bytes are unchanged from the already repaired bb0902130 source. The accepted shared-worker integration changes asyncio_compat; the benchmark controls were therefore rerun against these exact new bytes. Original raw benchmark measurements and stale-bytecode negative remain at their actual identities, not silently attributed here. No new speed number or full governance/API/DB performance claim follows.
