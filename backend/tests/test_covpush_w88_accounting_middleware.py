# -*- coding: utf-8 -*-
"""Coverage wave 88 — accounting/ + middleware/ packages.

Strategy (extend, don't duplicate):
1. REUSE: re-register the prior accounting/middleware coverage-wave test
   modules' test classes/functions under tagged aliases so a single-file
   coverage run of this file carries the packages' accumulated coverage.
   Their internal helpers/fixtures keep resolving in their own module
   globals; module-level fixtures are copied under their original names.
2. NEW GAP TESTS written here for the modules the prior waves left open:
   - middleware/security.py (0% — full coverage: rate limit, input
     validation, security headers, CSRF, utilities)
   - middleware/governance_middleware.py (remaining branch gaps)
   - accounting/export_service.py (_sanitize_csv_cell CSV-injection
     branches + AccountExporter paths)
   - accounting/document_processor.py (optional-import fallback branch)

No network, no LLM, mock Session objects throughout.
"""
import importlib
import sys
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ============================================================================
# Part 1 — reuse prior coverage waves (aliased re-registration)
# ============================================================================
# Each prior wave module is imported and its collected tests are re-exposed
# here under ``<name>__<tag>`` aliases so running THIS file alone reproduces
# (and extends) the accumulated package coverage. Fixtures are copied under
# their original names (first definition wins).

_REUSE_MODULES = [
    ('tests.test_covpush_w72a_accounting', 'w72a'),
    ('tests.test_covpush_w74a_accounting2', 'w74a'),
    ('tests.test_covpush_w75a_accounting3', 'w75a'),
    ('tests.test_covpush_w74b_accounting_admin', 'w74b'),
    ('tests.test_covpush_w109_accounting_docs', 'w109'),
    ('tests.test_covpush_w45_governance_middleware', 'w45'),
    ('tests.test_covpush_w73a_middleware', 'w73a',
     # limit to middleware-relevant modules? no — reuse everything
     ),
]

for _entry in _REUSE_MODULES:
    _path, _tag = _entry[0], _entry[1]
    _mod = importlib.import_module(_path)
    for _name in dir(_mod):
        if _name.startswith('_'):
            continue
        _obj = getattr(_mod, _name)
        # Fixture detection across pytest generations: legacy exposes
        # _pytestfixturefunction, newer wraps in __pytest_wrapped__, and the
        # newest exposes FixtureFunctionDefinition directly. Without all
        # three, every cross-module fixture (memory_db, mw, …) silently
        # disappears and reused test classes error at setup.
        _is_fixture = (
            hasattr(_obj, '_pytestfixturefunction')
            or hasattr(getattr(_obj, '__pytest_wrapped__', None), '_pytestfixturefunction')
            or type(_obj).__name__ in ('FixtureFunctionDefinition', 'pytest_fixture')
        )
        if _is_fixture:
            # module-level fixture: register under original name, first wins
            globals().setdefault(_name, _obj)
        elif _name.startswith(('test_', 'Test')):
            globals()['%s__%s' % (_name, _tag)] = _obj
        # everything else stays in the original module's namespace


# ============================================================================
# Part 2a — accounting.export_service: CSV-injection sanitizer branches
# ============================================================================
from accounting.export_service import (  # noqa: E402
    AccountExporter,
    _sanitize_csv_cell,
)
from accounting.models import AccountType, EntryType  # noqa: E402


