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
non-empty unresolved requirement; no gap is approved.

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
