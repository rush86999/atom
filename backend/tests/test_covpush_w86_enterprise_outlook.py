# -*- coding: utf-8 -*-
"""Coverage wave 86 — integrations.atom_enterprise_security_service,
integrations.outlook_service, integrations.atom_enterprise_unified_service.

No network, no LLM spend: aiohttp sessions, circuit breakers, rate limiters
and DB sessions are all mocked at module boundaries.
"""
import base64
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import integrations.atom_enterprise_security_service as sec_mod
import integrations.atom_enterprise_unified_service as uni_mod
import integrations.outlook_service as out_mod
from integrations.atom_enterprise_security_service import (
    AuditEventType,
    AtomEnterpriseSecurityService,
    ComplianceStandard,
    SecurityLevel,
    ThreatDetection,
    ThreatType,
)
from integrations.atom_enterprise_unified_service import (
    AtomEnterpriseUnifiedService,
    ComplianceAutomation,
    ComplianceWorkflowType,
    EnterpriseServiceType,
    EnterpriseWorkflow,
    SecurityWorkflowAction,
    WorkflowSecurityLevel,
    _coerce_compliance_standard,
)
from integrations.outlook_service import OutlookService


# ============================================================================
# Shared fixtures — keep circuit breaker / rate limiter green everywhere
# ============================================================================

@pytest.fixture(autouse=True)
def green_gates():
    with patch.object(sec_mod, 'circuit_breaker') as cb, \
         patch.object(sec_mod, 'rate_limiter') as rl, \
         patch.object(uni_mod, 'circuit_breaker') as ucb, \
         patch.object(uni_mod, 'rate_limiter') as url:
        for m in (cb, ucb):
            m.is_enabled = AsyncMock(return_value=True)
        for m in (rl, url):
            m.is_rate_limited = AsyncMock(return_value=(False, 100))
        yield


@pytest.fixture()
def sec():
    return AtomEnterpriseSecurityService(tenant_id='t', config={
        'ai_service': None})


@pytest.fixture()
def sec_ai():
    return AtomEnterpriseSecurityService(tenant_id='t', config={
        'ai_service': MagicMock()})


def _policy_data(**over):
    data = {
        'name': 'p1',
        'description': 'd',
        'security_level': 'enterprise',
        'compliance_standards': ['gdpr', ComplianceStandard.SOC2],
        'rules': [],
        'enforcement_actions': ['block'],
    }
    data.update(over)
    return data


# ============================================================================
# Security service — initialize / policy creation
# ============================================================================

async def test_sec_initialize(sec):
    assert await sec.initialize() is True
    assert sec.monitoring_active is True
    assert sec.compliance_monitoring['gdpr']['enabled'] is True
    assert sec.threat_detection_config['ai_enabled'] is True
    assert sec.encryption_config['algorithm'] == 'AES-256-GCM'
    assert sec.security_policies['password_policy']['min_length'] == 12


async def test_sec_initialize_failure(sec):
    with patch.object(sec, '_initialize_encryption',
                      side_effect=RuntimeError('boom')):
        assert await sec.initialize() is False


def test_sec_init_defaults(sec):
    assert sec.security_config['session_timeout'] == 3600
    assert sec.cipher_suite is not None
    assert 'sql_injection' in sec.malicious_patterns
    assert sec.security_metrics['total_threats_detected'] == 0
    assert ComplianceStandard.GDPR in sec.security_config[
        'compliance_standards']


async def test_sec_create_policy_success(sec):
    sec.db = MagicMock()
    sec.db.store_security_policy = AsyncMock()
    sec.db.store_security_audit = AsyncMock()
    res = await sec.create_security_policy(_policy_data(), 'admin')
    assert res['ok'] is True
    assert res['policy']['security_level'] == SecurityLevel.ENTERPRISE
    sec.db.store_security_policy.assert_awaited_once()
    assert len(sec.audit_logs) >= 1


async def test_sec_create_policy_bad_standard(sec):
    res = await sec.create_security_policy(
        _policy_data(compliance_standards=['nope']), 'admin')
    assert res['ok'] is False and 'Invalid compliance standard' in res['error']


async def test_sec_create_policy_validation_failure(sec):
    with patch.object(sec, '_validate_security_policy',
                      AsyncMock(return_value={'valid': False,
                                              'errors': ['bad']})):
        res = await sec.create_security_policy(_policy_data(), 'admin')
    assert res['ok'] is False and 'validation failed' in res['error']


async def test_sec_create_policy_exception(sec):
    with patch.object(sec, '_validate_security_policy',
                      AsyncMock(side_effect=RuntimeError('x'))):
        res = await sec.create_security_policy(_policy_data(), 'admin')
    assert res['ok'] is False


async def test_sec_policy_rate_limited(sec):
    # HTTPException raised internally is swallowed by the broad except
    sec_mod.rate_limiter.is_rate_limited = AsyncMock(return_value=(True, 0))
    res = await sec.create_security_policy(_policy_data(), 'admin')
    assert res['ok'] is False


# ============================================================================
# Security service — threat detection & mitigation
# ============================================================================

async def test_sec_detect_threat_sql_injection(sec):
    res = await sec.detect_threat({
        'source_ip': '9.9.9.9', 'user_id': 'u1', 'session_id': 's1',
        'content': 'SELECT * FROM users; DROP TABLE x'})
    assert res is not None
    assert res.threat_type == ThreatType.SQL_INJECTION
    assert res.severity == 'high'
    assert res.mitigated is True  # high severity -> mitigation ran
    assert '9.9.9.9' in sec.blocked_ips
    assert sec.security_metrics['total_threats_detected'] == 1
    assert sec.security_metrics['threats_mitigated'] == 1


async def test_sec_detect_threat_xss(sec):
    res = await sec.detect_threat({'user_id': 'u', 'content':
                                    '<script>alert(1)</script>'})
    assert res.threat_type == ThreatType.XSS
    assert res.severity == 'medium'
    assert res.mitigated is False


async def test_sec_detect_threat_path_traversal(sec):
    res = await sec.detect_threat({'url': '/files/../../etc/passwd'})
    assert res.threat_type == ThreatType.AUTH_BYPASS


async def test_sec_detect_threat_benign(sec):
    assert await sec.detect_threat({'content': 'hello world'}) is None


async def test_sec_detect_threat_ai_branch(sec_ai):
    sec_ai._ai_threat_detection = AsyncMock(return_value=[
        {'type': 'phishing', 'severity': 'low', 'confidence': 0.8,
         'description': 'd'}])
    res = await sec_ai.detect_threat({'user_id': 'u', 'content': 'x'})
    assert res.threat_type == ThreatType.PHISHING


async def test_sec_detect_threat_error_returns_none(sec):
    sec._pattern_based_detection = AsyncMock(side_effect=RuntimeError('x'))
    assert await sec.detect_threat({'content': 'x'}) is None


def test_sec_matches_pattern_fields(sec):
    info = {'patterns': [r'javascript:']}
    assert sec._matches_pattern({'headers': 'x-javascript: 1'}, info) is True
    assert sec._matches_pattern({'user_input': 'safe'}, info) is False


