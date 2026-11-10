# Existing-mechanism reuse decision

No new architectural choice was introduced; the export action composes
existing Atom mechanisms.

- `core/workflow_endpoints.py` already owns the durable execution detail read,
  generated read-scope/owner authorization, and the generated source of truth
  (`WorkflowExecution.outputs` + `Workflow` compiled steps). The new route is a
  thin read projection over those.
- `backend/api/assignment_routes.py` (`download_assignment_deliverable`) is the
  existing safe artifact-delivery pattern: resolve/allow the artifact, never
  expose a local path, return an attachment response. The export follows the
  same response discipline, but derives bytes from the durable execution row
  rather than a filesystem artifact.
- `frontend-nextjs/pages/documents/[docId].tsx` is the existing user-visible
  blob-download UX: fetch blob, safe filename, create/revoke object URL, inline
  error. Execution Details reuses that transport/UX pattern.
- `backend/api/workflow_template_routes.py` exposes execution step results as
  JSON; the export endpoint adds a supported downloadable projection without
  changing that read response or introducing a second result store.

No Camunda/other framework or external doc-generation dependency was added.
Definition/instance lifecycle distinction remains the same as the prior
workflow handoff work.
