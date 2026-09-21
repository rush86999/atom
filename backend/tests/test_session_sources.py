"""Per-conversation source handles, re-extracted from the transcript.

RCA 2026-09-17 finding 3: the PRICE VIPUL workbook was opened on one turn
and denied to exist the next. The transcript is the durable store — these
tests pin extraction from assistant/user text, dedupe, bounds, and the
planner-prompt block.
"""
from core.session_sources import (
    conversation_source_names,
    conversation_sources_block,
    extract_source_handles,
)


def test_extracts_workbook_and_document_names():
    text = ("The PRICE VIPUL (6).xlsx workbook, Sheet1, row 235 gives the "
            "chain. See also report_v2.pdf for the RFQ.")
    assert extract_source_handles([text]) == [
        "PRICE VIPUL (6).xlsx", "report_v2.pdf"]


def test_dedupes_case_insensitively():
    text = ("price vipul (6).xlsx first, and later PRICE VIPUL (6).xlsx "
            "again")
    assert extract_source_handles([text]) == ["price vipul (6).xlsx"]


def test_bare_extension_is_not_a_filename():
    assert extract_source_handles(["convert it to .pdf please"]) == []


def test_cap_bounds_output_newest_first_input():
    texts = [f"file_{i}.xlsx attached" for i in range(12)]
    out = extract_source_handles(texts, cap=8)
    assert len(out) == 8
    assert out[0] == "file_0.xlsx"


def test_history_newest_first_and_errors_skipped():
    history = [
        {"message": "old ask", "response": {"message": "see old.xlsx"}},
        {"message": "failed ask", "error": True,
         "response": {"message": "failed_run.csv"}},
        {"message": "later ask",
         "response": {"message": "Opened PRICE VIPUL (6).xlsx for you."}},
    ]
    names = conversation_source_names(history)
    assert names[0] == "PRICE VIPUL (6).xlsx"
    assert "old.xlsx" in names
    assert "failed_run.csv" not in names


def test_block_names_sources_and_requires_reuse():
    history = [{"message": "find the price list",
                "response": {"message": "Found PRICE VIPUL (6).xlsx — "
                                        "Sheet1, 240 rows."}}]
    block = conversation_sources_block(history)
    assert "PRICE VIPUL (6).xlsx" in block
    assert "SOURCES RETRIEVED EARLIER" in block
    assert "instead of searching elsewhere" in block


def test_a_mention_is_never_reported_as_retrieved():
    """R1 (review 2026-09-17): provenance must be earned, not inferred.

    The user asking about a file and the assistant FAILING to find it is not a
    discovery. The old block called it "already found once" and told the planner
    to REUSE it — how a nonexistent file becomes asserted fact.
    """
    history = [{"message": "Find vendor_scorecard.xlsx",
                "response": {"message": "I could not locate it."}}]
    block = conversation_sources_block(history)
    assert "RETRIEVED EARLIER" not in block
    assert "NOT CONFIRMED AS RETRIEVED" in block
    assert "instead of searching elsewhere" not in block, (
        "an unconfirmed name must not be described as reusable"
    )


def test_mention_handle_strips_the_request_verb():
    """The handle is the file, not the ask: 'Find vendor_scorecard.xlsx'
    must yield 'vendor_scorecard.xlsx' (find/search/locate are request
    verbs, not name fragments — added to _LEADING_STOPWORDS 2026-09-17)."""
    from core.session_sources import extract_source_handles

    handles = extract_source_handles(
        ["Find vendor_scorecard.xlsx", "search for the RFQ list.pdf",
         "locate price_august.xlsx"])
    assert "vendor_scorecard.xlsx" in handles
    assert "price_august.xlsx" in handles
    assert not any(h.split(".")[0].split()[-1] in
                   ("find", "search", "locate", "try") for h in handles)


def test_an_openable_path_proves_retrieval():
    history = [{"message": "open it",
                "response": {"message": "Opened PRICE VIPUL (6).xlsx (open: "
                                        "knowledge/documents/ext_1/content.lines)"}}]
    assert "SOURCES RETRIEVED EARLIER" in conversation_sources_block(history)


def test_block_empty_when_nothing_located():
    history = [{"message": "hello",
                "response": {"message": "Hi! How can I help?"}}]
    assert conversation_sources_block(history) == ""
    assert conversation_sources_block([]) == ""


# --- Step-2 durable source refs (2026-09-20): the openable path is the
# identity; the display name is not. ---

def test_ref_pairs_name_with_openable_path():
    from core.session_sources import conversation_source_refs

    history = [{"message": "open it",
                "response": {"message": (
                    "Opened PRICE VIPUL (6).xlsx (open: "
                    "knowledge/documents/ext_1/content.lines) — Sheet1, "
                    "240 rows.")}}]
    refs = conversation_source_refs(history)
    assert refs == [{"name": "PRICE VIPUL (6).xlsx",
                     "path": "knowledge/documents/ext_1/content.lines"}]


def test_ref_block_carries_the_reopen_instruction():
    from core.session_sources import conversation_sources_block

    history = [{"message": "open it",
                "response": {"message": (
                    "Opened PRICE VIPUL (6).xlsx (open: "
                    "knowledge/documents/ext_1/content.lines) — Sheet1, "
                    "240 rows.")}}]
    block = conversation_sources_block(history)
    assert "reopen by path: knowledge/documents/ext_1/content.lines" in block
    assert "documents.read" in block


def test_same_name_different_paths_both_survive():
    """The acceptance matrix's display-name collision row: two stores hold
    same-named files — the PATH disambiguates, both refs are listed."""
    from core.session_sources import conversation_source_refs

    history = [
        {"message": "open it",
         "response": {"message": (
             "Opened price list.xlsx (open: "
             "knowledge/documents/ext_9/content.lines) — older copy.")}},
        {"message": "open it again",
         "response": {"message": (
             "Opened price list.xlsx (open: "
             "knowledge/documents/ext_2/content.lines) — the one from the "
             "email.")}},
    ]
    refs = conversation_source_refs(history)
    paths = {r["path"] for r in refs}
    assert paths == {"knowledge/documents/ext_9/content.lines",
                     "knowledge/documents/ext_2/content.lines"}
    assert all(r["name"] == "price list.xlsx" for r in refs)


def test_no_pairing_when_reply_names_two_files():
    """A wrong (name, path) pairing reopens the wrong file. The extractor's
    documented prose-spanning yields a GLUED handle for two-file sentences
    ("price list.xlsx and notes.docx" — interior extension dot); such a
    handle must never receive a path."""
    from core.session_sources import conversation_source_refs

    history = [{"message": "open both",
                "response": {"message": (
                    "Opened price list.xlsx and notes.docx (open: "
                    "knowledge/documents/ext_1/content.lines).")}}]
    refs = conversation_source_refs(history)
    assert refs, "the glued handle is still a name-only hint"
    assert all(r["path"] == "" for r in refs)


def test_no_pairing_when_two_paths_one_name():
    history = [{"message": "open it",
                "response": {"message": (
                    "Opened price list.xlsx — see "
                    "full: knowledge/documents/a/content.lines and "
                    "open: knowledge/documents/b/content.lines.")}}]
    from core.session_sources import conversation_source_refs

    refs = conversation_source_refs(history)
    assert refs and refs[0]["path"] == ""
