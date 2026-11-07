"""Official REST readbacks expose published_at, not request-only published.

Only the Shopify HTTP leaf is doubled.  The real registered action, GenericAgent
consumer, Article material mapper, Oracle and durable claim remain in the path.
"""
import copy
import uuid

import pytest

from tests.test_oracle_shopify_article_create import (
    FakeShopifyTransport,
    _add_store,
    _agent,
    _article_args,
    _call,
    _claim_row,
    _context,
    _install_transport,
    env,
)

_MISSING = object()
_PAST = "2020-01-01T00:00:00Z"
_PAST_OFFSET = "2020-01-01T00:00:00-05:00"
_FUTURE = "2999-01-01T00:00:00Z"


def _run_case(
    env,
    monkeypatch,
    *,
    published,
    published_at=_MISSING,
    published_marker=_MISSING,
):
    _add_store(env)
    transport = FakeShopifyTransport()

    def rest_readback(blog_id, article_id, article):
        item = copy.deepcopy(article)
        item.pop("published", None)
        if published_at is _MISSING:
            item.pop("published_at", None)
        else:
            item["published_at"] = published_at
        if published_marker is not _MISSING:
            item["published"] = published_marker
        return item

    transport.read_override = rest_readback
    _install_transport(monkeypatch, transport)
    operation_id = f"rest-shape-{uuid.uuid4().hex}"
    result = _call(
        _agent(),
        _article_args(operation_id, published=published),
        _context(operation_id),
    )
    return result, transport, operation_id


def _assert_unverified(result, transport, operation_id, env):
    assert len(transport.posts) == 1, result
    assert result.get("success") is not True, result
    assert result.get("oracle_verified") is not True, result
    assert _claim_row(env, operation_id)[0] == "uncertain_effect", result


@pytest.mark.parametrize(
    "published,observed_at",
    [(True, _PAST), (True, _PAST_OFFSET), (False, None)],
)
def test_official_rest_publication_readback_is_usable(
    env, monkeypatch, published, observed_at
):
    result, transport, operation_id = _run_case(
        env, monkeypatch, published=published, published_at=observed_at
    )
    assert len(transport.posts) == 1, result
    assert result.get("oracle_verified") is True, result
    assert result.get("status") == "success", result
    assert _claim_row(env, operation_id)[0] == "succeeded", result


@pytest.mark.parametrize("published", [True, False])
def test_future_published_at_is_scheduled_not_certified(
    env, monkeypatch, published
):
    result, transport, operation_id = _run_case(
        env, monkeypatch, published=published, published_at=_FUTURE
    )
    _assert_unverified(result, transport, operation_id, env)
    assert result["verification"]["mismatches"] == ["published"], result


@pytest.mark.parametrize(
    "observed_at",
    [
        _MISSING,
        "",
        "not-a-date",
        "2020-01-01",
        "2020-01-01T00:00:00",
    ],
)
def test_missing_malformed_or_naive_published_at_stays_unknown(
    env, monkeypatch, observed_at
):
    result, transport, operation_id = _run_case(
        env, monkeypatch, published=True, published_at=observed_at
    )
    _assert_unverified(result, transport, operation_id, env)
    assert result["verification"]["mismatches"] == ["published"], result


@pytest.mark.parametrize(
    "published,observed_at,marker",
    [
        (True, None, True),
        (False, _PAST, False),
        (True, _FUTURE, True),
    ],
)
def test_contradictory_published_and_published_at_is_unknown(
    env, monkeypatch, published, observed_at, marker
):
    result, transport, operation_id = _run_case(
        env,
        monkeypatch,
        published=published,
        published_at=observed_at,
        published_marker=marker,
    )
    _assert_unverified(result, transport, operation_id, env)
    assert result["verification"]["mismatches"] == ["published"], result


def test_requested_published_but_null_readback_is_draft(
    env, monkeypatch
):
    result, transport, operation_id = _run_case(
        env, monkeypatch, published=True, published_at=None
    )
    _assert_unverified(result, transport, operation_id, env)
    assert result["verification"]["mismatches"] == ["published"], result


def test_requested_draft_but_published_readback_is_unexpected(
    env, monkeypatch
):
    result, transport, operation_id = _run_case(
        env, monkeypatch, published=False, published_at=_PAST
    )
    _assert_unverified(result, transport, operation_id, env)
    assert result["verification"]["mismatches"] == ["published"], result


def test_published_only_readback_is_not_official_shape(
    env, monkeypatch
):
    result, transport, operation_id = _run_case(
        env,
        monkeypatch,
        published=True,
        published_at=_MISSING,
        published_marker=True,
    )
    _assert_unverified(result, transport, operation_id, env)
    assert result["verification"]["mismatches"] == ["published"], result


@pytest.mark.parametrize(
    "published,observed_at",
    [(True, _PAST), (False, None)],
)
def test_consistent_legacy_published_compatibility_is_justified(
    env, monkeypatch, published, observed_at
):
    result, transport, operation_id = _run_case(
        env,
        monkeypatch,
        published=published,
        published_at=observed_at,
        published_marker=published,
    )
    assert len(transport.posts) == 1, result
    assert result.get("oracle_verified") is True, result
    assert _claim_row(env, operation_id)[0] == "succeeded", result


def test_official_rest_shape_replays_without_second_create(env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"rest-replay-{uuid.uuid4().hex}"
    args = _article_args(operation_id, published=True)
    context = _context(operation_id)

    first = _call(_agent(), args, context)
    assert first.get("oracle_verified") is True, first
    assert len(transport.posts) == 1

    second = _call(_agent(), dict(args), dict(context))
    assert len(transport.posts) == 1, "replay created a second article"
    assert second.get("oracle_verified") is True, second
    assert second.get("action_result") == "already_applied", second
    assert _claim_row(env, operation_id)[0] == "succeeded", second
