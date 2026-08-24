"""RFC 8785 (JCS) canonicalization + algo-tagged self-consistency hashing.

Locks the item-#8 contract:
- canonicalize() follows JCS: UTF-16 code-unit key ordering, minimal string
  escapes, ECMAScript number formatting.
- The voter hashes samples with JCS and tags every VoteResult with
  hash_algo="jcs-sha256"; legacy sort_keys hashes remain computable and are
  only comparable within legacy rows (version, don't migrate).
- SelfConsistencyVote persists hash_algo (NULL = legacy row).
"""
import json

import pytest

from core.llm.jcs import canonicalize, jcs_sha256_hex
from core.llm.self_consistency_voter import (
    HASH_ALGO_JCS,
    HASH_ALGO_LEGACY,
    SelfConsistencyVoter,
    VoteResult,
)


class TestCanonicalizeSpec:
    def test_rfc8785_appendix_a_example(self):
        # The canonical example from RFC 8785 Appendix A (numbers as strings
        # to avoid float parsing ambiguity in the expectation).
        src = {
            "numbers": [333333333.33333329, 1E30, 4.50, 2e-3, 0.000000000000000000000000001],
            "string": "\u20ac$\u000F\u000aA'\u0042\u0022\u005c\\\"/",
            "literals": [None, True, False],
        }
        expected = (
            '{"literals":[null,true,false],'
            '"numbers":[333333333.3333333,1e+30,4.5,0.002,1e-27],'
            '"string":"€$\\u000f\\nA\'B\\"\\\\\\\\\\"/"}'
        )
        assert canonicalize(src) == expected

    def test_key_order_is_utf16_code_units(self):
        # U+FFFF sorts AFTER an astral emoji under code-point order, but the
        # emoji's UTF-16 surrogate pair (0xD83D 0xDE00) sorts BEFORE U+FFFF.
        # JCS must emit the emoji first; sort_keys=True emits it second.
        src = {"\uffff": 1, "\U0001f600": 2}
        jcs = canonicalize(src)
        assert jcs.index("\U0001f600") < jcs.index("\uffff")
        assert jcs == '{"😀":2,"￿":1}'
        legacy = json.dumps(src, sort_keys=True)
        assert legacy.index("\\uffff") < legacy.index("\\ud83d")

    def test_minimal_string_escapes(self):
        assert canonicalize({"k": "a\nb\tc\"d\\e"}) == '{"k":"a\\nb\\tc\\"d\\\\e"}'
        # Control chars use short \u forms, lowercase hex.
        assert canonicalize({"k": "\x00\x1f"}) == '{"k":"\\u0000\\u001f"}'
        # No escaping for non-ASCII.
        assert canonicalize({"k": "é你好"}) == '{"k":"é你好"}'

    def test_ecmascript_number_forms(self):
        assert canonicalize({"a": 1.0}) == '{"a":1}'
        assert canonicalize({"a": 4.50}) == '{"a":4.5}'
        assert canonicalize({"a": 1e-7}) == '{"a":1e-7}'
        assert canonicalize({"a": 1e21}) == '{"a":1e+21}'
        assert canonicalize({"a": 0.002}) == '{"a":0.002}'
        assert canonicalize({"a": -0.0}) == '{"a":0}'

    def test_nan_infinity_rejected(self):
        with pytest.raises(ValueError):
            canonicalize(float("nan"))
        with pytest.raises(ValueError):
            canonicalize(float("inf"))

    def test_nested_structures_and_unknown_scalars(self):
        out = canonicalize({"b": [1, {"z": True, "a": None}], "a": "x"})
        assert out == '{"a":"x","b":[1,{"a":null,"z":true}]}'
        # Non-JSON scalars stringify (matches the legacy default=str spirit).
        import datetime
        dt = datetime.datetime(2026, 8, 23, 12, 0, 0)
        assert canonicalize({"t": dt}) == '{"t":"2026-08-23 12:00:00"}'

    def test_field_order_irrelevant(self):
        assert canonicalize({"a": 1, "b": 2}) == canonicalize({"b": 2, "a": 1})


