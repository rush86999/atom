"""Workload-aware edit planning: a header-only edit plans in a small
envelope (owner systemic item 4, 2026-10-08).

A small/header edit is a couple of find→replace ops; the multi-row
14,000-token output reservation spent the interactive deadline on space
the plan never used. Pins: small shape detected (header edit, no
fresh-data, short); multi-row vocabulary and large prompts stay on the
full allowance; the envelope threads into the structured call.
"""
from __future__ import annotations

import os

os.environ.setdefault("TESTING", "1")

from core.chat_canvas_editor import _small_edit_shape


def test_header_edit_is_small():
    msg = ('Change the subject to "Q3 Pricing Update" and keep everything '
           'else exactly as it is.')
    assert _small_edit_shape(msg, prompt_len=12000) is True


def test_short_single_value_change_is_small():
    msg = 'Update the greeting line to "Hi Steve," — nothing else.'
    assert _small_edit_shape(msg, prompt_len=8000) is True


def test_multi_row_request_is_not_small():
    msg = 'Update rows 1 to 5 with the new prices.'
    assert _small_edit_shape(msg, prompt_len=12000) is False


def test_rebuild_vocabulary_is_not_small():
    for msg in ('Rebuild the whole table.',
                'Regenerate the entire draft.',
                'Rewrite the email completely.'):
        assert _small_edit_shape(msg, prompt_len=9000) is False, msg


def test_large_prompt_is_not_small():
    msg = 'Change the subject line.'
    assert _small_edit_shape(msg, prompt_len=40000) is False


def test_long_instruction_is_not_small():
    msg = "Change the subject to 'Q3' and also update the greeting, the " \
          "footer, the CC line, the validity note, and re-check every " \
          "price in the table while you are at it, thanks."
    assert _small_edit_shape(msg, prompt_len=12000) is False
