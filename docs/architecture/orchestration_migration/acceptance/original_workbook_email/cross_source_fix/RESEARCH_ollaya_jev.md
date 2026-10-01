# Research: ollaya / Jev — typed local decision models for NLU (2026-09-29)

Owner question: is there value in ollaya/Jev-class tools for better
classification? Researched (web) + measured locally (ollaya 0.7.5,
darwin-arm64, laya:en 421M ModernBERT ONNX, CPU).

## What the class is

- **Jev** (TypeSafe AI, hosted): closed "System One" typed-decision model
  — returns typed choices/scores with calibrated probabilities from label
  logits (single forward pass, no text generation). Claimed ~25x faster /
  ~1/76 cost vs LLMs (third-party). Raschka's read: ModernBERT-class
  classifier + calibration (RLCR/Brier-style); the moat is data
  curation/generalization, not architecture.
- **ollaya** (Apache-2.0 runtime): "Ollama for decision models" — local,
  free, private; ONNX/MLX; port 11435; TypeSafe-compatible HTTP API +
  MCP serve; weights sha256-pinned from HF. Models: Mica 4B (routing),
  JevK5 4B/9B (JSON decisions), GLiNER 2.5-Decide (<10ms labels, Apple
  Silicon), Lia/laya 421M (BERT-style strict classification).

## Measured (this box, our real prompts)

| Task | Latency | Quality |
|---|---|---|
| Our possessive source-vs-attribute judgment | 40–70 ms (noul) | 1/5 — NO-biased (p .05–.27), non-discriminative |
| Our anaphoric file-reference judgment | 32–40 ms | 2/4 — same NO bias |
| Home-turf agent gating (built-in preset) | 110–150 ms | mis-gates: "delete all customer records" → run p=.75 |

Latency/cost/privacy thesis: REAL (sub-100ms, free, local — vs metered
1–3s LLM round trips; also removes the provider-credit failure class we
hit live when the cheap-nlu tail fail-closed). Quality: laya:en (421M,
3 days old) is not production-grade for our judgments — coarse or
subtle. The 4B/9B local decoders (Mica, JevK5) are unmeasured here and
are the honest candidates.

## Verdict

1. For the cheap-nlu refinement layer shipped today: NO change — the
   floor -> budget-LLM residue design stays correct; laya:en fails the
   residue judgments. Keep cheap_nlu's interface stable so a local
   backend can slot in behind a QUALITY GATE (must pass our labeled
   incident+control set before routing anything to it).
2. Where the value plausibly IS: coarse, high-volume, preset-shaped
   gating/triage now paid to LLMs (intent fallback, action gating,
   guardrails) — but only after a measured pilot on a labeled sample;
   and GLiNER 2.5-Decide as a future regex-floor replacement for label
   evaluation, once measured.
3. Watch, don't adopt: the space is a week old, vendor-benchmarked.
   Jev hosted works reportedly better but is closed + metered; the
   local-first ollaya route fits this repo's single-tenant stance IF a
   model passes the gate.

Runtime left installed at ~/.local/bin/ollaya (server stopped). No
production wiring changed by this research.

## Addendum (same day): Mica / JevK5 measured

Owner asked to test the 4B/9B decoders. Results on this box (arm64 Mac,
llama.cpp, Q8_0):

- **Mica**: NOT published in registry 0.7.5 (tried mica, :latest, :v0.1,
  :4b — "not found"). Site lineup is ahead of the registry/runtime;
  untestable until published or a newer runtime ships.
- **JevK5-9b**: not in registry either. **JevK5-4b**: pulled (4.5 GB) and
  measured.

| Task | laya:en 421M | JevK5-4B | gate |
|---|---|---|---|
| possessive source-vs-attribute | 1/5 (NO-bias) | 2/5 — clear case p=0.78 YES ✓, but Brennan Machinery p=0.58 (wrong), Sam 0.43, supplier 0.41 | fail |
| anaphoric file-reference | 2/4 (NO-bias) | 2/4 — all probs 0.30–0.44, non-discriminative | fail |
| warm latency | 40–70 ms | ~215 ms (20 s cold load) | — |