class TestVoterHashing:
    def test_structurally_equal_samples_hash_equal_under_jcs(self):
        a = {"plan": "step", "n": 1}
        b = {"n": 1, "plan": "step"}  # different insertion order
        assert SelfConsistencyVoter._hash_sample(a) == SelfConsistencyVoter._hash_sample(b)

    def test_jcs_differs_from_legacy_for_astral_keys(self):
        # Where the two orderings disagree, the hashes MUST differ — this is
        # exactly why rows are versioned by hash_algo.
        sample = {"\uffff": 1, "\U0001f600": 2}
        assert SelfConsistencyVoter._hash_sample(sample) != SelfConsistencyVoter._hash_sample_legacy(sample)

    def test_legacy_helper_matches_old_scheme_exactly(self):
        sample = {"z": "é", "a": [1, 2.5]}
        legacy = json.dumps(sample, sort_keys=True, default=str)
        import hashlib
        expect = hashlib.sha256(legacy.encode("utf-8")).hexdigest()
        assert SelfConsistencyVoter._hash_sample_legacy(sample) == expect

    def test_hashes_match_cross_algo_never_true(self):
        h_jcs = SelfConsistencyVoter._hash_sample({"a": 1})
        h_legacy = SelfConsistencyVoter._hash_sample_legacy({"a": 1})
        # A legacy row (algo NULL) vs a JCS vote: never equal, even if the
        # hex strings happened to coincide.
        assert not SelfConsistencyVoter.hashes_match(None, h_legacy, HASH_ALGO_JCS, h_jcs)
        # Same algo + same hash: match.
        assert SelfConsistencyVoter.hashes_match(None, h_legacy, HASH_ALGO_LEGACY, h_legacy)
        assert SelfConsistencyVoter.hashes_match(HASH_ALGO_JCS, h_jcs, HASH_ALGO_JCS, h_jcs)
        # Missing hashes never match.
        assert not SelfConsistencyVoter.hashes_match(None, None, HASH_ALGO_JCS, h_jcs)


class TestVoteResultAlgoTagging:
    def test_vote_tags_jcs_and_uses_it_for_agreement(self):
        from unittest.mock import AsyncMock, MagicMock
        from types import SimpleNamespace

        plan = {"action": "send_email", "to": "a@b.c"}
        handler = MagicMock()
        handler.generate_structured_response = AsyncMock(
            side_effect=[dict(plan), dict(plan)]
        )
        voter = SelfConsistencyVoter(handler=handler)
        import asyncio

        result = asyncio.run(voter.vote_with_consensus(
            prompt="p", response_model=dict, sample_count=2,
        ))
        assert isinstance(result, VoteResult)
        assert result.hash_algo == HASH_ALGO_JCS
        assert result.winner_count == 2
        assert result.winner_hash == jcs_sha256_hex(plan)[:16]

    def test_no_samples_result_has_no_algo(self):
        from unittest.mock import AsyncMock, MagicMock

        handler = MagicMock()
        handler.generate_structured_response = AsyncMock(side_effect=[None, None])
        voter = SelfConsistencyVoter(handler=handler)
        import asyncio

        result = asyncio.run(voter.vote_with_consensus(
            prompt="p", response_model=dict, sample_count=2,
        ))
        assert result.winner_hash is None
        assert result.hash_algo is None


class TestPersistenceColumn:
    def test_model_has_hash_algo_column(self):
        from core.models import SelfConsistencyVote

        cols = {c.name for c in SelfConsistencyVote.__table__.columns}
        assert "hash_algo" in cols
        algo_col = SelfConsistencyVote.__table__.columns["hash_algo"]
        assert algo_col.nullable is True  # NULL = legacy rows

    def test_persist_vote_writes_hash_algo(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/votes.db")
        from core.database import Base, get_db_session
        from core.models import SelfConsistencyVote
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool

        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()

        from core.llm_service import LLMService

        svc = LLMService.__new__(LLMService)
        svc._db = session
        svc._tenant_id = "default"
        svc._workspace_id = "default"

        vote = VoteResult(
            winner={"a": 1}, agreement_ratio=1.0, level="high",
            sample_count=2, valid_count=2, winner_count=2,
            distinct_hashes=1, temperatures=[0.2, 0.5],
            winner_hash="abcd1234abcd1234", hash_algo=HASH_ALGO_JCS,
            prompt_hash="deadbeefdeadbeef",
        )
        svc._write_self_consistency_audit(
            vote=vote, agent_id="ag", user_id="u", session_id="s",
            response_model=dict,
        )
        row = session.query(SelfConsistencyVote).one()
        assert row.hash_algo == HASH_ALGO_JCS
        assert row.winner_hash == "abcd1234abcd1234"
        session.close()
