# Deterministic rule authoring through the ordinary UI

This bundle records deterministic-rule authoring through the **normal canvas
capability panel**, not a developer-installed manifest file.

## Executed workflow

On clean source `31ba9725e02a` (`dirty=false`, PID 67158):

1. signed in to the normal app and opened an employee canvas through
   **Agents → Teach**;
2. opened the canvas **capability panel** and replaced the manifest with a
   table manifest containing three ordered `decision_rules`:
   - `DENY` when `Status = Closed`;
   - `APPROVE` when `Status = Open` and `Amount >= 100`;
   - `REVIEW` when `Status = Open` and `Amount` is 50–99;
3. bound `capability.csv` through the panel's file binding;
4. ran **Assess**. The response served
   `route.served_provider=deterministic` and returned
   `D-1 APPROVE / D-2 REVIEW / D-3 DENY`, each with its rule basis
   (`result.json`);
5. the assessment was a draft (`authorized=false`) until the exact-content
   approval button was used; the panel then showed the authorized assessment
   and the decisions could be used;
6. no page errors were recorded.

`manifest-authoring.json` is the exact manifest entered in the panel;
`screenshot.png` is the panel after assessment/decision use.

## Boundary

Deterministic rules apply only to rule-expressible policies. Model-dependent
substantive judgment remains unqualified and is not represented by this
evidence.
