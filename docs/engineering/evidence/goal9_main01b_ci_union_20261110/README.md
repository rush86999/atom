# Budget/main CI union

PR832 head2b209d376 conflicted with main01b554c55 in only the CI workflow and additive selection manifest; no Actions ran for that conflicting head. Merge source18f407681 preserves all nine jobs, both parents' ordered steps, and every additive entry. The combined CI-contract, budget/upgrade, and independent nine-binding gate passed65tests at unchangedsource, actualexit0.

No production rule or existing gate was relaxed. Previous source/evidence identities remain unchanged. Atomic concurrent reservation remains separate.
