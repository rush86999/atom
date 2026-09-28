"""
Hybrid Retrieval Service: Two-stage retrieval orchestration

Coarse stage: FastEmbed (384-dim, top-100)
Fine stage: a TRAINED cross-encoder reranker over the top-50, off the event
loop and bounded, with an observable fallback to the coarse ranking.

Latency figures quoted in earlier revisions of this module's docstring were
design targets written before any measurement existed, and a stated
relevance-improvement percentage was never measured at all. They are not
repeated here, because a target restated in a docstring is read as a result.
`rerank_timing()` returns what the running machine actually did. The one
number that was always real is the CPU cost: a large cross-encoder over 50
pairs takes seconds on CPU, which is why inference runs in a bounded worker
and the caller has a timeout at all.

Ranking degradation (reranker unavailable, saturated, slow or timed out) is
reported as RANKING status and never as a retrieval failure: the candidates
were retrieved, they are just ordered by the coarse stage. Conflating the two
is what produced "evidence was fully searched" claims over a degraded ranking.
"""
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Tuple, Optional
import asyncio
import logging
import os
import threading
import time

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Check for NumPy availability
# Check for CUDA availability
CUDA_AVAILABLE = False
try:
    import torch
    CUDA_AVAILABLE = torch.cuda.is_available()
    if CUDA_AVAILABLE:
        logger.info(f"CUDA available: {torch.cuda.get_device_name(0)}")
    else:
        logger.info("CUDA not available, will use CPU for reranking")
except ImportError:
    logger.info("PyTorch not available, will use CPU for reranking")


# --- Reranker checkpoint selection -------------------------------------------
#
# The previous default, BAAI/bge-large-en-v1.5, is an EMBEDDING checkpoint.
# Loaded through CrossEncoder it produces cosine similarity between a query and
# a passage — a quantity that is not a trained relevance judgement, and whose
# scale is not comparable across pairs. Ranking by it is not reranking, and the
# scores it produced were then min-max normalised into a confident-looking
# [0,1], so a ranking artefact was indistinguishable from a relevance signal.
# The trained cross-encoder family (BAAI/bge-reranker-*) is the correct
# checkpoint class for this stage.
#
# Nothing here downloads anything at request time. A checkpoint must already be
# resolvable from the local cache or an explicit local path; otherwise the
# rerank tier reports itself unavailable and ranking degrades observably.
DEFAULT_RERANK_MODEL = os.getenv("ATOM_RERANK_MODEL", "BAAI/bge-reranker-base")
_RERANK_LOCAL_ONLY = os.getenv("ATOM_RERANK_MODEL_LOCAL_ONLY", "1") != "0"
_RERANK_ALLOW_EMBEDDING_CHECKPOINT = (
    os.getenv("ATOM_RERANK_ALLOW_EMBEDDING_CHECKPOINT", "0") == "1"
)

# Bounded inference. A cross-encoder call is blocking CPU work: awaiting it
# with a timeout does NOT stop the thread, so an unbounded pool accumulates
# orphaned inferences that keep burning CPU after every caller has given up.
# One worker plus a bounded admission queue caps the damage at a known number
# of in-flight inferences, and saturation is reported rather than hidden.
_RERANK_WORKERS = max(1, int(os.getenv("ATOM_RERANK_WORKERS", "1")))
_RERANK_MAX_QUEUE = max(0, int(os.getenv("ATOM_RERANK_MAX_QUEUE", "2")))
_rerank_executor: Optional[ThreadPoolExecutor] = None
_rerank_slots: Optional[threading.BoundedSemaphore] = None
_rerank_lock = threading.Lock()
RERANK_TIMING: Dict[str, float] = {
    "calls": 0, "saturated": 0, "timed_out": 0, "failed": 0,
    "total_ms": 0.0, "max_ms": 0.0, "last_ms": 0.0,
}


def _rerank_pool() -> Tuple[ThreadPoolExecutor, threading.BoundedSemaphore]:
    global _rerank_executor, _rerank_slots
    with _rerank_lock:
        if _rerank_executor is None:
            _rerank_executor = ThreadPoolExecutor(
                max_workers=_RERANK_WORKERS,
                thread_name_prefix="atom-rerank",
            )
        if _rerank_slots is None:
            _rerank_slots = threading.BoundedSemaphore(
                _RERANK_WORKERS + _RERANK_MAX_QUEUE
            )
        return _rerank_executor, _rerank_slots


