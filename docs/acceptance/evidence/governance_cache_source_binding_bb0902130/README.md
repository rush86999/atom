# Benchmark source-binding repair

Executed source: `bb0902130443c0e202dfb37cde9c8e0d8384f471`.

A real cache copy with a harmless appended marker demonstrated that timestamp/size-valid stale bytecode could execute while the earlier loader reported newer disk-source hashes. The exact original3eb script is retained and matches Git. Reproduced negative exits1; the repaired loader exits0 with the new marker and equal loaded/disk digests. No cache implementation was replaced and this probe makes no performance claim.

The selected cache and compatibility dependency are now compiled directly from captured bytes, tagged with the executed digest, and compared with retained source files before/after measurement. Changes during loading refuse without a published result.

64 controls pass at this clean integrated source on both Python3.11 and3.14:37 benchmark controls and27 CI-preservation controls. Default cache-only measurement runs complete on both runtimes with correct hit/miss counts, raw batches/samples, and matching loaded/source digests. Timing is host/run specific; no threshold or system tuning is applied. Full permission/authority, database, budget, approval, Oracle, HTTP, cold-start, universal throughput and PERF-01 qualification remain open.

Earlier95abe265d measurements and evidence remain unchanged at their original source. The accepted alignment-main integration preserves both required CI additions. This packet qualifies the current loader/measurement method; it does not relabel earlier measurements or certify whole-app performance.
