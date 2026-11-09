## Current integration

- `persistCanvasTypeSwitch` (`frontend-nextjs/components/canvas/canvasType.ts:200-210`) still issues its own `apiClient.put` with `retype=true`, returns `void`, and does not use the verified receipt contract.
- Both hosts (`CanvasPanel.tsx:586-619`, `canvas-host.tsx:356-393`) apply the converted component/content locally **before** persistence finishes.
- Backend support already exists: `canvas_routes.py:688-761` accepts `retype`, `operation_id`, and `expected_prior_audit_id`; `canvas_write_service.update_canvas_verified` maps `manual_retype` through `canonical_update_content`.

## Risks

1. **A 200 is not proof of success.** `update_canvas_verified` can return `status: "committed_unverified"` or `"effect_unknown"` with HTTP 200. The current retype PUT resolves normally, so the UI records an unverified type change as saved.
2. **Bypassing `saveCanvasAudit` loses critical safeguards.** `persistCanvasTypeSwitch` has no explicit `JSON.stringify` (bare strings/arrays), no `retry: false`, no `canvas_id`/`verification.status` check, and no idempotency or CAS token.
3. **Optimistic local state can outlive a failed retype.** If the PUT fails or is unconfirmed, the rendered type stays changed; a later autosave can write the new type without `retype=true`, losing the pin or saving the wrong shape.
4. **No concurrency guard.** `handleTypeSwitch` reads `state` after awaiting `flushAutosave()`; the canvas may have closed or changed. No `expected_prior_audit_id` is sent, so a concurrent agent/tab edit can be overwritten.
5. **WS echo handling is fragile.** `lastSavedSigRef` is not updated for retype, and updating it optimistically would suppress the authoritative broadcast after an unknown result. Frames arriving during the pending switch can reset the converted view.

## Recommendations

1. **Add an optional options argument to `saveCanvasAudit`**, e.g. `{ retype?: boolean; operationId?: string; expectedPriorAuditId?: string }`. When `retype` is set, append `retype=true` and the optional tokens while preserving the existing JSON encoding, `retry: false`, and verified-response checks. Replace `persistCanvasTypeSwitch`’s direct PUT with this call and return a verified result/receipt.
2. **Make the switch transactional in both hosts:** capture canvas ID and prior revision/audit identity, flush pending edits, build the conversion, await `saveCanvasAudit`, and only on `true` apply `setState`, `localContentRef`, email metadata/body, and sheet data. On `false` or `CanvasAuditSaveError`, leave the rendered type/content unchanged and surface a blocked state.
3. **Block unknown effects explicitly.** Treat `effect_unknown`, `committed_unverified`, and all non-verified receipts as non-retryable: disable further switching/saving, show “check version history,” and never fall through to the legacy artifacts path. Expose `effect`/`replay` on the error if needed to distinguish this in the UI.
4. **Pass `operation_id` and `expected_prior_audit_id`** from the loaded canvas frame. If the frame only carries `version`, do not assume it is an audit ID; add the prior audit ID to the present/read payload or use another explicit CAS token. Re-check the active canvas identity after every await and abort if it changed.
5. **Guard the pending switch against WS resets.** Track a per-canvas “retype pending” token in `applyCanvasMessage`; hold or defer same-canvas content frames until the save resolves. Set `lastSavedSigRef` only after verified success, using the same signature derivation as `applyCanvasMessage`; on failure, release the guard and apply the authoritative frame rather than leaving optimistic local state.

Review only; no files changed and no tests run.
