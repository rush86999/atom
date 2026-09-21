"""Planner-prompt routing contracts (2026-09-20 gap fixes).

Live evidence (2026-09-17 four-turn acceptance, scratch canvas e275e9ce):
"open PRICE VIPUL (6).xlsx and check R235" routed THREE TIMES to
documents.grep — whose tree does not hold spreadsheet rows — while the
workbook lived in the dataset catalog; the turn that happened to add
"K235" to the query routed to datasets and succeeded. The catalog is the
planner's ONLY capability signal, so the descriptions must say where a
named spreadsheet opens. Same session: a not-found evidence block
produced "I will open it now — shall I proceed?" (an action the reply
cannot take, re-asking authorization the user had just given).
"""


def test_datasets_description_names_the_spreadsheet_open_lane():
    from core.chat_tool_planner import _SERVICE_DESCRIPTIONS

    desc = _SERVICE_DESCRIPTIONS["datasets"]
    assert "OPEN a named spreadsheet" in desc
    assert "*.xlsx" in desc or "xlsx" in desc
    assert "search its filename HERE" in desc


def test_documents_description_redirects_spreadsheet_rows():
    from core.chat_tool_planner import _SERVICE_DESCRIPTIONS

    desc = _SERVICE_DESCRIPTIONS["documents"]
    assert "SPREADSHEET rows are NOT here" in desc
    assert "datasets" in desc


def test_grounding_rule_forbids_promised_actions_and_reasking():
    """The T2b shape: tools already ran pre-reply; the model must not
    promise 'I will open it now' nor re-ask authorization the current
    message already gave."""
    from core.chat_tool_planner import _GROUNDING_RULE

    assert "NEVER promise an action in this reply" in _GROUNDING_RULE
    assert "already authorized" in _GROUNDING_RULE
    assert "offer the NEXT concrete search" in _GROUNDING_RULE
    # prior contracts survive the extension (deepseek's in-flight tests
    # depend on the absence-claim wording staying)
    assert "as wide as the search performed" in _GROUNDING_RULE
    assert "COMPLETE coverage" not in _GROUNDING_RULE
