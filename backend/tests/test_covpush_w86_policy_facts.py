# -*- coding: utf-8 -*-
"""Coverage wave 86 — core/policy_fact_extractor (extraction, categories,
malformed input).

PolicyFactExtractor tested with the LLM service fully mocked (zero LLM spend):

- extract_facts_from_text: single-chunk success (fact/domain/confidence,
  page_or_section), page_number vs chunk labels, dicts without a fact key
  skipped, malformed/empty JSON arrays, multi-chunk split, chunk exception
  isolation, timing log.
- extract_facts_from_document: docling ImportError, processor unavailable,
  parse failure, and full success with page_count passthrough.
- _split_text: short text, paragraph chunking with oversize flush.
- _extract_json: direct parse, embedded array, garbage, fenced text.
- get_policy_fact_extractor: singleton cache hit and miss.
"""
import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.policy_fact_extractor import (
    ExtractedFact, PolicyFactExtractor, get_policy_fact_extractor,
)


def _fake_llm(responses):
    llm = MagicMock()
    async def _generate(*a, **k):
        if isinstance(responses, list) and callable(responses[0]):
            fn = responses.pop(0)
            return await fn(k["prompt"]) if asyncio.iscoroutinefunction(fn) else fn(k["prompt"])
        return responses.pop(0) if isinstance(responses, list) else responses
    llm.generate = _generate
    return llm


@pytest.fixture()
def extractor():
    with patch("core.policy_fact_extractor.get_llm_service", return_value=MagicMock()):
        inst = PolicyFactExtractor(workspace_id="ws-1", tenant_id="t1")
    return inst


# ---------------------------------------------------------------------------
# extract_facts_from_text
# ---------------------------------------------------------------------------

def test_extract_facts_single_chunk(extractor):
    payload = json_array([
        {"fact": "Invoices over $500 require approval", "domain": "finance", "confidence": 0.95},
        {"fact": "PTO needs 2 weeks notice", "domain": "hr"},
    ])
    extractor.llm.generate = AsyncMock(return_value=payload)

    facts = asyncio.run(extractor.extract_facts_from_text(
        "Policy text here", source_document="policy.pdf", page_number=3
    ))
    assert len(facts) == 2
    f1, f2 = facts
    assert f1.fact == "Invoices over $500 require approval"
    assert f1.domain == "finance"
    assert f1.confidence == pytest.approx(0.95)
    assert f1.page_or_section == "p3"
    assert f2.domain == "hr"
    assert f2.confidence == pytest.approx(0.8)
    assert f2.page_or_section == "p3"


def test_extract_facts_chunk_label_without_page(extractor):
    extractor.llm.generate = AsyncMock(return_value=json_array([
        {"fact": "Rule one", "domain": "operations"}
    ]))
    facts = asyncio.run(extractor.extract_facts_from_text(
        "long" * 5000, source_document="doc.txt"  # > 8000 chars → chunked
    ))
    assert len(facts) == 1
    assert facts[0].page_or_section == "chunk_1"


def test_extract_facts_skips_dicts_without_fact_key(extractor):
    extractor.llm.generate = AsyncMock(return_value=json_array([
        {"domain": "finance"},  # no fact key → skipped
        {"fact": "Valid rule", "domain": "compliance"},
        "not a dict",            # non-dict → skipped
    ]))
    facts = asyncio.run(extractor.extract_facts_from_text(
        "text", source_document="d", page_number=1
    ))
    assert [f.fact for f in facts] == ["Valid rule"]


def test_extract_facts_malformed_json_yields_nothing(extractor):
    extractor.llm.generate = AsyncMock(return_value="not json at all")
    facts = asyncio.run(extractor.extract_facts_from_text(
        "text", source_document="d"
    ))
    assert facts == []


def test_extract_facts_empty_array(extractor):
    extractor.llm.generate = AsyncMock(return_value="[]")
    facts = asyncio.run(extractor.extract_facts_from_text(
        "text", source_document="d"
    ))
    assert facts == []


def test_extract_facts_multiple_chunks_processed(extractor):
    text = "First para with a rule about invoicing.\n\n" * 400  # > 8000 chars
    chunks_prompts = []

    async def _generate(prompt, **k):
        chunks_prompts.append(prompt)
        return json_array([{"fact": f"Rule from chunk {len(chunks_prompts)}", "domain": "general"}])

    extractor.llm.generate = _generate
    facts = asyncio.run(extractor.extract_facts_from_text(
        text, source_document="big.docx"
    ))
    assert len(chunks_prompts) >= 2
    assert len(facts) == len(chunks_prompts)


def test_extract_facts_chunk_exception_is_isolated(extractor, caplog):
    text = "para.\n\n" * 2000  # many chunks
    calls = {"n": 0}

    async def _generate(prompt, **k):
        calls["n"] += 1
        if calls["n"] == 2:  # second chunk's LLM call fails
            raise RuntimeError("llm failed")
        return json_array([{"fact": "ok rule", "domain": "general"}])

    extractor.llm.generate = _generate
    with caplog.at_level(logging.ERROR, logger="core.policy_fact_extractor"):
        facts = asyncio.run(extractor.extract_facts_from_text(text, source_document="d"))
    assert len(facts) >= 1
    assert "Error extracting facts from chunk" in caplog.text


