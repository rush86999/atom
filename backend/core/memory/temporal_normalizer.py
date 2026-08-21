"""
Temporal normalization layer (Temporal Evolution phase — A2/A7/A8).

Extracts deterministic, regex-based temporal anchors ("as of", "on <date>",
ISO dates, "<Month> <year>", "<Q<n>> <year>", "by end of <year>") from ingested
record text and from structured records, then feeds them to the
`temporal_entities` memory receiver (workspace-scoped, in-memory store) so the
agent timeline can answer "what was true as of <date>" with the same bi-temporal
semantics as `GraphRAGEngine.edges_as_of` (valid while
`as_of <= t < valid_until`).

Checked against the repo contracts:
  - Flag-gated: `ATOM_TEMPORALITY_ENABLED` (experiments `temporal_normalization`,
    default ON). When off, everything returns the legacy (empty/unchanged) shape.
  - Never raises: every public entry point degrades to a safe fallback.
  - Timezone-safe (R13): all datetimes normalized to UTC; naive inputs are
    assumed UTC. No `str(e)` ever reaches a caller.
  - Ingest is additive: `normalize_record` returns a copy with extra keys,
    never mutating the input.

See docs/architecture/AGENT_MEMORY_UNIFICATION_PLAN.md (temporal P0).
"""

import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.experiments import is_enabled

logger = logging.getLogger(__name__)

UTC = timezone.utc

_MAX_ENTITIES_PER_TEXT = 10
_MAX_ENTITIES_PER_WORKSPACE = 500

_MONTHS: Dict[str, int] = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9, "october": 10,
    "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}


@dataclass
class TemporalEntity:
    """A temporal anchor extracted from text or a structured record."""

    name: str
    entity_type: str
    as_of: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    source_text: str = ""
    confidence: float = 1.0
    provenance: Optional[str] = None


def _to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _now_utc() -> datetime:
    return datetime.now(UTC)


# ============================================================================
# Extraction (deterministic regex anchors)
# ============================================================================

# Applied in this order; later patterns must not re-consume earlier matches'
# spans. Duplicates collapse to the highest-confidence keeping order.
_PATTERNS = [
    # ISO dates: 2026-03-03
    (r"\b(20\d{2})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\b", "date", 1.0),
    # Windows: Q3 2026
    (r"\b(Q[1-4])\s*(20\d{2})\b", "window", 0.9),
    # Windows: by end of 2026
    (r"\bby\s+end\s+of\s+(20\d{2})\b", "window", 0.6),
    # Anchored month-day-year: as of March 3, 2026 / on Jan 15 2026
    (r"\b(?:as of|on|until|before)\s+([A-Z][a-zA-Z]+)\s+(\d{1,2})(?:st|nd|rd|th)?[,\s]+(20\d{2})\b", "date", 0.95),
    # Bare month-day-year: March 3, 2026
    (r"\b([A-Z][a-zA-Z]+)\s+(\d{1,2})(?:st|nd|rd|th)?[,\s]+(20\d{2})\b", "date", 0.9),
    # Month-year: in March 2026 / as of March 2026
    (r"\b(?:as of|in)\s+([A-Z][a-zA-Z]+)\s+(20\d{2})\b", "month", 0.85),
]

import re  # noqa: E402  (kept local-adjacent to the pattern table for readability)


def _match_to_entity(match: "re.Match[str]", entity_type: str, confidence: float) -> Optional[TemporalEntity]:
    """Convert a regex match to a TemporalEntity; invalid dates return None."""
    try:
        span = match.group(0).strip()
        if entity_type == "window":
            groups = [g for g in match.groups() if g]
            if groups and groups[0].lower().startswith("q"):
                q = int(groups[0][1])
                year = int(groups[1])
                start = datetime(year, (q - 1) * 3 + 1, 1, tzinfo=UTC)
                end_month = q * 3 + 1
                end = datetime(year if end_month <= 12 else year + 1, (end_month - 1) % 12 + 1, 1, tzinfo=UTC)
                return TemporalEntity(span, "window", as_of=start, valid_until=end,
                                      source_text=span, confidence=confidence)
            year_str = groups[-1]
            year = int(year_str)
            return TemporalEntity(span, "window", as_of=_now_utc(),
                                  valid_until=datetime(year + 1, 1, 1, tzinfo=UTC),
                                  source_text=span, confidence=confidence)
        if entity_type == "date":
            dates = [g for g in match.groups() if g]
            iso = re.fullmatch(r"\d{4}-\d{2}-\d{2}", span)
            if iso:
                return TemporalEntity(span, "date", as_of=datetime.fromisoformat(span).replace(tzinfo=UTC),
                                      source_text=span, confidence=confidence)
            month_name = str(dates[-3])
            day = str(dates[-2])
            year = int(dates[-1])
            month = _MONTHS.get(month_name.lower())
            if not month:
                return None
            return TemporalEntity(span, "date", as_of=datetime(year, month, int(re.sub(r"\D", "", day)), tzinfo=UTC),
                                  source_text=span, confidence=confidence)
        month_name = str(match.groups()[0])
        year = int(match.groups()[1])
        month = _MONTHS.get(month_name.lower())
        if not month:
            return None
        return TemporalEntity(span, "month", as_of=datetime(int(year), month, 1, tzinfo=UTC),
                              source_text=span, confidence=confidence)
    except Exception as e:
        logger.debug(f"Temporal anchor skipped: {e}")
        return None


