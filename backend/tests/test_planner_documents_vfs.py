"""The documents (knowledge VFS) planner lane.

Search lanes hand the model bounded EXCERPTS; the grounding rule cites
'full: knowledge/conversations/<id>' and says to open it with
documents.cat / search everything with documents.grep. Until this lane
existed the chat planner had NO 'documents' service — no catalog entry,
no dispatch — so the promised follow-up turn could never run: long
threads were excerpts the agent could not open (live 2026-09-13, the
canvas a1a13834 incident's closing gap). These tests pin the routing,
the path/pattern normalization, and the honest-failure contracts.
"""

import asyncio
import importlib

import pytest

import core.chat_tool_planner as planner
from core.chat_tool_planner import (
    ToolPlan,
    _documents_vfs_block,
    _normalize_vfs_path,
    _split_vfs_grep_query,
    execute_tool_plan,
)


# --- path + grep-query normalization ---------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        # Evidence lines cite 'full: <path>' — the planner may copy it whole.
        ("full: knowledge/conversations/AAMk99=", "knowledge/conversations/AAMk99=/content.lines"),
        ("knowledge/conversations/AAMk99=/content.lines", "knowledge/conversations/AAMk99=/content.lines"),
        ("open knowledge/documents/doc-1/meta.json please", "knowledge/documents/doc-1/meta.json"),
        ("knowledge/documents/doc-1", "knowledge/documents/doc-1/content.lines"),
        ("", ""),
        ("no path in here at all", ""),
    ],
)
def test_normalize_vfs_path(raw, expected):
    assert _normalize_vfs_path(raw) == expected


@pytest.mark.parametrize(
    "query,pattern,prefix",
    [
        ("5,350.00 in knowledge/conversations", "5,350.00", "knowledge/conversations"),
        ('"WG-350DSAV" under knowledge/documents', "WG-350DSAV", "knowledge/documents"),
        ("grep F-5216", "F-5216", "knowledge"),
        ("search for Tennsmith", "Tennsmith", "knowledge"),
        ("5,350.00", "5,350.00", "knowledge"),
        # A scope word without the tree prefix is completed.
        ("payment terms in conversations", "payment terms", "knowledge/conversations"),
    ],
)
def test_split_vfs_grep_query(query, pattern, prefix):
    assert _split_vfs_grep_query(query) == (pattern, prefix)


# --- lane execution (registry mocked at the action boundary) ----------------


class _FakeAction:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def __call__(self, name, args, context):
        self.calls.append((name, dict(args)))
        return self.result


def _plan(intent, query):
    return ToolPlan(
        use_tool=True, service="documents", intent=intent, query=query
    )


def test_cat_intent_routes_to_registry_with_normalized_path(monkeypatch):
    fake = _FakeAction(
        {
            "success": True,
            "content": "L1: $ 5,350.00 – 10 %  in stock\nL2: Do you prefer a used shear ?",
            "line_count": 2,
            "meta": {"timestamp": "2026-08-26 14:06:28"},
            "path": "knowledge/conversations/id-1/content.lines",
        }
    )
    monkeypatch.setattr(
        "core.action_registry.action_registry.execute_action", fake
    )
    block = asyncio.run(
        _documents_vfs_block(
            _plan("cat", "full: knowledge/conversations/id-1"),
            "u1",
            {"history": []},
        )
    )
    name, args = fake.calls[0]
    assert name == "documents.cat"
    assert args["path"] == "knowledge/conversations/id-1/content.lines"
    assert "L1: $ 5,350.00" in block
    assert "received: 2026-08-26 14:06:28" in block


def test_cat_of_a_huge_body_elides_the_middle(monkeypatch):
    """79k-char threads must not flood the prompt: the cat block carries a
    bounded head+tail with an honest elision marker (the middle stays
    reachable via grep citations + documents.read windows)."""
    big = "\n".join(f"L{i}: filler line {i}" for i in range(1, 4000))
    fake = _FakeAction(
        {"success": True, "content": big, "line_count": 3999, "meta": {}}
    )
    monkeypatch.setattr(
        "core.action_registry.action_registry.execute_action", fake
    )
    block = asyncio.run(
        _documents_vfs_block(
            _plan("cat", "knowledge/conversations/id-1"), "u1", {}
        )
    )
    assert fake.calls[0][0] == "documents.cat"
    assert "middle elided" in block
    assert len(block) < planner._DOCUMENTS_VFS_CAT_CAP + 3000