async def test_sec_behavioral_anomaly_detection(sec):
    assert await sec._behavioral_anomaly_detection({'content': 'x'}) == []
    sec._detect_anomalies = MagicMock(return_value=[
        {'severity': 'low', 'confidence': 0.9, 'description': 'd',
         'indicators': ['i']}])
    threats = await sec._behavioral_anomaly_detection({'user_id': 'u'})
    assert threats[0]['type'] == ThreatType.ANOMALOUS_BEHAVIOR.value


async def test_sec_ai_threat_detection(sec_ai):
    with patch.object(sec_mod, 'AIRequest', MagicMock(), create=True), \
         patch.object(sec_mod, 'AITaskType', MagicMock(), create=True), \
         patch.object(sec_mod, 'AIModelType', MagicMock(), create=True), \
         patch.object(sec_mod, 'AIServiceType', MagicMock(), create=True):
        resp = MagicMock(ok=True, confidence=0.9, output_data='{}')
        sec_ai.ai_service.process_ai_request = AsyncMock(return_value=resp)
        sec_ai._parse_ai_threat_results = MagicMock(return_value=[
            {'type': 'malware', 'severity': 'low', 'confidence': 0.8,
             'description': 'd'}])
        threats = await sec_ai._ai_threat_detection({'content': 'x'})
        assert threats[0]['type'] == 'malware'

        # low confidence -> ignored
        resp2 = MagicMock(ok=True, confidence=0.3, output_data='{}')
        sec_ai.ai_service.process_ai_request = AsyncMock(return_value=resp2)
        assert await sec_ai._ai_threat_detection({'content': 'x'}) == []

    # service raising -> swallowed
    sec_ai.ai_service.process_ai_request = AsyncMock(
        side_effect=RuntimeError('x'))
    assert await sec_ai._ai_threat_detection({'content': 'x'}) == []

    # no service
    sec_ai.ai_service = None
    assert await sec_ai._ai_threat_detection({'content': 'x'}) == []


def _threat(threat_type=ThreatType.COMPROMISED_ACCOUNT, severity='high'):
    return ThreatDetection(
        detection_id='d1', threat_type=threat_type, severity=severity,
        confidence=0.9, source_ip='1.1.1.1', user_id='u1',
        session_id='sess1', timestamp=datetime.now(timezone.utc),
        description='d', indicators=['i'])


async def test_sec_mitigate_threat_compromised(sec):
    sec.active_sessions['sess1'] = {}
    await sec._mitigate_threat(_threat())
    assert 'sess1' not in sec.active_sessions
    assert '1.1.1.1' in sec.blocked_ips


async def test_sec_mitigate_threat_insider(sec):
    sec.user_security_contexts['u1'] = {}
    await sec._mitigate_threat(_threat(ThreatType.INSIDER_THREAT))
    assert sec.user_security_contexts['u1']['locked'] is True


async def test_sec_mitigate_threat_low_severity_noop(sec):
    t = _threat(severity='low')
    await sec._mitigate_threat(t)
    assert t.mitigated is True
    assert '1.1.1.1' not in sec.blocked_ips


async def test_sec_mitigate_threat_error(sec):
    sec._block_ip = AsyncMock(side_effect=RuntimeError('x'))
    await sec._mitigate_threat(_threat())  # logged, not raised


# ============================================================================
# Security service — audit / compliance
# ============================================================================

def _audit_data(**over):
    data = {
        'event_type': 'user_login', 'user_id': 'u1', 'resource': 'r',
        'action': 'login', 'result': 'success', 'ip_address': '2.2.2.2',
        'metadata': {},
    }
    data.update(over)
    return data


async def test_sec_audit_event_success(sec):
    sec.db = MagicMock()
    sec.db.store_security_audit = AsyncMock()
    audit = await sec.audit_event(_audit_data())
    assert audit.event_type == AuditEventType.USER_LOGIN
    assert sec.security_metrics['audit_events_logged'] == 1


async def test_sec_audit_event_unknown_type_fallback(sec):
    audit = await sec.audit_event(_audit_data(event_type='zzz'))
    assert audit.event_type == AuditEventType.CONFIG_CHANGED


async def test_sec_audit_event_missing_fields(sec):
    assert await sec.audit_event({'event_type': 'user_login'}) is None


async def test_sec_audit_event_error(sec):
    sec.db = MagicMock()
    sec.db.store_security_audit = AsyncMock(side_effect=RuntimeError('x'))
    assert await sec.audit_event(_audit_data()) is None


async def test_sec_check_compliance(sec_ai):
    report = await sec_ai.check_compliance(ComplianceStandard.GDPR, 'monthly')
    assert report.standard == ComplianceStandard.GDPR
    assert report.report_id.startswith('compliance_gdpr')
    assert report.overall_score == 100.0
    assert report.findings == []


async def test_sec_check_compliance_error(sec):
    sec._get_compliance_data = AsyncMock(side_effect=RuntimeError('x'))
    assert await sec.check_compliance(ComplianceStandard.GDPR) is None


async def test_sec_ai_compliance_analysis(sec_ai):
    with patch.object(sec_mod, 'AIRequest', MagicMock(), create=True), \
         patch.object(sec_mod, 'AITaskType', MagicMock(), create=True), \
         patch.object(sec_mod, 'AIModelType', MagicMock(), create=True), \
         patch.object(sec_mod, 'AIServiceType', MagicMock(), create=True):
        resp = MagicMock(ok=True, output_data='{}')
        sec_ai.ai_service.process_ai_request = AsyncMock(return_value=resp)
        sec_ai._parse_ai_compliance_results = MagicMock(
            return_value={'findings': [], 'recommendations': ['r'],
                          'score': 90.0})
        out = await sec_ai._ai_compliance_analysis(ComplianceStandard.SOC2, {})
        assert out['score'] == 90.0

        resp2 = MagicMock(ok=False)
        sec_ai.ai_service.process_ai_request = AsyncMock(return_value=resp2)
        out = await sec_ai._ai_compliance_analysis(ComplianceStandard.SOC2, {})
        assert out['score'] == 0.0

        sec_ai.ai_service.process_ai_request = AsyncMock(
            side_effect=RuntimeError('x'))
        out = await sec_ai._ai_compliance_analysis(ComplianceStandard.SOC2, {})
        assert out['findings'] == []

    sec_ai.ai_service = None
    out = await sec_ai._ai_compliance_analysis(ComplianceStandard.SOC2, {})
    assert out['score'] == 0.0


def test_sec_compliance_score_deductions(sec):
    findings = [{'severity': s} for s in ('critical', 'high', 'medium', 'low')]
    assert sec._calculate_compliance_score({'findings': findings}) == 50.0
    # clamped at zero
    many = [{'severity': 'critical'}] * 6
    assert sec._calculate_compliance_score({'findings': many}) == 0.0
    assert sec._calculate_compliance_score(
        {'findings': [{'severity': 'medium'}]}) == 90.0
    assert sec._calculate_compliance_score({}) == 100.0
    # unknown severity -> no deduction
    assert sec._calculate_compliance_score(
        {'findings': [{'severity': 'weird'}]}) == 100.0
    # malformed findings -> exception branch
    assert sec._calculate_compliance_score(
        {'findings': [None]}) in (100.0, 0.0)


def test_sec_compliance_requirements(sec):
    assert len(sec._get_compliance_requirements(
        ComplianceStandard.GDPR)) == 3
    assert sec._get_compliance_requirements(
        ComplianceStandard.PCI_DSS) == []