class TestSanitizeCsvCellW88:
    def test_non_string_passthrough(self):
        assert _sanitize_csv_cell(42) == 42
        assert _sanitize_csv_cell(3.5) == 3.5
        assert _sanitize_csv_cell(None) is None

    def test_clean_strings_untouched(self):
        assert _sanitize_csv_cell('Coffee vendor') == 'Coffee vendor'
        assert _sanitize_csv_cell('') == ''
        assert _sanitize_csv_cell('ACC-100') == 'ACC-100'  # '-' not leading

    def test_formula_prefixes_neutralized(self):
        for payload in ('=1+1', '+SUM(A1)', '-2', '@cmd'):
            assert _sanitize_csv_cell(payload) == "'" + payload
        # leading tab/CR alone is stripped by lstrip() (and by spreadsheet
        # importers), so the cell is NOT quoted — but a formula hidden
        # behind the tab IS neutralized
        assert _sanitize_csv_cell('\ttab') == '\ttab'
        assert _sanitize_csv_cell('\t=cmd') == "'\t=cmd"

    def test_leading_whitespace_before_prefix_neutralized(self):
        # spreadsheet apps trim leading whitespace on import, re-exposing
        # the formula — so '  =cmd' must be prefixed too
        assert _sanitize_csv_cell('  =cmd') == "'  =cmd"
        assert _sanitize_csv_cell('\n=cmd') == "'\n=cmd"
        # whitespace-only / non-prefix stays clean
        assert _sanitize_csv_cell('  plain') == '  plain'


class TestAccountExporterW88:
    def _ledger_db(self, entries):
        db = MagicMock()
        q = MagicMock()
        q.join.return_value = q
        q.filter.return_value = q
        q.order_by.return_value.all.return_value = entries
        db.query.return_value = q
        return db

    def _balance_db(self, accounts):
        db = MagicMock()
        q_accounts = MagicMock()
        q_accounts.filter.return_value.all.return_value = accounts
        q_sum = MagicMock()
        q_sum.filter.return_value.scalar.return_value = None  # sums -> 0.0
        db.query.side_effect = [q_accounts, q_sum, q_sum]
        return db

    def test_export_general_ledger_csv(self):
        acc = MagicMock()
        acc.code = '=SUM(A1)'          # malicious account code
        acc.name = 'Hacked @Vendor'
        acc.standards_mapping = {'gaap': '+1000', 'ifrs': 'IFRS-1'}
        tx = MagicMock()
        tx.id = 'tx-1'
        tx.transaction_date.strftime.return_value = '2026-01-02'
        tx.description = 'desc'
        entry = MagicMock()
        entry.account = acc
        entry.transaction = tx
        entry.type = EntryType.DEBIT
        entry.amount = 25.0
        entry.description = None
        entry.currency = 'USD'

        db = self._ledger_db([entry])
        out = AccountExporter(db).export_general_ledger_csv('ws-1')
        assert 'Date' in out
        assert "'=SUM(A1)" in out          # sanitizer applied
        assert 'Hacked @Vendor' in out     # '@' not leading -> untouched
        assert "'+1000" in out
        # debit column populated for DEBIT entry
        assert '25.0' in out

    def test_export_trial_balance_json(self):
        acc = MagicMock()
        acc.code = 'ACC-1'
        acc.name = 'Cash'
        acc.type = AccountType.ASSET
        acc.standards_mapping = {'gaap': 'g'}
        db = self._balance_db([acc])
        report = AccountExporter(db).export_trial_balance_json('ws-1')
        assert report['workspace_id'] == 'ws-1'
        assert report['standard'].startswith('Multi-Standard')
        assert report['accounts'][0]['code'] == 'ACC-1'
        assert report['accounts'][0]['debits'] == 0.0   # scalar() None -> 0.0
        assert report['accounts'][0]['credits'] == 0.0
        assert report['accounts'][0]['net_balance'] == 0.0


# ============================================================================
# Part 2b — accounting.document_processor: optional-import fallback
# ============================================================================
import accounting.document_processor as dp_mod  # noqa: E402


class TestDocumentProcessorImportFallbackW88:
    def test_ai_enhanced_import_failure_degrades(self, monkeypatch):
        # Setting a sys.modules entry to None makes `import X` raise ImportError
        monkeypatch.setitem(sys.modules, 'integrations.ai_enhanced_service', None)
        try:
            reloaded = importlib.reload(dp_mod)
            assert reloaded.AIModelType is None
            assert reloaded.AIRequest is None
            assert reloaded.AIServiceType is None
            assert reloaded.AITaskType is None
            assert reloaded.ai_enhanced_service is None
        finally:
            importlib.reload(dp_mod)  # restore real bindings