def test_read_intent_dispatches_documents_read_with_the_hints_kwargs(monkeypatch):
    """The grounding rule and every grep citation hint advertise
    documents.read(path, start_line, max_lines) — the lane must dispatch
    exactly that. It used to alias "read" to whole-file cat and DROP the
    kwargs, so the middle-elision cap could hide precisely the region a
    citation pointed at (2026-09-15 review: the advertised paging loop
    could never run)."""
    fake = _FakeAction(
        {
            "success": True,
            "content": "L313: R235 | F-52\"x16G | 7519.0",
            "path": "knowledge/documents/doc-1/content.lines",
            "start_line": 313, "end_line": 313, "total_lines": 324,
            "next_start": 314, "returned_lines": 1, "complete": False,
            "degraded": False,
        }
    )
    monkeypatch.setattr(
        "core.action_registry.action_registry.execute_action", fake
    )
    block = asyncio.run(
        _documents_vfs_block(
            _plan(
                "read",
                "documents.read(path='knowledge/documents/doc-1/content.lines',"
                " start_line=313, max_lines=20)",
            ),
            "u1",
            {},
        )
    )
    name, args = fake.calls[0]
    assert name == "documents.read"
    assert args["path"] == "knowledge/documents/doc-1/content.lines"
    assert args["start_line"] == 313 and args["max_lines"] == 20
    assert "L313: R235" in block
    # the paging loop the grounding rule promises: where to continue
    assert "lines 313–313 of 324" in block
    assert "start_line=314" in block


def test_read_intent_without_kwargs_reads_a_bounded_first_window(monkeypatch):
    """A bare 'read <path>' keeps the anti-flood intent of the old
    read→cat+elision alias, but via the bounded primitive: first 200 lines
    with paging metadata, never a whole 79k-char dump."""
    fake = _FakeAction(
        {
            "success": True,
            "content": "\n".join(f"L{i}: row {i}" for i in range(1, 201)),
            "path": "knowledge/conversations/id-1/content.lines",
            "start_line": 1, "end_line": 200, "total_lines": 3999,
            "next_start": 201, "returned_lines": 200, "complete": False,
            "degraded": False,
        }
    )
    monkeypatch.setattr(
        "core.action_registry.action_registry.execute_action", fake
    )
    block = asyncio.run(
        _documents_vfs_block(
            _plan("read", "knowledge/conversations/id-1"), "u1", {}
        )
    )
    name, args = fake.calls[0]
    assert name == "documents.read"
    assert args == {
        "path": "knowledge/conversations/id-1/content.lines",
        "start_line": 1,
        "max_lines": 200,
    }
    assert "lines 1–200 of 3999" in block
    assert "start_line=201" in block


def test_read_intent_clamps_an_echoed_huge_max_lines(monkeypatch):
    """The lane clamps max_lines at _DOCUMENTS_VFS_READ_MAX_LINES — a
    planner query echoing max_lines=50000 must not inject 50k lines."""
    fake = _FakeAction(
        {"success": True, "content": "L1: x", "returned_lines": 1,
         "start_line": 1, "end_line": 1, "total_lines": 1,
         "next_start": None, "complete": True, "degraded": False}
    )
    monkeypatch.setattr(
        "core.action_registry.action_registry.execute_action", fake
    )
    asyncio.run(
        _documents_vfs_block(
            _plan(
                "read",
                "knowledge/documents/doc-1/content.lines start_line=5 "
                "max_lines=50000",
            ),
            "u1",
            {},
        )
    )
    name, args = fake.calls[0]
    assert name == "documents.read"
    assert args["max_lines"] == planner._DOCUMENTS_VFS_READ_MAX_LINES
    assert args["start_line"] == 5