async def test_sec_check_compliance_for_event(sec):
    from integrations.atom_enterprise_security_service import SecurityAudit
    audit = SecurityAudit(
        audit_id='a', event_type=AuditEventType.DATA_ACCESS,
        user_id='u', resource='r', action='data_access', result='ok',
        ip_address='ip', user_agent='ua',
        timestamp=datetime.now(timezone.utc), metadata={})
    issues = await sec._check_compliance_for_event(audit)
    assert issues[0]['standard'] == 'SOC2'

    audit.action = 'data_export'
    issues = await sec._check_compliance_for_event(audit)
    assert issues[0]['standard'] == 'GDPR'

    audit.action = 'read'
    assert await sec._check_compliance_for_event(audit) == []


# ============================================================================
# Security service — encryption / password / behavior / info
# ============================================================================

async def test_sec_encrypt_decrypt_with_context(sec):
    enc = await sec.encrypt_data('secret', {'tenant': 't'})
    data, ctx = await sec.decrypt_data(enc)
    assert data == 'secret' and ctx == {'tenant': 't'}


async def test_sec_encrypt_decrypt_no_context(sec):
    enc = await sec.encrypt_data('plain')
    data, ctx = await sec.decrypt_data(enc)
    assert data == 'plain' and ctx is None


async def test_sec_decrypt_garbage_raises(sec):
    with pytest.raises(Exception):
        await sec.decrypt_data('not-base64-encrypted!!')


async def test_sec_validate_password(sec):
    good = await sec.validate_password('Str0ng!Passw0rdX')
    assert good['valid'] is True and good['score'] == 100

    weak = await sec.validate_password('password')
    assert weak['valid'] is False
    assert weak['issues']
    assert len(weak['suggestions']) == 3


async def test_sec_validate_password_partial_scores(sec):
    res = await sec.validate_password('weakpass')
    assert res['valid'] is False
    assert res['score'] == 20  # lowercase only


async def test_sec_analyze_user_behavior(sec):
    res = await sec.analyze_user_behavior('u1', '24h')
    assert res['login_frequency'] == 0.0
    assert res['unusual_activities'] == []


async def test_sec_analyze_user_behavior_ai(sec_ai):
    sec_ai._ai_behavior_analysis = AsyncMock(
        return_value={'risk_score': 0.7, 'anomalies': ['a']})
    res = await sec_ai.analyze_user_behavior('u1')
    assert res['risk_score'] == 0.7 and res['anomalies'] == ['a']


async def test_sec_analyze_user_behavior_error(sec):
    sec._get_user_activities = AsyncMock(side_effect=RuntimeError('x'))
    assert 'error' in await sec.analyze_user_behavior('u1')


async def test_sec_private_state_helpers(sec):
    await sec._block_ip('3.3.3.3', 60)
    assert '3.3.3.3' in sec.blocked_ips
    sec.active_sessions['s'] = {}
    await sec._terminate_session('s')
    assert 's' not in sec.active_sessions
    sec.user_security_contexts['u'] = {}
    await sec._lock_user_account('u')
    await sec._quarantine_resource('res1')
    assert sec.quarantined_resources['res1'] is not None


async def test_sec_log_security_audit(sec):
    audit = await sec._log_security_audit(
        AuditEventType.SECURITY_ALERT, 'sys', 'r', 'act', 'success',
        metadata={'x': 1})
    assert audit is not None and audit.metadata == {'x': 1}


async def test_sec_info_metrics_close(sec):
    info = await sec.get_service_info()
    assert info['status'] == 'ACTIVE'
    metrics = await sec.get_security_metrics()
    assert metrics['blocked_ips'] == 0
    sec.http_session = MagicMock()
    sec.http_session.close = AsyncMock()
    await sec.close()
    sec.http_session.close.assert_awaited_once()


def test_sec_parse_ai_threat_results(sec):
    assert sec._parse_ai_threat_results('anything') == []


# ============================================================================
# Outlook service — token handling
# ============================================================================

@pytest.fixture()
def outlook():
    return OutlookService(tenant_id='t', config={
        'client_id': 'cid', 'client_secret': 'cs', 'tenant_id': 'mid'})


def _token_record(access_token='tok', refresh_token='rtok',
                  expires_at=None, has_token=True):
    rec = MagicMock()
    rec.access_token = access_token if has_token else None
    rec.refresh_token = refresh_token
    rec.expires_at = expires_at
    return rec


def _db_ctx(record):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = record
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=db)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx, db


def test_outlook_token_expired(outlook):
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    assert outlook._is_token_expired({'expires_at': None}) is True
    assert outlook._is_token_expired(
        {'expires_at': future.timestamp()}) is False
    assert outlook._is_token_expired({'expires_at': past.timestamp()}) is True
    assert outlook._is_token_expired(
        {'expires_at': future.isoformat()}) is False
    assert outlook._is_token_expired({'expires_at': 'garbage'}) is True


async def test_outlook_get_access_token_valid(outlook, monkeypatch):
    ctx, _ = _db_ctx(_token_record(
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1)))
    monkeypatch.setattr('core.database.get_db_session',
                        MagicMock(return_value=ctx))
    assert await outlook._get_access_token('u1') == 'tok'


async def test_outlook_get_access_token_no_record(outlook, monkeypatch):
    ctx, _ = _db_ctx(None)
    monkeypatch.setattr('core.database.get_db_session',
                        MagicMock(return_value=ctx))
    assert await outlook._get_access_token('u1') is None


async def test_outlook_get_access_token_expired_refreshes(
        outlook, monkeypatch):
    ctx, _ = _db_ctx(_token_record(
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1)))
    monkeypatch.setattr('core.database.get_db_session',
                        MagicMock(return_value=ctx))
    outlook._refresh_access_token = AsyncMock(return_value='new-tok')
    assert await outlook._get_access_token('u1') == 'new-tok'


async def test_outlook_get_access_token_error(outlook, monkeypatch):
    def boom():
        raise RuntimeError('db down')
    monkeypatch.setattr('core.database.get_db_session', boom)
    assert await outlook._get_access_token('u1') is None


def _aiohttp_resp(status=200, payload=None, text='err'):
    resp = MagicMock()
    resp.status = status
    resp.json = AsyncMock(return_value=payload if payload is not None else {})
    resp.text = AsyncMock(return_value=text)
    return resp


def _install_aiohttp(monkeypatch, response, method='post'):
    session = MagicMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=response)
    ctx.__aexit__ = AsyncMock(return_value=False)
    setattr(session, method, MagicMock(return_value=ctx))
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=session)
    client.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr('integrations.outlook_service.aiohttp.ClientSession',
                        MagicMock(return_value=client))
    return session


async def test_outlook_refresh_success(outlook, monkeypatch):
    payload = {'access_token': 'new', 'refresh_token': 'nrt',
               'expires_in': 3600}
    _install_aiohttp(monkeypatch, _aiohttp_resp(200, payload))
    ctx, db = _db_ctx(_token_record())
    monkeypatch.setattr('core.database.get_db_session',
                        MagicMock(return_value=ctx))
    with patch('core.privsec.token_encryption.encrypt_token',
               side_effect=lambda v: v):
        token = await outlook._refresh_access_token(
            'u1', {'refresh_token': 'rt'})
    assert token == 'new'
    db.commit.assert_called_once()


