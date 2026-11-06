# NULL/empty scope precision — docs-only follow-up

This note corrects the wording of the accepted atomic-scope bundle
`oracle01_direct_canvas_82ac9681a_atomic_scope/` without changing the accepted
canvas source or evidence hashes.

The accepted implementation normalizes the expected scope with `or ""` before
building the CAS predicates. Therefore:

- **NULL and empty string are equivalent legacy-unscoped states.** They are not
  distinguished by the guarded write.
- Foreign effective-scope moves and moves between legacy-unscoped and a
  non-equivalent real/`default` scope are fenced by the guarded DML.
- A tested NULL -> literal `default` move refuses correctly. A NULL <-> empty
  move is **not** an established zero-match guarantee.
- If exact raw-representation fencing is later required, preserve the raw
  nullable values in the snapshot and use `IS NULL` versus `= ""` explicitly.
  That is a small future tightening, not part of this accepted authorization
  repair.

The accepted 22 source/artifact hashes remain the authority for the accepted
canvas bundle; this note is additive and does not rewrite them.
