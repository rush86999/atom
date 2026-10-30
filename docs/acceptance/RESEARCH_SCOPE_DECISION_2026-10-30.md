# Autonomous third-party research — scope decision

Status: **bounded workflow implemented and controlled-tested; live-source
qualification requires one approved read-only source.** Unrestricted autonomous
browsing remains unclaimed. No real external research call is authorized by
this document.

## What is already demonstrated

- `external.research` dispatches only registered read-only actions through the
  shared action registry, validates required result fields, and records
  retrieved content as evidence with action/arguments/time provenance.
- A missing result becomes a typed `external_research` obligation. Resolving it
  resumes the same assignment with raw evidence; teaching and authority are
  unchanged.
- Current tests cover successful retrieval, typed obligation/resume, write-action
  refusal and teaching preservation.
- Controlled external replies can wake a durable wait with exact correlation.

## Live qualification request

The implementation is complete; only an approved source is missing. Provide:

- one existing read-only source (e.g. an already-connected Microsoft mailbox,
  OneDrive/SharePoint folder, or uploaded document set);
- the exact missing fact/field and identifier/date scope;
- permission to run up to five read-only retrieval queries within 10 minutes;
- whether retrieved excerpts may remain in assignment evidence.

No new credential or write/send/purchase permission is requested. Unrestricted
browsing is explicitly deferred.