# ============================================================================
# Part 2c — middleware.governance_middleware remaining branches
# ============================================================================
import middleware.governance_middleware as gov_mod  # noqa: E402
from middleware.governance_middleware import (  # noqa: E402
    Gatekeeper,
    governance_middleware as gatekeeper_singleton,
    mask_response_fields,
)


class TestMaskResponseFieldsW88:
    def test_empty_masked_set_returns_input_unchanged(self):
        data = {'access_token': 'x'}
        assert mask_response_fields(data, set()) is data

    def test_nested_and_case_insensitive_masking(self):
        data = {
            'ACCESS_TOKEN': 'secret',
            'refresh-token': 's2',
            'nested': [{'accessToken': 's3', 'ok': 1}],
            'plain': 'keep',
        }
        out = mask_response_fields(data, {'access_token', 'refresh_token'})
        assert out['ACCESS_TOKEN'] == '***'
        assert out['refresh-token'] == '***'
        assert out['nested'][0]['accessToken'] == '***'
        assert out['nested'][0]['ok'] == 1
        assert out['plain'] == 'keep'
        assert mask_response_fields([1, 'a'], {'x'}) == [1, 'a']


class TestGatekeeperW88:
    @pytest.fixture()
    def gk(self):
        g = Gatekeeper()
        g._config.clear()
        return g

    async def test_rate_limit_zero_blocks_all(self, gk):
        gk.configure('slack', {'rate_limit': 0})
        res = await gk.check_action_risk('Slack', 'post_message')
        assert res['allowed'] is False
        assert 'Rate limit exceeded' in res['reason']

    async def test_rate_limited_by_limiter(self, gk):
        gk.configure('github', {'rate_limit': 5})
        with patch.object(
            gov_mod.rate_limiter, 'is_rate_limited',
            AsyncMock(return_value=(True, 0)),
        ):
            res = await gk.check_action_risk('github', 'create_issue')
        assert res['allowed'] is False
        assert res['reason'].startswith('Rate limit exceeded for github')

    async def test_required_scopes_missing_fails_closed(self, gk):
        gk.configure('stripe', {'required_scopes': {'write:charge'}})
        res = await gk.check_action_risk('stripe', 'create_charge', scopes=set())
        assert res['allowed'] is False
        assert 'Missing required scopes' in res['reason']
        assert 'write:charge' in res['reason']

    async def test_required_scopes_satisfied_allows(self, gk):
        gk.configure('stripe', {'required_scopes': {'a', 'b'}})
        res = await gk.check_action_risk('stripe', 'create_charge',
                                         scopes={'a', 'b'})
        assert res == {'allowed': True}

    async def test_taint_tracker_blocks_outbound(self, gk):
        taint = MagicMock()
        taint.check_outbound.return_value = {
            'allowed': False, 'reason': 'PII observed',
            'violation_type': 'VT_PROVENANCE', 'max_observed': 'restricted',
        }
        res = await gk.check_action_risk(
            'slack', 'post_message', taint_tracker=taint,
            agent_id='a1', workspace_id='ws1')
        assert res['allowed'] is False
        assert res['reason'] == 'PII observed'
        assert res['violation_type'] == 'VT_PROVENANCE'
        assert res['max_observed'] == 'restricted'

    async def test_taint_tracker_exception_tolerated(self, gk):
        # W88 fail-closed policy: an unavailable taint tracker BLOCKS the
        # action (previously tolerated open — an exception in the sensitivity
        # check would let restricted data flow). The block is a structured
        # denial naming the tracker outage, not an exception.
        taint = MagicMock()
        taint.check_outbound.side_effect = RuntimeError('boom')
        res = await gk.check_action_risk('slack', 'post_message',
                                         taint_tracker=taint)
        assert res['allowed'] is False
        assert 'Data-sensitivity check unavailable' in res['reason']

    async def test_hitl_intervention_created_pauses(self, gk):
        gk.configure('jira', {'require_approval_for': {'delete_issue'}})
        with patch.object(
            gov_mod.intervention_service, 'request_intervention',
            AsyncMock(return_value={'action_id': 'iv-9'}),
        ):
            res = await gk.check_action_risk('jira', 'delete_issue',
                                             agent_id='a', user_id='u')
        assert res['allowed'] is False
        assert res['paused'] is True
        assert res['intervention_id'] == 'iv-9'
        assert 'manual review' in res['reason']

    async def test_hitl_unavailable_fails_closed(self, gk):
        gk.configure('jira', {'require_approval_for': {'delete_issue'}})
        with patch.object(
            gov_mod.intervention_service, 'request_intervention',
            AsyncMock(side_effect=RuntimeError('db down')),
        ):
            res = await gk.check_action_risk('jira', 'delete_issue')
        assert res['allowed'] is False
        assert 'HITL unavailable' in res['reason']

    async def test_hitl_no_action_id_fails_closed(self, gk):
        gk.configure('jira', {'require_approval_for': {'delete_issue'}})
        with patch.object(
            gov_mod.intervention_service, 'request_intervention',
            AsyncMock(return_value={}),
        ):
            res = await gk.check_action_risk('jira', 'delete_issue')
        assert res['allowed'] is False
        assert 'HITL unavailable' in res['reason']

    def test_config_lookup_case_and_whitespace_normalized(self, gk):
        # pre-existing key with odd casing must still be found (never bypassed)
        gk._config['  Jira '] = {'rate_limit': 7}
        assert gk._get('jira', 'rate_limit', None) == 7

    def test_default_tables(self, gk):
        assert 'post_message' in gk._get('slack', 'mutations', set())
        assert 'create_issue' in gk._get('github', 'mutations', set())
        assert gk._get('unknown-svc', 'mutations', set()) == set()
        assert 'access_token' in gk._get('gmail', 'masked_fields', set())
        assert gk._get('unknown-svc', 'masked_fields', set()) == set()
        assert gk._get('slack', 'require_approval_for', set()) == set()
        assert gk._get('slack', 'anything_else', 'dflt') == 'dflt'

    def test_mask_response_uses_provider_defaults(self, gk):
        out = gk.mask_response('gmail', {'access_token': 't', 'data': 1})
        assert out == {'access_token': '***', 'data': 1}
        # configured override wins
        gk.configure('gmail', {'masked_fields': {'data'}})
        out2 = gk.mask_response('gmail', {'access_token': 't', 'data': 1})
        assert out2 == {'access_token': 't', 'data': '***'}

    def test_singleton_exists(self):
        assert isinstance(gatekeeper_singleton, Gatekeeper)


