"""Ingestion must preserve HTML email tables — like Outlook does.

Live gap (2026-09-02): quote/spec tables in emails were flattened by
_html_to_text into indistinguishable lines, so agents could not recognize
a table in ingested data or rebuild one in the email canvas. After this:
data tables become markdown in content (FTS/vector + LLM readable) and
structured rows ride in metadata["tables"]; single-column signature/layout
tables are skipped.
"""

from integrations.atom_communication_ingestion_pipeline import (
    _html_to_text,
    _html_to_text_with_tables,
)

QUOTE_EMAIL = """<html><body>
<p>Hi Rish,</p>
<p>Quote options below:</p>
<table border="1"><tbody>
<tr><td>Machine</td><td>Price</td><td>Delivery</td></tr>
<tr><td>Linmac WG-350DSAV</td><td>$12,400</td><td>6 weeks</td></tr>
<tr><td>HYDMECH DM-10 (used)</td><td>$8,900</td><td>2 weeks</td></tr>
</tbody></table>
<p>Thanks, Jacob Schulz</p>
<table><tr><td>Rish M.</td></tr></table>
</body></html>"""


def test_data_table_becomes_markdown_and_metadata():
    text, tables = _html_to_text_with_tables(QUOTE_EMAIL)
    assert "| Machine | Price | Delivery |" in text
    assert "| Linmac WG-350DSAV | $12,400 | 6 weeks |" in text
    assert "---" in text
    assert len(tables) == 1, "the 1-column signature/layout table is skipped"
    assert tables[0]["n_cols"] == 3 and tables[0]["n_rows"] == 3  # header + 2 data rows
    assert tables[0]["rows"][0] == ["Machine", "Price", "Delivery"]
    assert tables[0]["rows"][1] == ["Linmac WG-350DSAV", "$12,400", "6 weeks"]


def test_plain_html_without_tables_unchanged():
    text, tables = _html_to_text_with_tables("<p>Hi Jacob,</p><p>Any news?</p>")
    assert "Hi Jacob," in text and "Any news?" in text
    assert tables == []


def test_legacy_html_to_text_still_strips_tags():
    assert "Hi" in _html_to_text("<p>Hi</p> <b>Jacob</b>")


def test_no_table_marker_is_a_fast_noop():
    # No '<table' in the body: no parsing work at all.
    text, tables = _html_to_text_with_tables("<p>plain day</p>")
    assert tables == [] and "plain day" in text