async def test_outlook_refresh_no_refresh_token(outlook):
    assert await outlook._refresh_access_token('u1', {}) is None


async def test_outlook_refresh_missing_creds(outlook):
    outlook.client_id = None
    assert await outlook._refresh_access_token(
        'u1', {'refresh_token': 'r'}) is None


async def test_outlook_refresh_http_failure(outlook, monkeypatch):
    _install_aiohttp(monkeypatch, _aiohttp_resp(500))
    assert await outlook._refresh_access_token(
        'u1', {'refresh_token': 'r'}) is None


async def test_outlook_refresh_missing_access_token(outlook, monkeypatch):
    _install_aiohttp(monkeypatch, _aiohttp_resp(200, {'foo': 'bar'}))
    assert await outlook._refresh_access_token(
        'u1', {'refresh_token': 'r'}) is None


async def test_outlook_refresh_error(outlook, monkeypatch):
    def boom():
        raise RuntimeError('net')
    monkeypatch.setattr(
        'integrations.outlook_service.aiohttp.ClientSession', boom)
    assert await outlook._refresh_access_token(
        'u1', {'refresh_token': 'r'}) is None


# ============================================================================
# Outlook service — graph request core
# ============================================================================

async def test_outlook_handle_response_statuses(outlook):
    r = _aiohttp_resp(200, {'id': 'x'})
    assert (await outlook._handle_response(r)) == {'id': 'x'}
    assert (await outlook._handle_response(
        _aiohttp_resp(202))) == {'success': True}
    assert (await outlook._handle_response(
        _aiohttp_resp(204))) == {'success': True}
    assert (await outlook._handle_response(_aiohttp_resp(404))) is None
    bad = MagicMock()
    bad.status = 200
    bad.json = AsyncMock(side_effect=RuntimeError('x'))
    assert (await outlook._handle_response(bad)) is None


async def test_outlook_graph_request_no_token(outlook):
    outlook._get_access_token = AsyncMock(return_value=None)
    assert await outlook._make_graph_request('u1', '/me') is None


@pytest.mark.parametrize('method', ['get', 'post', 'patch', 'delete'])
async def test_outlook_graph_request_methods(outlook, monkeypatch, method):
    _install_aiohttp(monkeypatch, _aiohttp_resp(200, {'ok': True}),
                     method=method)
    res = await outlook._make_graph_request(
        'u1', '/me', method=method.upper(), access_token='tok',
        data={'a': 1} if method != 'get' else None)
    assert res == {'ok': True}


async def test_outlook_graph_request_unsupported_method(outlook):
    assert await outlook._make_graph_request(
        'u1', '/me', method='PUT', access_token='t') is None


async def test_outlook_graph_request_exception(outlook, monkeypatch):
    def boom():
        raise RuntimeError('net')
    monkeypatch.setattr(
        'integrations.outlook_service.aiohttp.ClientSession', boom)
    assert await outlook._make_graph_request(
        'u1', '/me', access_token='t') is None


# ============================================================================
# Outlook service — email / calendar / contacts / tasks
# ============================================================================

@pytest.fixture()
def graphed(outlook):
    outlook._make_graph_request = AsyncMock(
        return_value={'value': [{'id': 'm1', 'subject': 'Subj',
                                 'bodyPreview': 'prev',
                                 'receivedDateTime': '2026-08-01'}]})
    return outlook


async def test_outlook_get_user_emails_folders(graphed):
    for folder, expected in (
            ('inbox', 'inbox'), ('sent', 'sentitems'),
            ('drafts', 'drafts'), ('other', None)):
        emails = await graphed.get_user_emails(
            'u1', folder=folder, query='q', include_attachments=True)
        assert emails[0]['id'] == 'm1'
        called = graphed._make_graph_request.await_args.args[1]
        assert 'messages' in called
    # non-list result
    graphed._make_graph_request = AsyncMock(return_value=None)
    assert await graphed.get_user_emails('u1') == []


async def test_outlook_get_user_emails_error(outlook):
    outlook._make_graph_request = AsyncMock(side_effect=RuntimeError('x'))
    assert await outlook.get_user_emails('u1') == []


async def test_outlook_send_email(graphed):
    graphed._make_graph_request = AsyncMock(return_value={'success': True})
    res = await graphed.send_email(
        'u1', ['a@b.c'], 's', 'body', cc_recipients=['c@d.e'],
        bcc_recipients=['e@f.g'])
    assert res == {'success': True}
    graphed._make_graph_request = AsyncMock(side_effect=RuntimeError('x'))
    assert await graphed.send_email('u1', ['a@b.c'], 's', 'b') is None


async def test_outlook_reply_and_delete(graphed):
    graphed._make_graph_request = AsyncMock(return_value={'success': True})
    assert await graphed.reply_to_email('u1', 'm1', 'hi') is True
    assert await graphed.delete_email('u1', 'm1') is True
    graphed._make_graph_request = AsyncMock(return_value=None)
    assert await graphed.reply_to_email('u1', 'm1', 'hi') is False
    assert await graphed.delete_email('u1', 'm1') is False
    graphed._make_graph_request = AsyncMock(side_effect=RuntimeError('x'))
    assert await graphed.reply_to_email('u1', 'm1', 'hi') is False
    assert await graphed.delete_email('u1', 'm1') is False


async def test_outlook_draft_and_get_by_id(graphed):
    graphed._make_graph_request = AsyncMock(return_value={'id': 'd1'})
    assert (await graphed.create_draft_email('u1', ['a@b.c'], 's', 'b'))[
        'id'] == 'd1'
    graphed._make_graph_request = AsyncMock(
        return_value={'id': 'm1', 'subject': 'Subj'})
    email = await graphed.get_email_by_id('u1', 'm1')
    assert email['id'] == 'm1'
    graphed._make_graph_request = AsyncMock(return_value=None)
    assert await graphed.get_email_by_id('u1', 'm1') is None
    graphed._make_graph_request = AsyncMock(side_effect=RuntimeError('x'))
    assert await graphed.create_draft_email('u1', ['a@b.c'], 's', 'b') is None
    assert await graphed.get_email_by_id('u1', 'm1') is None


async def test_outlook_attachment_content(graphed):
    payload = {'contentBytes': base64.b64encode(b'raw').decode()}
    graphed._make_graph_request = AsyncMock(return_value=payload)
    assert await graphed.get_attachment_content('u1', 'm', 'a') == b'raw'
    graphed._make_graph_request = AsyncMock(return_value={'id': 'a'})
    assert await graphed.get_attachment_content('u1', 'm', 'a') is None
    graphed._make_graph_request = AsyncMock(side_effect=RuntimeError('x'))
    assert await graphed.get_attachment_content('u1', 'm', 'a') is None


async def test_outlook_calendar(graphed):
    graphed._make_graph_request = AsyncMock(return_value={
        'value': [{'id': 'e1', 'subject': 'Meet', 'start':
                   {'dateTime': '2026-08-01T10:00:00'},
                   'end': {'dateTime': '2026-08-01T11:00:00'},
                   'organizer': {'emailAddress': {'address': 'o@x.y'}}}]})
    for tmin, tmax in ((None, None), ('2026-08-01', None),
                       (None, '2026-08-02'), ('2026-08-01', '2026-08-02')):
        events = await graphed.get_calendar_events(
            'u1', time_min=tmin, time_max=tmax)
        assert events[0]['id'] == 'e1'
    graphed._make_graph_request = AsyncMock(return_value=None)
    assert await graphed.get_calendar_events('u1') == []
    graphed._make_graph_request = AsyncMock(side_effect=RuntimeError('x'))
    assert await graphed.get_calendar_events('u1') == []


