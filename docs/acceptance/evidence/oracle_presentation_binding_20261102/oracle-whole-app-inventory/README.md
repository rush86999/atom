# Whole-app ORACLE mutation-surface inventory

Source: `0d8767e3ac2494dd7a4b88ffc790f898035e8586`

This is a static matrix, not a qualification run. It records where mutations exist and where an independent postcondition verifier is registered.

## Registered actions

- Total registered actions: **90**
- External/provider mutation actions: **6** (6 covered)
- Local durable-state mutation actions: **8** (8 covered)
- Plan-output validators: **1** (1 covered; structural, not persisted execution proof)
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

- none

## Highest-priority next verifiers

- Map the 827 mutation-shaped HTTP declarations to actually reachable write consumers; group them by effect family instead of adding a bespoke checker per route.
- Provider send/connect/disconnect/refresh routes: require explicit operation identity and authoritative readback before claiming success.
- Plan-output validation remains structural; add persistence postconditions only where the action actually persists a plan or evaluation.

## Boundary

This inventory does not close ORACLE-01's whole-app promise. It shows why the six connected action classes cannot be treated as every mutation surface: hundreds of HTTP mutation routes and many provider write methods sit outside that registry.
