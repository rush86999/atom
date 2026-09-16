# -*- coding: utf-8 -*-
"""Relevant-window containment (incident closure item 5).

``relevant_window`` picks the region of a cited artifact to show the one-shot
reply model. The first implementation selected a LINE RANGE and then, if the
result still exceeded the size bound, sliced it with ``window[:2 * max_chars]``
— keeping the FRONT. A long line (or a single-line document, or a match that
sits at the end of the selected range) was therefore cut off exactly at the
point the window existed to expose.

The invariant these tests pin: **the matched passage is always inside the
returned window**, whatever the surrounding text looks like, and the window
never exceeds the requested size.
"""
import pytest

from core.llm.prompt_budget import relevant_window

MATCH = "R235 | Product Name=F-52\"x16G | LIST Price=7519.0 | $7,519.00"


class TestMatchIsAlwaysContained:
    def test_single_line_document(self):
        """One enormous line: line-range selection cannot help, and the old
        front-slice dropped a match near the end."""
        text = ("filler " * 4000) + MATCH + (" tail " * 4000)
        window, matched, _line = relevant_window(
            text, "what is the 7519 list price", max_chars=2000)
        assert matched is True
        assert "R235" in window, "the matched passage was cut out of the window"
        assert "$7,519.00" in window
        assert len(window) <= 4000

    def test_long_preceding_line(self):
        """A single huge line BEFORE the match must not push it out."""
        text = ("z" * 50000) + "\n" + MATCH + "\n" + ("q" * 500)
        window, _matched, _line = relevant_window(
            text, "7519 list price", max_chars=2000)
        assert "R235" in window

    def test_match_at_the_end_of_the_text(self):
        text = "\n".join(f"filler line {i} " + "y" * 160 for i in range(300))
        text = text + "\n" + MATCH
        window, _matched, _line = relevant_window(
            text, "7519 list price", max_chars=1500)
        assert "R235" in window

    def test_repeated_common_words_do_not_displace_the_answer(self):
        """'price'/'list' appear everywhere; the match must still be shown."""
        filler = "\n".join(
            f"- price list entry {i}: list price applies, see price list"
            for i in range(200))
        text = filler + "\n" + MATCH + "\n" + filler
        window, _matched, _line = relevant_window(
            text, "7519 list price", max_chars=1200)
        assert "R235" in window, (
            "a common word was matched instead of the distinctive figure")

    def test_competing_matches_pick_one_and_keep_it(self):
        text = "\n".join(
            [f"- price list {i}" for i in range(50)]
            + [MATCH]
            + [f"- price list {i}" for i in range(50, 100)])
        window, matched, line = relevant_window(
            text, "7519", max_chars=900)
        assert matched is True
        assert "R235" in window
        assert line is not None and line > 0

    @pytest.mark.parametrize("size", [200, 600, 1500, 3800])
    def test_window_never_exceeds_the_requested_size(self, size):
        text = ("word " * 20000)
        window, _m, _l = relevant_window(text, "word", max_chars=size)
        assert len(window) <= size * 2


class TestUnmatchedBehaviour:
    def test_unrelated_query_reports_no_match(self):
        text = "\n".join(f"line {i} " + "z" * 100 for i in range(200))
        window, matched, line = relevant_window(
            text, "zebra migration patterns", max_chars=800)
        assert matched is False and line is None
        assert window, "a fallback view is still returned"

    def test_short_text_is_returned_whole(self):
        window, matched, _line = relevant_window("short body", "body", 2000)
        assert matched is True and window == "short body"

    def test_empty_inputs(self):
        assert relevant_window("", "x", 100)[0] == ""
        assert relevant_window(None, "x", 100)[0] == ""
        assert relevant_window("abc", "x", 0)[0] == ""