async def test_outlook_calendar_create_update(graphed):
    graphed._make_graph_request = AsyncMock(return_value={'id': 'e1'})
    res = await graphed.create_calendar_event(
        'u1', 'Meet', body='b', start={'dateTime': 'x', 'timeZone': 'UTC'},
        end={'dateTime': 'y', 'timeZone': 'UTC'},
        location={'displayName': 'here'}, attendees=['a@b.c'])
    assert res == {'id': 'e1'}
    res = await graphed.create_calendar_event('u1', 'Meet')  # defaults
    assert res == {'id': 'e1'}
    assert (await graphed.update_calendar_event(
        'u1', 'e1', {'subject': 'z'})) == {'id': 'e1'}
    graphed._make_graph_request = AsyncMock(side_effect=RuntimeError('x'))
    assert await graphed.create_calendar_event('u1', 'M') is None
    assert await graphed.update_calendar_event('u1', 'e1', {}) is None


async def test_outlook_contacts(graphed):
    graphed._make_graph_request = AsyncMock(return_value={
        'value': [{'id': 'c1', 'displayName': 'Connie'}]})
    contacts = await graphed.get_user_contacts('u1', query='con')
    assert contacts[0]['display_name'] == 'Connie'
    graphed._make_graph_request = AsyncMock(return_value=None)
    assert await graphed.get_user_contacts('u1') == []
    graphed._make_graph_request = AsyncMock(return_value={'id': 'c2'})
    assert (await graphed.create_contact(
        'u1', 'New', given_name='N', surname='S',
        email_addresses=[{'address': 'a@b.c'}], business_phones=['1'],
        company_name='Co')) == {'id': 'c2'}
    graphed._make_graph_request = AsyncMock(side_effect=RuntimeError('x'))
    assert await graphed.get_user_contacts('u1') == []
    assert await graphed.create_contact('u1', 'X') is None


async def test_outlook_tasks(graphed):
    graphed._make_graph_request = AsyncMock(return_value={
        'value': [{'id': 't1', 'subject': 'Do'}]})
    tasks = await graphed.get_user_tasks('u1', status='notStarted')
    assert tasks[0]['id'] == 't1'
    graphed._make_graph_request = AsyncMock(return_value=None)
    assert await graphed.get_user_tasks('u1') == []
    graphed._make_graph_request = AsyncMock(return_value={'id': 't2'})
    assert (await graphed.create_task(
        'u1', 'New', body='b', importance='high',
        due_date_time={'dateTime': 'x'}, categories=['c'])) == {'id': 't2'}
    graphed._make_graph_request = AsyncMock(side_effect=RuntimeError('x'))
    assert await graphed.get_user_tasks('u1') == []
    assert await graphed.create_task('u1', 'X') is None


async def test_outlook_profile_unread_search(graphed):
    graphed._make_graph_request = AsyncMock(return_value={
        'id': 'u', 'displayName': 'User', 'value': [
            {'id': 'm1', 'subject': 's'}]})
    profile = await graphed.get_user_profile('u1')
    assert profile['display_name'] == 'User'
    unread = await graphed.get_unread_emails('u1')
    assert unread[0]['id'] == 'm1'
    found = await graphed.search_emails('u1', 's')
    assert found[0]['id'] == 'm1'
    graphed._make_graph_request = AsyncMock(return_value=None)
    assert await graphed.get_user_profile('u1') is None
    assert await graphed.get_unread_emails('u1') == []
    assert await graphed.search_emails('u1', 's') == []
    graphed._make_graph_request = AsyncMock(side_effect=RuntimeError('x'))
    assert await graphed.get_user_profile('u1') is None
    assert await graphed.get_unread_emails('u1') == []
    assert await graphed.search_emails('u1', 's') == []


# ============================================================================
# Outlook service — capabilities / operations / sync
# ============================================================================

def test_outlook_capabilities_health(outlook):
    caps = outlook.get_capabilities()
    assert caps['supports_webhooks'] is True
    assert outlook.health_check()['healthy'] is True
    bare = OutlookService(tenant_id='t', config={})
    assert bare.health_check()['healthy'] is False


async def test_outlook_execute_operation(outlook):
    outlook.send_email = AsyncMock(return_value={'success': True})
    res = await outlook.execute_operation(
        'send_email', {'user_id': 'u', 'to_recipients': ['a@b.c'],
                       'subject': 's', 'body': 'b'})
    assert res['success'] is True

    outlook.send_email = AsyncMock(return_value=None)
    assert (await outlook.execute_operation(
        'send_email', {'to_recipients': ['a@b.c'], 'subject': 's',
                       'body': 'b'}))['success'] is False

    outlook.get_user_emails = AsyncMock(return_value=[{'id': 'm'}])
    res = await outlook.execute_operation('read_emails', {'folder': 'inbox'})
    assert res['success'] is True

    outlook.create_calendar_event = AsyncMock(return_value={'id': 'e'})
    assert (await outlook.execute_operation(
        'create_calendar_event', {'subject': 's'}))['success'] is True

    assert (await outlook.execute_operation('zzz', {}))['success'] is False

    outlook.send_email = AsyncMock(side_effect=RuntimeError('x'))
    assert (await outlook.execute_operation(
        'send_email', {'to_recipients': ['a@b.c'], 'subject': 's',
                       'body': 'b'})) == {'success': False,
                                          'error': 'Outlook operation failed'}


async def test_outlook_execute_operation_tenant_mismatch(outlook):
    with pytest.raises(ValueError):
        await outlook.execute_operation(
            'send_email', {}, context={'tenant_id': 'other'})


async def test_outlook_sync_to_postgres_cache(outlook, monkeypatch):
    outlook._make_graph_request = AsyncMock(
        return_value={'totalItemCount': 10, 'unreadItemCount': 2})
    outlook.get_calendar_events = AsyncMock(return_value=[{'id': 'e'}])
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = None
    monkeypatch.setattr('core.database.SessionLocal',
                        MagicMock(return_value=db))
    res = await outlook.sync_to_postgres_cache('u1')
    assert res == {'success': True, 'metrics_synced': 3}

    # update-existing path
    db.query.return_value.filter_by.return_value.first.return_value = (
        MagicMock())
    assert (await outlook.sync_to_postgres_cache('u1'))['success'] is True

    # db save failure
    db.commit = MagicMock(side_effect=RuntimeError('x'))
    assert (await outlook.sync_to_postgres_cache(
        'u1'))['success'] is False

    # inbox fetch failure
    outlook._make_graph_request = AsyncMock(return_value=None)
    assert (await outlook.sync_to_postgres_cache(
        'u1'))['error'] == 'Failed to fetch Inbox stats'

    # outer failure
    outlook._make_graph_request = AsyncMock(side_effect=RuntimeError('x'))
    assert (await outlook.sync_to_postgres_cache(
        'u1'))['success'] is False


async def test_outlook_full_sync(outlook):
    outlook.sync_to_postgres_cache = AsyncMock(
        return_value={'success': True})
    res = await outlook.full_sync('u1')
    assert res['success'] is True and res['user_id'] == 'u1'