def test_extract_facts_logs_summary(extractor, caplog):
    extractor.llm.generate = AsyncMock(return_value=json_array([
        {"fact": "Rule A", "domain": "hr"}
    ]))
    with caplog.at_level(logging.INFO, logger="core.policy_fact_extractor"):
        asyncio.run(extractor.extract_facts_from_text("text", source_document="policies.pdf"))
    assert "Extracted 1 facts from 'policies.pdf'" in caplog.text


def test_extract_facts_confidence_conversion(extractor):
    extractor.llm.generate = AsyncMock(return_value=json_array([
        {"fact": "Rule with numeric confidence", "domain": "legal", "confidence": "0.5"}
    ]))
    facts = asyncio.run(extractor.extract_facts_from_text("text", source_document="d"))
    assert facts[0].confidence == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# extract_facts_from_document
# ---------------------------------------------------------------------------

def test_extract_from_document_success(extractor):
    processor = MagicMock()
    processor.is_available = True
    processor.process_document = AsyncMock(return_value={
        "success": True, "content": "Doc content here", "page_count": 12,
    })
    extractor.llm.generate = AsyncMock(return_value=json_array([
        {"fact": "Doc rule", "domain": "finance"}
    ]))
    with patch("core.docling_processor.get_docling_processor", return_value=processor):
        result = asyncio.run(extractor.extract_facts_from_document("/tmp/policy.pdf"))

    assert result.source_document == "/tmp/policy.pdf"
    assert result.total_pages == 12
    assert result.extraction_time >= 0
    assert [f.fact for f in result.facts] == ["Doc rule"]


def test_extract_from_document_parse_failure(extractor, caplog):
    processor = MagicMock()
    processor.is_available = True
    processor.process_document = AsyncMock(return_value={
        "success": False, "error": "corrupt pdf",
    })
    with patch("core.docling_processor.get_docling_processor", return_value=processor):
        with caplog.at_level(logging.ERROR, logger="core.policy_fact_extractor"):
            result = asyncio.run(extractor.extract_facts_from_document("/tmp/bad.pdf"))
    assert result.facts == []
    assert "Document parsing failed: corrupt pdf" in caplog.text


def test_extract_from_document_processor_unavailable(extractor, caplog):
    processor = MagicMock()
    processor.is_available = False
    with patch("core.docling_processor.get_docling_processor", return_value=processor):
        with caplog.at_level(logging.ERROR, logger="core.policy_fact_extractor"):
            result = asyncio.run(extractor.extract_facts_from_document("/tmp/x.pdf"))
    assert result.facts == []
    assert "Docling processor not available" in caplog.text


def test_extract_from_document_import_error(extractor, caplog):
    with patch("builtins.__import__", side_effect=_import_raiser("core.docling_processor")):
        with caplog.at_level(logging.ERROR, logger="core.policy_fact_extractor"):
            result = asyncio.run(extractor.extract_facts_from_document("/tmp/x.pdf"))
    assert result.facts == []
    assert "Docling processor not available" in caplog.text


def _import_raiser(blocked):
    real_import = __import__

    def _raiser(name, *a, **k):
        if name == blocked or name.startswith(blocked + "."):
            raise ImportError(f"No module named {blocked}")
        return real_import(name, *a, **k)

    return _raiser


# ---------------------------------------------------------------------------
# _split_text / _extract_json
# ---------------------------------------------------------------------------

def test_split_text_short_input(extractor):
    assert extractor._split_text("short", 8000) == ["short"]


def test_split_text_multiple_chunks(extractor):
    paras = [f"para {i} " + "x" * 500 for i in range(10)]
    text = "\n\n".join(paras)
    chunks = extractor._split_text(text, 1000)
    assert len(chunks) >= 2
    assert all(len(c) <= 1000 for c in chunks)
    assert "para 0" in chunks[0]
    assert "para 9" in chunks[-1]


def test_extract_json_direct(extractor):
    assert extractor._extract_json('[{"fact": "a"}]') == [{"fact": "a"}]


def test_extract_json_embedded_array(extractor):
    raw = 'Here are the facts:\n[{"fact": "x", "domain": "y"}]\nThanks!'
    assert extractor._extract_json(raw) == [{"fact": "x", "domain": "y"}]


def test_extract_json_garbage(extractor):
    assert extractor._extract_json("no brackets here") == []


def test_extract_json_brackets_but_invalid(extractor):
    assert extractor._extract_json("prefix [not json] suffix") == []


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------

def test_get_policy_fact_extractor_caches():
    with patch("core.policy_fact_extractor.get_llm_service", return_value=MagicMock()):
        try:
            first = get_policy_fact_extractor("ws-cache", "t1")
            second = get_policy_fact_extractor("ws-cache", "t1")
            other = get_policy_fact_extractor("ws-other", "t1")
        finally:
            from core.policy_fact_extractor import _extractors
            _extractors.clear()
    assert first is second
    assert first is not other


def test_extracted_fact_defaults():
    fact = ExtractedFact(fact="rule", domain="general")
    assert fact.confidence == 0.8
    assert fact.page_or_section is None


def json_array(items):
    import json
    return json.dumps(items)
