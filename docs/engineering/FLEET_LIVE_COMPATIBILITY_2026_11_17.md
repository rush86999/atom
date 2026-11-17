# Live fleet case 7 — failed workflow, bounded direct response

**Fleet result: FAILED.** One owner-approved synthetic run used product source
`0e9b0dfc9c7ee41b047714c1e1a5fc8a1f2bb464`. It did not establish completed
specialists, chain completion or fleet synthesis. Neither controller exit 0
nor chat HTTP 200 is workflow acceptance. The original 143 claims / 18 goals
remain incomplete.

The guarded run made 14 actual upstream requests within its 16-request cap;
13 structured-stage requests returned HTTP 400, and one plain reply returned
HTTP 200 with served identity `deepseek-v4.1-flash` and finish reason `stop`.
The local guard admitted 16 model calls and rejected another; admissions are
not the same as actual upstream sends. Every output request stayed within the
8,000-token ceiling. The one-shot allowance is consumed; no automatic rerun or
billing/Extra Usage change followed. Owned processes, process group and test
ports were independently verified absent, and the output pump drained.

Manual review of the direct response found the supplied USD 100 closed revenue,
USD 200 pipeline and USD 250 target, USD 150 gap, 40% attainment, and the caveat
that pipeline is not booked revenue. Literal verifier checks missed formatting
such as `USD 100` versus `USD100`. This narrow observation does not turn the
failed fleet run into a quality benchmark or a completed delegation.

The exact upstream 400 cause is **unknown**: response error bodies were not
retained. Captured request shapes included forced named tool choices without
an explicit native thinking setting, optional log probabilities, and an
OpenRouter-style reasoning extension; a JSON-mode planner also failed. There
was no `json_schema` request in this run. Native DeepSeek documents its thinking
and forced-tool restrictions, but that contract alone does not establish the
OpenCode Go gateway's mode or explain these specific errors.
[DeepSeek Chat Completions contract](https://api-docs.deepseek.com/api/create-chat-completion/).

A verifier limitation was identified after the run: upstream HTTP 400 was
recorded but rewrapped as generic HTTP 502 before Atom saw it, hiding the
signal from Atom's existing compatibility recovery. Therefore this run does
not prove that production recovery is broken. A separate offline verifier copy
preserves the status and narrowly normalized compatibility messages without
forwarding raw error bodies. That repair and the product investigation are
not a fresh live pass. The original failed artifacts remain unchanged.

The orchestrator returned its final report through sanitized output instead
of writing the configured result file. Root extracted exactly one final
report for independent adjudication; it did not infer success from an absent
file or rerun the task. Fresh source/configuration checks and new explicit
allowance are required before another live model test.
[Filtered failed-run result](evidence/fleet_case7_20261117/result.json).

A separately approved [case 8](FLEET_LIVE_DELEGATION_2026_11_17.md) later
recovered an optional-logprob rejection on merged main, then failed fleet
acceptance because it chose direct conversation. It does not establish the
original case7 error cause or retroactively change this failed result.
