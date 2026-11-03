# G5 two-domain probe — frozen source 80e3bd702

Status: **served quote work request passed; the two-domain campaign is blocked
at procurement evidence selection. G5 adaptive employee capability remains
unqualified.**

## Source and environment

| Item | Value |
|---|---|
| Branch | `codex/brennan-full-app-20261102` |
| Product source | `80e3bd702dc7e07d921f8082a20ab06926a062a6` |
| Worktree | clean detached worktree at `/private/tmp/atom-g5-clean` |
| Local model | `ollama/llama3.1:8b` at `127.0.0.1:11436/v1` |
| Policy | `ATOM_LLM_PROVIDER_POLICY` pinned to `ollama` for the scratch run |
| Transport | controlled local service/DB; no cloud/live provider |

The scratch service DB does not carry the installation `runtime_settings`
row, so the policy was supplied through the documented environment override.
That is configuration only; no product code or model was replaced.

## Served quote smoke — passed

The model selected `price-workbook` for the industrial quote, then returned a
valid `WorkAdaptationProposal` with a typed `quote_calculation` request:

- source step `read`;
- columns `Item` / `Qty` / `Price`;
- currency `USD`;
- freight term `freight` = `20.00`;
- tax term `tax_basis` = `none`.

The deterministic compiler issued the two calculation steps, the executor
adopted and completed them, and the calculated total was **370.00**. The exact
prompt, parsed response and raw provider completion are in
`served-quote-smoke-calls.jsonl`; the attempt journal is in
`served-quote-smoke-attempts.jsonl` under one attempt ID.

## Two-domain evidence selection — industrial pass, procurement negative

`two-domain-evidence-report.json` and `two-domain-evidence-calls.jsonl` preserve
the two held-out contexts from the existing evidence-selection probe.

| Domain | Result |
|---|---|
| Industrial quote | model source; selected `price-workbook`, `terms-agreement`, `customer-record`, `equivalence-record` |
| Procurement / bookkeeping | **negative**; parsed proposal mixed `source_id=receiving-records` with `action=calculate` and omitted `invoice-v1`; production validation rejected it and the deterministic floor selected only `purchase-order` |

The procurement failure is a model-semantic failure, not a transport failure:
the call returned a parsed `EmployeeWorkProposal` in 43.39 seconds. The
production validator correctly refused the mixed source/action read. No
retry, model switch or larger-model action was taken.

Because the invoice source was not selected, the invoice reconciliation,
corrected-invoice wait and supported bill stages were not run. The full
two-domain ordinary-product campaign is therefore **not** established.

## Deterministic mechanism campaign — passed

On the same frozen source, the existing two-domain mechanism campaign passed
**4/4** (`frozen-source-campaign.log`): changed quantities, governing price
revision, infeasible/approved delivery, invoice wait and correction, supported
bill preparation and period-close refusal. This is mechanism evidence only;
it is not a served-model adaptive result.

## Frozen-source controls

- Independent verifier probes: **20 passed**
  (`frozen-source-probes.log`).
- Focused typed-work/proof/adaptation/executor suite: **124 passed**
  (`frozen-source-focused.log`).

## Boundaries

No cloud provider, credential, consent, send, spend or deployment was used.
The prior deterministic acceptance at `28afe7248` remains intact; historical
`111/123`, planner `5/5`, goal router `1/2` and alignment gap `3.0` are
unchanged. The clean-worktree rerun with the default provider policy (no
environment override) returned `None` immediately because the scratch DB
lacked `runtime_settings`; that run is not counted as a model result.
