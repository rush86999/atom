"""Coverage wave 13 — LLMCredentialService (OAuth/BYOK/env chain) + 
SelfConsistencyVoter (TDD)."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.llm_credential_service import LLMCredentialService
from core.llm.self_consistency_voter import (
    SelfConsistencyVoter,
    VoteResult,
)


# =========================================================================== #
# LLMCredentialService
# =========================================================================== #
class TestCredentialService:
    def _service(self, user_id="u-1", tenant_id="t-1", workspace_id="ws-1"):
        with patch("core.llm_credential_service.get_byok_manager") as m:
            svc = LLMCredentialService(
                user_id=user_id, tenant_id=tenant_id, workspace_id=workspace_id
            )
        svc.oauth_handler = MagicMock()
        svc.byok_manager = m.return_value
        return svc

    @pytest.mark.asyncio
    async def test_oauth_priority(self):
        svc = self._service()
        svc.oauth_handler.get_active_credentials.return_value = "cred"
        svc.oauth_handler.validate_and_refresh_if_needed = AsyncMock(
            return_value=True
        )
        svc.oauth_handler.decrypt_access_token.return_value = "sk-oauth"
        ctype, cval = await svc.get_credential("openai")
        assert ctype == "oauth"
        assert cval == "sk-oauth"

    @pytest.mark.asyncio
    async def test_subscription_after_oauth_miss(self):
        svc = self._service()

        def _get_active(user, provider, credential_type=None):
            return None if credential_type == "oauth" else "sub-cred"

        svc.oauth_handler.get_active_credentials.side_effect = _get_active
        svc.oauth_handler.validate_and_refresh_if_needed = AsyncMock(
            return_value=True
        )
        svc.oauth_handler.decrypt_access_token.return_value = "sk-sub"
        ctype, cval = await svc.get_credential("openai")
        assert ctype == "subscription"
        assert cval == "sk-sub"

    @pytest.mark.asyncio
    async def test_byok_after_oauth_miss(self):
        svc = self._service()
        svc.oauth_handler.get_active_credentials.return_value = None
        svc.byok_manager.get_tenant_api_key.return_value = None
        svc.byok_manager.is_configured.return_value = True
        svc.byok_manager.get_api_key.return_value = "sk-byok"
        ctype, cval = await svc.get_credential("openai")
        assert ctype == "byok"
        assert cval == "sk-byok"

    @pytest.mark.asyncio
    async def test_env_after_all_miss(self):
        svc = self._service()
        svc.oauth_handler.get_active_credentials.return_value = None
        svc.byok_manager.get_tenant_api_key.return_value = None
        svc.byok_manager.is_configured.return_value = False
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-env"}):
            ctype, cval = await svc.get_credential("openai")
        assert ctype == "env"
        assert cval == "sk-env"

    @pytest.mark.asyncio
    async def test_no_credential_raises(self):
        svc = self._service()
        svc.oauth_handler.get_active_credentials.return_value = None
        svc.byok_manager.get_tenant_api_key.return_value = None
        svc.byok_manager.is_configured.return_value = False
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
            with pytest.raises(ValueError):
                await svc.get_credential("openai")

    @pytest.mark.asyncio
    async def test_invalid_credential_skipped(self):
        svc = self._service()
        svc.oauth_handler.get_active_credentials.return_value = "cred"
        svc.oauth_handler.validate_and_refresh_if_needed = AsyncMock(
            return_value=False
        )
        svc.byok_manager.get_tenant_api_key.return_value = "sk-tenant"
        ctype, cval = await svc.get_credential("openai")
        assert ctype == "byok"  # invalid oauth -> falls to byok
        assert cval == "sk-tenant"

    @pytest.mark.asyncio
    async def test_resolve_active_credential_no_user(self):
        svc = self._service(user_id=None)
        assert await svc._resolve_active_credential("openai", "oauth") is None

    @pytest.mark.asyncio
    async def test_oauth_info(self):
        svc = self._service()
        cred = SimpleNamespace(
            id="c1", provider_id="openai", account_email="a@b.c",
            account_name="A", is_active=True, expires_at=None,
            last_used_at=None, usage_count=3, created_at=None,
        )
        svc.oauth_handler.get_active_credentials.return_value = cred
        info = await svc.get_oauth_credential_info("openai")
        assert info["credential_id"] == "c1"
        assert info["usage_count"] == 3

    @pytest.mark.asyncio
    async def test_oauth_info_missing_and_error(self):
        svc = self._service()
        svc.oauth_handler.get_active_credentials.return_value = None
        assert await svc.get_oauth_credential_info("openai") is None
        svc.oauth_handler.get_active_credentials.side_effect = RuntimeError("db")
        assert await svc.get_oauth_credential_info("openai") is None

    def test_list_credentials(self):
        svc = self._service()
        cred = SimpleNamespace(
            id="c1", provider_id="openai", account_email="a@b.c",
            account_name="A", is_active=True, expires_at=None,
            last_used_at=None, usage_count=1, created_at=None,
        )
        svc.oauth_handler.list_credentials.return_value = [cred]
        out = svc.list_oauth_credentials()
        assert out[0]["provider_id"] == "openai"
        svc.oauth_handler.list_credentials.side_effect = RuntimeError("db")
        assert svc.list_oauth_credentials() == []

    def test_revoke_and_refresh(self):
        svc = self._service()
        svc.oauth_handler.revoke_credentials.return_value = True
        assert svc.revoke_oauth_credential("c1") is True
        svc.oauth_handler.revoke_credentials.side_effect = RuntimeError("db")
        assert svc.revoke_oauth_credential("c1") is False

    @pytest.mark.asyncio
    async def test_refresh_credential(self):
        svc = self._service()
        svc.oauth_handler.refresh_access_token = AsyncMock(return_value=True)
        assert await svc.refresh_oauth_credential("c1") is True
        svc.oauth_handler.refresh_access_token = AsyncMock(
            side_effect=RuntimeError("db")
        )
        assert await svc.refresh_oauth_credential("c1") is False

    def test_provider_status(self):
        svc = self._service()
        svc.oauth_handler.get_active_credentials.return_value = None
        svc.byok_manager.is_configured.return_value = False
        # root .env (loaded by other suites) may set OPENAI_API_KEY
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
            status = svc.get_provider_status("openai")
        assert status["provider_id"] == "openai"
        assert status["has_oauth"] is False
        assert status["active_method"] is None
        # oauth present -> active_method oauth
        svc.oauth_handler.get_active_credentials.return_value = SimpleNamespace(
            account_email="a@b.c", expires_at=None
        )
        status2 = svc.get_provider_status("openai")
        assert status2["has_oauth"] is True
        assert status2["active_method"] == "oauth"

    def test_env_credential_gemini_google_key(self):
        svc = self._service()
        with patch.dict(
            "os.environ", {"GOOGLE_API_KEY": "sk-google", "GEMINI_API_KEY": ""}
        ):
            assert svc._try_env_credential("gemini") == "sk-google"


# =========================================================================== #
# SelfConsistencyVoter
# =========================================================================== #
class _Sample:
    def __init__(self, value):
        self.value = value

    def model_dump(self, mode="python"):
        return {"value": self.value}

    def __hash__(self):
        return hash(self.value)

    def __eq__(self, other):
        return isinstance(other, _Sample) and other.value == self.value


class TestSelfConsistencyVoter:
    def _voter(self, handler=None):
        return SelfConsistencyVoter(handler or MagicMock())

    @pytest.mark.asyncio
    async def test_all_samples_fail_returns_none(self):
        voter = self._voter()
        voter.handler.generate_structured_response = AsyncMock(
            side_effect=RuntimeError("boom")
        )
        assert await voter.vote("p", _Sample, sample_count=3) is None

    @pytest.mark.asyncio
    async def test_single_valid_sample(self):
        voter = self._voter()
        voter.handler.generate_structured_response = AsyncMock(
            return_value=_Sample("only")
        )
        result = await voter.vote("p", _Sample, sample_count=1)
        assert result.value == "only"

    @pytest.mark.asyncio
    async def test_majority_vote(self):
        voter = self._voter()
        a, b = _Sample("a"), _Sample("b")
        voter.handler.generate_structured_response = AsyncMock(
            side_effect=[a, b, a]
        )
        result = await voter.vote("p", _Sample, sample_count=3)
        assert result.value == "a"  # majority

    @pytest.mark.asyncio
    async def test_distinct_samples_fall_back_to_first(self):
        voter = self._voter()
        a, b, c = _Sample("a"), _Sample("b"), _Sample("c")
        voter.handler.generate_structured_response = AsyncMock(
            side_effect=[a, b, c]
        )
        result = await voter.vote("p", _Sample, sample_count=3)
        assert result.value == "a"  # lowest temperature wins ties

    @pytest.mark.asyncio
    async def test_kwargs_shared_across_samples(self):
        voter = self._voter()
        seen = []

        async def _gen(**kwargs):
            seen.append((kwargs.get("system_instruction"), kwargs.get("task_type")))
            return _Sample("x")

        voter.handler.generate_structured_response = AsyncMock(side_effect=_gen)
        await voter.vote(
            "p", _Sample, sample_count=2,
            system_instruction="sys-1", task_type="reasoning",
        )
        assert seen == [("sys-1", "reasoning"), ("sys-1", "reasoning")]

    def test_temperatures_for(self):
        temps = SelfConsistencyVoter._temperatures_for(3)
        assert len(temps) == 3
        assert temps[1] == 0.7  # centered
        temps2 = SelfConsistencyVoter._temperatures_for(3, base=1.0)
        assert temps2[1] == 1.0

    def test_is_irreversible(self):
        assert SelfConsistencyVoter.is_irreversible({"action": "delete_record"}) is True
        assert SelfConsistencyVoter.is_irreversible({"action": "send_email"}) is True
        assert SelfConsistencyVoter.is_irreversible({"action": "search_web"}) is False
        # Bug #13: metadata fields never match
        assert SelfConsistencyVoter.is_irreversible(
            {"created_at": "2026-01-01", "updated_at": "x", "count": 3}
        ) is False
        assert SelfConsistencyVoter.is_irreversible(None) is False
        assert SelfConsistencyVoter.is_irreversible("delete_me_now") is True

    def test_diversity_overlays(self):
        assert SelfConsistencyVoter.diversity_overlays(3, enabled=False) == ["", "", ""]
        overlays = SelfConsistencyVoter.diversity_overlays(3, enabled=True)
        assert len(overlays) == 3
        assert overlays[0] != overlays[1]

    def test_hash_sample_variants(self):
        assert (
            SelfConsistencyVoter._hash_sample(_Sample("x"))
            == SelfConsistencyVoter._hash_sample(_Sample("x"))
        )
        assert (
            SelfConsistencyVoter._hash_sample({"a": 1})
            == SelfConsistencyVoter._hash_sample({"a": 1})
        )
        assert (
            SelfConsistencyVoter._hash_sample("plain")
            == SelfConsistencyVoter._hash_sample("plain")
        )

    def test_level_from_agreement(self):
        from core.llm.self_consistency_voter import (
            LEVEL_AMBIGUOUS, LEVEL_HIGH, LEVEL_PARTIAL,
        )

        assert SelfConsistencyVoter._level_from_agreement(0.9) == LEVEL_HIGH
        assert SelfConsistencyVoter._level_from_agreement(0.6) == LEVEL_PARTIAL
        assert SelfConsistencyVoter._level_from_agreement(0.2) == LEVEL_AMBIGUOUS

    def test_vote_result_helpers(self):
        vr = VoteResult(
            winner="x", agreement_ratio=0.9, level="high",
            sample_count=3, valid_count=3, winner_count=3,
            distinct_hashes=1,
        )
        assert vr.is_high is True
        assert vr.requires_review is False
        assert vr.is_no_samples is False

        vr2 = VoteResult(
            winner=None, agreement_ratio=0.0, level="ambiguous",
            sample_count=3, valid_count=0, winner_count=0, distinct_hashes=0,
        )
        assert vr2.is_no_samples is True
        assert vr2.requires_review is True

    @pytest.mark.asyncio
    async def test_vote_with_consensus_shape(self):
        voter = self._voter()
        a, b = _Sample("a"), _Sample("b")
        voter.handler.generate_structured_response = AsyncMock(
            side_effect=[a, b, a]
        )
        vr = await voter.vote_with_consensus("p", _Sample, sample_count=3)
        assert vr.winner.value == "a"
        assert vr.valid_count == 3
        assert vr.agreement_ratio == pytest.approx(2 / 3)
        assert vr.prompt_hash is not None

    @pytest.mark.asyncio
    async def test_vote_with_consensus_all_fail(self):
        voter = self._voter()
        voter.handler.generate_structured_response = AsyncMock(
            side_effect=RuntimeError("boom")
        )
        vr = await voter.vote_with_consensus("p", _Sample, sample_count=2)
        assert vr.winner is None
        assert vr.is_no_samples is True