# ============================================================================
# Part 2d — middleware.security (full coverage)
# ============================================================================
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import middleware.security as sec_mod  # noqa: E402
from middleware.security import (  # noqa: E402
    CSRFProtectionMiddleware,
    InputValidationMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    generate_api_key,
    hash_password,
    sanitize_input,
    setup_security_middleware,
    validate_email,
)


def _app_with(mw_cls, **kw):
    app = FastAPI()

    @app.get('/ping')
    async def ping():
        return {'ok': True}

    @app.post('/ping')
    async def ping_post():
        return {'ok': True}

    app.add_middleware(mw_cls, **kw) if kw else app.add_middleware(mw_cls)
    return app


class TestRateLimitMiddlewareW88:
    def test_allows_within_limit_and_sets_headers(self):
        app = _app_with(RateLimitMiddleware, requests_per_minute=60,
                        burst_size=10)
        client = TestClient(app)
        r = client.get('/ping')
        assert r.status_code == 200
        assert r.headers['X-RateLimit-Limit'] == '60'
        assert 'X-RateLimit-Remaining' in r.headers
        assert 'X-RateLimit-Reset' in r.headers

    def test_blocks_after_limit_with_429(self):
        app = _app_with(RateLimitMiddleware, requests_per_minute=2,
                        burst_size=1)
        client = TestClient(app)
        # burst token (1) then count up to RPM (2): third request is capped
        assert client.get('/ping').status_code == 200
        assert client.get('/ping').status_code == 200
        r = client.get('/ping')
        assert r.status_code == 429
        body = r.json()
        assert body['error']['type'] == 'rate_limit_exceeded'
        assert r.headers['Retry-After'] == '60'
        assert r.headers['X-RateLimit-Remaining'] == '0'

    def test_window_reset_restores_budget(self):
        mw = RateLimitMiddleware(app=MagicMock(), requests_per_minute=1,
                                 burst_size=0)
        mw.clients['1.2.3.4'] = {
            'count': 5, 'reset_time': time.time() - 1, 'burst_tokens': 0,
        }
        assert mw._is_rate_limited('1.2.3.4') is False  # window reset path
        assert mw.clients['1.2.3.4']['count'] == 1

    def test_burst_tokens_then_rpm_cap(self):
        mw = RateLimitMiddleware(app=MagicMock(), requests_per_minute=2,
                                 burst_size=1)
        assert mw._is_rate_limited('c') is False   # burst token
        assert mw._is_rate_limited('c') is False   # count 2/2
        assert mw._is_rate_limited('c') is True    # capped

    def test_stale_entry_eviction(self):
        mw = RateLimitMiddleware(app=MagicMock())
        mw.clients = {
            f'ip-{i}': {'count': 1, 'reset_time': time.time() - 100,
                        'burst_tokens': 0}
            for i in range(10001)
        }
        mw.clients['fresh'] = {'count': 0,
                               'reset_time': time.time() + 60,
                               'burst_tokens': 1}
        assert mw._is_rate_limited('fresh') is False
        assert 'ip-0' not in mw.clients  # evicted
        assert len(mw.clients) < 100

    def test_get_client_ip_variants(self, monkeypatch):
        mw = RateLimitMiddleware(app=MagicMock())
        req = MagicMock()
        req.headers = {}
        req.client = None
        assert mw._get_client_ip(req) == 'unknown'
        req.client = MagicMock()
        req.client.host = '9.9.9.9'
        req.headers = {'x-forwarded-for': '1.1.1.1, 2.2.2.2'}
        assert mw._get_client_ip(req) == '9.9.9.9'  # untrusted by default
        monkeypatch.setenv('TRUST_X_FORWARDED_FOR', '1')
        assert mw._get_client_ip(req) == '2.2.2.2'  # last entry
        req.headers = {}
        assert mw._get_client_ip(req) == '9.9.9.9'


