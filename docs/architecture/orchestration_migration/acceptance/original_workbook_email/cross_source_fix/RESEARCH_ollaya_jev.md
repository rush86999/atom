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
