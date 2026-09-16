# -*- coding: utf-8 -*-
"""Auto-open relevance window (audit item 6d).

The harness opens the top cited artifact for the one-shot reply model. It used
to take a blind head (2600 chars) + tail (1200 chars), so any decisive line in
the MIDDLE of a long thread was omitted while the model was given no signal
that its view was partial — the "surviving citation is not a complete
derivation" failure, one layer down.

Now the window is centred on the query's own terms, and when nothing matches
the header says so explicitly. These tests pin both halves: the mid-document
hit, and the honesty statement on a miss.
"""
import pytest

import integrations.chat_orchestrator as co


class _Res:
    def __init__(self, content):
        self.content = content


def _provider_for(text):
    class _Prov:
        async def cat(self, path, ctx=None):
            return _Res(text)

    return _Prov


def _long_thread_with_mid_row():
    filler = [f"filler line {i} " + "z" * 160 for i in range(60)]
    row = ("R235 | Product Name=F-52\"x16G | LIST Price=7519.0 | "
           "Factory Price=5350 | $7,519.00")
    return "\n".join(filler[:30] + [row] + filler[30:]), row


@pytest.mark.asyncio
async def test_mid_document_row_is_surfaced(monkeypatch):
    text, row = _long_thread_with_mid_row()
    import integrations.vfs.knowledge_vfs as vfs
    monkeypatch.setattr(vfs, "KnowledgeVFSProvider", _provider_for(text))

    block = ("- [ingested mailbox] From: a@b.ca | quote | full: "
             "knowledge/conversations/msg-1")
    out = await co._auto_open_top_citation(
        block, query="figure out how the 7519 list price was derived")
    assert out is not None
    assert "R235" in out, "the decisive mid-document row was not surfaced"
    assert "$7,519.00" in out
    assert "window around line" in out, (
        "the header must say the window is a targeted region, so the model "
        "does not treat it as the whole artifact")


@pytest.mark.asyncio
async def test_head_tail_would_have_missed_it(monkeypatch):
    """Premise check for the test above — if this stops being true the
    relevance window is no longer load-bearing."""
    text, _row = _long_thread_with_mid_row()
    assert "R235" not in (text[:2600] + "\n…\n" + text[-1200:])


@pytest.mark.asyncio
async def test_unrelated_query_states_it_is_not_a_targeted_match(monkeypatch):
    text, _row = _long_thread_with_mid_row()
    import integrations.vfs.knowledge_vfs as vfs
    monkeypatch.setattr(vfs, "KnowledgeVFSProvider", _provider_for(text))

    block = "- [ingested mailbox] x | full: knowledge/conversations/msg-1"
    out = await co._auto_open_top_citation(
        block, query="completely unrelated zebra migration topic")
    assert out is not None
    assert "NOT a targeted match" in out, (
        "a miss must be stated, not silently presented as a full read")
    assert "do not present it as" in out


@pytest.mark.asyncio
async def test_short_artifact_is_reported_as_whole(monkeypatch):
    text = "L1 short body\nL2 second line"
    import integrations.vfs.knowledge_vfs as vfs
    monkeypatch.setattr(vfs, "KnowledgeVFSProvider", _provider_for(text))
    block = "- [ingested mailbox] x | full: knowledge/conversations/m1"
    out = await co._auto_open_top_citation(block, query="short body")
    assert out is not None
    assert "whole artifact" in out


@pytest.mark.asyncio
async def test_call_site_passes_the_turn_message():
    """Shape pin: without the query the window cannot be relevant."""
    import inspect

    src = inspect.getsource(co)
    assert "_auto_open_top_citation(_tool_block, query=message" in src, (
        "the production call site no longer passes the user's message, so "
        "the open is a blind head/tail again")
    assert "_auto_open_top_citation(_tool_block)" not in src
