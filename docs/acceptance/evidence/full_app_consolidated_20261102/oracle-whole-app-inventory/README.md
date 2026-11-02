# Whole-app ORACLE mutation-surface inventory

Source: `2b5db4b985cada1baf3edc0b554227f44d9b7b2d`

This is a static matrix, not a qualification run. It records where mutations exist and where an independent postcondition verifier is registered.

## Registered actions

- Total registered actions: **90**
- External/provider mutation actions: **6** (6 covered)
- Local durable-state mutation actions: **9** (2 covered)
- Read/other actions: **75**

## HTTP and provider surfaces

- Mutating HTTP routes (POST/PUT/PATCH/DELETE) under `api/` and `integrations/`: **827**
- High-risk route names/paths: **366**
- Provider-adapter write methods: **311**

## Covered external mutations

- `brennan.books.create_bill`
- `brennan.books.create_estimate`
- `brennan.outlook.create_draft`
- `connected.books.create_bill`
- `connected.books.create_estimate`
- `connected.outlook.create_draft`

## Uncovered registered mutations

- `canvas.present_chart`
- `canvas.restore_version`
- `canvas.update`
- `goal_runs.start`
- `goals.create`
- `goals.decompose`
- `goals.evaluate`

## Highest-priority next verifiers

- canvas.update / canvas.restore_version: compare persisted content revision/hash against the authorized mutation and reject stale or different-object writes.
- canvas.present_markdown / canvas.present_chart: verify the audit record and returned canvas identity, not only the broadcast.
- goals.create / goal_runs.start: verify the persisted goal/run identity and state before dependent work continues.
- goals.decompose / goals.evaluate: verify the persisted plan or evaluation revision and its source/goal binding.
- Provider send/connect/disconnect/refresh routes: require explicit operation identity and authoritative readback before claiming success.

## Boundary

This inventory does not close ORACLE-01's whole-app promise. It shows why the six connected action classes cannot be treated as every mutation surface: hundreds of HTTP mutation routes and many provider write methods sit outside that registry.
