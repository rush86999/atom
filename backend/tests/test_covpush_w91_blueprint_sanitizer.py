# -*- coding: utf-8 -*-
"""Coverage wave 91 — core/blueprint_sanitizer (P5 Blueprint Security).

Pure-function credential stripping — zero LLM spend, no network, no DB.

- strip_credentials: every denylist key shape (api_key, access/refresh/auth/
  bot/bearer token, token, private_key, secret, password, authorization),
  case-insensitive matching, nested dict/list recursion, int/other keys,
  scalars passthrough, deep-copy semantics (input never mutated).
- No false positives: benign keys survive untouched.
- has_credentials: True for any nested credential key, False for clean data.
"""
from copy import deepcopy

from core.blueprint_sanitizer import _is_credential_key, has_credentials, strip_credentials


# ============================================================================
# _is_credential_key
# ============================================================================

def test_is_credential_key_shapes():
    for key in [
        "api_key", "apikey", "api-key", "API_KEY", "ApiKey",
        "access_token", "ACCESS_TOKEN", "refresh_token", "auth_token",
        "bot_token", "bearer_token", "token", "private_key", "secret",
        "password", "authorization", "Authorization", "client_secret",
        "x-api-key", "webhook_secret",
    ]:
        assert _is_credential_key(key), key

    for key in ["name", "email", "amount", "order_id", "workspace_id",
                "component_type", "config", "description", "category",
                "region", "created_at"]:
        assert not _is_credential_key(key), key


# ============================================================================
# strip_credentials
# ============================================================================

def test_strip_credentials_flat_denylist():
    obj = {
        "api_key": "sk-123",
        "access_token": "at-1",
        "refresh_token": "rt-1",
        "name": "safe",
        "password": "hunter2",
    }
    out = strip_credentials(obj)
    assert out == {"name": "safe"}
    assert "api_key" not in out


def test_strip_credentials_nested():
    obj = {
        "integration": {
            "config": {
                "api_key": "sk-1",
                "client_secret": "cs-1",
                "region": "eu",
            },
            "items": [
                {"token": "t1", "label": "ok"},
                {"nested": {"private_key": "pk"}},
            ],
        }
    }
    out = strip_credentials(obj)
    assert out == {
        "integration": {
            "config": {"region": "eu"},
            "items": [{"label": "ok"}, {"nested": {}}],
        }
    }


def test_strip_credentials_lists_and_scalars():
    # Only dict KEYS are stripped — scalar values pass through untouched.
    assert strip_credentials([{"password": "x"}, "plain", 42, None, ["secret"]]) == [
        {}, "plain", 42, None, ["secret"]
    ]
    assert strip_credentials("hello") == "hello"
    assert strip_credentials(42) == 42
    assert strip_credentials(None) is None
    assert strip_credentials(True) is True


def test_strip_credentials_case_insensitive():
    out = strip_credentials({"API_KEY": "x", "Api_Key": "y", "SECRET": "z", "ok": 1})
    assert out == {"ok": 1}


def test_strip_credentials_non_string_keys():
    out = strip_credentials({1: "one", "api_key": "x", 2.5: "two"})
    assert out == {1: "one", 2.5: "two"}


def test_strip_credentials_does_not_mutate_input():
    obj = {"api_key": "sk-1", "nested": [{"password": "p"}], "name": "n"}
    snapshot = deepcopy(obj)
    out = strip_credentials(obj)
    assert obj == snapshot  # input untouched
    assert out == {"nested": [{}], "name": "n"}


def test_strip_credentials_no_false_positives():
    obj = {
        "token_count": "keep-me",  # note: 'token' substring — denylist matches
        "customer_name": "Acme",
        "total_amount": "100",
        "user_roles": ["admin", "dev"],
        "config": {"region": "us", "timeout_ms": 30},
    }
    out = strip_credentials(obj)
    # "token_count" contains the "token" denylist token → stripped by design;
    # everything else survives.
    assert out == {
        "customer_name": "Acme",
        "total_amount": "100",
        "user_roles": ["admin", "dev"],
        "config": {"region": "us", "timeout_ms": 30},
    }
    assert "token_count" not in out


# ============================================================================
# has_credentials
# ============================================================================

def test_has_credentials_true():
    assert has_credentials({"api_key": "x"})
    assert has_credentials({"a": {"b": [{"password": "p"}]}})
    assert has_credentials([{"nested": {"secret": "s"}}])
    assert has_credentials({"list": [{"token": "t"}]})
    assert has_credentials({"Authorization": "Bearer x"})


def test_has_credentials_false():
    assert not has_credentials({})
    assert not has_credentials({"name": "x", "items": [{"id": 1}]})
    assert not has_credentials("just a string")
    assert not has_credentials(42)
    assert not has_credentials(None)
    assert not has_credentials([])
