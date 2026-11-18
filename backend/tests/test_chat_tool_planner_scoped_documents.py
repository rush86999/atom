"""Documents search/find plans scoped by an explicit uploaded-only ask.

The Chat relevance gate and the defensive VFS executor share
``_scoped_document_query``. These tests exercise that helper's real
predicate/parser path; they never pass a caller-invented effective string.
"""
from types import SimpleNamespace

from core.chat_tool_planner import _scoped_document_query


SCOPED_ASK = (
    "Using my uploaded documentation only, what warranty period applies "
    "to the WG-350DSAV?"
)
INVENTED_QUERY = "knowledge/conversations/conv-42/content.lines"


def _plan(intent: str, service: str = "documents"):
    return SimpleNamespace(
        service=service, intent=intent, query=INVENTED_QUERY)


def test_search_plan_normalizes_to_the_scoped_original_turn():
    assert _scoped_document_query(_plan("search"), SCOPED_ASK) == SCOPED_ASK


def test_find_plan_normalizes_to_the_scoped_original_turn():
    assert _scoped_document_query(_plan("find"), SCOPED_ASK) == SCOPED_ASK


def test_explicit_grep_cat_and_read_keep_their_vfs_query():
    for intent in ("grep", "cat", "read"):
        assert _scoped_document_query(_plan(intent), SCOPED_ASK) is None


def test_unqualified_search_keeps_the_planner_query():
    assert _scoped_document_query(
        _plan("search"),
        "Find the WG-350DSAV warranty period") is None


def test_non_document_plans_are_untouched():
    assert _scoped_document_query(
        _plan("search", service="canvas"), SCOPED_ASK) is None
    assert _scoped_document_query(
        _plan("search", service="outlook"), SCOPED_ASK) is None


def test_empty_scope_is_not_normalized():
    assert _scoped_document_query(
        _plan("search"), "Using my uploaded documentation only,   ") is None
