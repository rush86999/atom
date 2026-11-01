"""GraphRAG extraction must degrade to the deterministic extractor."""
import pytest

from core.graphrag_engine import GraphRAGEngine


@pytest.mark.asyncio
async def test_failed_llm_extraction_falls_back_to_patterns(monkeypatch):
    engine = GraphRAGEngine()

    async def _no_llm(*args, **kwargs):
        return [], []

    monkeypatch.setattr(engine, "_is_llm_available", lambda *a, **k: True)
    monkeypatch.setattr(engine, "_llm_extract_entities_and_relationships", _no_llm)

    captured = {}

    def _ingest_structured(workspace_id=None, tenant_id=None, entities=None,
                           relationships=None):
        captured["entities"] = entities or []
        captured["relationships"] = relationships or []
        return {"entities": len(captured["entities"]),
                "relationships": len(captured["relationships"])}

    monkeypatch.setattr(engine, "ingest_structured_data", _ingest_structured)

    result = await engine.ingest_document(
        workspace_id="default",
        doc_id="fallback-doc",
        text="Contact alice@example.com on 2026-10-01 or visit https://example.com/a.",
        source="test",
    )

    names = {e["name"] for e in captured["entities"]}
    assert "alice@example.com" in names
    assert "https://example.com/a" in names
    assert result["entities"] >= 2
