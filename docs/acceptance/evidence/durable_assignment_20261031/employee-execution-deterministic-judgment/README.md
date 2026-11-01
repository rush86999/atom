# Deterministic substantive judgment — qualified for rule-expressible policies

This bundle qualifies a usable substantive-judgment configuration that does
**not** depend on a language model. It is deliberately separate from the failed
model qualification.

## Configuration

- mode: `deterministic`
- provider/model: **none**
- engine: `core.assessment_rules`
- rules: versioned `decision_rules` on the canvas capability manifest
- scope: policies that can be expressed as ordered field/operator rules

Rules are evaluated in manifest order; the first fully matching rule wins.
Missing or unparseable values cannot satisfy a rule. If no rule matches, the
fallback is `REVIEW` with a durable unresolved requirement. The platform still
requires human review by default (`ATOM_ASSESSMENT_REVIEW_POLICY=always`) and
binds approval to the exact assessment artifact.

## Frozen-set result

The frozen 24-record set was evaluated under both policies with the existing
safe-abstention judge:

| Phase | Determinate accuracy | Safe abstention | Verdict |
|---|---:|---|---|
| V1 / create | **18/18 (1.0)** | passed | passed |
| V3 / correct | **18/18 (1.0)** | passed | passed |

Gap inputs (blank Amount/Status/Risk, 99.99, 49.99, 0) return `REVIEW` plus a
non-empty unresolved requirement; no gap is approved. Higher-priority rules
that remain unknown are all retained: if any could change the decision, the
result is clarification rather than a later rule's confident answer.

`deterministic-qualification.json` contains the decisions, rules, mismatches
and judge output. `deterministic-judgment.log`: **4 passed** (canvas rule
integration + frozen qualification).

## Separation from model judgment

The model-dependent configuration remains **failed and unqualified**:

- local `ollama`/`llama3.1:8b`: 17/18 on V1 and 18/19 on V3/post-restart;
- stable Q-021 review and false `APPROVE` on Q-012.

No claim is made that arbitrary natural-language policy text can be converted
to rules automatically. Authoring the rules is an explicit human/teaching
action. Model-dependent judgment, live sending, multi-worker execution and
universal reliability remain out of scope.

## Corrected semantics and current qualification contract (2026-10-31)

Four defects were reproduced and repaired:

1. **Three-valued conditions** — a rule is false only when a condition is
   definitively false; missing or malformed input makes it *unknown*. A later
   matching rule no longer wins over an earlier unknown rule with a different
   decision; the result is clarification with the earlier field preserved.
2. **Value normalization** — `0` is a value, not a blank. Non-finite input
   (`NaN`, `Infinity`) and malformed numerics are rejected before comparison and
   surface as an unresolved invalid-input result, not an exception.
3. **Rules follow the taught policy** — the defensive V3 “blank Risk → REVIEW”
   rule was removed. V3 says “regardless of Risk”, so a blank Risk must not
   abstain.
4. **Current scoring contract** — the qualification now applies the hash-bound
   phase-aware V2 overlay: **18 determinate cases under V1 and 19 under V3**,
   plus safe abstention.

Reproduced result on the frozen set:

| Phase | Determinate | Accuracy | Safe abstention |
|---|---:|---:|---|
| V1 / create | 18 | 1.0 | passed |
| V3 / correct | 19 | 1.0 | passed |

The previous 18/18 V3 result used the old scoring interpretation and is
preserved as `deterministic-qualification.superseded.json`; it is superseded,
not deleted.

Negative twins: earlier unknown vs later conflicting match → clarification;
zero matched by a zero rule; `NaN` → explicit unresolved invalid input; V3
blank Risk → APPROVE. The frozen set also runs through the canvas assessment
boundary in `test_assessment_rules_semantics.py` (19/19 determinate, every gap
REVIEW with a preserved requirement).

## Multiple higher-priority unknowns (2026-10-31)

The verifier reproduced the remaining precedence bypass:

1. `Region = North → APPROVE`
2. `Risk = High → DENY`
3. `Amount >= 100 → APPROVE`

With Region and Risk missing and Amount 120, the evaluator kept only the first
unknown rule, saw its decision (APPROVE) match the later one, and returned
APPROVE with no requirement. Valid completions disagree: South+High gives DENY,
North+High gives APPROVE.

Repair: every higher-priority unknown rule is retained until a definite match. A
definite match decides only when no retained possibility has a different
decision; otherwise the result is REVIEW with the decisive fields preserved.
Repeated labels do not force clarification; a definitively false conjunction is
false even with another unknown condition.

Controls: the exact three-rule case, repeated labels, false conjunction, an
irrelevant missing field, and a completion-based table test that enumerates
fully specified completions — if they disagree, a confident partial result
fails the control.
