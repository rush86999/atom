"""
Journey 5: Federation — create DID, resolve, issue credential, verify.

Tests the Phase 4 zero-trust federation surface end-to-end.
"""

import pytest


class TestFederationDID:

    def test_create_and_resolve_did(self, registered_user):
        """Create a DID and resolve it back."""
        client, email, password, token = registered_user
        headers = {"Authorization": f"Bearer {token}"}

        # Create a DID.
        resp = client.post("/api/federation/dids", json={
            "entity_type": "agent",
            "entity_id": "test_agent_1",
        }, headers=headers)
        assert resp.status_code == 200, f"DID creation failed: {resp.text}"
        data = resp.json()
        assert data.get("did"), f"No DID returned: {data}"
        did = data["did"]

        # Resolve it.
        resp = client.get(f"/api/federation/dids/{did}", headers=headers)
        assert resp.status_code == 200, f"DID resolution failed: {resp.text}"
        resolved = resp.json()
        assert resolved.get("resolved") is not None or resolved.get("did") == did, \
            f"Resolution mismatch: {resolved}"


class TestFederationCredentials:

    def test_issue_credential(self, registered_user):
        """Issue a verifiable credential."""
        client, email, password, token = registered_user
        headers = {"Authorization": f"Bearer {token}"}

        # First create a DID to use as issuer.
        resp = client.post("/api/federation/dids", json={
            "entity_type": "agent",
            "entity_id": "issuer_1",
        }, headers=headers)
        assert resp.status_code == 200
        issuer_did = resp.json()["did"]

        # Issue a credential.
        resp = client.post("/api/federation/credentials", json={
            "issuer_did": issuer_did,
            "credential_type": "AgentIdentityCredential",
            "subject_did": issuer_did,
            "claims": {"name": "Test Agent"},
        }, headers=headers)
        assert resp.status_code == 200, f"Credential issuance failed: {resp.text}"


class TestFederationVerify:

    def test_verify_request(self, registered_user):
        """The verify endpoint returns an access decision."""
        client, email, password, token = registered_user
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.post("/api/federation/verify", json={
            "method": "GET",
            "path": "/test/resource",
            "action": "read",
            "resource_type": "generic",
        }, headers=headers)
        assert resp.status_code == 200, f"Verify failed: {resp.text}"
        data = resp.json()
        assert "allowed" in data, f"No 'allowed' key in verify response: {data}"


class TestFederationSecurity:

    def test_security_health(self, registered_user):
        """The security health endpoint responds."""
        client, email, password, token = registered_user
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.get("/api/federation/security/health", headers=headers)
        assert resp.status_code == 200, f"Security health failed: {resp.text}"

    def test_security_stats(self, registered_user):
        """The security stats endpoint responds."""
        client, email, password, token = registered_user
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.get("/api/federation/security/stats", headers=headers)
        assert resp.status_code == 200, f"Security stats failed: {resp.text}"
