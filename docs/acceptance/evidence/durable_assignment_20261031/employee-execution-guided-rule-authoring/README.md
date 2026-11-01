# Guided deterministic-rule authoring — ordinary UI

**Result: passed** on clean source `bc164fb96632` (`dirty=false`, PID 77558).

This exercises rule authoring without typing manifest JSON. The canvas
capability panel now has a guided editor:

- choose the subject / measure / status columns from the bound CSV;
- choose optional editable fields;
- choose the decision labels (REVIEW is the required fallback);
- add ordered rules, each with a decision, conditions (field, operator,
  value), and a basis;
- save through the existing manifest endpoint, so the server validator is the
  authority; the raw JSON editor remains under **Advanced**.

## Executed workflow

1. created a blank canvas through the normal UI and attached an employee;
2. enabled table operations and bound `capability.csv` through the panel;
3. mapped `Ref / Amount / Status`, marked `Amount` and `Status` editable;
4. built three rules with selects and inputs only:
   - `DENY` when `Status is Closed`;
   - `APPROVE` when `Status is Open` and `Amount is at least 100`;
   - `REVIEW` when `Status is Open`, `Amount is at least 50` and `Amount is at
     most 99`;
5. left the policy summary blank; the UI generated it from the rules;
6. saved: no validation error, and effective operations became
   `assess, bind, calculate, edit, export, read, select`;
7. assessed: `served_provider=deterministic`, decisions
   `D-1 APPROVE / D-2 REVIEW / D-3 DENY`;
8. approved the exact assessment and used the decisions.

`result.json` has the 13 checks, the persisted manifest and the serving
identity; `manifest.json` is the server-accepted manifest; `guided-rules.png`
shows the editor and the authorized decisions. The script is
`scripts/acceptance/guided_rule_authoring_smoke.py`.

## Boundary

The guided editor covers the supported rule vocabulary (the same ops the
validator accepts). Arbitrary prose policy interpretation and discretionary
model judgment remain outside this path.
