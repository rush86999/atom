"""Tests for human ground-truth intent labels (correctness > agreement)."""

import os
os.environ["TESTING"] = "1"

import pytest


def _session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from core.models import Base
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


class TestLabels:
    def test_roundtrip(self):
        from core import decision_automation as da
        s = _session()
        assert da.record_intent_label(s, "a1", "h1", True, False, "tester") is True
        acc = da.label_accuracy(s)
        assert acc == {"n": 1, "llm_accuracy": 1.0, "llm_n": 1,
                       "ollaya_accuracy": 0.0, "ollaya_n": 1}

    def test_relabel_updates(self):
        from core import decision_automation as da
        s = _session()
        da.record_intent_label(s, "a1", "h1", True, True)
        da.record_intent_label(s, "a1", "h1", False, True)
        acc = da.label_accuracy(s)
        assert acc["n"] == 1
        assert acc["llm_accuracy"] == 0.0

    def test_both_wrong_counts(self):
        from core import decision_automation as da
        s = _session()
        da.record_intent_label(s, "a1", "h1", False, False)
        da.record_intent_label(s, "a2", "h2", True, True)
        acc = da.label_accuracy(s)
        assert acc == {"n": 2, "llm_accuracy": 0.5, "llm_n": 2,
                       "ollaya_accuracy": 0.5, "ollaya_n": 2}

    def test_empty(self):
        from core import decision_automation as da
        assert da.label_accuracy(_session()) == {"n": 0}

    def test_db_error_never_raises(self):
        from unittest.mock import Mock
        from core import decision_automation as da
        bad = Mock()
        bad.add.side_effect = RuntimeError("db down")
        bad.query.side_effect = RuntimeError("db down")
        assert da.record_intent_label(bad, "a", "h", True, True) is False
        assert da.label_accuracy(bad) == {}
