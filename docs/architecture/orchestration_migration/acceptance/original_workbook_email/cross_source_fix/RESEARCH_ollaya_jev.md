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
