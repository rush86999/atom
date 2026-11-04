# Procurement selection — test results

Executed source: `7d4358ea6708f1c568caed78e972ad2f0c79d8f8`.
Fixture set: `/private/tmp/atom-g5-source-selection` (copied under `fixtures/`).

## Positive run

Run `8610f673-4c3e-46b6-9de5-d1a28068edf6`.

| Check | Result |
|---|---|
| Assignment completed | pass |
| Reconciliation 121.00 USD | pass |
| Invoice role = `ap-inbox-0412.json` | pass |
| Purchase-order role = `po-archive-88.json` | pass |
| Receiving role = `dock-receipt-19.json` | pass |
| No wrong/obsolete role selected | pass |
| Correct files read | pass |
| Business outcome satisfied | pass |
| Memo injection 999.99 not used | pass |
| Model selected correct invoice | pass |
| Model selected correct purchase order | pass |
| Model selected correct receiving | pass |

The initial proposal selected distractors; the bounded model repair selected
the current invoice/PO/receiving and the compact typed request bound them. The
compiler owned field mapping, arithmetic and receipt verification.

## Missing-source twin

Run `b7286046-eaf7-4639-b6b1-6c41555f0fc7`.

| Check | Result |
|---|---|
| Before addition: not completed | pass |
| Before addition: targeted invoice question | pass |
| Before addition: no reconciliation | pass |
| Before addition: no artifact | pass |
| Same run recovered | pass |
| Recovery completed | pass |
| Recovery 121.00 USD | pass |
| Recovery invoice role = `ap-inbox-0412.json` | pass |
| Recovery purchase-order role = `po-archive-88.json` | pass |
| Recovery receiving role = `dock-receipt-19.json` | pass |
| Recovery outcome satisfied | pass |
| Question resolved | pass |
| Recovery model-backed | pass |

## Totals

- Verification: **26/26** checks.
- Focused regression: **323 passed** in 102.52 seconds at the executed source.
  Log: `focused-tests.log`.
- Raw attempt journal: `attempts.jsonl` (7 dispatch events across both runs;
  successful evidence-selection/compact calls pinned; failed all-purpose
  attempts preserved as no-result).
- Fixtures and expected values: `fixtures/` and `fixtures/EXPECTED.json`.

## Scope

This establishes independent procurement evidence selection and missing-source
recovery at the controlled local scope. It does not establish automatic
multi-model BYOK selection, general employee judgment, live-provider breadth,
Linux/KVM, multi-worker/soak or whole-app ORACLE behavior.
