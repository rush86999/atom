# WA-045 connected-browser evidence — canvas save and reopen

This package records one signed-in browser transition on the WA-045 scratch
world, captured from the adjacent WA-045 worker run and its backend access log.
It is deliberately narrow: it proves that a specific canvas artifact was edited,
saved with HTTP 200, reopened, and read back with the exact multiline body.

- **Artifact:** `cbf43d3b-47d5-40a7-aabf-db3e7c3a42a9` (`document`,
  "Untitled canvas")
- **Source revision:** `8bb0c66f5fd30988c16585214707bf784fa39d41`
  (`8bb0c66f5`), confirmed by the backend `/health` identity with
  `identity_kind=git` and `dirty=false`
- **Save:** `PUT /api/canvas/{id}` → `200`, bound to the prior revision
  `413b4219-2aed-4060-8ca4-c573bdf6c70c`
- **Reopen:** the same `/canvas/{id}` URL reloaded; the editor model and the
  backend read-back both return the exact body below
- **Text:** 3 lines, 103 characters,
  sha256 `22171224cd4b9d7e87b4cdeb64a04b14415e1afd10e11fb0ffa277042507b265`

```text
WA-045 exact body line one: ORD-WA045-ALPHA
Exact body line two: 17 * 3 = 51
Trailing marker: WA045-END
```

`canvas-connected-browser.json` is the artifact; this README is a human view of
the same facts.

## Environment

The run used a fresh scratch world (`backend/data/acceptance_worlds/
wa045_canvas_blank_20261113`) with its own SQLite `atom.db`, a loopback frontend
on `127.0.0.1:3177` and backend on `127.0.0.1:8177`. The scheduler and ingestion
sync workers were disabled and provider credential variables were blanked for
the backend process; no live database, backup, or live credential was read.

## CDN scope (explicit)

The only non-loopback origin observed in the browser is
`https://cdn.jsdelivr.net`, and it is static editor code:

- package/version: `monaco-editor@0.55.1`, path prefix
  `/npm/monaco-editor@0.55.1/min/vs/`
- method: `GET` only, no request bodies
- loaded by `@monaco-editor/react`'s default loader (editor core, language
  contributions, CSS and worker scripts); the exact unique asset list is in the
  evidence JSON
- no workspace data, canvas content, token, or tenant identifier is part of
  these requests; no provider or model endpoint was contacted

No other external traffic is recorded. If the Monaco loader is ever pointed at
a different origin, or a CDN request starts carrying application data, this
package no longer describes the run.

## What this does and does not prove

- **Proves:** edit → autosave `PUT` 200 → reload → exact 103-character read-back
  for the artifact above on `8bb0c66f5`.
- **Does not prove:** artifact creation (the 29/29 harness package at
  `docs/acceptance/evidence/wa045_canvas_blank_20261113/canvas-blank-lifecycle.json`
  owns the create → save → reload transition, including scratch-DB rows), and it
  is not a production-build run.
- The save path here is the panel's idle autosave. The run also waited for a
  second explicit save, which did not occur because the edit was already saved
  and no **Save Changes** control was rendered.

## Sanitization and provenance

Raw worker/backend/frontend logs stay outside the repository and are not
committed. This package keeps only allowlisted facts: ids, types, ports,
statuses, the exact synthetic body and its hash, the CDN asset paths, and the
check list. Cookies/tokens, headers, absolute paths, process ids, account
identifiers, full log lines, and generated frontend build output are excluded.

The facts were read from the adjacent worker transcript and the run's backend
access log. The product-owned harness
(`scripts/acceptance/canvas_blank_lifecycle.py`) independently re-runs the same
transition on a fresh world; use it to reproduce rather than trusting this
transcript package as a live run.