Notable: JevK5's noul readout returned IDENTICAL probabilities under
instruction-style and short-statement phrasings — the readout keys on
the state text and is phrasing-insensitive, so prompt tuning will not
rescue these scores. Custom two-option CHOICE schemas are rejected by
the runtime (both models; ~9 ms no-op) — only preset label sets work in
0.7.5.

Verdict unchanged and now measured across both weight classes available
locally: the runtime pattern is right, the models are not. JevK5-4B
shows real calibration signal on the clearest case (0.78) and its
failure mode in our architecture would be fail-open (dropping a
legitimate org constraint), not dangerous — but 2/5+2/4 is far below
any gate. Re-test Mica/JevK5-9B when the registry publishes them; keep
the labeled incident+control set (in test_cross_source_followup_routing
+ this bench) as the gate. Test models removed after measurement;
runtime + laya remain installed.

## Addendum 2 (same day): JevK5-9B v0.3.3 measured — it crosses the gate on one task

The 9B is absent from the ollaya registry, so it was run through the
OFFICIAL path: Q8_0 GGUF (sha256-verified against the repo's SHA256SUMS)
on the portable drive, llama-server on Metal (port 8190), and the
stdlib-only `jevk5` runtime (`pip install --no-deps`, python3.12 venv on
the drive) — the exact SemIf readout with the repo's own calibration
(temperature 1.316 / knockout 1.05 from jevk5_config.json). Pipeline
sanity first: the README's parcel example reproduces exactly
(misdelivered p=0.978), and plain propositions calibrate correctly
(sky-blue 0.84 true / absurd 0.14).

| task (same 9 labeled cases) | laya 421M | JevK5-4B | JevK5-9B Q8 |
|---|---|---|---|
| possessive source-vs-attribute | 1/5 | 2/5 | 3/5 — true sources right (0.57–0.67), Brennan Machinery wrongly 0.69, supplier 0.49 coin-flip |
| anaphoric file-reference | 2/4 | 2/4 | **4/4** with margin: 0.79 / 0.71 yes, 0.17 / 0.03 no |
| median latency | 40–70 ms | ~215 ms | ~600–700 ms (Metal, cold load ~45 s) |

Reading: the 9B is genuinely discriminative where the smaller models
were biased — the anaphoric task would PASS the quality gate today. The
possessive judgment (pragmatic, needs world knowledge about
persons-vs-organizations) still belongs to the LLM tail. Practical
caveats for adoption: ~10 GB weights + ~1 GB KV on a local-first box, a
separate llama-server daemon (ollaya 0.7.5 cannot serve this model), and
English-only. A gated integration — 9B for the anaphoric refinement,
LLM for the possessive residue — is now a measured option rather than
speculation.

Artifacts on the portable drive (user-directed): /Volumes/Seagate
Portable Drive/jevk5-9b/ — GGUF (8.9 GB, hash-verified), scratch venv,
bench_9b.py. Servers stopped after measurement.

## Decision (owner, 2026-09-29)

Keep the budget-LLM tail as the sole refinement backend for now. The
local-decision-model option (JevK5-9B etc.) stays RESEARCH-ONLY; expand
only if recurring use shows problems. Concrete expansion triggers:

- the cheap-nlu circuit breaker opens repeatedly in normal use (provider
  outages/credit exhaustion of the kind already observed once);
- refinement latency or metered cost becomes visible in real sessions;
- new high-volume classification work lands in cheap_nlu where free +
  local compounds.

If a trigger fires: expand the labeled gate set from real session
history first (the 9 cases rank backends, they do not license adoption),
then re-run the staged benchmark (/Volumes/Seagate Portable Drive/
jevk5-9b/ — hash-verified GGUF, venv, bench script) and wire the winning
backend per question kind behind the existing kill switches, shadowed
before it routes anything. No production change in this decision.

## Addendum 3 (2026-09-30): SemIf/OpenJev — a GENERAL 4B readout clears the same gate set

Owner asked to consider https://openjev.com/ in decision routing, tested
locally. OpenJev is now **SemIf** (github.com/TheoLeeCJ/SemIf-OpenJev, MIT)
— the open reproduction of the Jev *interface pattern* (not the model):
runtime-defined {state, criterion, options} decisions decided by ONE
forward pass with softmax restricted to the declared option-letter tokens
("direct readout"), vs an autoregressive generation baseline. Published
browser ladder for general models: Qwen3-0.6B 0.44 / MiniCPM5-2B 0.686 /
Qwen3.5-4B 0.813 balanced accuracy. Unlike the ollaya runtimes above, SemIf
scores arbitrary custom criteria and runs as a plain library (torch/MLX/
llama.cpp backends) — no extra daemon, no preset label sets.

Measured on this box (arm64, MLX/Metal, mlx-community/Qwen3.5-4B-4bit
pinned 0e7ffd5c, repo venv): the SAME 9 labeled gate cases (bench_9b.py),
plus a new lane-routing workload: the 18 coverage-matrix turns × 5 action
kinds as binary criteria, labeled with the shipped contract's ACTUAL
decisions from coverage_matrix_results.json (17/18 correct corpus).

| gate set (9 cases) | laya 421M | JevK5-4B | JevK5-9B | **Qwen3.5-4B SemIf** |
|---|---|---|---|---|
| possessive source-vs-attribute | 1/5 | 2/5 | 3/5 | **4/5** |
| anaphoric file-reference | 2/4 | 2/4 | 4/4 | **4/4** (0.87/0.98 vs 0.13/0.13) |
| total | 3/9 | 4/9 | 7/9 | **8/9** |

The single miss is poss-4 Brennan Machinery (p=0.798 confident-wrong) —
the documented pragmatic residue the budget LLM exists for. Generation
baseline: identical 8/9, same miss (the two readouts agreed on EVERY row,
99/99 — with 2-token letter answers there is no quality gap; readout's
structural advantage is per-option probabilities with no decode loop).

Lane routing (18 turns × 5 kinds): **research recall 12/12, every true
research turn p≥0.98** — including "That filename is correct" (0.98) and
"find this in the tracker" (0.99) — zero omitted reads; learning 18/18,
presentation 17/18. Exact action-set match vs the contract: 11/18; ALL
misses are over-inclusion at the policy boundary (research/edit flavor on
presentation-without-reread, nomination-without-grant, and "remember
that…" turns, p 0.71–0.99): the model reproduces the SEMANTICS and has no
notion of authorization. Latency: warm 0.3–0.8 s per decision (short
prompts ~330–780 ms; history-bearing lane prompts ~0.5–1.5 s; forward-only
≈ total). 2.5 GB weights, no server, inputs never leave the box.

Reading: the candidate that passes the recorded quality gate is no longer
a Jev-class decision-model runtime — it is a general 4B instruct model via
SemIf-style readout behind cheap_nlu's existing interface, per question
kind, with the Brennan-class pragmatic residue staying on the budget LLM.
Replacing the lane contract itself is ruled out on this evidence AND on
principle (policy authorization must not become a model call; the
deterministic gates are the audit surface).

Standing owner decision unchanged (budget-LLM tail ships; expansion
triggers unchanged). If a trigger fires: expand the labeled set from real
session history first, then wire the readout behind cheap_nlu's kill
switches, shadowed before it routes anything. Bench + inputs + raw
outputs: /Volumes/Seagate Portable Drive/semif-qwen35-4b/atom_bench/
(build_inputs.py, run_generation.py, score.py, out_*.jsonl; scratch clone
was /tmp/semif-jev-test). No production change.
