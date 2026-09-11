"""Outlook poll page budget: a behind cursor must catch up, not crawl.

Live 2026-09-11: the poller's cursor sat ~2.5 months behind (June 24), walking
5 pages (~250 already-ingested messages) per poll, so September mail — and the
inline quote image the agent needed — was never stored.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from integrations.atom_communication_ingestion_pipeline import (
    _OUTLOOK_CATCHUP_FETCH_PAGES,
    _OUTLOOK_INCREMENTAL_FETCH_PAGES,
    _outlook_fetch_page_budget,
)

NOW = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)


def test_initial_sync_gets_the_catchup_budget():
    assert _outlook_fetch_page_budget(None, NOW) == _OUTLOOK_CATCHUP_FETCH_PAGES


def test_recent_cursor_keeps_the_small_budget():
    assert _outlook_fetch_page_budget(NOW - timedelta(hours=6), NOW) == (
        _OUTLOOK_INCREMENTAL_FETCH_PAGES)


def test_behind_cursor_gets_the_catchup_budget():
    # The live case: ~2.5 months behind.
    assert _outlook_fetch_page_budget(NOW - timedelta(days=79), NOW) == (
        _OUTLOOK_CATCHUP_FETCH_PAGES)


def test_naive_and_bad_cursors_are_safe():
    assert _outlook_fetch_page_budget(
        (NOW - timedelta(days=10)).replace(tzinfo=None), NOW) == (
        _OUTLOOK_CATCHUP_FETCH_PAGES)
    assert _outlook_fetch_page_budget("not-a-date", NOW) == (
        _OUTLOOK_INCREMENTAL_FETCH_PAGES)