class TestInputValidationMiddlewareW88:
    def test_clean_get_and_post_pass(self):
        app = _app_with(InputValidationMiddleware)
        client = TestClient(app)
        assert client.get('/ping?q=ok').status_code == 200
        r = client.post('/ping', json={'a': 1})
        assert r.status_code == 200

    def test_malicious_query_param_blocked(self):
        app = _app_with(InputValidationMiddleware)
        client = TestClient(app)
        r = client.get('/ping?q=union select * from users')
        assert r.status_code == 400
        assert r.json()['error']['type'] == 'invalid_input'

    def test_oversized_query_param_blocked(self):
        app = _app_with(InputValidationMiddleware)
        client = TestClient(app)
        r = client.get('/ping?q=' + 'a' * 1001)
        assert r.status_code == 400

    def test_malicious_post_body_blocked(self):
        app = _app_with(InputValidationMiddleware)
        client = TestClient(app)
        r = client.post('/ping', content=b'<script>alert(1)</script>')
        assert r.status_code == 400
        assert 'request content' in r.json()['error']['message']

    def test_body_read_failure_is_tolerated(self):
        app = _app_with(InputValidationMiddleware)
        client = TestClient(app)
        orig = InputValidationMiddleware.dispatch

        async def fake_dispatch(self, request, call_next):
            # simulate request.body() raising
            import starlette.datastructures as sd
            real_body = request.body

            async def boom():
                raise RuntimeError('stream consumed')
            request.body = boom
            try:
                return await orig.__wrapped__(self, request, call_next) \
                    if hasattr(orig, '__wrapped__') else await orig(
                        self, request, call_next)
            finally:
                request.body = real_body

        with patch.object(InputValidationMiddleware, 'dispatch', fake_dispatch):
            r = client.post('/ping', json={'a': 1})
        assert r.status_code == 200

    def test_validate_content_size_limit(self):
        mw = InputValidationMiddleware(app=MagicMock())
        assert mw._validate_content('x' * (10 * 1024 * 1024 + 1)) is False
        assert mw._validate_content('fine') is True

    def test_all_malicious_patterns_detected(self):
        mw = InputValidationMiddleware(app=MagicMock())
        payloads = [
            '<script>a</script>', 'javascript:alert(1)', 'onclick =x',
            'union select 1', 'drop table users', 'exec(code)',
            'eval(code)', 'system(cmd)',
        ]
        for p in payloads:
            assert mw._contains_malicious_content(p) is True, p
        assert mw._contains_malicious_content('hello world') is False


