# Live fleet case 8 — compatibility recovery, delegation not completed

**Fleet result: FAILED.** The new, separately approved synthetic run used exact
merged main `02c9b16744e4fc9cfe7c81dce2ebf82cac7bf909`, tree
`24a6c7d2b81be204c4cfb5f8c6b66f9001277052`. No unpublished compatibility patch
was included. The full 143 claims / 18 goals remain incomplete.

The task explicitly requested finance and sales specialists to analyze synthetic
closed revenue USD100, remaining pipeline USD200 and target USD250. Two synthetic
specialists were present. The app returned HTTP 200 and persisted a successful
outer chat execution, but **zero delegation chains and zero chain links**. There
were no specialist or final fleet synthesis model stages. Interpretation chose a
conversation action, and the answer used finance/sales perspectives without
actually consulting either specialist. This is an incomplete workflow regardless
of answer quality or outer execution status.

## Provider and guard evidence

Six calls were admitted and six relay starts recorded, below the maximum 16;
each requested output cap was at most 8,000 tokens. Four HTTP 200 completions
reported served model `deepseek-v4.1-flash`: interpretation, planning, direct
reply and verdict verification. The first interpretation attempt returned 400
with the static normalized category `logprobs_unsupported`; after Atom removed
the optional field, the next interpretation call succeeded with tool calls.
The final background fact-extraction start has no settled event in the retained
relay checkpoint. Its result is unknown; neither success nor an additional
finished request is inferred.

The corrected private verifier preserved upstream status and only normalized
whitelisted error categories; raw error bodies were neither forwarded nor saved.
Unlike case 7, the recovered 400 is therefore positive evidence for Atom's
existing reactive compatibility path at this exact Go Flash route. It does not
prove every gateway/model contract, and case 7's discarded error cause remains
unknown. No automatic rerun or Extra Usage change followed; this allowance is
consumed.

## Answer and outcome are distinct

Manual review found the supplied USD100 closed revenue, USD200 pipeline and
USD250 target, correct USD150 shortfall and40% attainment, and a clear warning
that open pipeline is not closed revenue. Literal verifier checks underrecognized
spaces such as `USD 150`. They were not changed after the live result, and no
whole-run pass is claimed. The independent durable absence of specialist
executions is sufficient to retain FAILED status. A single synthetic direct
answer is not a model-quality benchmark; unsupported generalizations in its
prose are not validated by the arithmetic check.

Controller exit 0 only means its wrapper completed. Root inspected the final
sanitized app report and durable rows, then verified the owned child/server/
process group absent and both owned ports refusing connections. The output
pump drained. No active owner app or data was used or stopped.

The next coding investigation follows the shared semantic interpretation,
planning and delegation mechanisms. It must preserve explicit collaboration
requirements without forcing ordinary single-agent analysis into delegation,
recognizing quoted/negated requests as commands, bypassing gates, or inventing
specialist contributions. Offline regression work does not qualify a future
live run. Fresh source checks and a new explicit allowance would be needed
before any further paid fleet test.

[Filtered run result](evidence/fleet_case8_20261117/result.json).
