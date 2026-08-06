"""
Round 21 TDD bug hunt — BUG-093: `enable_revocation` config is ignored.

`VCConfig.enable_revocation` (default True) declares whether credential
revocation is enabled, but `VerifiableCredentialManager.revoke_credential`
never consults it — a manager configured with `enable_revocation=False`
still happily revokes credentials. That makes the config flag a lie: an
operator who disables revocation to freeze the trust set gets silent
revocation anyway.

TDD: write the failing assertion first (red), then gate `revoke_credential`
and `_is_revoked` on `config.enable_revocation` (green).
"""
from datetime import datetime, timedelta

from core.identity.verifiable_credentials import (
    VCConfig,
    VCType,
    VerifiableCredential,
    VerifiableCredentialManager,
)


def _make_manager(enable_revocation: bool) -> VerifiableCredentialManager:
    manager = VerifiableCredentialManager(
        VCConfig(enable_revocation=enable_revocation)
    )
    # Simulate an environment without signing (proof stays None) — the config
    # checks under test are orthogonal to signature availability.
    manager.did_manager = None
    return manager


def _make_vc(manager: VerifiableCredentialManager):
    return manager.create_credential(
        issuer_did="did:example:issuer",
        credential_type=VCType.AGENT_IDENTITY,
        subject_did="did:example:subject",
        claims={"name": "test"},
    )


class TestEnableRevocationConfig:
    def test_revoke_disallowed_when_revocation_disabled(self):
        """revoke_credential must refuse when enable_revocation=False."""
        manager = _make_manager(enable_revocation=False)
        vc = _make_vc(manager)

        # The credential should NOT be revocable when the feature is disabled.
        assert manager.revoke_credential(vc.id) is False
        assert not manager._is_revoked(vc.id)

    def test_revoke_allowed_when_revocation_enabled(self):
        """Default config (enable_revocation=True) still revokes."""
        manager = _make_manager(enable_revocation=True)
        vc = _make_vc(manager)

        assert manager.revoke_credential(vc.id) is True
        assert manager._is_revoked(vc.id)
        assert not vc.is_valid()

    def test_verify_credential_with_revocation_disabled_never_reports_revoked(self):
        """A credential cannot be seen as revoked when revocation is disabled."""
        manager = _make_manager(enable_revocation=False)
        vc = _make_vc(manager)

        result = manager.verify_credential(vc, check_revocation=True)
        # "revoked" must never appear in the verification result.
        assert not any("revok" in e.lower() for e in result.errors)
        assert result.status.value != "revoked"

    def test_credential_is_valid_within_expiry_when_not_revoked(self):
        """Regression: an unrevoked, unexpired credential stays valid."""
        manager = _make_manager(enable_revocation=True)
        vc = _make_vc(manager)
        vc.expiration_date = datetime.now() + timedelta(days=30)

        assert vc.is_valid()
