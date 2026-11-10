# Compatibility negative (honest classification)

The fix intentionally corrects a precedence mismatch, so it is not a
zero-impact change:

1. **Existing unit expectation changed.** `test_email_canvas_service_draft_details`
   previously asserted draft-first for a `details` dict that carried a
   top-level `subject` ("Outer subject") and a nested draft subject ("Draft
   subject"). The corrected contract follows the read side: a present
   canonical top-level key wins. That test now uses a legacy-only draft
   (no top-level composer keys) for the legacy-positive case, and new tests
   pin top-level-wins and explicit-empty behavior.
2. **Callers that pass a details dict with a top-level canvas `subject` and a
   divergent draft subject will now see the top-level subject.** This is the
   intended contract correction, but it is a compatibility change for any
   out-of-repo caller that relied on the old draft-first behavior. In-repo
   callers were traced: the read view (`_email_visible_view`), native draft
   save (`_native_email_content`), chat draft coercion, canvas CRUD, and the
   acceptance trial helper all pass canonical content, not a canvas-title
   dict with a conflicting draft.
3. **Read fallback behavior change.** A content-bearing audit with a
   present-but-empty canonical body/subject/to/cc no longer falls back to
   stale `details.draft`. The legacy Canvas-row bridge (no content-bearing
   audit) is retained. Any external consumer that relied on an empty
   canonical body being filled from draft metadata now gets the explicit
   empty value — the root-authorized contract.

Preserved positive: content with only a legacy nested draft (no canonical
top-level keys) still resolves to the draft values, with `draft_id` and
provenance preserved and idempotent normalization.
