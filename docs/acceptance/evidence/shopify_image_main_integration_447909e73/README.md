# Image-content receipt — main integration checkpoint

**Status:** integration/evidence checkpoint. No live provider, CDN/image,
model, server, browser, account, credential, spend, send or install was used.
Only Shopify Admin HTTP and provider asset HTTP leaves are doubled. The root
capture and fulfillment/next-family worktrees were not touched.

## Exact source and merge

- **Merge head:** `447909e73ba9f7fd979b4e8a78e096cbf48119cc`
- **Parents:** `b9093b7b6` (delivered image evidence) and `2d251acdf`
  (current `origin/main`, Article PR746 merged).
- **Tested source:** `6cf37cb7d` — the source on which the decisive image,
  product and article controls were run and which root independently accepted
  (33 passed, exit 0).
- Normal `git merge`, no force and no rebase. History is preserved.

### Real conflicts / semantic duplicates

- `.github/workflows/ci.yml`: both sides added test entries. Resolved as the
  union; the only content change is main's two Article REST test entries.
- `backend/core/oracle/postcondition_verifiers.py`: the blog verifier existed
  identically on both sides, so the merge inserted it twice. The duplicate
  main-side block was dropped; the identical existing block remains.
- `backend/core/shopify_mutations.py`: the blog/article implementation was
  auto-merged as two byte-identical copies of eleven functions. The later
  copies were removed, leaving one copy exactly equal to main and to the
  tested source. No function body was changed.
- Image proof, product image verification, qualifiers and SSRF controls are
  retained unchanged.

### Base retarget

PR #748 is retargeted from `codex/shopify-article-rest-shape-20261107` to
`main` with a normal `gh pr edit`; the prerequisite is already merged. A base
edit alone does not trigger the default workflows, so this actual integration
checkpoint is pushed to start a fresh CI run against main.

## Why no gate was re-run

The seven runtime files are **byte-identical** across the tested source
`6cf37cb7d`, the delivered evidence head `b9093b7b6`, and this merge head
`447909e73`:

- `backend/core/asset_content_receipt.py`
- `backend/core/shopify_mutations.py`
- `backend/integrations/shopify_service.py`
- `backend/core/oracle/postcondition_verifiers.py`
- `backend/core/action_registry.py`
- `backend/core/connected_actions.py`
- `backend/core/oracle/request_expectations.py`

The image/SSRF tests are identical too. Runtime bytes did not change, so the
completed gates were not repeated merely because the base/evidence changed.
Proof: `runtime-identity.json` and `merge-runtime-identity.log`.

## Preserved boundaries

- Root verified image usability repair: 33 passed, exit 0
  (`root-image-usability-verified.log`).
- Root original unexplained failure preserved: 3 failed / 11 passed
  (`root-usable-image-negative.log`).
- Real decode, 40MP pre-decode bound, bomb refusal, MIME/format/dimension
  binding, qualifier preservation, replay by-id/content proof, SSRF allowlist
  and pinned no-redirect reads remain in force.
- Raw URL-only images remain **OPEN/unverified**; provider transforms remain
  **unknown/unverified**.

## Handoff

See `HANDOFF.md`. Agent2 fulfillment owns a separate worktree and must
rebase/review the shared Shopify/Oracle files. Root independently reviews this
worktree after handoff; no new family is started here.
