# Live-connected assignment gate

2026-10-29: the approved Microsoft client configuration was restored to the
qualification worktree. Presence-only preflight now reports `configured=true`,
and normal token resolution reports `state=valid`, `token_available=true`,
`requires_reconnect=false`. Secret values were not printed or stored.

The live guided gate stopped at the **resource/source authority boundary**:

- The named `Consolidated Price List 2019.xlsx` / `US$ SCOTCH PARTS` catalog
  rows are `zoho_workdrive`, not Microsoft/OneDrive.
- The Zoho WorkDrive access token expired on `2026-10-24T01:41:37Z`.
- No genuine Microsoft/OneDrive catalog entry for that workbook exists.
- Cached Parquet rows were not used as a substitute.
- No replacement catalog row or grant was seeded.
- The production price list was not modified.

A reproduced defect was fixed: an `active` token row with an `expires_at` in
the past was treated as current access. It now raises `source_access_expired`;
the real-catalog control is `test_expired_access_token_is_not_current_source_access`.

No live guided start or changed-source refresh was run after this boundary.
`gate-result.json` records the exact observed state and the two permitted next
actions.
