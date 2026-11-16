# Atomic, authorized Activity checkpoint decisions — November 16, 2026

A stale approval could mark its HITL record approved after a run was cancelled,
then return HTTP 200 with `resumed:false`. Activity could announce a resume
that never happened. The repair claims the pending checkpoint and the run's
exact current wait in one transaction; a stale or losing peer decision has no
approval, wait, plan, cursor or successor-dispatch effect.

A whole-caller audit also found governance approval accepted a foreign-workspace
team lead. Reviewer authority now belongs to the shared atomic claim: a real,
currently active actor in the exact canonical tenant/workspace must be the run
owner or an allowed supervisor and satisfy every persisted role requirement.
Personal Edition NULL/default scope remains equivalent. A conditional actor-row
write fences peer deactivation, role changes and scope moves before effects.
Activity, both approval aliases, the HITL bridge and InterventionService all
reach this claim. Scope refusal returns 404, insufficient authority 403 and
stale/changed authority 409; none is a false 200 or swallowed HTTP 500.

Ordinary non-checkpoint intervention decisions use the same existing RBAC
machinery to enforce BOTH the role column and governance snapshot. A lower
column must not override a stricter snapshot, and an unknown role fails closed
in either location. Two-factor action verification reuses that check rather
than repeating a separate column-only policy. No new registry or table was
added. These are cross-caller behavior changes, not an Activity-only gate.

## Final source and independent verification

[The sanitized receipt](evidence/activity_checkpoint_20261116/result.json) is
bound to final product source `1f70c17080084d0e25ed917a43f94d11fea2b14d`,
including authority repair `d5e8208f0`. Independent scratch/network-denied
checks passed: **118** checkpoint/approval/route controls, **27** active
intervention controls, **18** two-factor write controls and **71** authority
neighbors (**234 total**). These include valid twins, foreign tenant/workspace,
inactive/missing actors, owner/supervisor membership, persisted role policy,
peer revocation/move and Personal NULL/default cases. The original mounted
foreign-governance counter now returns 404 with HITL pending, reviewer NULL and
run waiting. A separate real-actor role counter now refuses a team lead when
the column is member but the existing snapshot requires admin.

The complete tracked frontend tree is unchanged from `c8dd2d381`, where root
independently passed **68 frontend tests** and built the production frontend.
That identical build was reused at the same API origin. The prior **644**
workflow/wire-format controls remain bound to C8; root verified workflow and
inventory bytes unchanged through the final product source. Newly added role
regressions are in an already-selected complete test file. All prior CI gates
remain required.

## Ordinary browser boundary and restart

On the final source, a fresh isolated world and normal form login produced a
real matching web session. The owner used native Approve and Reject once each
on separate synthetic checkpoint runs. Both returned 200 with `resumed:true`,
real persisted HITL decisions and achieved runs. Both API and frontend were
stopped and restarted against the same populated world. A fresh browser login
read both completed runs without any goal mutation, and read-only SQL verified
both decision rows. Unsigned API access returned 401 and unsigned page access
showed login with the exact return path. All owned app processes were stopped.

The fixture goals were deliberately already achieved. The actual goal evaluator
therefore terminated before model routing. This qualifies authorization,
dispatch and persistence; it does not prove model competence or completed agent
work. The source health correctly reported the three root draft documents as
dirty; backend/frontend/workflow source was separately verified clean and pinned.

## Earlier source-bound evidence and retained failures

At `2df00347f`, normal browser login exercised Activity list/result/failure/wait
timelines, a real Cancel, stale-tab 409 without changing the pending HITL,
valid decisions and exact readback of six fixture records after full restart.
At `c8dd2d381`, a fresh stale-request episode also verified the actual visible
production error message and absence of a false success toast. The shared API
error reader accepts production top-level `error.code/message`, bare FastAPI
`detail.error`, legacy strings and safe malformed fallbacks. Those earlier
worlds retain their original sources; they are not relabeled as final-source
proof or replayed.

C8 still accepted the foreign governance reviewer; root held it until repaired.
The first authority draft then weakened non-checkpoint snapshot role policy;
root held that draft too until the shared-policy fix passed the independent
counter. Earlier Welcome/preflight/response-envelope diagnostics remain
retained. Four historical legacy suites compared at C8 and matched-main source
had the same 19 failures/245 passes; that is explicitly not a passing suite or
qualification of the later authority changes. No check was skipped to merge.

The original **143 claims / 18 goals** and `app_complete: false` remain intact.
Broader model work, every integration approval surface and PostgreSQL
concurrency still require their own acceptance evidence.
