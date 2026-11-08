# Additional two-domain caller qualification

The earlier220-test selection did not include this campaign. Independent
caller review identified a stale expectation: a different terminal answer was
labeled exact replay. Executed unchanged at da280ff17: 1 failed, 3 passed.

Test-only successor c329f295c explicitly checks both original accepted material
→ already_applied and changed material → terminal, completed state retained,
exactly one bill effect. The full campaign passes4/4 on Python3.14 and3.11.
No runtime guard was weakened. The campaign is now in the existing CI step.

Counts overlap with other work; no full-app or question/gap identity claim.
Raw negative and positive specs/exits retain their original executed sources.
No live model/provider or external effect was used.
