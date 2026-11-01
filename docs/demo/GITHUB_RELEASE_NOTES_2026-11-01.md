# GitHub local-release handoff — November 1, 2026

## Public entry point

The repository is already public. The main README now leads with the local
sample, teaching, unfamiliar-data work, artifacts and durable restart/resume.
Hosted deployment is separate and remains outside this handoff.

The recommended reproducible snapshot remains
`successor-first-use-2026-11-01`. The immutable historical acceptance tag remains
`accepted-local-2026-11-01-90pct`; its known budget defect and repaired successor
are documented in the [acceptance record](../acceptance/VERIFIER_ACCEPTANCE_2026-11-01.md).
Neither tag was moved for this documentation integration.

## Integration and verification

- Integration base: GitHub `main` at `b5bab9e02`.
- Successor merged: `successor/first-use-polish-2026-11-01` at `87147d5cc`.
- Merge completed without conflicts; upstream chat/session changes were retained.
- Focused checks on the integrated checkout: **63 passed** (61 executor tests
  and the two public-route cancellation tests), using isolated scratch stores.
- Both launchers and setup script pass `bash -n`; the sample target was checked
  with `make -n sample` without running an external effect.
- New relative links in the edited public documentation resolve locally.
- The accepted **97-entry evidence manifest** is byte-identical to the accepted
  tag, and every referenced file matches its recorded hash and byte count.

This integration check does not requalify all 123 claims, repeat the historical
two-hour run, certify hosted deployment or run another live send. The accepted
111/123 milestone remains bound to its recorded sources and configurations.

## Public documentation updated

- Main README: outcome-led description, complete sample path, screenshot,
  measured timing, release references and explicit scope.
- Canonical quick start and older quick-start entry point: one consistent local
  setup, login, sample, port override and restart/data-preservation procedure.
- Docs hub, indexes, first steps, installation and troubleshooting: route new
  users to the verified workflow rather than stale setup promises.
- Architecture and feature catalogs: distinguish implemented architecture from
  tested qualification.
- Contributor guide: reproduce the sample and preserve scratch-store safety.
- Demo guide and marketing copy: no unsupported benchmark, pricing, competitor
  superiority or universal-reliability claims.

## Measurement and scope

First use was measured at approximately **5 min 15 s with warm package caches**
on one host. Fifteen minutes is a cold-install target, not a guarantee.
The later memory-path smoke is a separate focused check, not a repeat of the
installation journey. See the [first-use record](FIRST_USE_TEST_2026-11-01.md).

The sample performs local read/calculation/document work. Controlled effects,
the separately authorized Outlook send and Microsoft read-only qualification,
and unqualified connector/live-send breadth remain distinct. Deterministic
taught policy is not evidence of qualified discretionary-model judgment.
