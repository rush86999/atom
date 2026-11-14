/**
 * Pure Active Sessions selection helpers for the WA-075 replay.
 *
 * A signed-in scratch run has more than one non-current row: the driver mints
 * a bootstrap bearer with `POST /api/auth/login` before it opens a browser,
 * and that login is registered in the same session inventory as the form
 * sign-ins. The primary page therefore shows the bootstrap row *and* the
 * disposable secondary row as revocable.
 *
 * Selecting "the only revocable row", or clicking the first Revoke button,
 * can therefore revoke the wrong session. The disposable row is identified
 * from the secondary's OWN authenticated list (`is_current`), then addressed
 * by its exact id on the primary page. Nothing here performs I/O, so the
 * selection rule is regression-testable without a browser.
 */

function usableRows(rows) {
  return Array.isArray(rows)
    ? rows.filter((row) => row && typeof row.id === "string")
    : [];
}

/** The one row a bearer authenticates as, or null if it is not unambiguous. */
export function ownCurrentSession(rows) {
  const current = usableRows(rows).filter((row) => row.is_current === true);
  return current.length === 1 ? current[0] : null;
}

/** Rows the primary page renders with a Revoke control (everything but its own). */
export function revocableRows(rows) {
  return usableRows(rows).filter((row) => row.is_current !== true);
}

/**
 * Resolve the disposable secondary to the exact Revoke control on the primary
 * page. `secondaryRows` must come from the secondary's own bearer and
 * `primaryRows` from the primary's, so each side's `is_current` is meaningful.
 */
export function selectDisposableSession({ secondaryRows, primaryRows } = {}) {
  const own = ownCurrentSession(secondaryRows);
  if (!own) {
    return {
      ok: false,
      reason: "the secondary's own session list did not identify exactly one current row",
    };
  }
  const controlIndex = revocableRows(primaryRows)
    .findIndex((row) => row.id === own.id);
  if (controlIndex < 0) {
    return {
      ok: false,
      reason: `the secondary session ${own.id} is not a revocable row on the primary page`,
    };
  }
  return { ok: true, id: own.id, controlIndex, row: own };
}