def rerank_timing() -> Dict[str, Any]:
    """What the rerank tier actually did on this machine, in this process."""
    calls = RERANK_TIMING["calls"] or 1
    return {
        **RERANK_TIMING,
        "mean_ms": round(RERANK_TIMING["total_ms"] / calls, 2),
        "workers": _RERANK_WORKERS,
        "max_queue": _RERANK_MAX_QUEUE,
        "model": DEFAULT_RERANK_MODEL,
    }


def _classify_checkpoint(model_id: str) -> Dict[str, Any]:
    """Is this checkpoint a TRAINED cross-encoder, or a bi-encoder embedder?

    Read from the locally cached config, never from the network. A config with
    no classification head and no sequence-classification label count is a
    plain encoder: its logits are projection/cosine geometry, not relevance.
    """
    verdict: Dict[str, Any] = {
        "model_id": model_id, "trained_reranker": None, "reason": None,
    }
    try:
        from transformers import AutoConfig

        config = AutoConfig.from_pretrained(
            model_id, local_files_only=_RERANK_LOCAL_ONLY
        )
    except Exception as exc:  # noqa: BLE001 — absence is a verdict, not a crash
        verdict["reason"] = f"config_unavailable:{type(exc).__name__}"
        return verdict

    num_labels = getattr(config, "num_labels", None)
    architectures = list(getattr(config, "architectures", None) or [])
    arch_text = " ".join(architectures).lower()
    is_encoder = "encoder" in arch_text or "bert" in arch_text
    has_classifier = any("classification" in a or "ranking" in a for a in arch_text)

    if num_labels == 1 and is_encoder and not has_classifier:
        verdict["trained_reranker"] = False
        verdict["reason"] = "single_logit_encoder_without_classification_head"
    elif has_classifier or (is_encoder and isinstance(num_labels, int) and num_labels > 1):
        verdict["trained_reranker"] = True
        verdict["reason"] = "classification_head_present"
    else:
        verdict["trained_reranker"] = None
        verdict["reason"] = f"unrecognised_config:{arch_text or type(config).__name__}"
    return verdict