def test_degraded_read_is_an_error_not_end_of_artifact(monkeypatch):
    """A read that failed partway must SAY so: rendering it as a normal
    (empty/complete) window invites 'the figure isn't in the file'
    conclusions from a transient store error."""
    fake = _FakeAction(
        {"success": True, "content": "", "returned_lines": 0,
         "total_lines": 900, "start_line": 300, "degraded": True,
         "next_start": None, "complete": False}
    )
    monkeypatch.setattr(
        "core.action_registry.action_registry.execute_action", fake
    )
    block = asyncio.run(
        _documents_vfs_block(
            _plan(
                "read",
                "documents.read(path='knowledge/documents/doc-1/content.lines',"
                " start_line=300, max_lines=20)",
            ),
            "u1",
            {},
        )
    )
    assert "DEGRADED" in block
    assert "NOT the end of the artifact" in block


def test_grep_intent_renders_line_citations(monkeypatch):
    fake = _FakeAction(
        {
            "success": True,
            "pattern": "5,350.00",
            "matches": [
                {"path": "knowledge/conversations/id-1", "line": 81,
                 "snippet": "$ 5,350.00 – 10 %  in stock"},
                {"path": "knowledge/conversations/id-2", "line": 4,
                 "snippet": "quoted 5,350.00 below"},
            ],
        }
    )
    monkeypatch.setattr(
        "core.action_registry.action_registry.execute_action", fake
    )
    block = asyncio.run(
        _documents_vfs_block(
            _plan("grep", "5,350.00 in knowledge/conversations"), "u1", {}
        )
    )
    name, args = fake.calls[0]
    assert name == "documents.grep"
    assert args == {"pattern": "5,350.00", "path_prefix": "knowledge/conversations"}
    assert "knowledge/conversations/id-1:L81:" in block
    assert "$ 5,350.00 – 10 %  in stock" in block


def test_cat_of_missing_id_is_honest_not_empty_success(monkeypatch):
    """The provider returns an empty resource for unknown ids wrapped in
    success=True — the lane must say 'no stored message', not render an
    empty COMPLETE-message block."""
    fake = _FakeAction({"success": True, "content": "", "line_count": 0, "meta": {}})
    monkeypatch.setattr(
        "core.action_registry.action_registry.execute_action", fake
    )
    block = asyncio.run(
        _documents_vfs_block(
            _plan("cat", "knowledge/conversations/not-there"), "u1", {}
        )
    )
    assert "no stored message" in block
    # Not the success header (the grounding boilerplate also uses the word
    # "COMPLETE" — pin the header phrase, not the bare word).
    assert "COMPLETE stored message" not in block


def test_ls_leads_with_truncation_note(monkeypatch):
    """A truncated listing must SAY what it is not showing — the note node
    renders first, not lost under the entry cap."""
    fake = _FakeAction(
        {
            "success": True,
            "path": "knowledge/conversations",
            "entries": [
                {"name": "id-1", "type": "file", "path": "knowledge/conversations/id-1",
                 "size": 3475, "modified": "2026-08-26 14:06:28",
                 "meta": {"sender": "joelseguin@seguinmach.com", "subject": "FW: RFQ - Foot shear"}},
                {"name": "(showing 2000 of 7009 messages — newest first; use documents.grep)",
                 "type": "note", "path": "knowledge/conversations#truncated"},
            ],
        }
    )
    monkeypatch.setattr(
        "core.action_registry.action_registry.execute_action", fake
    )
    block = asyncio.run(
        _documents_vfs_block(_plan("ls", "knowledge/conversations"), "u1", {})
    )
    assert fake.calls[0][0] == "documents.ls"
    assert block.index("showing 2000 of 7009") < block.index("id-1")
    assert "joelseguin@seguinmach.com" in block


def test_kill_switch_returns_disabled_note(monkeypatch):
    fake = _FakeAction({"success": True, "content": "never runs"})
    monkeypatch.setattr(
        "core.action_registry.action_registry.execute_action", fake
    )
    monkeypatch.setattr(
        "core.knowledge_vfs_config.knowledge_vfs_enabled", lambda: False
    )
    block = asyncio.run(
        _documents_vfs_block(_plan("grep", "5,350.00"), "u1", {})
    )
    assert "disabled" in block
    assert not fake.calls


