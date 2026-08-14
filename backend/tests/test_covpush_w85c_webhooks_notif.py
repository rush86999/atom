# -*- coding: utf-8 -*-
"""W85C — coverage push for 10 backend modules (standalone >=95% each).

Targets:
 1. core/webhook_crud_dispatch.py     (42% baseline)
 2. core/webhook_handlers.py          (95% baseline)
 3. core/webhook_renewal_service.py   (43% baseline)
 4. core/webhook_security.py          (31% baseline)
 5. core/workflow_notifier.py         (68% baseline)
 6. core/notification_manager.py      (34% baseline)
 7. core/notification_service.py      (80% baseline)
 8. core/observation_filter_service.py(51% baseline)
 9. core/time_expression_parser.py    (62% baseline)
10. core/user_preference_service.py   (55% baseline)

Style: mocked deps, zero LLM spend, zero network, no real DB. All
providers/httpx/db are AsyncMock/MagicMock. Webhook conventions exercised:
signature verification (fail-closed in production, dev bypass only via
explicit env override), tombstone/out-of-order handling, staggered renewal
tiers, notification persistence/email opt-in, adaptive observation filter
rules + clustering, NL time expression patterns, preference CRUD.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sys
import types
from datetime import datetime, timedelta, timezone
from unittest.mock import ANY, AsyncMock, MagicMock, Mock, patch

import pytest

import core.notification_manager as nm_mod
import core.notification_service as ns_mod
import core.observation_filter_service as ofs_mod
import core.time_expression_parser as tep_mod
import core.user_preference_service as ups_mod
import core.webhook_crud_dispatch as wcd_mod
import core.webhook_renewal_service as wrs_mod
import core.webhook_security as ws_mod
from core.notification_manager import ConnectionManager, notification_manager
from core.notification_service import (
    HIGH_PRIORITY_TYPES,
    NotificationService,
    _classify,
    _default_title,
    _user_email_enabled,
)
from core.observation_filter_service import ObservationFilterService
from core.time_expression_parser import (
    TIME_PATTERNS,
    normalize_time_12h_to_24h,
    parse_time_expression,
    parse_with_llm,
    parse_with_patterns,
)
from core.user_preference_service import UserPreference, UserPreferenceService
from core.webhook_crud_dispatch import crud_dispatch, extract_crud_metadata
from core.webhook_handlers import (
    GmailWebhookHandler,
    SlackWebhookHandler,
    TeamsWebhookHandler,
    WebhookEvent,
    WebhookProcessor,
    get_webhook_processor,
)
from core.webhook_renewal_service import (
    ScheduledWebhookRenewalService,
    supports_drive_subscription,
)
from core.models import UserConnection
from core.webhook_security import (
    _get_webhook_secret,
    get_client_state_data,
    get_environment,
    sign_client_state,
    sign_client_state_with_connection,
    verify_client_state,
    verify_github_webhook,
    verify_slack_webhook,
    verify_stripe_webhook,
    verify_webhook_signature,
    verify_whatsapp_webhook,
)
from core.workflow_notifier import (
    NotificationSettings,
    NotificationType,
    WorkflowNotifier,
    get_notification_settings,
    notifier,
    set_notification_settings,
)


# ============================================================================
# Shared helpers
# ============================================================================


def _hmac_sha256(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _slack_sig(secret: str, timestamp: str, body: bytes) -> str:
    base = f"v0:{timestamp}:".encode() + body
    return "v0=" + hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()


class _FakeHttpxModule:
    """Stand-in for httpx supporting `async with httpx.AsyncClient()`."""

    def __init__(self):
        self.client = MagicMock()
        self.client.__aenter__ = AsyncMock(return_value=self.client)
        self.client.__aexit__ = AsyncMock(return_value=False)
        self.client.get = AsyncMock(return_value=MagicMock(status_code=200, json=MagicMock(return_value={"value": []})))
        self.client.delete = AsyncMock(return_value=MagicMock(status_code=204))
        mod = types.ModuleType("httpx")
        mod.AsyncClient = MagicMock(return_value=self.client)
        self.mod = mod

    def __enter__(self):
        self.patcher = patch.dict(sys.modules, {"httpx": self.mod})
        self.patcher.start()
        return self

    def __exit__(self, *exc):
        self.patcher.stop()


def _prod_env():
    return patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False)


def _dev_bypass_env():
    return patch.dict(
        os.environ, {"ENVIRONMENT": "development", "BYPASS_WEBHOOK_SIGNATURE": "true"}, clear=False
    )


# ============================================================================
# 1. core/webhook_security.py
# ============================================================================


class TestWebhookSecurity:
    def test_get_environment_default(self):
        with patch.dict(os.environ, {}, clear=True):
            assert get_environment() == "development"

    def test_get_environment_explicit(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "staging"}, clear=True):
            assert get_environment() == "staging"

    def test_verify_webhook_signature_valid(self):
        body = b'{"a": 1}'
        sig = _hmac_sha256("secret", body)
        assert verify_webhook_signature(body, sig, "secret") is True

    def test_verify_webhook_signature_with_prefix(self):
        body = b"payload"
        sig = "sha256=" + _hmac_sha256("secret", body)
        assert verify_webhook_signature(body, sig, "secret") is True

    def test_verify_webhook_signature_invalid(self):
        assert verify_webhook_signature(b"a", "deadbeef", "secret") is False

    def test_verify_webhook_signature_missing_signature(self):
        assert verify_webhook_signature(b"a", "", "secret") is False

    def test_verify_webhook_signature_missing_secret(self):
        assert verify_webhook_signature(b"a", "sig", "") is False

    def test_verify_webhook_signature_missing_both(self):
        assert verify_webhook_signature(b"a", "", "") is False

    def test_verify_webhook_signature_dev_bypass(self):
        with _dev_bypass_env():
            assert verify_webhook_signature(b"a", "whatever", "") is True

    def test_verify_webhook_signature_dev_no_bypass(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "development", "BYPASS_WEBHOOK_SIGNATURE": "no"}):
            assert verify_webhook_signature(b"a", "sig", "secret") is False

    def test_verify_webhook_signature_sha1_algorithm(self):
        body = b"x"
        sig = hmac.new(b"secret", body, hashlib.sha1).hexdigest()
        assert verify_webhook_signature(body, sig, "secret", "sha1") is True

    def test_verify_webhook_signature_bad_algorithm(self):
        assert verify_webhook_signature(b"x", "sig", "secret", "bogus_algo") is False

    def test_verify_slack_webhook_valid(self):
        body = b'{"event": {}}'
        ts = str(int(datetime.now().timestamp()))
        sig = _slack_sig("secret", ts, body)
        assert verify_slack_webhook(body, sig, ts, "secret") is True

    def test_verify_slack_webhook_invalid(self):
        ts = str(int(datetime.now().timestamp()))
        assert verify_slack_webhook(b"body", "v0=bad", ts, "secret") is False

    def test_verify_slack_webhook_missing_params(self):
        assert verify_slack_webhook(b"b", "", "", "") is False
        assert verify_slack_webhook(b"b", "sig", "", "secret") is False

    def test_verify_slack_webhook_old_timestamp(self):
        ts = str(int(datetime.now().timestamp()) - 400)
        body = b"b"
        sig = _slack_sig("secret", ts, body)
        assert verify_slack_webhook(body, sig, ts, "secret") is False

    def test_verify_slack_webhook_bad_timestamp_exception(self):
        assert verify_slack_webhook(b"b", "v0=x", "not-a-timestamp", "secret") is False

    def test_verify_slack_webhook_bypass(self):
        with _dev_bypass_env():
            assert verify_slack_webhook(b"b", "", "", "") is True

    def test_verify_stripe_webhook_success(self):
        stripe_mod = types.ModuleType("stripe")
        event = MagicMock(type="checkout.session.completed")
        stripe_mod.Webhook = MagicMock()
        stripe_mod.Webhook.construct_event = MagicMock(return_value=event)
        with patch.dict(sys.modules, {"stripe": stripe_mod}):
            assert verify_stripe_webhook(b"payload", "sig", "whsec_x") is True

    def test_verify_stripe_webhook_failure(self):
        stripe_mod = types.ModuleType("stripe")
        stripe_mod.Webhook = MagicMock()
        stripe_mod.Webhook.construct_event = MagicMock(side_effect=ValueError("bad sig"))
        with patch.dict(sys.modules, {"stripe": stripe_mod}):
            assert verify_stripe_webhook(b"payload", "sig", "whsec_x") is False

    def test_verify_stripe_webhook_missing(self):
        assert verify_stripe_webhook(b"payload", "", "") is False

    def test_verify_stripe_webhook_bypass(self):
        with _dev_bypass_env():
            assert verify_stripe_webhook(b"b", "", "") is True

    def test_verify_github_webhook_valid(self):
        body = b'{"ref": "main"}'
        sig = "sha256=" + _hmac_sha256("ghsecret", body)
        assert verify_github_webhook(body, sig, "ghsecret") is True

    def test_verify_github_webhook_invalid(self):
        assert verify_github_webhook(b"b", "sha256=bad", "ghsecret") is False

    def test_verify_github_webhook_missing(self):
        assert verify_github_webhook(b"b", "", "") is False

    def test_verify_github_webhook_bypass(self):
        with _dev_bypass_env():
            assert verify_github_webhook(b"b", "", "") is True

    def test_verify_github_webhook_delegate_exception(self):
        with patch("core.webhook_security.verify_webhook_signature", side_effect=RuntimeError("boom")):
            assert verify_github_webhook(b"b", "sig", "secret") is False

    def test_verify_whatsapp_webhook_valid(self):
        body = b"hi"
        sig = "sha256=" + _hmac_sha256("appsecret", body)
        assert verify_whatsapp_webhook(body, sig, "appsecret") is True

    def test_verify_whatsapp_webhook_invalid(self):
        assert verify_whatsapp_webhook(b"hi", "sha256=bad", "appsecret") is False

    def test_get_webhook_secret_from_env(self):
        with patch.dict(os.environ, {"WEBHOOK_CLIENT_STATE_SECRET": "state-secret"}, clear=False):
            assert _get_webhook_secret() == "state-secret"

    def test_get_webhook_secret_jwt_fallback(self):
        with patch.dict(
            os.environ,
            {"WEBHOOK_CLIENT_STATE_SECRET": "", "JWT_SECRET": "jwt-secret"},
            clear=False,
        ):
            assert _get_webhook_secret() == "jwt-secret"

    def test_get_webhook_secret_random_fallback_cached(self):
        with patch.dict(os.environ, {"WEBHOOK_CLIENT_STATE_SECRET": "", "JWT_SECRET": ""}, clear=False):
            ws_mod._get_webhook_secret._fallback = "cache-buster"
            del ws_mod._get_webhook_secret._fallback
            first = _get_webhook_secret()
            assert len(first) == 43
            assert _get_webhook_secret() == first

    def test_sign_and_verify_client_state_roundtrip(self):
        with patch.dict(os.environ, {"WEBHOOK_CLIENT_STATE_SECRET": "s1", "JWT_SECRET": ""}):
            signed = sign_client_state('{"a": 1}')
            assert signed.count("::") == 1
            assert verify_client_state(signed) is True
            data, sig = signed.rsplit("::", 1)
            assert data == '{"a": 1}'
            assert len(sig) == 64

    def test_verify_client_state_tampered(self):
        with patch.dict(os.environ, {"WEBHOOK_CLIENT_STATE_SECRET": "s1", "JWT_SECRET": ""}):
            signed = sign_client_state("hello")
            assert verify_client_state(signed + "x") is False

    def test_verify_client_state_malformed(self):
        assert verify_client_state("") is False
        assert verify_client_state("no-separator") is False

    def test_verify_client_state_bypass(self):
        with _dev_bypass_env():
            assert verify_client_state("garbage") is True

    def test_verify_client_state_wrong_secret(self):
        with patch.dict(os.environ, {"WEBHOOK_CLIENT_STATE_SECRET": "s1", "JWT_SECRET": ""}):
            signed = sign_client_state("hello")
        with patch.dict(os.environ, {"WEBHOOK_CLIENT_STATE_SECRET": "s2", "JWT_SECRET": ""}):
            assert verify_client_state(signed) is False

    def test_verify_client_state_exception_returns_false(self):
        with patch("core.webhook_security._get_webhook_secret", side_effect=RuntimeError("secret fail")):
            assert verify_client_state("data::sig") is False

    def test_get_client_state_data_with_sig(self):
        assert get_client_state_data("data::sig") == "data"

    def test_get_client_state_data_without_sig(self):
        assert get_client_state_data("plain") == "plain"

    def test_sign_client_state_with_connection(self):
        with patch.dict(os.environ, {"WEBHOOK_CLIENT_STATE_SECRET": "s1", "JWT_SECRET": ""}):
            signed = sign_client_state_with_connection("tenant-1", "conn-2")
            assert verify_client_state(signed) is True
            assert json.loads(get_client_state_data(signed)) == {
                "tenant_id": "tenant-1",
                "connection_id": "conn-2",
            }


# ============================================================================
# 2. core/webhook_crud_dispatch.py
# ============================================================================


class TestExtractCrudMetadata:
    def test_non_dict_payload(self):
        assert extract_crud_metadata("slack", "not-a-dict") == (None, None)

    def test_empty_payload(self):
        assert extract_crud_metadata("unknown", {}) == (None, None)

    def test_slack_message_deleted_with_deleted_ts(self):
        payload = {"event": {"type": "message", "subtype": "message_deleted", "deleted_ts": "1.1"}}
        assert extract_crud_metadata("slack", payload) == ("deleted", "1.1")

    def test_slack_message_deleted_previous_message_ts(self):
        payload = {
            "event": {
                "type": "message",
                "subtype": "message_deleted",
                "previous_message": {"ts": "2.2"},
            }
        }
        assert extract_crud_metadata("slack", payload) == ("deleted", "2.2")

    def test_slack_message_changed(self):
        payload = {"event": {"type": "message", "subtype": "message_changed", "message": {"ts": "3.3"}}}
        assert extract_crud_metadata("slack", payload) == ("updated", "3.3")

    def test_slack_message_created(self):
        payload = {"event": {"type": "message", "ts": "4.4"}}
        assert extract_crud_metadata("slack", payload) == ("created", "4.4")

    def test_salesforce_create(self):
        payload = {"changeEventHeader": {"changeType": "CREATE", "recordIds": ["r1"]}}
        assert extract_crud_metadata("salesforce", payload) == ("created", "r1")

    def test_salesforce_update(self):
        payload = {"changeEventHeader": {"changeType": "UPDATE", "recordIds": ["r2"]}}
        assert extract_crud_metadata("salesforce", payload) == ("updated", "r2")

    def test_salesforce_delete(self):
        payload = {"changeEventHeader": {"changeType": "DELETE", "recordIds": ["r3"]}}
        assert extract_crud_metadata("salesforce", payload) == ("deleted", "r3")

    def test_salesforce_gap_delete(self):
        payload = {"changeEventHeader": {"changeType": "GAP_DELETE", "recordIds": ["r4"]}}
        assert extract_crud_metadata("salesforce", payload) == ("deleted", "r4")

    def test_salesforce_no_record_ids(self):
        payload = {"changeEventHeader": {"changeType": "CREATE"}}
        assert extract_crud_metadata("salesforce", payload) == ("created", None)

    def test_salesforce_unknown_change_type(self):
        payload = {"changeEventHeader": {"changeType": "UNDELETE", "recordIds": ["r5"]}}
        assert extract_crud_metadata("salesforce", payload) == ("created", "r5")

    def test_hubspot_creation(self):
        payload = {"subscriptionType": "contact.creation", "objectId": 42}
        assert extract_crud_metadata("hubspot", payload) == ("created", "42")

    def test_hubspot_deletion(self):
        payload = {"subscriptionType": "contact.deletion", "objectId": "43"}
        assert extract_crud_metadata("hubspot", payload) == ("deleted", "43")

    def test_hubspot_property_change(self):
        payload = {"subscriptionType": "contact.propertyChange", "objectId": 44}
        assert extract_crud_metadata("hubspot", payload) == ("updated", "44")

    def test_hubspot_no_subscription_type(self):
        payload = {"objectId": 45}
        assert extract_crud_metadata("hubspot", payload) == ("created", "45")

    def test_github_issues_opened(self):
        payload = {"action": "opened", "issue": {"number": 7}}
        headers = {"x-github-event": "issues"}
        assert extract_crud_metadata("github", payload, headers) == ("created", "7")

    def test_github_issues_edited(self):
        payload = {"action": "edited", "issue": {"number": 8}}
        headers = {"X-GitHub-Event": "issues"}
        assert extract_crud_metadata("github", payload, headers) == ("updated", "8")

    def test_github_pull_request_deleted(self):
        payload = {"action": "deleted", "pull_request": {"number": 9}}
        headers = {"x-github-event": "pull_request"}
        assert extract_crud_metadata("github", payload, headers) == ("deleted", "9")

    def test_github_issue_comment_created(self):
        payload = {"action": "created", "comment": {"id": "c1"}}
        headers = {"x-github-event": "issue_comment"}
        assert extract_crud_metadata("github", payload, headers) == ("created", "c1")

    def test_github_other_event(self):
        payload = {"action": "completed"}
        headers = {"x-github-event": "workflow_run"}
        assert extract_crud_metadata("github", payload, headers) == (None, None)

    def test_google_drive_add(self):
        payload = {"id": "f1"}
        headers = {"x-goog-resource-state": "add"}
        assert extract_crud_metadata("google_drive", payload, headers) == ("created", "f1")

    def test_google_drive_trash(self):
        payload = {"id": "f2"}
        headers = {"X-Goog-Resource-State": "trash"}
        assert extract_crud_metadata("google_drive", payload, headers) == ("deleted", "f2")

    def test_google_drive_update(self):
        payload = {"id": "f3"}
        headers = {"x-goog-resource-state": "update"}
        assert extract_crud_metadata("google_drive", payload, headers) == ("updated", "f3")

    def test_google_drive_headers_fallback_id(self):
        payload = {}
        headers = {"x-goog-resource-state": "remove", "x-goog-resource-id": "rid-1"}
        assert extract_crud_metadata("google_drive", payload, headers) == ("deleted", "rid-1")

    def test_google_drive_unknown_state_keeps_payload_id(self):
        payload = {"id": "f4"}
        headers = {"x-goog-resource-state": "sync"}
        assert extract_crud_metadata("google_drive", payload, headers) == ("created", "f4")

    def test_notion_updated(self):
        payload = {"page": {"id": "p1"}}
        assert extract_crud_metadata("notion", payload) == ("updated", "p1")

    def test_notion_archived(self):
        payload = {"block": {"id": "p2", "archived": True}}
        assert extract_crud_metadata("notion", payload) == ("deleted", "p2")

    def test_outlook_passthrough(self):
        payload = {"changeType": "deleted", "resourceId": "rid-9"}
        assert extract_crud_metadata("outlook", payload) == ("deleted", "rid-9")

    def test_teams_message_delete(self):
        payload = {"eventType": "messageDelete", "id": "t1"}
        assert extract_crud_metadata("teams", payload) == ("deleted", "t1")

    def test_teams_message_update(self):
        payload = {"event": "messageUpdate", "message": {"id": "t2"}}
        assert extract_crud_metadata("teams", payload) == ("updated", "t2")

    def test_teams_message_create(self):
        payload = {"eventType": "messageCreate", "id": "t3"}
        assert extract_crud_metadata("teams", payload) == ("created", "t3")

    def test_teams_none_event(self):
        payload = {"id": "t4"}
        assert extract_crud_metadata("teams", payload) == ("created", "t4")

    def test_discord_message_delete(self):
        payload = {"event": "MESSAGE_DELETE", "id": "d1"}
        assert extract_crud_metadata("discord", payload) == ("deleted", "d1")

    def test_discord_message_update(self):
        payload = {"event": "MESSAGE_UPDATE", "message_id": "d2"}
        assert extract_crud_metadata("discord", payload) == ("updated", "d2")

    def test_discord_message_create(self):
        payload = {"event": "MESSAGE_CREATE", "id": "d3"}
        assert extract_crud_metadata("discord", payload) == ("created", "d3")

    def test_discord_none_event(self):
        payload = {"id": "d4"}
        assert extract_crud_metadata("discord", payload) == ("created", "d4")

    def test_monday_delete_item(self):
        payload = {"event": {"type": "delete_item", "pulseId": 11}}
        assert extract_crud_metadata("monday", payload) == ("deleted", "11")

    def test_monday_change_column_value(self):
        payload = {"event": {"type": "change_column_value", "pulseId": 12}}
        assert extract_crud_metadata("monday", payload) == ("updated", "12")

    def test_monday_create_item(self):
        payload = {"event": {"type": "create_item", "pulseId": 13}}
        assert extract_crud_metadata("monday", payload) == ("created", "13")

    def test_monday_create_subitem(self):
        payload = {"event": {"type": "create_subitem", "pulseId": 14}}
        assert extract_crud_metadata("monday", payload) == ("created", "14")

    def test_monday_unknown_event(self):
        payload = {"event": {"type": "update_board", "pulseId": 15}}
        assert extract_crud_metadata("monday", payload) == ("updated", "15")

    def test_jira_issue_deleted(self):
        payload = {"webhookEvent": "jira:issue_deleted", "issue": {"key": "J-1"}}
        assert extract_crud_metadata("jira", payload) == ("deleted", "J-1")

    def test_jira_issue_updated(self):
        payload = {"webhookEvent": "jira:issue_updated", "issue": {"id": "j2"}}
        assert extract_crud_metadata("jira", payload) == ("updated", "j2")

    def test_jira_issue_created(self):
        payload = {"webhookEvent": "jira:issue_created", "issue": {"key": "J-3"}}
        assert extract_crud_metadata("jira", payload) == ("created", "J-3")

    def test_jira_no_event(self):
        payload = {"issue": {"key": "J-4"}}
        assert extract_crud_metadata("jira", payload) == ("created", "J-4")

    def test_clickup_task_deleted(self):
        payload = {"event": "taskDeleted", "task_id": "cu1"}
        assert extract_crud_metadata("clickup", payload) == ("deleted", "cu1")

    def test_clickup_task_updated(self):
        payload = {"event": "taskUpdated", "taskId": "cu2"}
        assert extract_crud_metadata("clickup", payload) == ("updated", "cu2")

    def test_clickup_task_created(self):
        payload = {"event": "taskCreated", "task_id": "cu3"}
        assert extract_crud_metadata("clickup", payload) == ("created", "cu3")

    def test_clickup_no_event(self):
        payload = {"task_id": "cu4"}
        assert extract_crud_metadata("clickup", payload) == ("created", "cu4")

    def test_asana_removed(self):
        payload = {"events": [{"action": "removed", "resource": {"gid": "a1"}}]}
        assert extract_crud_metadata("asana", payload) == ("deleted", "a1")

    def test_asana_changed(self):
        payload = {"events": [{"action": "changed", "resource": {"gid": "a2"}}]}
        assert extract_crud_metadata("asana", payload) == ("updated", "a2")

    def test_asana_added(self):
        payload = {"events": [{"action": "added", "resource": {"gid": "a3"}}]}
        assert extract_crud_metadata("asana", payload) == ("created", "a3")

    def test_asana_empty_events(self):
        assert extract_crud_metadata("asana", {"events": []}) == (None, None)

    def test_generic_fallback_delete_keyword(self):
        payload = {"action": "DeleteThing", "id": 1}
        assert extract_crud_metadata("custom", payload) == ("deleted", "1")

    def test_generic_fallback_update_keyword(self):
        payload = {"change_type": "UpdateRecord", "object_id": 2}
        assert extract_crud_metadata("custom", payload) == ("updated", "2")

    def test_generic_fallback_create_keyword(self):
        payload = {"event": "CreateRecord", "resource_id": 3}
        assert extract_crud_metadata("custom", payload) == ("created", "3")

    def test_generic_fallback_type_field(self):
        payload = {"type": "remove", "pulseId": 4}
        assert extract_crud_metadata("custom", payload) == ("deleted", "4")

    def test_generic_fallback_other_keywords(self):
        payload = {"action": "destroy", "key": "k1"}
        assert extract_crud_metadata("custom", payload) == ("deleted", "k1")

    def test_resource_id_stringified(self):
        payload = {"action": "add", "id": 99}
        assert extract_crud_metadata("custom", payload) == ("created", "99")

    def test_default_created_when_resource_only(self):
        payload = {"id": "only-id"}
        assert extract_crud_metadata("custom", payload) == ("created", "only-id")


class TestCrudDispatch:
    def _db(self, dialect="sqlite"):
        db = MagicMock()
        db.bind.dialect.name = dialect
        return db

    def _patch_queue(self, job_id="job-1"):
        import api.routes.webhooks.ingestion_webhooks as ing_mod

        fake = MagicMock()
        fake.enqueue_ingestion_job = AsyncMock(return_value=job_id)
        return patch.object(ing_mod, "webhook_queue", fake)

    async def test_tombstone_blocks_create(self):
        db = self._db()
        db.query.return_value.filter.return_value.first.return_value = MagicMock()
        with self._patch_queue() as q:
            result = await crud_dispatch(db, "created", "slack", "t1", "r1", {})
        assert result == {"status": "ignored", "reason": "tombstoned"}
        q.enqueue_ingestion_job.assert_not_awaited()

    async def test_tombstone_blocks_update(self):
        db = self._db()
        db.query.return_value.filter.return_value.first.return_value = MagicMock()
        with self._patch_queue() as q:
            result = await crud_dispatch(db, "UPDATED", "slack", "t1", "r1", {})
        assert result == {"status": "ignored", "reason": "tombstoned"}

    async def test_delete_no_entities_creates_tombstone(self):
        db = self._db()
        db.query.return_value.filter.return_value.first.return_value = None
        db.query.return_value.filter.return_value.all.return_value = []
        result = await crud_dispatch(db, "deleted", "slack", "t1", "r1", {})
        assert result == {"status": "tombstoned"}
        db.add.assert_called_once()
        db.commit.assert_called_once()

    async def test_delete_no_entities_tombstone_exists(self):
        db = self._db()
        db.query.return_value.filter.return_value.first.return_value = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        result = await crud_dispatch(db, "deleted", "slack", "t1", "r1", {})
        assert result == {"status": "tombstoned"}
        db.add.assert_not_called()
        db.commit.assert_not_called()

    async def test_delete_with_entities(self):
        db = self._db()
        e1 = MagicMock()
        e2 = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [e1, e2]
        result = await crud_dispatch(db, "deleted", "slack", "t1", "r1", {})
        assert result == {"status": "deleted", "deleted_count": 2}
        db.delete.assert_any_call(e1)
        db.delete.assert_any_call(e2)
        db.commit.assert_called_once()

    async def test_delete_postgres_rls_branch(self):
        db = self._db(dialect="postgresql")
        db.query.return_value.filter.return_value.all.return_value = [MagicMock()]
        result = await crud_dispatch(db, "deleted", "slack", "t1", "r1", {})
        assert result["status"] == "deleted"
        assert db.execute.call_count == 2

    async def test_update_non_tier1_ignored(self):
        db = self._db()
        db.query.return_value.filter.return_value.first.return_value = None
        with self._patch_queue() as q:
            result = await crud_dispatch(db, "updated", "outlook", "t1", "r1", {})
        assert result == {"status": "ignored", "reason": "updates_ignored_for_tier"}
        q.enqueue_ingestion_job.assert_not_awaited()

    async def test_update_tier1_enqueues(self):
        db = self._db()
        db.query.return_value.filter.return_value.first.return_value = None
        with self._patch_queue() as q:
            result = await crud_dispatch(
                db, "updated", "github", "t1", "r1", {"payload": 1}, source_connection_id="conn-1"
            )
        assert result == {"status": "enqueued", "job_id": "job-1"}
        q.enqueue_ingestion_job.assert_awaited_once_with(
            tenant_id="t1",
            integration_id="github",
            trigger_type="webhook",
            payload={"payload": 1},
            source_connection_id="conn-1",
        )

    async def test_create_enqueues(self):
        db = self._db()
        db.query.return_value.filter.return_value.first.return_value = None
        with self._patch_queue() as q:
            result = await crud_dispatch(db, "created", "notion", "t1", "r1", {})
        assert result == {"status": "enqueued", "job_id": "job-1"}
        q.enqueue_ingestion_job.assert_awaited_once()


# ============================================================================
# 3. core/webhook_handlers.py (extensions)
# ============================================================================


class TestWebhookHandlersExtras:
    def test_slack_handler_env_secret_fallback(self):
        with patch.dict(os.environ, {"SLACK_SIGNING_SECRET": "env-secret"}):
            handler = SlackWebhookHandler()
        assert handler.signing_secret == "env-secret"

    def test_slack_verify_dev_no_secret_bypass(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False):
            handler = SlackWebhookHandler()
            assert handler.verify_signature("1", "v0=x", b"body") is True

    def test_slack_verify_production_no_secret_rejects(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False):
            handler = SlackWebhookHandler()
            assert handler.verify_signature("1", "v0=x", b"body") is False

    def test_slack_verify_valid_signature(self):
        """Regression (W85C): spec-compliant v0:{ts}:{body} signature must pass."""
        handler = SlackWebhookHandler(signing_secret="secret")
        ts = str(int(datetime.now().timestamp()))
        sig = _slack_sig("secret", ts, b"body")
        assert handler.verify_signature(ts, sig, b"body") is True

    def test_slack_verify_invalid_signature(self):
        handler = SlackWebhookHandler(signing_secret="secret")
        ts = str(int(datetime.now().timestamp()))
        assert handler.verify_signature(ts, "v0=bogus", b"body") is False

    def test_slack_verify_exception(self):
        handler = SlackWebhookHandler(signing_secret="secret")
        with patch("core.webhook_handlers.hmac.new", side_effect=TypeError("bad")):
            assert handler.verify_signature("1", "v0=x", b"body") is False

    def test_slack_parse_url_verification(self):
        handler = SlackWebhookHandler()
        ev = handler.parse_event({"type": "url_verification", "challenge": "ch-1"})
        assert ev is not None
        assert ev.event_type == "url_verification"
        assert ev.event_data == {"challenge": "ch-1"}

    def test_slack_parse_message_client_msg_id(self):
        handler = SlackWebhookHandler()
        raw = {
            "type": "event_callback",
            "event": {
                "type": "message",
                "client_msg_id": "cmid-1",
                "text": "hi",
                "user": "U1",
                "channel": "C1",
                "team": "T1",
                "thread_ts": "1.1",
                "parent_user_id": "U2",
            },
        }
        ev = handler.parse_event(raw)
        assert ev.event_data["id"] == "cmid-1"
        assert ev.event_data["metadata"]["thread_ts"] == "1.1"

    def test_teams_handler_app_id(self):
        handler = TeamsWebhookHandler(app_id="app-1")
        assert handler.app_id == "app-1"

    def test_gmail_verify_content_type_ok(self):
        handler = GmailWebhookHandler()
        assert handler.verify_signature({"content-type": "message/rfc822"}) is True

    def test_processor_register_callback(self):
        p = WebhookProcessor()
        cb = MagicMock()
        p.register_message_callback(cb)
        assert p.on_message_received is cb

    async def test_processor_slack_ignores_non_message_event(self):
        p = WebhookProcessor()
        p.slack_handler = MagicMock()
        p.slack_handler.verify_signature.return_value = True
        p.slack_handler.parse_event.return_value = WebhookEvent("slack", "reaction_added", {}, {})
        bg = MagicMock()
        req = MagicMock()
        req.body = AsyncMock(return_value=b"{}")
        req.headers = {}
        result = await p.process_slack_webhook(req, bg)
        assert result["status"] == "success"
        bg.add_task.assert_not_called()

    async def test_processor_gmail_no_callback_no_task(self):
        p = WebhookProcessor()
        p.gmail_handler = MagicMock()
        payload = {"message": {"data": base64.b64encode(b"{}").decode()}}
        p.gmail_handler.parse_event.return_value = WebhookEvent(
            "gmail", "push_notification", {}, payload
        )
        p.on_message_received = None
        req = MagicMock()
        req.json = AsyncMock(return_value=payload)
        bg = MagicMock()
        result = await p.process_gmail_webhook(req, bg)
        assert result["status"] == "success"
        bg.add_task.assert_not_called()

    async def test_process_message_unified_format(self):
        p = WebhookProcessor()
        seen = []

        async def cb(data):
            seen.append(data)

        p.register_message_callback(cb)
        ev = WebhookEvent("slack", "message", {"a": 1}, {"raw": 1})
        await p._process_message(ev)
        assert seen[0]["app_type"] == "slack"
        assert seen[0]["raw_event"] == {"raw": 1}

    def test_mark_processed_cleanup_threshold(self):
        p = WebhookProcessor()
        base = datetime.now()
        for i in range(10001):
            p.processed_events[f"e{i}"] = base + timedelta(seconds=i)
        p._mark_processed("new")
        assert len(p.processed_events) <= 10001
        assert "e0" not in p.processed_events
        assert "e10000" in p.processed_events

    def test_get_processor_singleton(self):
        from core.webhook_handlers import webhook_processor

        assert get_webhook_processor() is webhook_processor


# ============================================================================
# 4. core/webhook_renewal_service.py
# ============================================================================


class TestWebhookRenewalTiers:
    def test_supports_drive_subscription(self):
        assert supports_drive_subscription("microsoft365") is True
        assert supports_drive_subscription("outlook") is False
        assert supports_drive_subscription("slack") is False

    def test_get_tier_critical(self):
        svc = ScheduledWebhookRenewalService(MagicMock())
        for i in ["outlook", "gmail", "slack", "salesforce", "microsoft365"]:
            assert svc.get_tier_for_integration(i) == "tier_1_critical"

    def test_get_tier_business(self):
        svc = ScheduledWebhookRenewalService(MagicMock())
        for i in ["hubspot", "notion", "jira", "github"]:
            assert svc.get_tier_for_integration(i) == "tier_2_business"

    def test_get_tier_productivity(self):
        svc = ScheduledWebhookRenewalService(MagicMock())
        for i in ["asana", "trello", "monday", "figma"]:
            assert svc.get_tier_for_integration(i) == "tier_3_productivity"

    def test_get_tier_nice_to_have(self):
        svc = ScheduledWebhookRenewalService(MagicMock())
        assert svc.get_tier_for_integration("stripe") == "tier_4_nice_to_have"

    def test_get_renewal_interval_hours(self):
        svc = ScheduledWebhookRenewalService(MagicMock())
        assert svc.get_renewal_interval_hours("tier_1_critical") == 12.0
        assert svc.get_renewal_interval_hours("tier_2_business") == 24.0
        assert svc.get_renewal_interval_hours("tier_3_productivity") == 48.0
        assert svc.get_renewal_interval_hours("tier_4_nice_to_have") == 168.0
        assert svc.get_renewal_interval_hours("unknown") == 168.0

    def test_is_renewal_due_no_timestamps(self):
        conn = MagicMock()
        conn.last_refresh_at = None
        conn.updated_at = None
        conn.created_at = None
        svc = ScheduledWebhookRenewalService(MagicMock())
        assert svc.is_renewal_due(conn) is True

    def test_is_renewal_due_created_at_naive(self):
        conn = MagicMock()
        conn.last_refresh_at = None
        conn.updated_at = None
        conn.created_at = datetime.now(timezone.utc) - timedelta(hours=30)
        conn.integration_id = "slack"
        svc = ScheduledWebhookRenewalService(MagicMock())
        assert svc.is_renewal_due(conn) is True

    def test_is_renewal_due_updated_at_fresh(self):
        conn = MagicMock()
        conn.last_refresh_at = None
        conn.updated_at = datetime.now(timezone.utc) - timedelta(hours=1)
        conn.integration_id = "slack"
        svc = ScheduledWebhookRenewalService(MagicMock())
        assert svc.is_renewal_due(conn) is False

    def test_is_renewal_due_last_refresh_past_interval(self):
        conn = MagicMock()
        conn.last_refresh_at = datetime.now(timezone.utc) - timedelta(hours=50)
        conn.integration_id = "asana"
        svc = ScheduledWebhookRenewalService(MagicMock())
        assert svc.is_renewal_due(conn) is True

    def test_is_renewal_due_naive_last_refresh(self):
        conn = MagicMock()
        conn.last_refresh_at = datetime.now() - timedelta(hours=50)
        conn.integration_id = "slack"
        svc = ScheduledWebhookRenewalService(MagicMock())
        assert svc.is_renewal_due(conn) is True

    def test_is_renewal_due_tier4_not_due(self):
        conn = MagicMock()
        conn.last_refresh_at = datetime.now(timezone.utc) - timedelta(hours=100)
        conn.integration_id = "custom"
        svc = ScheduledWebhookRenewalService(MagicMock())
        assert svc.is_renewal_due(conn) is False


class TestRenewSubscription:
    def _svc(self, db=None, conn_service=None):
        with patch("core.webhook_renewal_service.ConnectionService") as CS:
            CS.return_value = conn_service or MagicMock()
            svc = ScheduledWebhookRenewalService(db or MagicMock())
        return svc

    def _conn(self, integration_id="slack", creds=None):
        conn = MagicMock()
        conn.id = "conn-1"
        conn.tenant_id = "t1"
        conn.integration_id = integration_id
        conn.credentials = creds if creds is not None else {"access_token": "tok"}
        conn.refresh_failure_count = 0
        return conn

    async def test_decrypt_failure(self):
        svc = self._svc()
        svc.connection_service._decrypt.return_value = None
        svc._handle_failure = MagicMock()
        conn = self._conn()
        result = await svc.renew_subscription_for_connection(conn)
        assert result == {"status": "failed", "error": "Decryption failure"}
        svc._handle_failure.assert_called_once_with(conn, "Could not decrypt credentials")

    async def test_token_refresh_updates_credentials(self):
        svc = self._svc()
        svc.connection_service._decrypt.return_value = {"access_token": "old"}
        svc.connection_service._refresh_token_if_needed = AsyncMock(
            return_value={"access_token": "new", "expires_in": "3600"}
        )
        svc.connection_service._encrypt.side_effect = lambda c: json.dumps(c)
        conn = self._conn()
        result = await svc.renew_subscription_for_connection(conn)
        assert result["status"] == "success"
        svc.connection_service._encrypt.assert_called_once()
        assert conn.expires_at is not None
        assert conn.last_refresh_at is not None
        assert conn.refresh_failure_count == 0
        svc.db.commit.assert_called()

    async def test_token_refresh_no_expires_in(self):
        svc = self._svc()
        svc.connection_service._decrypt.return_value = {"access_token": "old"}
        svc.connection_service._refresh_token_if_needed = AsyncMock(
            return_value={"access_token": "new"}
        )
        conn = self._conn()
        conn.expires_at = None
        result = await svc.renew_subscription_for_connection(conn)
        assert result["status"] == "success"
        assert conn.expires_at is None

    async def test_no_refresh_needed(self):
        svc = self._svc()
        svc.connection_service._decrypt.return_value = {"access_token": "tok"}
        svc.connection_service._refresh_token_if_needed = AsyncMock(return_value=None)
        conn = self._conn(integration_id="custom")
        result = await svc.renew_subscription_for_connection(conn)
        assert result == {"status": "success", "action": "recreated"}
        svc.connection_service._encrypt.assert_not_called()

    async def test_outlook_no_subscription_ids_recreated(self):
        svc = self._svc()
        svc.connection_service._decrypt.return_value = {"access_token": "tok"}
        svc.connection_service._refresh_token_if_needed = AsyncMock(return_value=None)
        conn = self._conn(integration_id="outlook")
        conn.credentials = {"access_token": "tok"}
        result = await svc.renew_subscription_for_connection(conn)
        assert result == {"status": "success", "action": "recreated"}

    async def test_outlook_renew_success(self):
        svc = self._svc()
        svc.connection_service._decrypt.return_value = {
            "access_token": "tok",
            "subscription_ids": ["sub-1"],
        }
        svc.connection_service._refresh_token_if_needed = AsyncMock(return_value=None)
        with _FakeHttpxModule() as http:
            http.client.get = AsyncMock(
                return_value=MagicMock(
                    status_code=200, json=MagicMock(return_value={"value": [{"id": "sub-1", "resource": "/me/messages"}]})
                )
            )
            with patch("integrations.microsoft365_service.microsoft365_service") as m365:
                m365.renew_subscription = AsyncMock(return_value={"status": "ok"})
                conn = self._conn(integration_id="outlook")
                result = await svc.renew_subscription_for_connection(conn)
        assert result == {"status": "success", "action": "success"}
        m365.renew_subscription.assert_awaited_once()

    async def test_outlook_renew_error_triggers_recreation(self):
        svc = self._svc()
        svc.connection_service._decrypt.return_value = {
            "access_token": "tok",
            "subscription_id": "sub-legacy",
        }
        svc.connection_service._refresh_token_if_needed = AsyncMock(return_value=None)
        with _FakeHttpxModule() as http:
            http.client.get = AsyncMock(return_value=MagicMock(status_code=500))
            with patch("integrations.microsoft365_service.microsoft365_service") as m365:
                m365.renew_subscription = AsyncMock(return_value={"status": "error", "message": "expired"})
                conn = self._conn(integration_id="outlook")
                result = await svc.renew_subscription_for_connection(conn)
        assert result == {"status": "success", "action": "recreated"}

    async def test_outlook_list_subscriptions_failure(self):
        svc = self._svc()
        svc.connection_service._decrypt.return_value = {
            "access_token": "tok",
            "subscription_ids": ["sub-2"],
        }
        svc.connection_service._refresh_token_if_needed = AsyncMock(return_value=None)
        with _FakeHttpxModule() as http:
            http.client.get = AsyncMock(side_effect=RuntimeError("graph down"))
            with patch("integrations.microsoft365_service.microsoft365_service") as m365:
                m365.renew_subscription = AsyncMock(return_value={"status": "ok"})
                conn = self._conn(integration_id="outlook")
                result = await svc.renew_subscription_for_connection(conn)
        assert result["status"] == "success"
        m365.renew_subscription.assert_awaited_once_with("tok", "sub-2", ANY)

    async def test_outlook_drive_subscription_deleted_for_non_m365(self):
        svc = self._svc()
        svc.connection_service._decrypt.return_value = {
            "access_token": "tok",
            "subscription_ids": ["sub-drive"],
        }
        svc.connection_service._refresh_token_if_needed = AsyncMock(return_value=None)
        with _FakeHttpxModule() as http:
            http.client.get = AsyncMock(
                return_value=MagicMock(
                    status_code=200,
                    json=MagicMock(return_value={"value": [{"id": "sub-drive", "resource": "/me/drive/root"}]}),
                )
            )
            with patch("integrations.microsoft365_service.microsoft365_service") as m365:
                m365.renew_subscription = AsyncMock(return_value={"status": "ok"})
                conn = self._conn(integration_id="outlook")
                result = await svc.renew_subscription_for_connection(conn)
        assert result["status"] == "success"
        http.client.delete.assert_awaited_once()
        m365.renew_subscription.assert_not_awaited()

    async def test_outlook_drive_subscription_kept_for_m365(self):
        svc = self._svc()
        svc.connection_service._decrypt.return_value = {
            "access_token": "tok",
            "subscription_ids": ["sub-drive"],
        }
        svc.connection_service._refresh_token_if_needed = AsyncMock(return_value=None)
        with _FakeHttpxModule() as http:
            http.client.get = AsyncMock(
                return_value=MagicMock(
                    status_code=200,
                    json=MagicMock(return_value={"value": [{"id": "sub-drive", "resource": "/me/drive/root"}]}),
                )
            )
            with patch("integrations.microsoft365_service.microsoft365_service") as m365:
                m365.renew_subscription = AsyncMock(return_value={"status": "ok"})
                conn = self._conn(integration_id="microsoft365")
                result = await svc.renew_subscription_for_connection(conn)
        assert result["status"] == "success"
        http.client.delete.assert_not_awaited()
        m365.renew_subscription.assert_awaited_once()

    async def test_outlook_drive_delete_failure_swallowed(self):
        svc = self._svc()
        svc.connection_service._decrypt.return_value = {
            "access_token": "tok",
            "subscription_ids": ["sub-drive"],
        }
        svc.connection_service._refresh_token_if_needed = AsyncMock(return_value=None)
        with _FakeHttpxModule() as http:
            http.client.get = AsyncMock(
                return_value=MagicMock(
                    status_code=200,
                    json=MagicMock(return_value={"value": [{"id": "sub-drive", "resource": "/me/drive/root"}]}),
                )
            )
            http.client.delete = AsyncMock(side_effect=RuntimeError("delete failed"))
            with patch("integrations.microsoft365_service.microsoft365_service") as m365:
                m365.renew_subscription = AsyncMock(return_value={"status": "ok"})
                conn = self._conn(integration_id="outlook")
                result = await svc.renew_subscription_for_connection(conn)
        assert result["status"] == "success"

    async def test_outlook_renew_exception_fails(self):
        svc = self._svc()
        svc.connection_service._decrypt.return_value = {
            "access_token": "tok",
            "subscription_ids": ["sub-3"],
        }
        svc.connection_service._refresh_token_if_needed = AsyncMock(return_value=None)
        svc._handle_failure = MagicMock()
        with _FakeHttpxModule() as http:
            http.client.get = AsyncMock(return_value=MagicMock(status_code=200, json=MagicMock(return_value={"value": []})))
            with patch("integrations.microsoft365_service.microsoft365_service") as m365:
                m365.renew_subscription = AsyncMock(side_effect=RuntimeError("renew boom"))
                conn = self._conn(integration_id="outlook")
                result = await svc.renew_subscription_for_connection(conn)
        assert result == {"status": "failed", "error": "renew boom"}
        svc._handle_failure.assert_called_once()

    async def test_general_integration_recreated(self):
        svc = self._svc()
        svc.connection_service._decrypt.return_value = {"access_token": "tok"}
        svc.connection_service._refresh_token_if_needed = AsyncMock(return_value=None)
        conn = self._conn(integration_id="hubspot")
        result = await svc.renew_subscription_for_connection(conn)
        assert result == {"status": "success", "action": "recreated"}
        assert conn.last_refresh_at is not None
        assert conn.status == "active"
        assert conn.last_refresh_error is None


class TestHandleFailure:
    def test_failure_increments_below_threshold(self):
        db = MagicMock()
        svc = ScheduledWebhookRenewalService(db)
        conn = MagicMock()
        conn.refresh_failure_count = 1
        svc._handle_failure(conn, "boom")
        assert conn.refresh_failure_count == 2
        assert conn.last_refresh_error == "boom"
        db.commit.assert_called_once()

    def test_failure_reaches_threshold_deactivates(self):
        db = MagicMock()
        svc = ScheduledWebhookRenewalService(db)
        conn = MagicMock()
        conn.refresh_failure_count = 2
        conn.tenant_id = "t1"
        conn.integration_id = "slack"
        conn.id = "conn-1"
        svc._handle_failure(conn, "boom")
        assert conn.refresh_failure_count == 3
        assert conn.status == "error"
        db.add.assert_called_once()
        alert = db.add.call_args[0][0]
        assert alert.alert_type == "WEBHOOK_RENEWAL_FAILURE"
        assert alert.severity == "critical"

    def test_failure_threshold_alert_error_swallowed(self):
        db = MagicMock()
        svc = ScheduledWebhookRenewalService(db)
        conn = MagicMock()
        conn.refresh_failure_count = 2
        conn.tenant_id = "t1"
        conn.integration_id = "slack"
        conn.id = "conn-1"
        with patch("core.webhook_renewal_service.TrainingAlert", side_effect=ValueError("bad alert")):
            svc._handle_failure(conn, "boom")
        assert conn.status == "error"
        db.commit.assert_called_once()

    def test_failure_no_prior_count(self):
        db = MagicMock()
        svc = ScheduledWebhookRenewalService(db)
        conn = MagicMock()
        conn.refresh_failure_count = None
        svc._handle_failure(conn, "err")
        assert conn.refresh_failure_count == 1


class TestStaggeredCycle:
    def _svc(self, db):
        with patch("core.webhook_renewal_service.ConnectionService") as CS:
            CS.return_value = MagicMock()
            return ScheduledWebhookRenewalService(db)

    async def test_mock_db_userconnection_rows(self):
        db = MagicMock()
        conn = MagicMock()
        conn.id = "c1"
        rows = [conn]
        db.query.return_value.filter.return_value.all.return_value = rows
        db.query.return_value.filter_by.return_value.first.return_value = conn
        svc = self._svc(db)
        svc.is_renewal_due = MagicMock(return_value=True)
        svc.renew_subscription_for_connection = AsyncMock(return_value={"status": "success"})
        result = await svc.run_staggered_renewal_cycle()
        assert result == {"total_checked": 1, "renewed": 1, "failed": 0, "skipped": 0}
        svc.renew_subscription_for_connection.assert_awaited_once_with(conn)

    async def test_mock_db_userconnection_instances(self):
        """Real UserConnection instances passed as rows (is_mock_db branch)."""
        db = MagicMock()
        conn = MagicMock()
        conn.id = "c-uc"
        row = UserConnection(
            user_id="u1",
            tenant_id="t1",
            integration_id="slack",
            connection_name="n",
            credentials={},
            status="active",
        )
        db.query.return_value.filter.return_value.all.return_value = [row]
        db.query.return_value.filter_by.return_value.first.return_value = conn
        svc = self._svc(db)
        svc.is_renewal_due = MagicMock(return_value=False)
        result = await svc.run_staggered_renewal_cycle()
        assert result["skipped"] == 1

    async def test_mock_db_row_with_id_attr(self):
        db = MagicMock()
        row = SimpleNamespaceWrapper()
        row.id = "c2"
        db.query.return_value.filter.return_value.all.return_value = [row]
        svc = self._svc(db)
        conn = MagicMock()
        svc.is_renewal_due = MagicMock(return_value=False)
        db.query.return_value.filter_by.return_value.first.return_value = conn
        result = await svc.run_staggered_renewal_cycle()
        assert result["skipped"] == 1

    async def test_mock_db_tuple_rows(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [("c3",)]
        svc = self._svc(db)
        conn = MagicMock()
        svc.is_renewal_due = MagicMock(return_value=False)
        db.query.return_value.filter_by.return_value.first.return_value = conn
        result = await svc.run_staggered_renewal_cycle()
        assert result["skipped"] == 1

    async def test_mock_db_list_rows(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [["c4"]]
        svc = self._svc(db)
        conn = MagicMock()
        svc.is_renewal_due = MagicMock(return_value=False)
        db.query.return_value.filter_by.return_value.first.return_value = conn
        result = await svc.run_staggered_renewal_cycle()
        assert result["skipped"] == 1

    async def test_mock_db_scalar_rows(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = ["c5"]
        svc = self._svc(db)
        conn = MagicMock()
        svc.is_renewal_due = MagicMock(return_value=False)
        db.query.return_value.filter_by.return_value.first.return_value = conn
        result = await svc.run_staggered_renewal_cycle()
        assert result["skipped"] == 1

    async def test_mock_db_conn_not_found_skipped(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = ["c6"]
        svc = self._svc(db)
        db.query.return_value.filter_by.return_value.first.return_value = None
        result = await svc.run_staggered_renewal_cycle()
        assert result["skipped"] == 1

    async def test_mock_db_failure_counted(self):
        db = MagicMock()
        row = SimpleNamespaceWrapper()
        row.id = "c7"
        db.query.return_value.filter.return_value.all.return_value = [row]
        svc = self._svc(db)
        conn = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = conn
        svc.is_renewal_due = MagicMock(return_value=True)
        svc.renew_subscription_for_connection = AsyncMock(return_value={"status": "failed"})
        result = await svc.run_staggered_renewal_cycle()
        assert result["failed"] == 1
        assert result["renewed"] == 0

    async def test_real_db_session_flow(self):
        rows = [SimpleNamespaceWrapper(), SimpleNamespaceWrapper()]
        rows[0].id = "c-real-1"
        rows[1].id = "c-real-2"

        class _FakeDB:
            def __init__(self):
                self.closed = False
                self._first = None

            def query(self, *a, **k):
                return self

            def filter(self, *a, **k):
                return self

            def filter_by(self, **k):
                return self

            def all(self):
                return rows

            def first(self):
                return self._first

            def close(self):
                self.closed = True

        db = _FakeDB()
        fresh = _FakeDB()
        conn1 = MagicMock()
        conn1.id = "c-real-1"
        fresh._first = conn1
        svc = self._svc(db)
        svc.is_renewal_due = MagicMock(return_value=True)
        svc.renew_subscription_for_connection = AsyncMock(return_value={"status": "success"})
        with patch("core.database.SessionLocal", return_value=fresh):
            result = await svc.run_staggered_renewal_cycle()
        assert result["total_checked"] == 2
        assert result["renewed"] == 2
        assert fresh.closed is True

    async def test_real_db_sessionlocal_exception(self):
        """SessionLocal() raises inside the loop -> fall back to self.db."""
        row = SimpleNamespaceWrapper()
        row.id = "c-err"

        class _FakeDB:
            def query(self, *a, **k):
                return self

            def filter(self, *a, **k):
                return self

            def filter_by(self, **k):
                return self

            def all(self):
                return [row]

            def first(self):
                return None

            def close(self):
                pass

        db = _FakeDB()
        svc = self._svc(db)
        with patch("core.database.SessionLocal", side_effect=RuntimeError("session fail")):
            result = await svc.run_staggered_renewal_cycle()
        assert result == {"total_checked": 1, "renewed": 0, "failed": 0, "skipped": 1}


class SimpleNamespaceWrapper:
    """Plain object with an id attribute (no mock identity)."""

    def __init__(self):
        self.id = None


# ============================================================================
# 5. core/workflow_notifier.py
# ============================================================================


class TestNotificationSettings:
    def test_defaults(self):
        s = NotificationSettings()
        assert s.enabled is True
        assert s.notify_on_success is True
        assert s.notify_on_failure is True
        assert s.slack_enabled is True
        assert s.slack_channel == ""
        assert s.slack_mention_users == []
        assert s.email_enabled is False
        assert s.email_recipients == []
        assert s.custom_success_message is None

    def test_to_dict_roundtrip(self):
        s = NotificationSettings(slack_channel="#x", slack_mention_users=["U1"], email_enabled=True)
        d = s.to_dict()
        assert d["slack_channel"] == "#x"
        s2 = NotificationSettings.from_dict(d)
        assert s2.slack_channel == "#x"
        assert s2.slack_mention_users == ["U1"]

    def test_from_dict_filters_unknown_keys(self):
        s = NotificationSettings.from_dict({"enabled": False, "bogus_key": 1})
        assert s.enabled is False
        assert not hasattr(s, "bogus_key")

    def test_store_get_set(self):
        s = NotificationSettings(enabled=False)
        set_notification_settings("wf-store", s)
        assert get_notification_settings("wf-store") is s
        default = get_notification_settings("wf-unknown")
        assert isinstance(default, NotificationSettings)
        assert default.enabled is True

    def test_notification_type_enum(self):
        assert NotificationType.SLACK.value == "slack"
        assert NotificationType.EMAIL.value == "email"


class TestWorkflowNotifier:
    @pytest.fixture(autouse=True)
    def _no_init_db(self):
        cm = MagicMock()
        cm.__enter__.return_value = MagicMock()
        cm.__exit__.return_value = False
        with patch("core.database.get_db_session", return_value=cm) as gdb:
            with patch("core.integration_registry.IntegrationRegistry") as IR:
                IR.return_value.get_all_integrations.return_value = {"slack": "svc-obj"}
                yield gdb

    def test_init_discovers_slack_service(self):
        n = WorkflowNotifier()
        assert n.slack_service == "svc-obj"
        assert n.default_slack_channel == os.getenv("WORKFLOW_SLACK_CHANNEL", "#workflow-alerts")

    def test_init_env_channel_and_token(self):
        with patch.dict(
            os.environ,
            {"WORKFLOW_SLACK_CHANNEL": "#alerts", "WORKFLOW_SLACK_TOKEN": "xoxb-tok"},
            clear=False,
        ):
            n = WorkflowNotifier()
        assert n.default_slack_channel == "#alerts"
        assert n.slack_token == "xoxb-tok"

    def test_init_exception_defers_slack(self):
        with patch("core.database.get_db_session", side_effect=RuntimeError("db down")):
            n = WorkflowNotifier()
        assert n.slack_service is None

    def test_global_notifier(self):
        assert isinstance(notifier, WorkflowNotifier)

    async def test_notify_completion_disabled(self):
        n = WorkflowNotifier()
        n._send_slack = AsyncMock()
        n._send_email = AsyncMock()
        s = NotificationSettings(enabled=False)
        await n.notify_completion("wf", "name", "exec", {"a": 1}, s)
        n._send_slack.assert_not_awaited()

    async def test_notify_completion_success_disabled(self):
        n = WorkflowNotifier()
        n._send_slack = AsyncMock()
        s = NotificationSettings(notify_on_success=False)
        await n.notify_completion("wf", "name", "exec", {}, s)
        n._send_slack.assert_not_awaited()

    async def test_notify_completion_custom_message_with_mentions(self):
        n = WorkflowNotifier()
        n._send_slack = AsyncMock()
        n._send_email = AsyncMock()
        s = NotificationSettings(
            custom_success_message="Done!",
            slack_mention_users=["U1", "U2"],
            email_enabled=True,
            email_recipients=["a@b.c"],
        )
        await n.notify_completion("wf", "name", "exec", {"r": 1}, s)
        msg = n._send_slack.await_args.args[1]
        assert msg.startswith("<@U1> <@U2>")
        assert "Done!" in msg
        n._send_slack.assert_awaited_once_with("#workflow-alerts", msg)
        email_kwargs = n._send_email.await_args.kwargs
        assert email_kwargs["recipients"] == ["a@b.c"]
        assert "*" not in email_kwargs["body"]
        assert "`" not in email_kwargs["body"]

    async def test_notify_completion_default_message_slack_only(self):
        n = WorkflowNotifier()
        n._send_slack = AsyncMock()
        n._send_email = AsyncMock()
        s = NotificationSettings(email_enabled=False)
        await n.notify_completion("wf", "MyWF", "exec-1", {"a": 1, "b": 2}, s)
        msg = n._send_slack.await_args.args[1]
        assert "Workflow Completed" in msg
        assert "MyWF" in msg
        assert "exec-1" in msg
        n._send_email.assert_not_awaited()

    async def test_notify_completion_uses_stored_settings(self):
        n = WorkflowNotifier()
        n._send_slack = AsyncMock()
        set_notification_settings("wf-stored", NotificationSettings(enabled=False))
        await n.notify_completion("wf-stored", "n", "e", {})
        n._send_slack.assert_not_awaited()

    async def test_notify_failure_disabled(self):
        n = WorkflowNotifier()
        n._send_slack = AsyncMock()
        s = NotificationSettings(enabled=False)
        await n.notify_failure("wf", "name", "exec", "err", s)
        n._send_slack.assert_not_awaited()

    async def test_notify_failure_on_failure_disabled(self):
        n = WorkflowNotifier()
        n._send_slack = AsyncMock()
        s = NotificationSettings(notify_on_failure=False)
        await n.notify_failure("wf", "name", "exec", "err", s)
        n._send_slack.assert_not_awaited()

    async def test_notify_failure_custom_message(self):
        n = WorkflowNotifier()
        n._send_slack = AsyncMock()
        s = NotificationSettings(custom_failure_message="Custom fail", slack_mention_users=["U9"])
        await n.notify_failure("wf", "name", "exec", "boom", s)
        msg = n._send_slack.await_args.args[1]
        assert msg.startswith("<@U9>")
        assert "Custom fail" in msg

    async def test_notify_failure_default_message(self):
        n = WorkflowNotifier()
        n._send_slack = AsyncMock()
        s = NotificationSettings()
        await n.notify_failure("wf", "MyWF", "exec-1", "boom", s)
        msg = n._send_slack.await_args.args[1]
        assert "Workflow Failed" in msg
        assert "boom" in msg

    async def test_notify_failure_email(self):
        n = WorkflowNotifier()
        n._send_slack = AsyncMock()
        n._send_email = AsyncMock()
        s = NotificationSettings(email_enabled=True, email_recipients=["x@y.z"])
        await n.notify_failure("wf", "MyWF", "e1", "err", s)
        email_kwargs = n._send_email.await_args.kwargs
        assert "Workflow Failed" in email_kwargs["subject"]
        assert "MyWF" in email_kwargs["body"]

    async def test_send_slack_no_token(self):
        n = WorkflowNotifier()
        n.slack_token = None
        await n._send_slack("#chan", "msg")
        assert True

    async def test_send_slack_success(self):
        n = WorkflowNotifier()
        n.slack_token = "xoxb"
        with _FakeHttpxModule() as http:
            http.client.post = AsyncMock(return_value=MagicMock(status_code=200))
            await n._send_slack("#chan", "msg")
        http.client.post.assert_awaited_once()

    async def test_send_slack_error_status(self):
        n = WorkflowNotifier()
        n.slack_token = "xoxb"
        with _FakeHttpxModule() as http:
            http.client.post = AsyncMock(return_value=MagicMock(status_code=500, text="nope"))
            await n._send_slack("#chan", "msg")
        http.client.post.assert_awaited_once()

    async def test_send_slack_exception(self):
        n = WorkflowNotifier()
        n.slack_token = "xoxb"
        with _FakeHttpxModule() as http:
            http.client.post = AsyncMock(side_effect=RuntimeError("net down"))
            await n._send_slack("#chan", "msg")
        http.client.post.assert_awaited_once()

    async def test_send_email_logs(self, caplog):
        import logging

        n = WorkflowNotifier()
        with caplog.at_level(logging.INFO):
            await n._send_email(["a@b.c"], "subj", "body")
        assert any("Would send email to ['a@b.c']: subj" in r.message for r in caplog.records)

    async def test_send_email_exception(self):
        n = WorkflowNotifier()
        with patch("core.workflow_notifier.logger.info", side_effect=RuntimeError("log fail")):
            await n._send_email(["a@b.c"], "subj", "body")
        assert True


# ============================================================================
# 6. core/notification_manager.py
# ============================================================================


class TestConnectionManager:
    async def test_connect_new_workspace(self):
        m = ConnectionManager()
        ws = MagicMock()
        ws.accept = AsyncMock()
        await m.connect(ws, "ws-1")
        assert m.active_connections["ws-1"] == [ws]
        ws.accept.assert_awaited_once()

    async def test_connect_existing_workspace(self):
        m = ConnectionManager()
        ws1, ws2 = MagicMock(), MagicMock()
        ws1.accept = AsyncMock()
        ws2.accept = AsyncMock()
        await m.connect(ws1, "ws-1")
        await m.connect(ws2, "ws-1")
        assert len(m.active_connections["ws-1"]) == 2

    def test_disconnect_present(self):
        m = ConnectionManager()
        ws = MagicMock()
        m.active_connections["ws-1"] = [ws]
        m.disconnect(ws, "ws-1")
        assert "ws-1" not in m.active_connections

    def test_disconnect_last_removes_key(self):
        m = ConnectionManager()
        ws1, ws2 = MagicMock(), MagicMock()
        m.active_connections["ws-1"] = [ws1, ws2]
        m.disconnect(ws1, "ws-1")
        assert m.active_connections["ws-1"] == [ws2]
        m.disconnect(ws2, "ws-1")
        assert "ws-1" not in m.active_connections

    def test_disconnect_absent_websocket(self):
        m = ConnectionManager()
        m.active_connections["ws-1"] = [MagicMock()]
        m.disconnect(MagicMock(), "ws-1")
        assert "ws-1" in m.active_connections

    def test_disconnect_unknown_workspace(self):
        m = ConnectionManager()
        m.disconnect(MagicMock(), "nope")

    async def test_broadcast_no_workspace(self):
        m = ConnectionManager()
        await m.broadcast({"x": 1}, "missing")
        assert True

    async def test_broadcast_sends_to_all(self):
        m = ConnectionManager()
        ws1, ws2 = MagicMock(), MagicMock()
        ws1.send_json = AsyncMock()
        ws2.send_json = AsyncMock()
        m.active_connections["ws-1"] = [ws1, ws2]
        await m.broadcast({"x": 1}, "ws-1")
        ws1.send_json.assert_awaited_once_with({"x": 1})
        ws2.send_json.assert_awaited_once_with({"x": 1})

    async def test_broadcast_removes_failed(self):
        m = ConnectionManager()
        good, bad = MagicMock(), MagicMock()
        good.send_json = AsyncMock()
        bad.send_json = AsyncMock(side_effect=RuntimeError("socket dead"))
        m.active_connections["ws-1"] = [good, bad]
        await m.broadcast({"x": 1}, "ws-1")
        assert m.active_connections["ws-1"] == [good]

    async def test_send_urgent_notification(self):
        m = ConnectionManager()
        ws = MagicMock()
        ws.send_json = AsyncMock()
        m.active_connections["ws-1"] = [ws]
        await m.send_urgent_notification("TROUBLE", "ws-1", channel="slack")
        ws.send_json.assert_awaited_once()
        payload = ws.send_json.await_args.args[0]
        assert payload["type"] == "urgent_alert"
        assert payload["message"] == "TROUBLE"
        assert payload["channel"] == "slack"

    def test_singleton(self):
        assert isinstance(notification_manager, ConnectionManager)
        assert nm_mod.notification_manager is notification_manager


# ============================================================================
# 7. core/notification_service.py
# ============================================================================


class TestNotificationService:
    def _db(self, user=None):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = user
        return db

    async def test_send_notification_persists_row(self):
        db = self._db()
        svc = NotificationService(db)
        result = await svc.send_notification("u1", "agent_graduated", {"title": "T", "message": "M"})
        assert result["success"] is True
        assert result["emailed"] is False
        db.add.assert_called_once()
        notif = db.add.call_args[0][0]
        assert notif.user_id == "u1"
        assert notif.title == "T"
        assert notif.message == "M"
        assert notif.type == "success"
        assert notif.read is False
        db.commit.assert_called_once()
        db.refresh.assert_called_once()

    async def test_send_notification_defaults(self):
        db = self._db()
        svc = NotificationService(db)
        await svc.send_notification("u1", "something_new", {})
        notif = db.add.call_args[0][0]
        assert notif.title == "New notification"
        assert notif.message == "New notification"
        assert notif.workspace_id == "default"
        assert notif.tenant_id == "default"
        assert notif.type == "info"

    async def test_send_notification_metadata_stripping(self):
        db = self._db()
        svc = NotificationService(db)
        await svc.send_notification(
            "u1",
            "approval_needed",
            {
                "title": "T",
                "message": "M",
                "workspace_id": "w1",
                "tenant_id": "t1",
                "action_url": "http://x",
                "action_label": "Go",
                "extra": {"nested": 1},
            },
        )
        notif = db.add.call_args[0][0]
        assert notif.workspace_id == "w1"
        assert notif.tenant_id == "t1"
        assert notif.action_url == "http://x"
        assert notif.action_label == "Go"
        assert notif.metadata_json == {
            "notification_type": "approval_needed",
            "extra": {"nested": 1},
        }

    async def test_send_notification_title_truncated(self):
        db = self._db()
        svc = NotificationService(db)
        await svc.send_notification("u1", "x", {"title": "T" * 600, "message": "M"})
        notif = db.add.call_args[0][0]
        assert len(notif.title) == 500

    async def test_send_notification_high_priority_email_sent(self):
        user = MagicMock()
        user.notification_preferences = {"email_enabled": True}
        user.email = "u@x.com"
        db = self._db(user)
        svc = NotificationService(db)
        with patch("core.email_utils.send_smtp_email", return_value=True) as send:
            result = await svc.send_notification("u1", "security_alert", {"title": "Alert", "message": "B"})
        assert result["emailed"] is True
        send.assert_called_once_with(to_email="u@x.com", subject="Alert", body="B")

    async def test_send_notification_priority_flag_forces_email(self):
        user = MagicMock()
        user.notification_preferences = {"email_enabled": True}
        user.email = "u@x.com"
        db = self._db(user)
        svc = NotificationService(db)
        with patch("core.email_utils.send_smtp_email", return_value=True):
            result = await svc.send_notification("u1", "normal_type", {"title": "T", "message": "M", "priority": "HIGH"})
        assert result["emailed"] is True

    async def test_send_notification_no_email_for_low_priority(self):
        db = self._db()
        svc = NotificationService(db)
        with patch("core.email_utils.send_smtp_email") as send:
            result = await svc.send_notification("u1", "info_type", {"title": "T", "message": "M"})
        assert result["emailed"] is False
        send.assert_not_called()

    async def test_email_skipped_when_user_not_found(self):
        db = self._db(None)
        svc = NotificationService(db)
        with patch("core.email_utils.send_smtp_email") as send:
            result = await svc.send_notification("u1", "security_alert", {"title": "T", "message": "M"})
        assert result["emailed"] is False
        send.assert_not_called()

    async def test_email_skipped_when_not_opted_in(self):
        user = MagicMock()
        user.notification_preferences = {"email_enabled": False}
        user.email = "u@x.com"
        db = self._db(user)
        svc = NotificationService(db)
        with patch("core.email_utils.send_smtp_email") as send:
            result = await svc.send_notification("u1", "security_alert", {"title": "T", "message": "M"})
        assert result["emailed"] is False
        send.assert_not_called()

    async def test_email_skipped_when_no_email_address(self):
        user = MagicMock()
        user.notification_preferences = {"email_enabled": True}
        user.email = None
        db = self._db(user)
        svc = NotificationService(db)
        with patch("core.email_utils.send_smtp_email") as send:
            result = await svc.send_notification("u1", "security_alert", {"title": "T", "message": "M"})
        assert result["emailed"] is False
        send.assert_not_called()

    async def test_email_send_exception_swallowed(self):
        user = MagicMock()
        user.notification_preferences = {"email_enabled": True}
        user.email = "u@x.com"
        db = self._db(user)
        svc = NotificationService(db)
        with patch("core.email_utils.send_smtp_email", side_effect=RuntimeError("smtp down")):
            result = await svc.send_notification("u1", "security_alert", {"title": "T", "message": "M"})
        assert result["success"] is True
        assert result["emailed"] is False

    async def test_email_user_query_exception_swallowed(self):
        db = self._db()
        db.query.return_value.filter.return_value.first.side_effect = RuntimeError("query boom")
        svc = NotificationService(db)
        result = await svc.send_notification("u1", "security_alert", {"title": "T", "message": "M"})
        assert result["emailed"] is False

    async def test_email_legacy_flag_enabled(self):
        user = MagicMock()
        user.notification_preferences = None
        user.email_notifications_enabled = True
        user.email = "u@x.com"
        db = self._db(user)
        svc = NotificationService(db)
        with patch("core.email_utils.send_smtp_email", return_value=True):
            result = await svc.send_notification("u1", "approval_needed", {"title": "T", "message": "M"})
        assert result["emailed"] is True

    async def test_db_none_opens_own_session(self):
        with patch("core.database.SessionLocal") as SL:
            session = MagicMock()
            SL.return_value = session
            svc = NotificationService(None)
            result = await svc.send_notification("u1", "x", {"title": "T", "message": "M"})
        assert result["success"] is True
        session.add.assert_called_once()
        session.commit.assert_called_once()
        session.close.assert_called_once()
        assert svc.db is None

    async def test_db_none_session_close_exception_swallowed(self):
        with patch("core.database.SessionLocal") as SL:
            session = MagicMock()
            session.close.side_effect = RuntimeError("close fail")
            SL.return_value = session
            svc = NotificationService(None)
            result = await svc.send_notification("u1", "x", {"title": "T", "message": "M"})
        assert result["success"] is True
        assert svc.db is None

    async def test_persist_exception_soft_fails(self):
        svc = NotificationService(MagicMock())
        with patch.object(svc, "_persist_and_maybe_email", side_effect=RuntimeError("boom")):
            result = await svc.send_notification("u1", "x", {"title": "T"})
        assert result == {
            "success": False,
            "notification_id": None,
            "emailed": False,
            "error": "notification_failed",
        }

    async def test_email_recipient_uses_user_email(self):
        user = MagicMock()
        user.notification_preferences = {"email_enabled": True}
        user.email = "real@x.com"
        db = self._db(user)
        svc = NotificationService(db)
        with patch("core.email_utils.send_smtp_email", return_value=True) as send:
            await svc.send_notification("u1", "security_alert", {"title": "T", "message": "M"})
        send.assert_called_once_with(to_email="real@x.com", subject="T", body="M")


class TestNotificationHelpers:
    def test_user_email_enabled_variants(self):
        u1 = MagicMock()
        u1.notification_preferences = {"email_enabled": True}
        assert _user_email_enabled(u1) is True
        u2 = MagicMock()
        u2.notification_preferences = {"email_enabled": False}
        assert _user_email_enabled(u2) is False
        u3 = MagicMock()
        u3.notification_preferences = None
        u3.email_notifications_enabled = True
        assert _user_email_enabled(u3) is True
        u4 = MagicMock()
        u4.notification_preferences = {}
        assert _user_email_enabled(u4) is False

    def test_classify(self):
        assert _classify("security_alert") == "error"
        assert _classify("backend_error") == "error"
        assert _classify("warning_issue") == "warning"
        assert _classify("approval_needed") == "warning"
        assert _classify("promotion_done") == "success"
        assert _classify("agent_graduated") == "success"
        assert _classify("random") == "info"
        assert _classify("") == "info"

    def test_default_title(self):
        assert _default_title("agent_graduated") == "Your agent graduated to the next tier"
        assert _default_title("approval_needed") == "An approval is needed"
        assert _default_title("security_alert") == "Security alert"
        assert _default_title("other") == "New notification"

    def test_high_priority_types(self):
        assert HIGH_PRIORITY_TYPES == {"agent_graduated", "approval_needed", "security_alert"}


# ============================================================================
# 8. core/observation_filter_service.py
# ============================================================================


class TestObservationFilterService:
    @pytest.fixture(autouse=True)
    def _enable(self):
        with patch.object(ofs_mod, "OBSERVATION_FILTER_ENABLED", True):
            yield

    def _svc(self):
        svc = ObservationFilterService(MagicMock())
        svc.threshold = 0.9
        svc.KEEP_LAST_N = 2
        svc.embedding_min_step = 3
        return svc

    async def test_disabled_passthrough(self):
        svc = ObservationFilterService(MagicMock())
        with patch.object(ofs_mod, "OBSERVATION_FILTER_ENABLED", False):
            history, stats = await svc.filter_history("some text", 1, "task")
        assert history == "some text"
        assert stats["enabled"] is False
        assert stats["savings_tokens"] == 0
        assert stats["original_tokens"] == stats["filtered_tokens"]

    async def test_enabled_rule_pass_only(self):
        svc = self._svc()
        llm = MagicMock()
        svc.llm = llm
        with patch.object(svc, "_count_tokens", side_effect=lambda t: len(t)):
            history, stats = await svc.filter_history("Observation: a\nObservation: a\nplain", 1, "task")
        assert stats["enabled"] is True
        assert stats["embedding_pass"] is False
        assert history == "Observation: a\nplain"

    async def test_rule_pass_exception_falls_back(self):
        svc = self._svc()
        with patch.object(svc, "_apply_rules", side_effect=RuntimeError("rule boom")):
            history, stats = await svc.filter_history("obs text", 1, "task")
        assert history == "obs text"
        assert stats["enabled"] is True

    async def test_embedding_pass_runs_at_min_step(self):
        svc = self._svc()
        llm = MagicMock()
        llm.generate_embeddings_batch = AsyncMock(return_value=[[1.0, 0.0], [1.0, 0.0], [1.0, 0.0]])
        svc.llm = llm
        history = "Observation: x\nObservation: x\nObservation: x"
        filtered, stats = await svc.filter_history(history, 5, "task")
        assert stats["embedding_pass"] is True
        assert stats["enabled"] is True

    async def test_embedding_exception_skipped(self):
        svc = self._svc()
        llm = MagicMock()
        llm.generate_embeddings_batch = AsyncMock(side_effect=RuntimeError("emb fail"))
        llm.generate_embedding = AsyncMock(side_effect=RuntimeError("emb fail 2"))
        svc.llm = llm
        history = "\n".join(f"Observation: o{i}" for i in range(5))
        _, stats = await svc.filter_history(history, 5, "task")
        assert stats["embedding_pass"] is False

    async def test_savings_math(self):
        svc = self._svc()
        with patch.object(svc, "_count_tokens", side_effect=lambda t: 100 if t.startswith("orig") else 60):
            with patch.object(svc, "_apply_rules", return_value="filtered"):
                _, stats = await svc.filter_history("original text", 1, "task")
        assert stats["savings_tokens"] == 40
        assert stats["original_tokens"] == 100
        assert stats["filtered_tokens"] == 60

    def test_apply_rules_ansi_and_control_scrub(self):
        svc = self._svc()
        out = svc._apply_rules("Obs\x1b[31mervation: \x00raw\x7f\nnext")
        assert "\x1b[31m" not in out
        assert "\x00" not in out
        assert "\x7f" not in out
        assert "next" in out

    def test_apply_rules_dedup_and_truncate(self):
        svc = self._svc()
        long_obs = "A" * 5000
        with patch.object(ofs_mod, "PER_OBSERVATION_LENGTH_CAP", 100):
            out = svc._apply_rules(f"Observation: {long_obs}\nObservation: {long_obs}\nObservation: short")
        lines = out.split("\n")
        assert len(lines) == 2
        assert "[truncated]" in lines[0]
        assert lines[0].startswith("Observation: ")

    def test_apply_rules_repeated_errors_collapsed(self):
        svc = self._svc()
        out = svc._apply_rules(
            "Observation: Error: boom Error: boom Error: nope\nObservation: Error: boom Error: nope"
        )
        assert out.count("boom") == 1
        assert out.count("nope") == 1

    def test_collapse_repeated_errors_no_error(self):
        svc = self._svc()
        assert svc._collapse_repeated_errors("no errors here") == "no errors here"

    def test_collapse_repeated_errors_single(self):
        svc = self._svc()
        assert svc._collapse_repeated_errors("Error: one") == "Error: one"

    async def test_collapse_semantic_duplicates_too_few(self):
        svc = self._svc()
        history = "Observation: a\nObservation: b"
        assert await svc._collapse_semantic_duplicates(history) == history

    async def test_collapse_semantic_duplicates_drops(self):
        svc = self._svc()
        llm = MagicMock()
        llm.generate_embeddings_batch = AsyncMock(
            return_value=[[1.0, 0.0], [1.0, 0.0], [1.0, 0.0], [0.0, 1.0], [0.0, 1.0]]
        )
        svc.llm = llm
        history = "\n".join(f"Observation: o{i}" for i in range(5))
        out = await svc._collapse_semantic_duplicates(history)
        assert "o0" not in out
        assert "o1" in out
        assert "o2" in out
        assert "o3" in out
        assert "o4" in out

    async def test_collapse_semantic_duplicates_batch_fallback_per_item(self):
        svc = self._svc()
        llm = MagicMock()
        llm.generate_embeddings_batch = AsyncMock(return_value=None)
        llm.generate_embedding = AsyncMock(side_effect=lambda text: [1.0, 0.0])
        svc.llm = llm
        history = "\n".join(f"Observation: o{i}" for i in range(5))
        out = await svc._collapse_semantic_duplicates(history)
        assert llm.generate_embedding.await_count == 5
        assert len(out.split("\n")) == 2

    async def test_collapse_semantic_duplicates_batch_raises_fallback(self):
        svc = self._svc()
        llm = MagicMock()
        llm.generate_embeddings_batch = AsyncMock(side_effect=RuntimeError("batch boom"))
        llm.generate_embedding = AsyncMock(side_effect=lambda text: [0.0, 1.0])
        svc.llm = llm
        history = "\n".join(f"Observation: o{i}" for i in range(5))
        out = await svc._collapse_semantic_duplicates(history)
        assert len(out.split("\n")) == 2

    async def test_collapse_semantic_no_drops_unchanged(self):
        svc = self._svc()
        llm = MagicMock()
        llm.generate_embeddings_batch = AsyncMock(
            return_value=[[1.0, 0.0], [0.0, 1.0], [0.0, 1.0], [1.0, 0.0]]
        )
        svc.llm = llm
        history = "\n".join(f"Observation: o{i}" for i in range(4))
        out = await svc._collapse_semantic_duplicates(history)
        assert out == history

    def test_count_tokens_tiktoken(self):
        svc = self._svc()
        enc = MagicMock()
        enc.encode.return_value = list(range(7))
        fake_tiktoken = types.ModuleType("tiktoken")
        fake_tiktoken.get_encoding = MagicMock(return_value=enc)
        with patch.dict(sys.modules, {"tiktoken": fake_tiktoken}):
            assert svc._count_tokens("hello world") == 7
        enc.encode.assert_called_once_with("hello world")

    def test_count_tokens_fallback(self):
        svc = self._svc()
        with patch.dict(sys.modules, {"tiktoken": None}):
            assert svc._count_tokens("abcd") == 1

    def test_cosine_numpy(self):
        assert abs(ObservationFilterService._cosine([1.0, 0.0], [1.0, 0.0]) - 1.0) < 1e-9
        assert abs(ObservationFilterService._cosine([1.0, 0.0], [0.0, 1.0])) < 1e-9

    def test_cosine_zero_norm(self):
        assert ObservationFilterService._cosine([0.0, 0.0], [1.0, 0.0]) == 0.0

    def test_cosine_import_failure(self):
        with patch.dict(sys.modules, {"numpy": None}):
            assert ObservationFilterService._cosine([1.0], [1.0]) == 0.0


# ============================================================================
# 9. core/time_expression_parser.py
# ============================================================================


class TestTimeNormalization:
    def test_no_period(self):
        assert normalize_time_12h_to_24h(9, 30, None) == (9, 30)

    def test_pm_afternoon(self):
        assert normalize_time_12h_to_24h(2, 15, "pm") == (14, 15)

    def test_pm_noon_unchanged(self):
        assert normalize_time_12h_to_24h(12, 0, "PM") == (12, 0)

    def test_am_midnight(self):
        assert normalize_time_12h_to_24h(12, 5, "am") == (0, 5)

    def test_am_morning(self):
        assert normalize_time_12h_to_24h(8, 45, "am") == (8, 45)


class TestParseWithPatterns:
    def test_daily_at_time(self):
        result = parse_with_patterns("daily at 9:30am")
        assert result["schedule_type"] == "cron"
        assert result["cron_expression"] == "30 9 * * *"
        assert result["human_readable"] == "Every day at 09:30"
        assert result["matched_text"] == "daily at 9:30am"

    def test_daily_default_time(self):
        result = parse_with_patterns("every day")
        assert result["cron_expression"] == "0 9 * * *"

    def test_daily_pm_time(self):
        result = parse_with_patterns("daily at 5pm")
        assert result["cron_expression"] == "0 17 * * *"

    def test_every_hours(self):
        result = parse_with_patterns("every 2 hours")
        assert result["schedule_type"] == "interval"
        assert result["interval_minutes"] == 120
        assert result["human_readable"] == "Every 2 hours"

    def test_every_single_hour(self):
        result = parse_with_patterns("every 1 hour")
        assert result["interval_minutes"] == 60

    def test_every_minutes(self):
        result = parse_with_patterns("every 15 minutes")
        assert result["interval_minutes"] == 15
        assert result["human_readable"] == "Every 15 minutes"

    def test_weekdays_at_time(self):
        result = parse_with_patterns("weekdays at 10:15am")
        assert result["cron_expression"] == "15 10 * * 1-5"
        assert result["human_readable"] == "Every weekday at 10:15"

    def test_weekdays_default(self):
        result = parse_with_patterns("every weekday")
        assert result["cron_expression"] == "0 9 * * 1-5"

    def test_weekdays_pm(self):
        result = parse_with_patterns("weekdays at 11pm")
        assert result["cron_expression"] == "0 23 * * 1-5"

    def test_weekends_at_time(self):
        result = parse_with_patterns("weekends at 8am")
        assert result["cron_expression"] == "0 8 * * 0,6"
        assert result["human_readable"] == "Every weekend at 08:00"

    def test_weekends_default(self):
        result = parse_with_patterns("every weekend")
        assert result["cron_expression"] == "0 9 * * 0,6"

    def test_specific_day_with_time(self):
        result = parse_with_patterns("every monday at 2pm")
        assert result["cron_expression"] == "0 14 * * 1"
        assert result["human_readable"] == "Every Monday at 14:00"

    def test_specific_day_default_time(self):
        result = parse_with_patterns("sunday")
        assert result["cron_expression"] == "0 9 * * 0"

    def test_specific_day_with_minutes(self):
        result = parse_with_patterns("wednesdays at 3:45am")
        assert result["cron_expression"] == "45 3 * * 3"

    def test_first_day_of_month_at_time(self):
        result = parse_with_patterns("on the first day of the month at 6am")
        assert result["cron_expression"] == "0 6 1 * *"
        assert result["human_readable"] == "First day of each month at 06:00"

    def test_first_day_default(self):
        result = parse_with_patterns("first day of every month")
        assert result["cron_expression"] == "0 9 1 * *"

    def test_last_day_of_month(self):
        result = parse_with_patterns("last day of each month at 7:30pm")
        assert result["cron_expression"] == "30 19 L * *"
        assert result["human_readable"] == "Last day of each month at 19:30"

    def test_unmatched_returns_none(self):
        assert parse_with_patterns("tomorrow afternoon") is None

    def test_case_insensitive(self):
        result = parse_with_patterns("DAILY AT 9AM")
        assert result["cron_expression"] == "0 9 * * *"


class TestParseWithLLM:
    async def test_valid_result_returned(self):
        ai = MagicMock()
        ai.process_with_nlu = AsyncMock(
            return_value={"schedule_type": "cron", "cron_expression": "0 9 * * 1-5", "human_readable": "x"}
        )
        result = await parse_with_llm("weekday at 9", ai)
        assert result["schedule_type"] == "cron"
        ai.process_with_nlu.assert_awaited_once()

    async def test_result_missing_schedule_type(self):
        ai = MagicMock()
        ai.process_with_nlu = AsyncMock(return_value={"human_readable": "x"})
        assert await parse_with_llm("complex", ai) is None

    async def test_result_none(self):
        ai = MagicMock()
        ai.process_with_nlu = AsyncMock(return_value=None)
        assert await parse_with_llm("complex", ai) is None

    async def test_exception_returns_none(self):
        ai = MagicMock()
        ai.process_with_nlu = AsyncMock(side_effect=RuntimeError("llm down"))
        assert await parse_with_llm("complex", ai) is None

    async def test_non_dict_result(self):
        ai = MagicMock()
        ai.process_with_nlu = AsyncMock(return_value="string result")
        assert await parse_with_llm("complex", ai) is None


class TestParseTimeExpression:
    async def test_pattern_match_first(self):
        ai = AsyncMock()
        result = await parse_time_expression("daily at 9am", ai)
        assert result["schedule_type"] == "cron"
        ai.process_with_nlu.assert_not_awaited()

    async def test_no_ai_service_returns_none(self):
        assert await parse_time_expression("random phrase") is None

    async def test_llm_fallback_success(self):
        ai = MagicMock()
        ai.process_with_nlu = AsyncMock(return_value={"schedule_type": "date", "run_date": "2026-01-01"})
        result = await parse_time_expression("december 25 at 10am", ai)
        assert result["schedule_type"] == "date"
        ai.process_with_nlu.assert_awaited_once()

    async def test_llm_fallback_failure(self):
        ai = MagicMock()
        ai.process_with_nlu = AsyncMock(return_value=None)
        assert await parse_time_expression("december 25 at 10am", ai) is None

    def test_pattern_table_shape(self):
        assert len(TIME_PATTERNS) >= 8
        for config in TIME_PATTERNS.values():
            assert config["type"] in ("cron", "interval")


# ============================================================================
# 10. core/user_preference_service.py
# ============================================================================


class TestUserPreferenceModel:
    def test_model_columns(self):
        assert UserPreference.__tablename__ == "user_preferences"
        assert UserPreference.__table__.columns["user_id"].nullable is False
        assert UserPreference.__table__.columns["workspace_id"].nullable is False
        assert UserPreference.__table__.columns["key"].nullable is False

    def test_unique_constraint(self):
        names = [c.name for c in UserPreference.__table__.constraints]
        assert "uix_user_workspace_key" in names

    def test_construct(self):
        p = UserPreference(user_id="u1", workspace_id="w1", key="k", value="v")
        assert p.user_id == "u1"
        assert p.value == "v"


class TestUserPreferenceService:
    def _db(self):
        return MagicMock()

    def test_set_preference_new(self):
        db = self._db()
        db.query.return_value.filter_by.return_value.first.return_value = None
        svc = UserPreferenceService(db)
        assert svc.set_preference("u1", "w1", "theme", {"dark": True}) is True
        db.add.assert_called_once()
        pref = db.add.call_args[0][0]
        assert isinstance(pref, UserPreference)
        assert pref.value == json.dumps({"dark": True})
        db.commit.assert_called_once()

    def test_set_preference_existing(self):
        db = self._db()
        existing = UserPreference(user_id="u1", workspace_id="w1", key="theme", value="old")
        db.query.return_value.filter_by.return_value.first.return_value = existing
        svc = UserPreferenceService(db)
        assert svc.set_preference("u1", "w1", "theme", "new-value") is True
        assert existing.value == '"new-value"'
        db.add.assert_not_called()

    def test_set_preference_commit_error_rolls_back(self):
        db = self._db()
        db.query.return_value.filter_by.return_value.first.return_value = None
        db.commit.side_effect = RuntimeError("db down")
        svc = UserPreferenceService(db)
        with pytest.raises(RuntimeError):
            svc.set_preference("u1", "w1", "k", "v")
        db.rollback.assert_called_once()

    def test_get_preference_parsed_json(self):
        db = self._db()
        pref = UserPreference(user_id="u1", workspace_id="w1", key="k", value='{"a": 1}')
        db.query.return_value.filter_by.return_value.first.return_value = pref
        svc = UserPreferenceService(db)
        assert svc.get_preference("u1", "w1", "k", "default") == {"a": 1}

    def test_get_preference_raw_fallback(self):
        db = self._db()
        pref = UserPreference(user_id="u1", workspace_id="w1", key="k", value="not-json")
        db.query.return_value.filter_by.return_value.first.return_value = pref
        svc = UserPreferenceService(db)
        assert svc.get_preference("u1", "w1", "k", "default") == "not-json"

    def test_get_preference_missing_returns_default(self):
        db = self._db()
        db.query.return_value.filter_by.return_value.first.return_value = None
        svc = UserPreferenceService(db)
        assert svc.get_preference("u1", "w1", "k", "fallback") == "fallback"

    def test_get_preference_empty_value_returns_default(self):
        db = self._db()
        pref = UserPreference(user_id="u1", workspace_id="w1", key="k", value=None)
        db.query.return_value.filter_by.return_value.first.return_value = pref
        svc = UserPreferenceService(db)
        assert svc.get_preference("u1", "w1", "k", "d") == "d"

    def test_get_all_preferences(self):
        db = self._db()
        p1 = UserPreference(user_id="u1", workspace_id="w1", key="a", value='{"x": 1}')
        p2 = UserPreference(user_id="u1", workspace_id="w1", key="b", value="raw")
        db.query.return_value.filter_by.return_value.all.return_value = [p1, p2]
        svc = UserPreferenceService(db)
        result = svc.get_all_preferences("u1", "w1")
        assert result == {"a": {"x": 1}, "b": "raw"}

    def test_get_all_preferences_empty(self):
        db = self._db()
        db.query.return_value.filter_by.return_value.all.return_value = []
        svc = UserPreferenceService(db)
        assert svc.get_all_preferences("u1", "w1") == {}