async def test_outlook_fetch_recent_messages(outlook, monkeypatch):
    outlook.get_user_emails = AsyncMock(return_value=[{'id': 'm1'}])
    pipeline = MagicMock()
    pipeline.ingest_message = AsyncMock()
    monkeypatch.setattr(
        'integrations.atom_communication_ingestion_pipeline.get_ingestion_pipeline',
        MagicMock(return_value=pipeline))
    msgs = await outlook.fetch_recent_messages('u1')
    assert msgs == [{'id': 'm1'}]
    pipeline.ingest_message.assert_awaited_once()

    outlook.get_user_emails = AsyncMock(return_value=[])
    assert await outlook.fetch_recent_messages('u1') == []

    outlook.get_user_emails = AsyncMock(side_effect=RuntimeError('x'))
    assert await outlook.fetch_recent_messages('u1') == []


async def test_outlook_sync_calendar_events(outlook, monkeypatch):
    event = {
        'id': 'e1', 'subject': 'Meet', 'bodyPreview': 'bp',
        'start': {'dateTime': 's'}, 'end': {'dateTime': 'e'},
        'location': {'displayName': 'L'},
        'organizer': {'emailAddress': {'address': 'o@x.y', 'name': 'O'}},
        'attendees': [{'emailAddress': {'address': 'a@b.c', 'name': 'A'}}],
    }
    outlook.get_calendar_events = AsyncMock(return_value=[event])
    pipeline = MagicMock()
    pipeline.ingest_message = AsyncMock()
    monkeypatch.setattr(
        'integrations.atom_communication_ingestion_pipeline.get_ingestion_pipeline',
        MagicMock(return_value=pipeline))
    events = await outlook.sync_calendar_events('u1')
    assert events == [event]
    pipeline.ingest_message.assert_awaited_once()

    outlook.get_calendar_events = AsyncMock(return_value=[])
    assert await outlook.sync_calendar_events('u1') == []

    outlook.get_calendar_events = AsyncMock(side_effect=RuntimeError('x'))
    assert await outlook.sync_calendar_events('u1') == []


# ============================================================================
# Unified service — helpers
# ============================================================================

@pytest.fixture()
def unified():
    svc = AtomEnterpriseUnifiedService(tenant_id='t', config={
        'security_service': MagicMock(),
        'ai_service': None,
        'ai_integration': None,
        'workflow_service': None})
    svc.security_service.audit_event = AsyncMock()
    return svc


def _wf_data(**over):
    data = {
        'name': 'wf1',
        'description': 'd',
        'service_type': 'security',
        'security_level': 'internal',
        'compliance_standards': ['gdpr'],
        'triggers': [{'type': 'manual'}],
        'steps': [{'type': 'security_check', 'name': 's1'}],
        'actions': [{'type': 'notification', 'config': {}}],
        'metadata': {},
    }
    data.update(over)
    return data


def _make_workflow(unified, **over):
    data = _wf_data(**over)
    from integrations.atom_enterprise_unified_service import (
        _coerce_compliance_standard as _cc)
    wf = EnterpriseWorkflow(
        workflow_id=over.get('workflow_id', 'wf_x'),
        name=data['name'], description=data['description'],
        service_type=EnterpriseServiceType(data['service_type']),
        security_level=WorkflowSecurityLevel(data['security_level']),
        compliance_standards=[_cc(s) for s in data['compliance_standards']],
        triggers=data['triggers'], steps=data['steps'],
        actions=data['actions'],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc), created_by='u',
        status='active', metadata=data.get('metadata', {}),
        audit_trail=[], compliance_checks=[])
    unified.enterprise_workflows[wf.workflow_id] = wf
    return wf


def test_unified_coerce_standard():
    assert _coerce_compliance_standard('gdpr') == ComplianceStandard.GDPR
    assert _coerce_compliance_standard(
        ComplianceStandard.GDPR) == ComplianceStandard.GDPR
    assert _coerce_compliance_standard('GDPR') == ComplianceStandard.GDPR
    with pytest.raises(ValueError):
        _coerce_compliance_standard(123)


def test_unified_init_defaults():
    svc = AtomEnterpriseUnifiedService(tenant_id='t', config={})
    assert svc.enterprise_metrics['total_workflows'] == 0
    assert svc.is_initialized is False


# ============================================================================
# Unified service — initialize / create workflow
# ============================================================================

async def test_unified_initialize_missing_services():
    svc = AtomEnterpriseUnifiedService(tenant_id='t', config={
        'security_service': None, 'ai_service': None})
    assert await svc.initialize() is False


async def test_unified_initialize_success(unified):
    unified.ai_service = MagicMock()
    unified.security_service.setup_workflow_monitoring = AsyncMock()
    unified.security_service.setup_compliance_automation = AsyncMock()
    unified.security_service.start_monitoring = AsyncMock()
    assert await unified.initialize() is True
    assert unified.is_initialized is True


async def test_unified_create_workflow_success(unified):
    unified.db = MagicMock()
    unified.db.store_enterprise_workflow = AsyncMock()
    res = await unified.create_enterprise_workflow(_wf_data(), 'admin')
    assert res['ok'] is True
    assert res['security_actions'] and res['compliance_automations']
    assert 'wf1' in res['workflow_id'] or res['workflow_id']
    unified.db.store_enterprise_workflow.assert_awaited_once()


async def test_unified_create_workflow_with_workflow_service(unified):
    unified.workflow_service = MagicMock()
    unified.workflow_service.create_workflow = AsyncMock(
        return_value={'ok': True})
    res = await unified.create_enterprise_workflow(_wf_data(), 'admin')
    assert res['ok'] is True

    unified.workflow_service.create_workflow = AsyncMock(
        return_value={'ok': False, 'error': 'x'})
    res = await unified.create_enterprise_workflow(_wf_data(), 'admin')
    assert res['ok'] is False


async def test_unified_create_workflow_validation_failure(unified):
    unified._validate_workflow_security = AsyncMock(
        return_value={'valid': False, 'errors': ['bad']})
    res = await unified.create_enterprise_workflow(_wf_data(), 'admin')
    assert res['ok'] is False and 'validation failed' in res['error']


async def test_unified_create_workflow_bad_input(unified):
    res = await unified.create_enterprise_workflow(
        _wf_data(compliance_standards=['nope']), 'admin')
    assert res['ok'] is False


async def test_unified_create_workflow_exception(unified):
    unified._validate_enterprise_workflow = AsyncMock(
        side_effect=RuntimeError('x'))
    res = await unified.create_enterprise_workflow(_wf_data(), 'admin')
    assert res['ok'] is False


# ============================================================================
# Unified service — execute workflow
# ============================================================================

async def test_unified_execute_not_found(unified):
    res = await unified.execute_enterprise_workflow('nope', {}, 'u')
    assert res['ok'] is False


async def test_unified_execute_success_all_step_types(unified):
    _make_workflow(unified, steps=[
        {'type': 'security_check'},
        {'type': 'compliance_check'},
        {'type': 'ai_analysis'},
        {'type': 'data_processing'},
        {'type': 'notification'},
        {'type': 'custom_thing'},
    ])
    res = await unified.execute_enterprise_workflow('wf_x', {'a': 1}, 'u')
    assert res['ok'] is True
    assert len(res['execution_results']) == 6
    assert unified.enterprise_metrics['automations_executed'] == 1
    assert unified.enterprise_workflows['wf_x'].audit_trail