def test_execute_tool_plan_routes_documents_service(monkeypatch):
    """The lane must be reachable from the planner's dispatch, not just
    directly — this is the wiring the grounding rule promises."""
    captured = {}

    async def fake_block(plan, user_id, context):
        captured["plan"] = plan
        captured["user"] = user_id
        return "VFS BLOCK"

    monkeypatch.setattr(planner, "_documents_vfs_block", fake_block)
    out = asyncio.run(
        execute_tool_plan(
            ToolPlan(use_tool=True, service="documents", intent="cat",
                     query="knowledge/conversations/id-1"),
            "u1",
            "default",
            context={},
        )
    )
    assert out == "VFS BLOCK"
    assert captured["plan"].service == "documents"
    assert captured["user"] == "u1"


def test_documents_in_planner_catalog_when_enabled(monkeypatch):
    """No catalog entry, no plan: the planner LLM can only offer services
    the catalog lists. 'documents' appears when the VFS flag is on and not
    when it is off."""
    monkeypatch.setattr(
        "core.knowledge_vfs_config.knowledge_vfs_enabled", lambda: True
    )
    assert "documents" in planner._available_platform_services()
    assert "documents" in planner._SERVICE_DESCRIPTIONS
    monkeypatch.setattr(
        "core.knowledge_vfs_config.knowledge_vfs_enabled", lambda: False
    )
    assert "documents" not in planner._available_platform_services()


def test_documents_excluded_from_ingest():
    """No upstream integration to pull from — an ingest plan for documents
    must fall through to the search/read lanes, never an ingest pull."""
    assert "documents" in planner._INGEST_EXCLUDED_SERVICES


def test_search_shaped_plan_with_a_vfs_path_reroutes_to_cat(monkeypatch):
    """'open that full message' planned as intent=search with the cited
    path as the query (live 2026-09-13 flash-planner behavior) must CAT the
    path, not grep for the path string."""
    fake = _FakeAction(
        {"success": True, "content": "L1: $ 5,350.00 – 10 %  in stock",
         "line_count": 1, "meta": {}}
    )
    monkeypatch.setattr(
        "core.action_registry.action_registry.execute_action", fake
    )
    block = asyncio.run(
        _documents_vfs_block(
            _plan("search", "knowledge/conversations/id-1/content.lines"),
            "u1",
            {},
        )
    )
    assert fake.calls[0][0] == "documents.cat"
    assert "L1: $ 5,350.00" in block


def test_grep_with_a_path_mention_stays_grep(monkeypatch):
    """A genuine content search that NAMES a path in passing must not be
    rerouted: only a query that IS (mostly) a path is an open request."""
    fake = _FakeAction(
        {"success": True, "pattern": "5,350.00", "matches": []}
    )
    monkeypatch.setattr(
        "core.action_registry.action_registry.execute_action", fake
    )
    asyncio.run(
        _documents_vfs_block(
            _plan("search", "5,350.00 in knowledge/conversations"), "u1", {}
        )
    )
    assert fake.calls[0][0] == "documents.grep"


def test_grep_narrow_result_hydrates_top_hit(monkeypatch):
    """One-shot turns cannot chain grep→cat: a narrow grep result (≤3
    distinct messages) must carry the top hit's FULL line-numbered text in
    the SAME block — otherwise the model honestly reports the rest of the
    body 'isn't in front of me yet' while the thread sat one call away
    (live 2026-09-13)."""
    results = {
        "documents.grep": {
            "success": True,
            "pattern": "Fintek F5216",
            "matches": [
                {"path": "knowledge/conversations/id-1", "line": 51,
                 "snippet": "- 18896-99_Fintek F5216 Foot Shear (1).doc"},
            ],
        },
        "documents.cat": {
            "success": True,
            "content": "L1: $ 5,350.00 – 10 %  in stock\nL2: Do you prefer a used shear ?",
            "line_count": 2,
            "meta": {},
        },
    }

    class _Routing:
        calls = []

        async def __call__(self, name, args, context):
            self.calls.append(name)
            return results[name]

    routing = _Routing()
    monkeypatch.setattr(
        "core.action_registry.action_registry.execute_action", routing
    )
    block = asyncio.run(
        _documents_vfs_block(_plan("grep", "Fintek F5216"), "u1", {})
    )
    assert routing.calls == ["documents.grep", "documents.cat"]
    assert routing.calls[1] == "documents.cat"
    assert "FULL TEXT of the top hit" in block
    assert "L1: $ 5,350.00 – 10 %  in stock" in block