def extract_temporal(text: Any, *, max_entities: int = _MAX_ENTITIES_PER_TEXT) -> List[TemporalEntity]:
    """Extract temporal anchors from text. Deterministic, never raises."""
    if not is_enabled("temporal_normalization"):
        return []
    if not isinstance(text, str) or not text.strip():
        return []

    entities: List[TemporalEntity] = []
    seen: Dict[tuple, float] = {}
    for pattern, entity_type, confidence in _PATTERNS:
        try:
            for match in re.finditer(pattern, text):
                entity = _match_to_entity(match, entity_type, confidence)
                if entity and entity.as_of:
                    # Value-based dedupe: "as of March 3, 2026" and the bare
                    # "March 3, 2026" both anchor 2026-03-03 → one entity
                    # (higher-confidence pattern wins by application order).
                    key = (entity.entity_type, entity.as_of.isoformat(),
                           entity.valid_until.isoformat() if entity.valid_until else None)
                    if key in seen:
                        continue
                    seen[key] = confidence
                    entities.append(entity)
        except Exception as e:
            logger.debug(f"Temporal extraction pattern failed: {e}")

    entities.sort(key=lambda e: e.as_of or datetime.min.replace(tzinfo=UTC), reverse=True)
    return entities[:max_entities]


def _record_text(record: Dict[str, Any]) -> str:
    """Concatenate the text-ish fields of a structured record."""
    parts = []
    for key in ("name", "title", "summary", "subject", "text", "description"):
        value = record.get(key)
        if isinstance(value, str) and value:
            parts.append(value)
        elif value is not None:
            parts.append(str(value))
    return " ".join(parts)


def normalize_record(record: Any) -> Dict[str, Any]:
    """Additive normalize: returns a copy of the record plus temporal keys.

    Never mutates the input; never raises (non-dict inputs degrade to an
    empty dict or a plain copy when they are already dict-shaped).
    """
    if not is_enabled("temporal_normalization"):
        if isinstance(record, dict):
            return dict(record)
        return {}
    try:
        base = dict(record) if isinstance(record, dict) else dict(record)
    except (TypeError, ValueError):
        return {}

    entities = extract_temporal(_record_text(base))
    if not entities:
        return base

    top = entities[0]
    payload = [asdict(e) for e in entities]
    base["temporal_entities"] = payload
    base["as_of"] = top.as_of.isoformat() if top.as_of else None
    base["temporal_axis"] = top.source_text or top.name
    return base


# ============================================================================
# temporal_entities memory receiver (A8): store / encode
# ============================================================================

_STORE: Dict[str, List[TemporalEntity]] = {}


def _reset_store() -> None:
    _STORE.clear()