async def test_unified_execute_security_precheck_fail(unified):
    unified._check_user_authorization = AsyncMock(
        return_value={'authorized': False})
    _make_workflow(unified)
    res = await unified.execute_enterprise_workflow('wf_x', {}, 'u')
    assert res['ok'] is False and 'security_violation' in res


async def test_unified_execute_context_security_fail(unified):
    unified._validate_context_security = AsyncMock(
        return_value={'valid': False})
    _make_workflow(unified)
    res = await unified.execute_enterprise_workflow('wf_x', {}, 'u')
    assert res['ok'] is False and 'Security check failed' in res['error']


async def test_unified_execute_compliance_precheck_fail(unified):
    unified._check_compliance_requirements = AsyncMock(
        return_value={'compliant': False})
    _make_workflow(unified)
    res = await unified.execute_enterprise_workflow('wf_x', {}, 'u')
    assert res['ok'] is False and 'Compliance check failed' in res['error']


async def test_unified_execute_security_precheck_error(unified):
    unified._check_user_authorization = AsyncMock(
        side_effect=RuntimeError('x'))
    _make_workflow(unified)
    res = await unified.execute_enterprise_workflow('wf_x', {}, 'u')
    assert res['ok'] is False


async def test_unified_execute_compliance_precheck_error(unified):
    unified._check_compliance_requirements = AsyncMock(
        side_effect=RuntimeError('x'))
    _make_workflow(unified)
    res = await unified.execute_enterprise_workflow('wf_x', {}, 'u')
    assert res['ok'] is False


async def test_unified_execute_step_error(unified):
    _make_workflow(unified, steps=[{'type': 'security_check'}])
    unified._execute_security_check = AsyncMock(
        side_effect=RuntimeError('boom'))
    res = await unified.execute_enterprise_workflow('wf_x', {}, 'u')
    assert res['ok'] is True  # step errors are contained
    assert res['execution_results'][0]['success'] is False


async def test_unified_execute_with_alerts(unified):
    _make_workflow(unified, steps=[{'type': 'security_check'},
                                   {'type': 'compliance_check'}])
    unified.security_service.log_security_alert = AsyncMock()
    unified.security_service.log_compliance_violation = AsyncMock()
    unified._monitor_step_execution = AsyncMock(
        return_value={'alert': True, 'severity': 'high'})
    unified._monitor_step_compliance = AsyncMock(
        return_value={'violation': True, 'severity': 'high'})
    res = await unified.execute_enterprise_workflow('wf_x', {}, 'u')
    assert res['ok'] is True
    assert unified.enterprise_workflows['wf_x'].status == 'blocked'


async def test_unified_get_ai_enhanced_context(unified):
    wf = _make_workflow(unified)
    assert (await unified._get_ai_enhanced_context(
        wf, {'x': 1})) == {'ai_enhanced': False, 'context': {'x': 1}}

    unified.ai_service = MagicMock()
    with patch.object(uni_mod, 'AIRequest', MagicMock(), create=True), \
         patch.object(uni_mod, 'AITaskType', MagicMock(), create=True), \
         patch.object(uni_mod, 'AIModelType', MagicMock(), create=True), \
         patch.object(uni_mod, 'AIServiceType', MagicMock(), create=True):
        resp = MagicMock(ok=True, output_data={'i': 1}, confidence=0.9)
        unified.ai_service.process_ai_request = AsyncMock(return_value=resp)
        ctx = await unified._get_ai_enhanced_context(wf, {'x': 1})
        assert ctx['ai_enhanced'] is True

        resp2 = MagicMock(ok=False)
        unified.ai_service.process_ai_request = AsyncMock(return_value=resp2)
        assert (await unified._get_ai_enhanced_context(
            wf, {'x': 1}))['ai_enhanced'] is False

        unified.ai_service.process_ai_request = AsyncMock(
            side_effect=RuntimeError('x'))
        assert (await unified._get_ai_enhanced_context(
            wf, {'x': 1}))['ai_enhanced'] is False


# ============================================================================
# Unified service — automations
# ============================================================================

async def test_unified_create_security_automation(unified):
    unified.create_enterprise_workflow = AsyncMock(
        return_value={'ok': True, 'workflow_id': 'wf9'})
    res = await unified.create_security_automation(
        {'name': 'sec1', 'description': 'd'}, 'admin')
    assert res['ok'] is True
    assert res['config']['automation_type'] == 'security'
    assert 'sec_auto_' in res['automation_id']

    unified.create_enterprise_workflow = AsyncMock(
        return_value={'ok': False, 'error': 'x'})
    assert (await unified.create_security_automation(
        {'name': 's', 'description': 'd'}, 'u'))['ok'] is False


async def test_unified_create_compliance_automation(unified):
    unified.create_enterprise_workflow = AsyncMock(
        return_value={'ok': True, 'workflow_id': 'wf9'})
    res = await unified.create_compliance_automation(
        {'name': 'c1', 'description': 'd', 'workflow_type': 'audit_remediation',
         'compliance_standards': ['gdpr']}, 'admin')
    assert res['ok'] is True
    assert res['compliance_automation']['compliance_standard'] == 'gdpr'

    unified.create_enterprise_workflow = AsyncMock(
        return_value={'ok': False, 'error': 'x'})
    assert (await unified.create_compliance_automation(
        {'name': 'c', 'description': 'd',
         'workflow_type': 'audit_remediation',
         'compliance_standards': ['gdpr']}, 'admin'))['ok'] is False


async def test_unified_handle_security_event(unified):
    _make_workflow(unified)
    unified.active_automations['a1'] = {
        'automation_id': 'a1', 'automation_type': 'security',
        'threat_types': [], 'severity_levels': ['high'],
        'workflow_id': 'wf_x'}
    res = await unified.handle_security_event(
        {'threat_type': 'malware', 'severity': 'high'})
    assert res['ok'] is True and res['relevant_automations'] == 1
    assert unified.enterprise_metrics['security_incidents_resolved'] == 1


async def test_unified_handle_compliance_violation(unified):
    wf = _make_workflow(unified, metadata={'automation_id': 'ca1'})
    unified.compliance_automations['ca1'] = ComplianceAutomation(
        automation_id='ca1', compliance_standard='gdpr',
        workflow_type=ComplianceWorkflowType.AUDIT_REMEDIATION,
        triggers=[], actions=[], schedule=None, approval_required=True,
        escalation_rules=[], reporting_frequency='monthly',
        artifact_generation=[], audit_requirements=[])
    res = await unified.handle_compliance_violation({'standard': 'gdpr'})
    assert res['ok'] is True and res['relevant_automations'] == 1
    assert unified.enterprise_metrics[
        'compliance_violations_resolved'] == 1

    # non-matching standard
    res2 = await unified.handle_compliance_violation(
        {'standard': 'hipaa'})
    assert res2['relevant_automations'] == 0