class RerankUnavailable(Exception):
    """The rerank tier cannot run. Ranking degrades; retrieval does not fail."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class HybridRetrievalService:
    """
    Two-stage hybrid retrieval: FastEmbed coarse + trained cross-encoder rerank.

    ``retrieve_semantic_hybrid`` returns ``(episode_id, score, stage)`` triples
    where ``stage`` names which stage produced the ORDER: ``reranked``,
    ``coarse_only`` (no reranker), ``coarse_timeout_fallback``,
    ``coarse_saturated_fallback`` (admission queue full) or
    ``coarse_failed_fallback``. A caller can always tell a degraded ranking
    from a clean one, and the last retrieval's degradation is available from
    ``last_ranking_status`` for surfacing at the evidence boundary.
    """

    def __init__(self, db: Session):
        self.db = db
        # Import EmbeddingService here to avoid circular imports
        from core.embedding_service import EmbeddingService
        self.embedding_service = EmbeddingService(provider="fastembed")
        self._reranker_model = None  # Lazy load cross-encoder
        self._reranker_verdict: Optional[Dict[str, Any]] = None
        self._reranker_probe_done = False
        self.last_ranking_status: Dict[str, Any] = {
            "status": "not_attempted", "reason": None, "model": DEFAULT_RERANK_MODEL,
        }

    async def _get_reranker_model(self):
        """Load the configured reranker, or report precisely why it cannot run.

        Returns the model, or ``False`` when the tier is unavailable (the
        historical sentinel — ``False`` means "no model", ``None`` means
        "not probed yet", and a real model is anything else). Availability is
        probed once and cached, including the REASON, so "reranking was off"
        and "the configured checkpoint is an embedding model" and "the
        checkpoint is not in the local cache" are three different, reportable
        facts rather than one silent ``False``.

        The probe attributes are read defensively so a service assembled
        without ``__init__`` (a documented pattern in this repo's tests, and
        how a long-lived worker restores state) still loads a model instead of
        raising an AttributeError that reads as "reranking is broken".
        """
        if not getattr(self, "_reranker_probe_done", False):
            self._reranker_probe_done = True
            try:
                from sentence_transformers import CrossEncoder

                verdict = _classify_checkpoint(DEFAULT_RERANK_MODEL)
                self._reranker_verdict = verdict
                if (verdict.get("trained_reranker") is False
                        and not _RERANK_ALLOW_EMBEDDING_CHECKPOINT):
                    logger.error(
                        "Reranker checkpoint %s rejected: %s. A bi-encoder "
                        "embedding checkpoint ranks by cosine geometry, not by "
                        "trained relevance; set ATOM_RERANK_MODEL to a trained "
                        "cross-encoder, or ATOM_RERANK_ALLOW_EMBEDDING_CHECKPOINT=1 "
                        "to accept the degraded ordering deliberately.",
                        DEFAULT_RERANK_MODEL, verdict.get("reason"),
                    )
                    self._reranker_model = False
                else:
                    device = "cuda" if CUDA_AVAILABLE else "cpu"
                    self._reranker_model = CrossEncoder(
                        DEFAULT_RERANK_MODEL,
                        device=device,
                        local_files_only=_RERANK_LOCAL_ONLY,
                    )
                    logger.info(
                        "Cross-encoder loaded: %s (device=%s, trained_reranker=%s, local_only=%s)",
                        DEFAULT_RERANK_MODEL, device,
                        verdict.get("trained_reranker"), _RERANK_LOCAL_ONLY,
                    )
            except ImportError:
                logger.warning("sentence_transformers not available, reranking disabled")
                self._reranker_model = False
                self._reranker_verdict = {
                    "model_id": DEFAULT_RERANK_MODEL, "trained_reranker": None,
                    "reason": "sentence_transformers_missing",
                }
            except Exception as e:
                logger.error("Failed to load cross-encoder %s: %r", DEFAULT_RERANK_MODEL, e)
                self._reranker_model = False
                self._reranker_verdict = {
                    "model_id": DEFAULT_RERANK_MODEL, "trained_reranker": None,
                    "reason": f"load_failed:{type(e).__name__}",
                }
        return self._reranker_model

    def reranker_verdict(self) -> Dict[str, Any]:
        return dict(
            getattr(self, "_reranker_verdict", None)
            or {"model_id": DEFAULT_RERANK_MODEL, "trained_reranker": None,
                "reason": "not_probed"}
        )

    async def retrieve_semantic_hybrid(
        self,
        agent_id: str,
        query: str,
        coarse_top_k: int = 100,
        rerank_top_k: int = 50,
        use_reranking: bool = True
    ) -> List[Tuple[str, float, str]]:
        """
        Hybrid semantic retrieval (coarse + fine).

        Args:
            agent_id: Agent ID for filtering episodes
            query: Search query text
            coarse_top_k: Number of candidates from FastEmbed (default: 100)
            rerank_top_k: Number of results after reranking (default: 50)
            use_reranking: Whether to use reranking (default: True)

        Returns:
            List of (episode_id, relevance_score, stage) where ``stage`` names
            the stage that produced the ORDER: "reranked", "coarse_only",
            "coarse_timeout_fallback", "coarse_saturated_fallback" or
            "coarse_failed_fallback". Scores are ranking scores on the reranker's
            own scale, not calibrated correctness probabilities.

        Ranking degradation is recorded in ``self.last_ranking_status``; it is
        never reported as a retrieval failure.
        """
        started = time.monotonic()

        # Stage 1: Coarse search with FastEmbed
        logger.info(f"[HYBRID] Stage 1: Coarse search (top-{coarse_top_k})")
        coarse_results = await self.embedding_service.coarse_search_fastembed(
            agent_id=agent_id,
            query=query,
            top_k=coarse_top_k,
            db=self.db
        )

        if not coarse_results:
            logger.warning("[HYBRID] No coarse results found")
            self.last_ranking_status = {
                "status": "not_attempted", "reason": "no_coarse_candidates",
                "model": DEFAULT_RERANK_MODEL,
            }
            return []

        coarse_duration = (time.monotonic() - started) * 1000
        logger.info(f"[HYBRID] Coarse search: {len(coarse_results)} results in {coarse_duration:.1f}ms")

        # Stage 2: rerank with the trained cross-encoder (if available)
        if use_reranking:
            model = getattr(self, "_reranker_model", None)
            if model is None:
                reranker = await self._get_reranker_model()
            else:
                reranker = model
            if reranker is False:
                reason = self.reranker_verdict().get("reason") or "unavailable"
                logger.warning("[HYBRID] Reranking unavailable (%s); coarse order kept", reason)
                self.last_ranking_status = {
                    "status": "degraded", "reason": reason,
                    "model": DEFAULT_RERANK_MODEL,
                    "checkpoint": self.reranker_verdict(),
                }
                return [(ep_id, score, "coarse_only") for ep_id, score in coarse_results[:rerank_top_k]]

            batch = coarse_results[:rerank_top_k]
            logger.info(f"[HYBRID] Stage 2: reranking {len(batch)} candidates")

            try:
                reranked_results = await self._predict_bounded(
                    reranker, query, batch, agent_id,
                    timeout=float(os.getenv("HYBRID_RERANK_TIMEOUT_S", "0.200")),
                )
            except asyncio.TimeoutError:
                elapsed = (time.monotonic() - started) * 1000
                RERANK_TIMING["timed_out"] += 1
                logger.warning(
                    "[HYBRID] Reranking exceeded its budget after %.1fms; the "
                    "worker keeps the pair set it already took, and admission "
                    "stops new work while it drains. Coarse order kept.", elapsed,
                )
                self.last_ranking_status = {
                    "status": "degraded", "reason": "rerank_timeout",
                    "model": DEFAULT_RERANK_MODEL,
                    "checkpoint": self.reranker_verdict(),
                    "elapsed_ms": round(elapsed, 2),
                }
                return [(ep_id, score, "coarse_timeout_fallback")
                        for ep_id, score in coarse_results[:rerank_top_k]]
            except RerankUnavailable as unavailable:
                RERANK_TIMING["saturated" if unavailable.reason == "queue_saturated"
                              else "failed"] += 1
                logger.warning("[HYBRID] Rerank admission refused (%s); coarse order kept",
                               unavailable.reason)
                stage = ("coarse_saturated_fallback"
                         if unavailable.reason == "queue_saturated"
                         else "coarse_failed_fallback")
                self.last_ranking_status = {
                    "status": "degraded", "reason": unavailable.reason,
                    "model": DEFAULT_RERANK_MODEL,
                    "checkpoint": self.reranker_verdict(),
                }
                return [(ep_id, score, stage) for ep_id, score in coarse_results[:rerank_top_k]]

            rerank_ms = RERANK_TIMING["last_ms"]
            total_ms = (time.monotonic() - started) * 1000
            logger.info(
                "[HYBRID] Reranked %d candidates in %.1fms (total %.1fms)",
                len(reranked_results), rerank_ms, total_ms,
            )
            self.last_ranking_status = {
                "status": "ok", "reason": None, "model": DEFAULT_RERANK_MODEL,
                "checkpoint": self.reranker_verdict(),
                "elapsed_ms": rerank_ms,
            }
            return [(ep_id, score, "reranked") for ep_id, score in reranked_results]

        self.last_ranking_status = {
            "status": "not_attempted", "reason": "reranking_disabled_by_caller",
            "model": DEFAULT_RERANK_MODEL,
        }
        return [(ep_id, score, "coarse_only") for ep_id, score in coarse_results[:rerank_top_k]]

    async def _predict_bounded(
        self,
        model: Any,
        query: str,
        candidates: List[Tuple[str, float]],
        agent_id: str,
        timeout: float,
    ) -> List[Tuple[str, float]]:
        """Run ``model.predict`` OFF the event loop, under bounded admission.

        Three defects met here. (1) The call was synchronous inside an async
        coroutine: on CPU a 50-pair pass blocks the whole loop for seconds, so
        every concurrent request in the process stalls — the surrounding
        ``wait_for`` timeout could not preempt it, because the coroutine it was
        waiting on never got to run. (2) Moving it to a thread fixes the loop
        but not the timeout: cancelling the await does not stop the thread, so
        repeated timeouts accumulate orphaned inferences that keep consuming
        CPU. (3) The scores were min-max normalised per query, so a reranker
        that returned one score, or a NaN, or a different length than the
        candidate list produced a confident-looking ordering over the wrong
        records.

        So: one bounded worker, non-blocking admission (saturation is refused
        and reported rather than queued), and the score vector is validated for
        cardinality and finiteness before it is allowed to reorder anything.
        """
        pairs, pair_ids = self._rerank_pairs(query, candidates, agent_id)
        if not pairs:
            raise RerankUnavailable("no_candidate_content")

        executor, slots = _rerank_pool()
        if not slots.acquire(blocking=False):
            raise RerankUnavailable("queue_saturated")

        # The permit is released by the WORKER, not by the awaiting coroutine.
        # A coroutine that gives up on a timeout is precisely the case where the
        # thread keeps burning CPU — releasing there would hand the permit back
        # while the inference is still running, so every subsequent caller would
        # be admitted and the orphaned work would grow without bound. This is
        # the only placement that actually caps concurrent inference.
        def _run() -> Any:
            try:
                return model.predict(pairs)
            finally:
                slots.release()

        started = time.monotonic()
        future = executor.submit(_run)
        try:
            try:
                scores = await asyncio.wait_for(
                    asyncio.wrap_future(future), timeout=timeout
                )
            except asyncio.TimeoutError:
                raise
            except Exception as exc:  # noqa: BLE001
                raise RerankUnavailable(f"predict_failed:{type(exc).__name__}") from exc
        except BaseException:
            # Only the timeout path leaves the work running; every other exit
            # already released the permit inside _run.
            future.cancel()
            raise

        elapsed_ms = (time.monotonic() - started) * 1000
        RERANK_TIMING["calls"] += 1
        RERANK_TIMING["total_ms"] += elapsed_ms
        RERANK_TIMING["last_ms"] = round(elapsed_ms, 2)
        RERANK_TIMING["max_ms"] = max(RERANK_TIMING["max_ms"], elapsed_ms)

        scores = [float(s) for s in list(scores)]
        if len(scores) != len(pair_ids):
            raise RerankUnavailable(
                f"score_cardinality_mismatch:{len(scores)}_for_{len(pair_ids)}"
            )
        if not all(s == s and s not in (float("inf"), float("-inf")) for s in scores):
            raise RerankUnavailable("non_finite_scores")

        # Pairwise relevance scores are on the model's own scale, not calibrated
        # correctness probabilities. Keeping the raw value (and the coarse
        # score it competes with) is what lets a caller report a ranking
        # without implying a confidence it does not have.
        score_by_id = dict(zip(pair_ids, scores))
        combined = [
            (ep_id, 0.3 * coarse + 0.7 * score_by_id[ep_id])
            for ep_id, coarse in candidates
            if ep_id in score_by_id
        ]
        combined.sort(key=lambda x: x[1], reverse=True)
        return combined

    def _rerank_pairs(
        self, query: str, candidates: List[Tuple[str, float]], agent_id: str
    ) -> tuple[List[Tuple[str, str]], List[str]]:
        """(query, text) pairs for the candidates that actually have content,
        with the episode id each score belongs to."""
        from core.models import Episode

        episode_ids = [ep_id for ep_id, _ in candidates]
        episodes = self.db.query(Episode).filter(
            Episode.id.in_(episode_ids),
            Episode.agent_id == agent_id
        ).all()
        episode_map = {ep.id: ep for ep in episodes}
        pair_ids: List[str] = []
        pairs: List[Tuple[str, str]] = []
        for ep_id, _ in candidates:
            episode = episode_map.get(ep_id)
            if episode is None:
                continue
            text = (episode.task_description or "").strip()
            if not text:
                continue
            pair_ids.append(ep_id)
            pairs.append((query, text))
        return pairs, pair_ids

    async def _rerank_cross_encoder(
        self,
        query: str,
        candidates: List[Tuple[str, float]],
        agent_id: str
    ) -> List[Tuple[str, float]]:
        """Rerank candidates using the cross-encoder.

        Retained as the named entry point and delegated to the bounded,
        off-loop, validated path. The body it replaces called ``model.predict``
        synchronously inside an async coroutine, min-max normalised the
        resulting scores per query, and mapped them back to candidates by
        position — so a short or NaN score vector produced a confident
        ordering over the WRONG records, and the surrounding timeout could not
        preempt the blocking call it was meant to bound.

        Raises ``RerankUnavailable`` / ``asyncio.TimeoutError`` rather than
        inventing an ordering; the caller degrades to the coarse ranking and
        records that it did.
        """
        model = await self._get_reranker_model()
        if model is False:
            raise RerankUnavailable("reranker_unavailable")
        return await self._predict_bounded(
            model, query, candidates, agent_id,
            timeout=float(os.getenv("HYBRID_RERANK_TIMEOUT_S", "0.200")),
        )

    async def retrieve_semantic_baseline(
        self,
        agent_id: str,
        query: str,
        top_k: int = 50
    ) -> List[Tuple[str, float]]:
        """
        Baseline semantic retrieval (FastEmbed only, no reranking).

        Used for A/B testing and performance comparison.
        """
        results = await self.embedding_service.coarse_search_fastembed(
            agent_id=agent_id,
            query=query,
            top_k=top_k,
            db=self.db
        )
        return [(ep_id, score) for ep_id, score in results]
