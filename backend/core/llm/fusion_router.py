"""Fusion routing: panel + judge generation for high-stakes one-off tasks.

Sends the prompt to N top-ranked models in parallel, then uses a judge model
to synthesize the best answer from the candidates. Extends the existing
generate_structured_moa pattern to free-text responses.

EVIDENCE-BASED RESTRICTIONS (per research):
  - [Spheron MoA](https://www.spheron.network/blog/mixture-of-agents-gpu-cloud):
    MoA latency/cost math is inappropriate for real-time or batch paths.
  - [OpenPipe](https://openpipe.ai/blog/mixture-of-agents): deliberate
    latency-for-quality tradeoff.
  - [Nagesh Nama](https://www.linkedin.com/pulse/mixture-agents-moa-framework-technical-dive-nagesh-nama-isdhe):
    limiting to 1 layer captures most quality gains.

This is ONLY viable for one-off high-stakes tasks. It must NEVER fire on
batch/workflow automation paths (where N× cost and latency is unacceptable).

Eligibility gate (ALL must be true):
  1. x-atom-strategy: fusion header explicitly set
  2. ATOM_FUSION_ROUTING_ENABLED=true (default ON, but header still required)
  3. Cognitive tier is COMPLEX (highest tier)
  4. NOT a batch/workflow task type
  5. Multiple providers available (≥2 candidates)
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

FUSION_ENABLED: bool = os.getenv("ATOM_FUSION_ROUTING_ENABLED", "true").lower() == "true"
FUSION_SAMPLE_COUNT: int = int(os.getenv("ATOM_FUSION_SAMPLES", "3"))
# Task types that are batch/workflow — fusion must NEVER fire on these.
_BATCH_TASK_TYPES = frozenset({"agentic", "extraction", "pdf_ocr"})


def is_fusion_eligible(
    strategy: Optional[str],
    cognitive_tier: Optional[str],
    task_type: Optional[str],
    num_candidates: int,
) -> bool:
    """Check ALL eligibility conditions for fusion routing.

    Returns True only when fusion should fire. This is the gate that
    protects batch/workflow automation from N× cost and latency.
    """
    if not FUSION_ENABLED:
        return False
    if strategy != "fusion":
        return False
    if cognitive_tier != "complex":
        return False
    if task_type and task_type.lower() in _BATCH_TASK_TYPES:
        return False
    if num_candidates < 2:
        return False
    return True


async def run_fusion(
    handler: Any,
    prompt: str,
    system_instruction: str,
    options: List[Tuple[str, str]],
    temperature: float,
    task_type: Optional[str],
    agent_id: Optional[str],
    chain_id: Optional[str],
    turn_index: int,
) -> Tuple[str, Dict[str, Any]]:
    """Run a fusion generation: N parallel models + judge synthesis.

    Returns (best_answer, metadata). Falls back to the highest-quality
    candidate on any judge failure (fail-open).

    ``handler`` is a BYOKHandler instance with ``generate_response``.
    """
    n = min(FUSION_SAMPLE_COUNT, len(options))
    sample_specs = options[:n]  # best-ranked first

    # 1. Gather N parallel samples (anti-recursion: no fusion inside samples)
    async def _sample(pair: Tuple[str, str]) -> Optional[str]:
        try:
            result = await handler.generate_response(
                prompt=prompt,
                system_instruction=system_instruction,
                model_type="auto",
                temperature=temperature,
                task_type=task_type,
                agent_id=agent_id,
                chain_id=chain_id,
                turn_index=turn_index,
            )
            return result
        except Exception as e:
            logger.warning(f"Fusion sample failed for {pair[0]}/{pair[1]}: {e}")
            return None

    samples = await asyncio.gather(*[_sample(p) for p in sample_specs])
    valid = [(spec, s) for spec, s in zip(sample_specs, samples) if s]
    if not valid:
        raise RuntimeError("All fusion samples failed")

    # 2. Pre-rank via deterministic quality assessment (skip judge if one
    #    candidate is clearly best).
    try:
        from core.llm.response_quality import assess_response_quality
        scored = []
        for spec, text in valid:
            quality = assess_response_quality(text, finish_reason="stop")
            scored.append((spec, text, quality))
        scored.sort(key=lambda x: x[2], reverse=True)
    except Exception:
        scored = [(spec, text, 0.7) for spec, text in valid]

    # If best candidate is clearly dominant (quality ≥0.8, second <0.5), skip
    # the judge — saves a call when the answer is obvious.
    if len(scored) >= 2 and scored[0][2] >= 0.8 and scored[1][2] < 0.5:
        logger.info("[Fusion] skipping judge — dominant candidate detected")
        return scored[0][1], {
            "fusion": True,
            "samples": len(valid),
            "judge_skipped": True,
            "best_provider": scored[0][0][0],
            "best_model": scored[0][0][1],
        }

    # 3. Judge synthesis: send candidates to the best-ranked model.
    best_spec = scored[0][0] if scored else valid[0][0]
    candidate_texts = [text for _, text, _ in scored]
    judge_prompt = _build_judge_prompt(prompt, candidate_texts)

    try:
        judge_result = await asyncio.wait_for(
            handler.generate_response(
                prompt=judge_prompt,
                system_instruction=(
                    "You are a synthesis judge. Given multiple candidate "
                    "answers, produce the best possible answer by combining "
                    "their strengths. Output ONLY the final answer."
                ),
                model_type="auto",
                temperature=0.3,  # lower temperature for judge consistency
                task_type=task_type,
            ),
            timeout=30.0,
        )
        if judge_result and judge_result.strip():
            return judge_result, {
                "fusion": True,
                "samples": len(valid),
                "judge_skipped": False,
                "best_provider": best_spec[0],
                "best_model": best_spec[1],
            }
    except Exception as e:
        logger.warning(f"[Fusion] judge failed, using best candidate: {e}")

    # 4. Fallback: highest-quality candidate
    return scored[0][1], {
        "fusion": True,
        "samples": len(valid),
        "judge_skipped": True,
        "judge_failed": True,
        "best_provider": scored[0][0][0],
        "best_model": scored[0][0][1],
    }


def _build_judge_prompt(original_prompt: str, candidates: List[str]) -> str:
    """Build the judge synthesis prompt from N candidate answers."""
    parts = [
        f"Original question/request:\n{original_prompt}\n",
        f"{len(candidates)} candidate answers were generated by different models:\n",
    ]
    for i, c in enumerate(candidates, 1):
        parts.append(f"\n--- Candidate {i} ---\n{c}\n")
    parts.append(
        "\nSynthesize the best possible answer from these candidates. "
        "Combine the strongest elements, correct any errors, and produce "
        "a single authoritative response. Output ONLY the final answer."
    )
    return "\n".join(parts)