async def test_unified_get_workflows_filters(unified):
    _make_workflow(unified, service_type='security')
    _make_workflow(unified, workflow_id='wf_y', name='wf2',
                   service_type='compliance')
    all_wfs = await unified.get_enterprise_workflows()
    assert len(all_wfs) == 2
    sec_only = await unified.get_enterprise_workflows(
        filters={'service_type': 'security'})
    assert len(sec_only) == 1
    assert await unified.get_enterprise_workflows(
        filters={'security_level': 'secret'}) == []
    assert await unified.get_enterprise_workflows(
        filters={'compliance_standard': 'gdpr'})
    assert await unified.get_enterprise_workflows(
        filters={'compliance_standard': 'hipaa'}) == []
    assert sec_only[0]['steps_count'] == 1


async def test_unified_get_automations_status(unified):
    unified.active_automations['a1'] = {
        'automation_type': 'security', 'active': True}
    unified.active_automations['a2'] = {
        'automation_type': 'compliance', 'active': False}
    status = await unified.get_automations_status()
    assert status['total_automations'] == 2
    assert status['security_automations'] == 1
    assert status['compliance_automations'] == 1
    assert status['active_automations'] == 1
    assert status['automations_by_type']['security'] == 1


# ============================================================================
# Unified service — alerts, blocking, helpers, info
# ============================================================================

async def test_unified_alert_and_violation_handlers(unified):
    wf = _make_workflow(unified)
    unified.security_service.log_security_alert = AsyncMock()
    unified.security_service.log_compliance_violation = AsyncMock()

    await unified._handle_security_alert(
        {'severity': 'high'}, wf, {'id': 's'}, 'u')
    assert wf.status == 'blocked'

    await unified._handle_security_alert(
        {'severity': 'medium'}, wf, {}, 'u')
    assert unified.workflow_monitoring['wf_x']['level'] == 'enhanced'

    await unified._handle_compliance_violation(
        {'severity': 'high'}, wf, {}, 'u')
    await unified._handle_compliance_violation(
        {'severity': 'medium'}, wf, {}, 'u')
    assert unified.workflow_monitoring['wf_x']['compliance_logging'] is True

    # no security_service configured
    unified.security_service = None
    await unified._handle_security_alert({'severity': 'high'}, wf, {}, 'u')
    await unified._handle_compliance_violation(
        {'severity': 'low'}, wf, {}, 'u')

    # handler-level error swallowed
    unified.security_service = MagicMock()
    unified.security_service.log_security_alert = AsyncMock(
        side_effect=RuntimeError('x'))
    await unified._handle_security_alert({'severity': 'high'}, wf, {}, 'u')


async def test_unified_block_workflow_execution(unified):
    _make_workflow(unified)
    unified.active_workflows['wf_x'] = MagicMock()
    await unified._block_workflow_execution('wf_x', 'test')
    assert unified.enterprise_workflows['wf_x'].status == 'blocked'
    assert unified.active_workflows['wf_x'].status == 'blocked'


async def test_unified_step_executors(unified):
    ctx = {}
    assert (await unified._execute_security_check({}, ctx))['success'] is True
    assert (await unified._execute_compliance_check({}, ctx))[
        'success'] is True
    assert (await unified._execute_ai_analysis({}, ctx))['success'] is True
    assert (await unified._execute_data_processing({}, ctx))[
        'success'] is True
    assert (await unified._execute_notification({}, ctx))['success'] is True
    assert (await unified._execute_custom_step({}, ctx))['success'] is True
    assert (await unified._monitor_step_execution({}, {}, 'u'))['alert'] is \
        False
    assert (await unified._monitor_step_compliance({}, {}, 'u'))[
        'violation'] is False
    assert (await unified._get_security_ai_analysis({}))['ai_analysis']
    assert (await unified._get_compliance_ai_analysis({}))['ai_analysis']
    assert (await unified._assess_action_risk(
        {}, WorkflowSecurityLevel.INTERNAL))['risk_level'] == 'medium'
    assert (await unified._check_user_authorization(
        'u', WorkflowSecurityLevel.INTERNAL))['authorized'] is True
    assert (await unified._validate_context_security(
        {}, WorkflowSecurityLevel.INTERNAL))['valid'] is True
    assert (await unified._check_compliance_requirements(
        'gdpr', {}, 'u'))['compliant'] is True
    assert (await unified._security_post_check(unified, [], 'u'))[
        'passed'] is True
    assert (await unified._compliance_post_check(unified, [], 'u'))[
        'passed'] is True


async def test_unified_execute_workflow_step_dispatch_error(unified):
    # step dict missing 'type' -> exception branch of the dispatcher
    res = await unified._execute_workflow_step({}, {}, 'u')
    assert res['success'] is False


async def test_unified_log_enterprise_event(unified):
    await unified._log_enterprise_event('e', 'u', 'r', 'a', 'ok')
    unified.security_service.audit_event.assert_awaited_once()

    unified.security_service = None
    await unified._log_enterprise_event('e', 'u', 'r', 'a', 'ok')


async def test_unified_setup_helpers(unified):
    unified.security_service.setup_workflow_monitoring = AsyncMock()
    unified.security_service.setup_compliance_automation = AsyncMock()
    unified.security_service.start_monitoring = AsyncMock()
    ai_int = MagicMock()
    ai_int.setup_workflow_automation = AsyncMock()
    ai_int.start_monitoring = AsyncMock()
    unified.ai_integration = ai_int
    await unified._setup_workflow_security_integration()
    await unified._setup_compliance_automation()
    await unified._setup_ai_powered_automation()
    await unified._start_enterprise_monitoring()
    ai_int.setup_workflow_automation.assert_awaited_once()

    # error branches swallowed
    unified.security_service.setup_workflow_monitoring = AsyncMock(
        side_effect=RuntimeError('x'))
    unified.security_service.setup_compliance_automation = AsyncMock(
        side_effect=RuntimeError('x'))
    ai_int.setup_workflow_automation = AsyncMock(side_effect=RuntimeError('x'))
    ai_int.start_monitoring = AsyncMock(side_effect=RuntimeError('x'))
    await unified._setup_workflow_security_integration()
    await unified._setup_compliance_automation()
    await unified._setup_ai_powered_automation()
    await unified._start_enterprise_monitoring()


async def test_unified_info_metrics_close(unified):
    info = await unified.get_service_info()
    assert info['status'] == 'ACTIVE'
    assert 'security' in info['supported_services']
    metrics = await unified.get_enterprise_metrics()
    assert metrics['total_workflows'] == 0
    await unified.close()


async def test_unified_initialize_enterprise_services(unified):
    unified.security_service = None
    unified.ai_integration = None
    with patch('integrations.atom_enterprise_unified_service'
               '.atom_enterprise_security_service', MagicMock()):
        # the ai_integration fallback import fails in this environment,
        # which exercises the error branch
        await unified._initialize_enterprise_services()


async def test_unified_validate_enterprise_workflow(unified):
    wf = _make_workflow(unified)
    res = await unified._validate_enterprise_workflow(wf)
    assert res['valid'] is True

    unified._validate_workflow_security = AsyncMock(
        return_value={'valid': False, 'errors': ['s1']})
    unified._validate_workflow_compliance = AsyncMock(
        return_value={'valid': False, 'errors': ['c1']})
    res = await unified._validate_enterprise_workflow(wf)
    assert res['valid'] is False and res['errors'] == ['s1', 'c1']

    unified._validate_workflow_security = AsyncMock(
        side_effect=RuntimeError('x'))
    res = await unified._validate_enterprise_workflow(wf)
    assert res['valid'] is False
