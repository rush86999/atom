Updated only `frontend-nextjs/lib/canvasAuditSave.ts`.

## Proposed implementation

- **Added `CanvasAuditReceipt`**
  - `auditId: string` — required exact, non-empty server value.
  - `operationId?: string` — included only when the server supplies a canonical opaque value.

- **Added shared transport `putCanvasAudit`**
  - One implementation for URL construction, explicit `JSON.stringify(content)`, `Content-Type: application/json`, `retry: false`, legacy-404 detection, status validation, and exact-canvas verification.
  - Returns `null` only for a genuine legacy 404; all other unconfirmed outcomes throw the existing `CanvasAuditSaveError`.
  - Adds `expected_prior_audit_id` via `encodeURIComponent` only when `expectedPriorAuditId !== undefined`. No trimming, coercion, counter inference, or aliasing.

- **Preserved `saveCanvasAudit`**
  - Same arguments and `Promise<boolean>` contract.
  - Returns `true` for any exact-canvas verified response, including legacy responses without `audit_id`.
  - No extra request is made to obtain a receipt.
  - Genuine legacy 404 still returns `false`.

- **Added `saveCanvasAuditReceipt`**
  - Same arguments as `saveCanvasAudit`, plus `retype` and `expectedPriorAuditId`.
  - Returns `CanvasAuditReceipt | null`; `null` only for genuine legacy 404.
  - Requires the same verified response checks **and** an exact non-empty `audit_id`; otherwise throws `CanvasAuditSaveError`.

- **Legacy exports/error behavior retained**
  - `CanvasAuditSaveErrorDetails`, `CanvasAuditSaveError`, and `saveCanvasAudit` remain exported with the same error class, code, retryability, and safe field handling.

## Limitations for root review

- No type-check, test, build, or runtime verification was run, per the no-shell/test constraint.
- The backend is assumed to return top-level `audit_id` / `operation_id` fields and honor the `expected_prior_audit_id` query parameter; this was not validated.
- Receipt extraction intentionally does not inspect nested objects, aliases, numbers, or trimmed strings.
- An explicitly supplied empty-string `expectedPriorAuditId` is treated as “provided” because only `undefined` is considered absent; it is encoded as an empty query value rather than coerced.
- `saveCanvasAudit` is semantically unchanged, but its transport now flows through the shared helper; root should confirm the refactor preserves any call-site assumptions.