class TestSecurityHeadersMiddlewareW88:
    def test_headers_added(self):
        app = _app_with(SecurityHeadersMiddleware)
        client = TestClient(app)
        r = client.get('/ping')
        assert r.headers['X-Content-Type-Options'] == 'nosniff'
        assert r.headers['X-Frame-Options'] == 'DENY'
        assert 'Strict-Transport-Security' in r.headers
        assert 'unsafe-eval' not in r.headers['Content-Security-Policy']
        assert 'Permissions-Policy' in r.headers


class TestCSRFProtectionMiddlewareW88:
    def _client(self):
        app = _app_with(CSRFProtectionMiddleware)
        client = TestClient(app)
        client.get('/ping')  # force middleware stack to be built
        stack = client.app.middleware_stack
        mw = None
        while stack is not None:
            if isinstance(stack, CSRFProtectionMiddleware):
                mw = stack
                break
            stack = getattr(stack, 'app', None)
        assert mw is not None
        return client, mw

    def test_get_skips_check(self):
        client, _ = self._client()
        assert client.get('/ping').status_code == 200

    def test_post_without_token_403(self):
        client, _ = self._client()
        r = client.post('/ping', json={'a': 1})
        assert r.status_code == 403
        assert r.json()['error']['type'] == 'csrf_token_invalid'

    def test_post_with_bearer_exempt(self):
        client, _ = self._client()
        r = client.post('/ping', json={'a': 1},
                        headers={'Authorization': 'Bearer tok'})
        assert r.status_code == 200

    def test_valid_token_passes_and_expired_fails(self):
        client, mw = self._client()
        token = mw.generate_csrf_token('sess-1')
        assert mw.generate_csrf_token('s2') != token
        assert mw._validate_csrf_token(token) is True
        r = client.post('/ping', headers={'X-CSRF-Token': token})
        assert r.status_code == 200
        # unknown token
        assert mw._validate_csrf_token('nope') is False
        # expired token is deleted and rejected
        mw.csrf_tokens[token]['expiry'] = time.time() - 1
        assert mw._validate_csrf_token(token) is False
        assert token not in mw.csrf_tokens
        r2 = client.post('/ping', headers={'X-CSRF-Token': token})
        assert r2.status_code == 403


class TestSecuritySetupAndUtilsW88:
    def test_setup_security_middleware_adds_all(self):
        app = FastAPI()
        setup_security_middleware(app)
        client = TestClient(app)
        r = client.get('/ping') if False else None  # no routes needed
        added = [m.cls for m in app.user_middleware]
        assert SecurityHeadersMiddleware in added
        assert CSRFProtectionMiddleware in added
        assert InputValidationMiddleware in added
        assert RateLimitMiddleware in added
        # end-to-end: full stack lets a Bearer GET through with headers
        @app.get('/ping')
        async def ping():
            return {'ok': True}
        resp = client.get('/ping')
        assert resp.status_code == 200
        assert resp.headers['X-Frame-Options'] == 'DENY'

    def test_hash_password(self):
        h = hash_password('secret')
        assert h and h != 'secret'

    def test_generate_api_key_unique(self):
        assert generate_api_key() != generate_api_key()

    def test_validate_email(self):
        assert validate_email('a.b+tag@example.co') is True
        assert validate_email('bad@@example') is False
        assert validate_email('nope') is False

    def test_sanitize_input(self):
        assert sanitize_input('<b>hi</b>"\'') == 'hi'
        assert sanitize_input('  spaced  ') == 'spaced'