def _coerce(raw: Any) -> Optional[TemporalEntity]:
    """Coerce a dict/dataclass into a TemporalEntity; skip invalid entries."""
    try:
        if isinstance(raw, TemporalEntity):
            return raw
        if isinstance(raw, dict):
            entity = TemporalEntity(
                name=str(raw.get("name") or ""),
                entity_type=str(raw.get("entity_type") or "date"),
                as_of=_parse_dt(raw.get("as_of")),
                valid_until=_parse_dt(raw.get("valid_until")),
                source_text=str(raw.get("source_text") or ""),
                confidence=float(raw.get("confidence") or 1.0),
                provenance=raw.get("provenance"),
            )
        elif hasattr(raw, "as_of"):
            entity = TemporalEntity(
                name=getattr(raw, "name", ""),
                entity_type=getattr(raw, "entity_type", "date"),
                as_of=getattr(raw, "as_of", None),
                valid_until=getattr(raw, "valid_until", None),
                source_text=getattr(raw, "source_text", ""),
                confidence=float(getattr(raw, "confidence", 1.0)),
                provenance=getattr(raw, "provenance", None),
            )
        else:
            return None
        if not entity.name or not entity.entity_type:
            return None
        entity.as_of = _to_utc(_parse_dt(entity.as_of))
        entity.valid_until = _to_utc(_parse_dt(entity.valid_until))
        if entity.as_of is None:
            return None
        return entity
    except Exception as e:
        logger.debug(f"Temporal entity skipped: {e}")
        return None


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def handle_temporal_entities(entities: Any, workspace_id: str, *, source: Optional[str] = None) -> int:
    """Store temporal entities for a workspace (temporal_entities receiver).

    Never raises; invalid entries are skipped. Returns the count stored.
    """
    if not is_enabled("temporal_normalization"):
        return 0
    try:
        ws = str(workspace_id)
        bucket = _STORE.setdefault(ws, [])
        stored = 0
        if isinstance(entities, dict):
            entities = [entities]
        for raw in entities or []:
            entity = _coerce(raw)
            if not entity:
                continue
            if not entity.provenance and source:
                entity.provenance = str(source)
            bucket.append(entity)
            stored += 1
        if len(bucket) > _MAX_ENTITIES_PER_WORKSPACE:
            # Keep the newest (sort is by as_of desc at encode time; trimming
            # oldest as_of keeps the timeline stable under heavy ingestion).
            bucket.sort(key=lambda e: e.as_of or datetime.min.replace(tzinfo=UTC))
            del bucket[: len(bucket) - _MAX_ENTITIES_PER_WORKSPACE]
        return stored
    except Exception as e:
        logger.debug(f"Temporal receiver failed: {e}")
        return 0


def _visible_at(entity: "TemporalEntity", t: datetime) -> bool:
    """Bi-temporal visibility: as_of <= t < valid_until (valid_until open)."""
    as_of = entity.as_of
    if as_of is None or as_of > t:
        return False
    return entity.valid_until is None or entity.valid_until > t


def encode_temporal_context(
    workspace_id: str, *, limit: int = 20, as_of: Optional[datetime] = None
) -> List[Dict[str, Any]]:
    """Re-encode stored entities for context assembly (bi-temporal read).

    Visible at time ``as_of`` when ``entity.as_of <= as_of`` and
    ``entity.valid_until is None or entity.valid_until > as_of`` — the same
    semantics as GraphRAGEngine.edges_as_of. Never raises.
    """
    if not is_enabled("temporal_normalization"):
        return []
    try:
        bucket = _STORE.get(str(workspace_id), [])
        if as_of is not None:
            t = _to_utc(as_of)
            assert t is not None
            bucket = [e for e in bucket if _visible_at(e, t)]
        bucket = sorted(bucket, key=lambda e: e.as_of or datetime.min.replace(tzinfo=UTC), reverse=True)
        out = []
        for e in bucket[:limit]:
            out.append({
                "name": e.name,
                "entity_type": e.entity_type,
                "as_of": e.as_of.isoformat() if e.as_of else None,
                "valid_until": e.valid_until.isoformat() if e.valid_until else None,
                "confidence": e.confidence,
                "source_text": e.source_text,
                "provenance": e.provenance,
            })
        return out
    except Exception as e:
        logger.debug(f"Temporal context encode failed: {e}")
        return []


# ============================================================================
# Service facade
# ============================================================================

class TemporalNormalizer:
    """Instance facade over the module functions (kept for DI/factory parity)."""

    def extract(self, text: Any, *, max_entities: int = _MAX_ENTITIES_PER_TEXT) -> List[TemporalEntity]:
        return extract_temporal(text, max_entities=max_entities)

    def normalize(self, record: Any) -> Dict[str, Any]:
        return normalize_record(record)

    def handle(self, entities: Any, workspace_id: str, *, source: Optional[str] = None) -> int:
        return handle_temporal_entities(entities, workspace_id, source=source)

    def encode(self, workspace_id: str, *, limit: int = 20, as_of: Optional[datetime] = None) -> List[Dict[str, Any]]:
        return encode_temporal_context(workspace_id, limit=limit, as_of=as_of)


_normalizer: Optional[TemporalNormalizer] = None


def get_temporal_normalizer() -> TemporalNormalizer:
    global _normalizer
    if _normalizer is None:
        _normalizer = TemporalNormalizer()
    return _normalizer