# Independent regression baseline comparison

The lead ran the 18 existing affected files at source `a08ce72f0`, whose tree exactly matches merged main `8a577f14a`: **711 passed, 9 failed**. Agent 1's retained broader run at `b0a1f538a` includes two additional contract/journey files: **761 passed, the same 9 failed**. The failure IDs match exactly, with no new or cleared failures. The lead also independently ran 196 focused candidate controls, all passing.

This proves the recorded baseline classification. It does not make the broader run all green or qualify whole-app ORACLE. The baseline uses its own tracked tests; the candidate's fixture changes and two new files were not copied into it. Both runs use Python 3.14 with different installed environments (project virtual environment versus system Python). This is not an identical-environment performance comparison.

- `run-spec.json` records the baseline command and the original test blobs.
- `comparison.json` records both observed failure lists.
- `baseline-sanitized.log` derives from the retained raw lead capture using the merged log redactor and path substitutions. Its failure IDs are preserved. The original remains private and unchanged.

These controls use scratch SQLite. They do not qualify model/provider behavior, guest execution, live accounts or deployment. The earlier 11-failure record at `bb807d62d` remains unchanged at its original source.

The lead then integrated accepted main `6d791db46` into the registry branch at `bfdc49404`. The CI-only conflict was resolved by retaining every previous step and including both the goal-write and ORACLE gates exactly once. The combined committed runtime passed **227 controls, with 3 documented same-kind nullable-matrix skips**. `combined-sanitized.log` records that new run. The earlier `b0a1f538a` measurements were not relabeled.

The runtime tree was tracked and committed at qualification. Bootstrap/order/probe files were untracked, so this is not an assertion of a completely clean working tree. The supplied independent probes used in the run are now copied byte-for-byte into `independent-probes/`; they were not tracked at the runtime source. This later evidence commit preserves their exact controls and makes that distinction explicit. No runtime source changed while the gate ran.
