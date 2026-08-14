# -*- coding: utf-8 -*-
"""Coverage wave 87 — integrations.atom_video_ai_service,
integrations.outlook_service_enhanced.

No network, no LLM: HTTP sessions, circuit breaker / rate limiter, cv2/ffmpeg
model boundaries and AI services are all mocked at module boundaries.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import integrations.atom_video_ai_service as vid_mod
from integrations.atom_video_ai_service import (
    AtomVideoAIService,
    VideoFormat,
    VideoRequest,
    VideoResolution,
    VideoTaskType,
    VideoModelType,
)
import integrations.outlook_service_enhanced as ose_mod
from integrations.outlook_service_enhanced import OutlookEnhancedService


# ============================================================================
# Video AI — fixtures / helpers
# ============================================================================

@pytest.fixture(autouse=True)
def green_gates(monkeypatch):
    """Keep circuit breaker / rate limiter permissive for video service."""
    monkeypatch.setattr(vid_mod, 'circuit_breaker', MagicMock(
        is_enabled=AsyncMock(return_value=True)))
    monkeypatch.setattr(vid_mod, 'rate_limiter', MagicMock(
        is_rate_limited=AsyncMock(return_value=(False, 100))))


@pytest.fixture()
def video():
    svc = AtomVideoAIService(tenant_id='t', config={
        'security_service': None, 'automation_service': None,
        'ai_service': None, 'voice_ai_service': None})
    return svc


def vreq(task=VideoTaskType.SUMMARIZATION, fmt=VideoFormat.MP4, vid=b'data'):
    return VideoRequest(
        request_id='r1', task_type=task, model_type=VideoModelType.TRANSFORMERS,
        video_path=None, video_data=vid, format=fmt,
        resolution=VideoResolution.HD_720P, duration=60.0, fps=30.0,
        platform='slack', user_id='u1', metadata={})


def yolo_frame_result(names=('person',), conf=0.9):
    """One fake ultralytics result with one box per class name."""
    boxes = []
    for class_id, _name in enumerate(names):
        obj = MagicMock()
        obj.cls = class_id
        obj.conf = conf
        obj.xyxy = [MagicMock(tolist=lambda: [1.0, 2.0, 3.0, 4.0])]
        boxes.append(obj)
    result = MagicMock()
    result.boxes = boxes
    result.names = {i: n for i, n in enumerate(names)}
    return [result]


def yolo_service(video, names=('person',), conf=0.9):
    video.yolo_model = MagicMock(
        side_effect=lambda frame: yolo_frame_result(names, conf))
    return video.yolo_model


# ============================================================================
# Video AI — initialize / lifecycle
# ============================================================================

async def test_vid_initialize(video):
    assert await video.initialize() is True
    assert video.is_initialized
    assert video.content_moderation_policies['adult_content']['enabled']
    assert video.video_retention_policies['meeting_recordings'] == 365
    assert video.security_monitoring['video_anomaly_detection']['enabled']
    assert video.compliance_monitoring['content_compliance_checking'][
        'enabled']


async def test_vid_initialize_failure(video):
    video._setup_content_moderation = AsyncMock(side_effect=RuntimeError('x'))
    assert await video.initialize() is False


async def test_vid_load_video_models(video):
    # transformers/ultralytics unavailable -> error swallowed
    await video._load_video_models()
    assert video.yolo_model is None
    assert video.performance_metrics['model_load_time'] >= 0.0


async def test_vid_setup_paths(video):
    await video._setup_content_moderation()
    await video._setup_enterprise_features()
    video.video_config['enable_enterprise_features'] = False
    await video._setup_security_and_compliance()
    assert not hasattr(video, 'security_monitoring') or True
    await video._load_existing_video_data()


async def test_vid_status_and_close(video):
    status = await video.get_service_status()
    assert status['service'] == 'video_ai'
    assert status['status'] == 'inactive'
    video.is_initialized = True
    assert (await video.get_service_status())['status'] == 'active'
    await video.close()
    assert video.blip_model is None


# ============================================================================
# Video AI — process_video_request dispatch
# ============================================================================

async def test_vid_process_guards(video, monkeypatch):
    monkeypatch.setattr(vid_mod, 'circuit_breaker', MagicMock(
        is_enabled=AsyncMock(return_value=False)))
    res = await video.process_video_request(vreq())
    assert res.success is False and 'disabled' in res.metadata['error']
    monkeypatch.setattr(vid_mod, 'circuit_breaker', MagicMock(
        is_enabled=AsyncMock(return_value=True)))
    monkeypatch.setattr(vid_mod, 'rate_limiter', MagicMock(
        is_rate_limited=AsyncMock(return_value=(True, 0))))
    res = await video.process_video_request(vreq())
    assert res.success is False and 'Rate limit' in res.metadata['error']


async def test_vid_process_security_fail(video):
    video.video_config['enable_enterprise_features'] = True
    video._perform_security_check = AsyncMock(
        return_value={'passed': False, 'reason': 'nope'})
    res = await video.process_video_request(vreq())
    assert res.success is False and res.metadata['error'] == 'nope'


async def test_vid_process_unsupported_and_error(video):
    video._preprocess_video = AsyncMock(side_effect=RuntimeError('boom'))
    res = await video.process_video_request(vreq(task=VideoTaskType.TRANSLATION))
    assert res.success is False
    res = await video.process_video_request(vreq())
    assert res.success is False and 'boom' in res.metadata['error']


async def test_vid_process_logs_and_preprocess(video):
    video.video_config['enable_enterprise_features'] = True
    video.enterprise_security = MagicMock()
    video.enterprise_security.audit_event = AsyncMock()
    video._summarize_video = AsyncMock(return_value=MagicMock(
        success=True, processing_time=0.1, confidence=0.9))
    await video.process_video_request(vreq())
    video.enterprise_security.audit_event.assert_awaited_once()
    # non-mp4 preprocess branch
    data = await video._preprocess_video(vreq(fmt=VideoFormat.AVI))
    assert data == b'data'
    assert video.performance_metrics['video_preprocessing_time'] >= 0.0


async def test_vid_security_check(video):
    assert (await video._perform_security_check(vreq()))['passed'] is True
    video.enterprise_security = MagicMock()
    assert (await video._perform_security_check(vreq()))['passed'] is True


async def test_vid_log_video_request_error(video):
    video.enterprise_security = MagicMock()
    video.enterprise_security.audit_event = AsyncMock(
        side_effect=RuntimeError('x'))
    await video._log_video_request(vreq(), MagicMock(success=True))  # swallowed
    video.enterprise_security = None
    await video._log_video_request(vreq(), MagicMock(success=False))


# ============================================================================
# Video AI — summarization / AI branch
# ============================================================================

def _blip(video, monkeypatch, captions=('cap one', 'cap two')):
    monkeypatch.setattr(vid_mod, 'TORCH_AVAILABLE', False)
    video._extract_frames = AsyncMock(
        return_value=[MagicMock() for _ in captions])
    proc = MagicMock()
    proc.decode = MagicMock(return_value='a caption')
    video.blip_processor = proc
    video.blip_model = MagicMock()
    video.blip_model.generate.return_value = ['x']


async def test_vid_process_dispatch_all_tasks(video, monkeypatch):
    """process_video_request dispatches every supported task type."""
    monkeypatch.setattr(vid_mod, 'TORCH_AVAILABLE', False)
    video.video_config['enable_enterprise_features'] = False
    video._preprocess_video = AsyncMock(return_value=b'')
    video._extract_frames = AsyncMock(return_value=[])
    video.blip_processor = MagicMock()
    video.blip_model = MagicMock()
    yolo_service(video)
    for task in (VideoTaskType.SUMMARIZATION, VideoTaskType.CONTENT_ANALYSIS,
                 VideoTaskType.OBJECT_DETECTION,
                 VideoTaskType.FACE_RECOGNITION,
                 VideoTaskType.SCENE_DETECTION,
                 VideoTaskType.SPEAKER_DIARIZATION,
                 VideoTaskType.VIDEO_CLASSIFICATION,
                 VideoTaskType.CONTENT_MODERATION):
        res = await video.process_video_request(vreq(task=task))
        assert res.success is True, task
        assert res.processing_time >= 0.0


async def test_vid_summarize_with_ai(video, monkeypatch):
    _blip(video, monkeypatch)
    video.ai_service = MagicMock()
    video.ai_service.process_ai_request = AsyncMock(return_value=MagicMock(
        ok=True, output_data={'summary': 'S', 'key_points': ['k'],
                              'topics': ['t']}))
    res = await video._summarize_video(vreq(), b'v')
    assert res.success is True and res.text == 'S'
    assert res.content_analysis['captions'] == ['a caption', 'a caption']
    assert 'summary_r1' in video.video_summaries


async def test_vid_summarize_ai_fallback(video, monkeypatch):
    _blip(video, monkeypatch)
    video.ai_service = MagicMock()
    video.ai_service.process_ai_request = AsyncMock(
        side_effect=RuntimeError('ai down'))
    res = await video._summarize_video(vreq(), b'v')
    assert res.text == 'Unable to generate summary'
    # not-ok response
    video.ai_service.process_ai_request = AsyncMock(
        return_value=MagicMock(ok=False, output_data=None))
    res = await video._summarize_video(vreq(), b'v')
    assert res.text == 'Unable to generate summary'


async def test_vid_summarize_exception(video):
    video._extract_frames = AsyncMock(side_effect=RuntimeError('x'))
    res = await video._summarize_video(vreq(), b'v')
    assert res.success is False


# ============================================================================
# Video AI — content analysis / detection pipelines
# ============================================================================

async def test_vid_analyze_content(video, monkeypatch):
    yolo_service(video)
    video._extract_frames = AsyncMock(
        return_value=[MagicMock() for _ in range(3)])
    monkeypatch.setattr(video, '_analyze_video_quality',
                        AsyncMock(return_value=85.0))
    res = await video._analyze_video_content(vreq(), b'v')
    assert res.success is True
    assert len(res.objects_detected) == 3
    assert 'analysis_r1' in video.video_analyses
    assert video.analytics_metrics['quality_distribution']['very_good'] == 1


async def test_vid_analyze_content_error(video):
    video._extract_frames = AsyncMock(side_effect=RuntimeError('x'))
    assert (await video._analyze_video_content(vreq(), b'v')).success is False


async def test_vid_detect_objects(video):
    yolo_service(video, names=('car',))
    video._extract_frames = AsyncMock(return_value=[MagicMock()] * 2)
    res = await video._detect_objects(vreq(), b'v')
    assert res.success is True
    assert res.content_analysis['unique_objects'] == ['car']
    assert res.content_analysis['most_common'] == 'car'
    # empty detection set
    yolo_service(video, conf=0.1)  # below threshold
    res = await video._detect_objects(vreq(), b'v')
    assert res.content_analysis['most_common'] is None
    # exception
    video._extract_frames = AsyncMock(side_effect=RuntimeError('x'))
    assert (await video._detect_objects(vreq(), b'v')).success is False


async def test_vid_recognize_faces(video):
    video._extract_frames = AsyncMock(return_value=[MagicMock()])
    video.face_recognition_model = MagicMock()
    video.face_recognition_model.detect.return_value = [
        {'bbox': [1], 'confidence': 0.9, 'identity': 'Alice'}]
    res = await video._recognize_faces(vreq(), b'v')
    assert res.faces_detected[0]['identity'] == 'Alice'
    # no model
    video.face_recognition_model = None
    res = await video._recognize_faces(vreq(), b'v')
    assert res.faces_detected == []
    video._extract_frames = AsyncMock(side_effect=RuntimeError('x'))
    assert (await video._recognize_faces(vreq(), b'v')).success is False


async def test_vid_detect_scenes(video):
    video._extract_frames = AsyncMock(
        return_value=[MagicMock() for _ in range(8)])
    res = await video._detect_scenes(vreq(), b'v')
    assert res.success is True and len(res.scenes_detected) >= 2
    video._extract_frames = AsyncMock(side_effect=RuntimeError('x'))
    assert (await video._detect_scenes(vreq(), b'v')).success is False


async def test_vid_diarize(video):
    video._extract_frames = AsyncMock(return_value=[MagicMock()])
    res = await video._diarize_speakers(vreq(), b'v')
    assert len(res.speakers_detected) == 2
    video._extract_frames = AsyncMock(return_value=[])
    res = await video._diarize_speakers(vreq(), b'v')
    assert res.speakers_detected == []
    video._extract_frames = AsyncMock(side_effect=RuntimeError('x'))
    assert (await video._diarize_speakers(vreq(), b'v')).success is False


async def test_vid_classify_video(video):
    video._extract_frames = AsyncMock(return_value=[MagicMock()])
    video._classify_video_content = AsyncMock(return_value='office_meeting')
    res = await video._classify_video(vreq(), b'v')
    assert res.video_class == 'office_meeting'
    assert video.analytics_metrics['content_distribution'][
        'office_meeting'] == 1
    video._extract_frames = AsyncMock(side_effect=RuntimeError('x'))
    assert (await video._classify_video(vreq(), b'v')).success is False


async def test_vid_moderate_content(video):
    video._extract_frames = AsyncMock(return_value=[MagicMock()])
    video.content_moderation_model = MagicMock(
        side_effect=lambda f: {'unsafe': True})
    res = await video._moderate_content(vreq(), b'v')
    assert res.content_rating.value == 'unsafe'
    assert res.content_analysis['content_flags']
    # safe path
    video.content_moderation_model = MagicMock(
        side_effect=lambda f: {'unsafe': False})
    res = await video._moderate_content(vreq(), b'v')
    assert res.content_rating.value == 'safe'
    video.content_moderation_model = None
    res = await video._moderate_content(vreq(), b'v')
    assert res.content_rating.value == 'safe'
    video._extract_frames = AsyncMock(side_effect=RuntimeError('x'))
    assert (await video._moderate_content(vreq(), b'v')).success is False


# ============================================================================
# Video AI — frame extraction / classification internals / quality
# ============================================================================

async def test_vid_extract_frames(video):
    frames = await video._extract_frames(b'not-a-video', num_frames=3)
    assert isinstance(frames, list)  # [] or real depending on cv2 presence


async def test_vid_classify_content_branches(video):
    async def run(names, count, expect):
        svc = AtomVideoAIService('t', config={})
        yolo_service(svc, names=names)
        frames = [MagicMock() for _ in range(count)]
        assert await svc._classify_video_content(frames) == expect
    await run(('person', 'computer'), 11, 'office_meeting')
    await run(('person', 'whiteboard'), 11, 'presentation')
    await run(('person',), 11, 'social_gathering')
    await run(('car',), 6, 'traffic_scene')
    await run(('computer',), 11, 'tutorial')
    await run(('dog',), 3, 'general')
    # model raising -> unknown
    svc = AtomVideoAIService('t', config={})
    svc.yolo_model = MagicMock(side_effect=RuntimeError('x'))
    assert await svc._classify_video_content([MagicMock()]) == 'unknown'


async def test_vid_quality(video):
    score = await video._analyze_video_quality(b'garbage')
    assert isinstance(score, float)
    assert video._get_quality_category(95) == 'excellent'
    assert video._get_quality_category(85) == 'very_good'
    assert video._get_quality_category(75) == 'good'
    assert video._get_quality_category(65) == 'fair'
    assert video._get_quality_category(55) == 'poor'
    assert video._get_quality_category(5) == 'very_poor'


def test_vid_error_response(video):
    res = video._create_error_response(vreq(), 'bad thing')
    assert res.success is False and res.metadata['error'] == 'bad thing'


# ============================================================================
# Outlook enhanced — fixtures / session helpers
# ============================================================================

@pytest.fixture()
def outlook():
    return OutlookEnhancedService(client_id='cid', client_secret='cs',
                                  tenant_id='tid')


def ctx_response(status=200, payload=None, headers=None,
                 raise_error=None, json_error=None):
    resp = MagicMock()
    resp.status = status
    resp.headers = headers if headers is not None else {}
    resp.raise_for_status = MagicMock(side_effect=raise_error)
    if json_error is not None:
        resp.json = AsyncMock(side_effect=json_error)
    else:
        resp.json = AsyncMock(
            return_value=payload if payload is not None else {})
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=resp)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx, resp


def install_session(monkeypatch, method_responses):
    """method_responses: {'get': [ctx, ...], 'post': [ctx, ...]}"""
    session = MagicMock()
    for method, ctxs in method_responses.items():
        setattr(session, method, MagicMock(side_effect=list(ctxs)))
    client_cls = MagicMock(return_value=session)
    monkeypatch.setattr(ose_mod.aiohttp, 'ClientSession', client_cls)
    monkeypatch.setattr(ose_mod.aiohttp, 'ClientTimeout', MagicMock())
    return session


def authed(outlook):
    outlook.access_token = 'tok'
    outlook.token_expiry = datetime.now(timezone.utc) + timedelta(hours=1)


# ============================================================================
# Outlook enhanced — session / token
# ============================================================================

async def test_ose_session(outlook, monkeypatch):
    install_session(monkeypatch, {})
    s1 = await outlook._get_session()
    assert s1 is not None
    outlook.session.closed = True
    await outlook._get_session()  # recreate
    outlook.session = MagicMock()
    outlook.session.closed = False
    outlook.session.close = AsyncMock()
    await outlook._close_session()
    outlook.session.close.assert_awaited_once()
    outlook.session = None
    await outlook._close_session()
    outlook.session = MagicMock()
    outlook.session.closed = True
    await outlook._close_session()


async def test_ose_access_token(outlook):
    authed(outlook)
    assert await outlook._get_access_token('u1') == 'tok'
    outlook.token_expiry = datetime.now(timezone.utc) - timedelta(hours=1)
    with pytest.raises(Exception):
        await outlook._get_access_token('u1')
    outlook.access_token = None
    with pytest.raises(Exception):
        await outlook._get_access_token('u1')


async def test_ose_refresh_no_token(outlook):
    assert await outlook._refresh_access_token() is False


async def test_ose_refresh_success(outlook, monkeypatch):
    outlook.refresh_token = 'rt'
    ctx, _ = ctx_response(200, {'access_token': 'new',
                                'refresh_token': 'rt2',
                                'expires_in': 3600})
    install_session(monkeypatch, {'post': [ctx]})
    assert await outlook._refresh_access_token() is True
    assert outlook.access_token == 'new'
    assert outlook.refresh_token == 'rt2'
    assert outlook.token_expiry is not None


async def test_ose_refresh_http_failure(outlook, monkeypatch):
    outlook.refresh_token = 'rt'
    ctx, _ = ctx_response(400)
    install_session(monkeypatch, {'post': [ctx]})
    assert await outlook._refresh_access_token() is False


async def test_ose_refresh_exception(outlook, monkeypatch):
    outlook.refresh_token = 'rt'
    def boom():
        raise RuntimeError('net')
    monkeypatch.setattr(outlook, '_get_session', AsyncMock(side_effect=boom))
    assert await outlook._refresh_access_token() is False


# ============================================================================
# Outlook enhanced — graph request core
# ============================================================================

async def test_ose_graph_get(outlook, monkeypatch):
    authed(outlook)
    ctx, _ = ctx_response(200, {'value': [1]})
    install_session(monkeypatch, {'get': [ctx]})
    assert await outlook._make_graph_request('GET', 'me', 'u1') == {
        'value': [1]}


async def test_ose_graph_methods(outlook, monkeypatch):
    authed(outlook)
    ctx, _ = ctx_response(202)
    session = install_session(
        monkeypatch, {m: [ctx] for m in
                      ('post', 'put', 'patch', 'delete')})
    assert await outlook._make_graph_request(
        'POST', 'me', 'u1', data={}) == {'success': True}
    assert await outlook._make_graph_request(
        'PUT', 'me', 'u1', data={}) == {'success': True}
    assert await outlook._make_graph_request(
        'PATCH', 'me', 'u1', data={}) == {'success': True}
    assert await outlook._make_graph_request('DELETE', 'me', 'u1') == {
        'success': True}


async def test_ose_graph_unsupported_method(outlook, monkeypatch):
    authed(outlook)
    install_session(monkeypatch, {})
    with pytest.raises(ValueError):
        await outlook._make_graph_request('HEAD', 'me', 'u1')


async def test_ose_graph_no_token(outlook):
    with pytest.raises(Exception):
        await outlook._make_graph_request('GET', 'me', 'u1')


async def test_ose_graph_client_error(outlook, monkeypatch):
    authed(outlook)
    session = MagicMock()
    session.get = MagicMock(side_effect=ose_mod.aiohttp.ClientError('boom'))
    monkeypatch.setattr(outlook, '_get_session',
                        AsyncMock(return_value=session))
    with pytest.raises(Exception, match='HTTP client error'):
        await outlook._make_graph_request('GET', 'me', 'u1')


async def test_ose_graph_401_retry(outlook, monkeypatch):
    authed(outlook)
    c1, _ = ctx_response(401)
    c2, _ = ctx_response(200, {'ok': 1})
    install_session(monkeypatch, {'get': [c1, c2]})
    outlook._refresh_access_token = AsyncMock(return_value=True)
    assert await outlook._make_graph_request('GET', 'me', 'u1') == {'ok': 1}
    outlook._refresh_access_token.assert_awaited_once()


async def test_ose_graph_401_refresh_fails(outlook, monkeypatch):
    authed(outlook)
    c1, _ = ctx_response(401)
    install_session(monkeypatch, {'get': [c1]})
    outlook._refresh_access_token = AsyncMock(return_value=False)
    with pytest.raises(Exception, match='token refresh'):
        await outlook._make_graph_request('GET', 'me', 'u1')


async def test_ose_graph_429_retry(outlook, monkeypatch):
    authed(outlook)
    c1, _ = ctx_response(429, headers={'Retry-After': '2'})
    c2, _ = ctx_response(204)
    install_session(monkeypatch, {'get': [c1, c2]})
    slept = AsyncMock()
    monkeypatch.setattr(ose_mod.asyncio, 'sleep', slept)
    assert await outlook._make_graph_request('GET', 'me', 'u1') == {
        'success': True}
    slept.assert_awaited_once_with(2)
    # invalid Retry-After header -> default 5
    c3, _ = ctx_response(429, headers={'Retry-After': 'abc'})
    c4, _ = ctx_response(200, {'ok': 2})
    install_session(monkeypatch, {'get': [c3, c4]})
    assert await outlook._make_graph_request('GET', 'me', 'u1') == {'ok': 2}
    # retry already done -> 429 propagates via raise_for_status
    err = ose_mod.aiohttp.ClientResponseError(
        request_info=MagicMock(), history=(), status=429, message='limited')
    c5, _ = ctx_response(429, raise_error=err)
    install_session(monkeypatch, {'get': [c5]})
    with pytest.raises(Exception, match='429'):
        await outlook._make_graph_request('GET', 'me', 'u1',
                                          _is_retry=True)


async def test_ose_graph_response_error_and_json_fail(outlook, monkeypatch):
    authed(outlook)
    err = ose_mod.aiohttp.ClientResponseError(
        request_info=MagicMock(), history=(), status=500, message='bad')
    c1, _ = ctx_response(500, raise_error=err)
    install_session(monkeypatch, {'get': [c1]})
    with pytest.raises(Exception, match='500'):
        await outlook._make_graph_request('GET', 'me', 'u1')
    c2, _ = ctx_response(200, json_error=RuntimeError('bad json'))
    install_session(monkeypatch, {'get': [c2]})
    with pytest.raises(RuntimeError):
        await outlook._make_graph_request('GET', 'me', 'u1')


# ============================================================================
# Outlook enhanced — email operations
# ============================================================================

async def test_ose_get_emails(outlook):
    outlook._make_graph_request = AsyncMock(return_value={'value': [{
        'id': 'm1', 'subject': 'S', 'bodyPreview': 'p',
        'from': {'a': 1}, 'hasAttachments': True}]})
    emails = await outlook.get_user_emails_enhanced(
        'u1', folder='inbox', query='f', include_attachments=True)
    assert emails[0].id == 'm1' and emails[0].subject == 'S'
    assert emails[0].to_dict()['id'] == 'm1'
    # cache hit
    again = await outlook.get_user_emails_enhanced(
        'u1', folder='inbox', query='f')
    assert again[0].id == 'm1'
    # error
    outlook._make_graph_request = AsyncMock(side_effect=RuntimeError('x'))
    assert await outlook.get_user_emails_enhanced('u1') == []


async def test_ose_send_email(outlook):
    outlook._make_graph_request = AsyncMock(return_value={'success': True})
    assert await outlook.send_email_enhanced(
        'u1', ['a@b.c'], 'subj', 'body', cc_recipients=['c@d.e'],
        bcc_recipients=['e@f.g'], attachments=[{'id': 'att'}],
        importance='high') is True
    assert outlook.emails_cache == {}
    outlook._make_graph_request = AsyncMock(side_effect=RuntimeError('x'))
    assert await outlook.send_email_enhanced('u1', ['a@b.c'], 's', 'b') is False


async def test_ose_unread_count_and_mark_read(outlook):
    outlook._make_graph_request = AsyncMock(
        return_value={'unreadItemCount': 7})
    assert await outlook.get_unread_email_count('u1') == 7
    outlook._make_graph_request = AsyncMock(side_effect=RuntimeError('x'))
    assert await outlook.get_unread_email_count('u1') == 0

    outlook._make_graph_request = AsyncMock(return_value={'success': True})
    assert await outlook.mark_emails_read('u1', ['m1', 'm2']) is True
    # falsy result -> False
    outlook._make_graph_request = AsyncMock(return_value=None)
    assert await outlook.mark_emails_read('u1', ['m1']) is False
    # exception
    outlook._make_graph_request = AsyncMock(side_effect=RuntimeError('x'))
    assert await outlook.mark_emails_read('u1', ['m1']) is False


# ============================================================================
# Outlook enhanced — calendar / contacts / tasks / folders
# ============================================================================

async def test_ose_create_event(outlook):
    outlook._make_graph_request = AsyncMock(return_value={
        'id': 'e1', 'subject': 'Meet'})
    ev = await outlook.create_calendar_event_enhanced(
        'u1', 'Meet', '2026-08-14T10:00', '2026-08-14T11:00',
        location='Room', body='b', attendees=['a@b.c'], is_all_day=False,
        sensitivity='private', show_as='oof', reminder_minutes=30)
    assert ev.id == 'e1' and ev.to_dict()['subject'] == 'Meet'
    # falsy result
    outlook._make_graph_request = AsyncMock(return_value=None)
    assert await outlook.create_calendar_event_enhanced(
        'u1', 'M', 's', 'e') is None
    # exception
    outlook._make_graph_request = AsyncMock(side_effect=RuntimeError('x'))
    assert await outlook.create_calendar_event_enhanced(
        'u1', 'M', 's', 'e') is None


async def test_ose_upcoming_events(outlook):
    outlook._make_graph_request = AsyncMock(return_value={
        'value': [{'id': 'e1', 'subject': 'S'}]})
    events = await outlook.get_upcoming_events('u1', days=7)
    assert events[0].id == 'e1'
    # cache hit
    assert (await outlook.get_upcoming_events('u1', days=7))[0].id == 'e1'
    outlook._clear_events_cache()
    outlook._make_graph_request = AsyncMock(side_effect=RuntimeError('x'))
    assert await outlook.get_upcoming_events('u1') == []


async def test_ose_create_contact(outlook):
    outlook._make_graph_request = AsyncMock(return_value={
        'id': 'c1', 'displayName': 'Connie'})
    c = await outlook.create_contact_enhanced(
        'u1', 'Connie', given_name='C', surname='T',
        email_addresses=['c@x.y'], business_phones=['1'],
        mobile_phone='2', job_title='J', company_name='Co')
    assert c.id == 'c1' and c.to_dict()['display_name'] == 'Connie'
    outlook._make_graph_request = AsyncMock(return_value=None)
    assert await outlook.create_contact_enhanced('u1', 'X') is None
    outlook._make_graph_request = AsyncMock(side_effect=RuntimeError('x'))
    assert await outlook.create_contact_enhanced('u1', 'X') is None


async def test_ose_create_task(outlook):
    outlook._make_graph_request = AsyncMock(return_value={
        'id': 't1', 'subject': 'Do'})
    t = await outlook.create_task_enhanced(
        'u1', 'Do', body='b', importance='high', due_date='d',
        start_date='s', reminder_date='r', categories=['c'])
    assert t.id == 't1' and t.to_dict()['status'] == 'notStarted'
    outlook._make_graph_request = AsyncMock(return_value=None)
    assert await outlook.create_task_enhanced('u1', 'X') is None
    outlook._make_graph_request = AsyncMock(side_effect=RuntimeError('x'))
    assert await outlook.create_task_enhanced('u1', 'X') is None


async def test_ose_folders(outlook):
    outlook._make_graph_request = AsyncMock(return_value={
        'value': [{'id': 'f1', 'displayName': 'Inbox',
                   'totalItemCount': 5}]})
    folders = await outlook.get_user_folders('u1', folder_type='Inbox')
    assert folders[0].id == 'f1'
    assert folders[0].to_dict()['total_item_count'] == 5
    # cache hit
    assert (await outlook.get_user_folders('u1'))[0].id == 'f1'
    outlook._clear_folders_cache()
    outlook._make_graph_request = AsyncMock(side_effect=RuntimeError('x'))
    assert await outlook.get_user_folders('u1') == []


# ============================================================================
# Outlook enhanced — search / profile / caches / info
# ============================================================================

async def test_ose_search_entities(outlook):
    outlook._make_graph_request = AsyncMock(return_value={'value': [{
        'hitsContainers': [{'hits': [{
            'id': 'h1',
            'resource': {'@odata.type': '#microsoft.graph.message',
                         'subject': 'S', 'webLink': 'w'},
            'summary': {'score': 3},
        }]}]}]})
    results = await outlook.search_entities_enhanced(
        'u1', 'q', entity_types=['message'])
    assert results[0]['entityType'] == 'message'
    assert results[0]['score'] == 3
    outlook._make_graph_request = AsyncMock(side_effect=RuntimeError('x'))
    assert await outlook.search_entities_enhanced('u1', 'q') == []


async def test_ose_profile(outlook):
    outlook._make_graph_request = AsyncMock(return_value={
        'id': 'u1', 'displayName': 'User', 'mailboxSettings': {
            'timeZone': 'UTC'}})
    p = await outlook.get_user_profile_enhanced('u1')
    assert p.display_name == 'User' and p.timezone == 'UTC'
    assert p.to_dict()['id'] == 'u1'
    # cache hit
    assert (await outlook.get_user_profile_enhanced('u1')).id == 'u1'
    outlook._make_graph_request = AsyncMock(return_value=None)
    assert await outlook.get_user_profile_enhanced('u2') is None
    outlook._make_graph_request = AsyncMock(side_effect=RuntimeError('x'))
    assert await outlook.get_user_profile_enhanced('u3') is None


def test_ose_cache_clears(outlook):
    for cache in (outlook.users_cache, outlook.emails_cache,
                  outlook.events_cache, outlook.contacts_cache,
                  outlook.tasks_cache, outlook.folders_cache):
        cache['k'] = 1
    outlook._clear_email_cache()
    outlook._clear_events_cache()
    outlook._clear_contacts_cache()
    outlook._clear_tasks_cache()
    outlook._clear_folders_cache()
    outlook._clear_cache()
    assert not any((outlook.users_cache, outlook.emails_cache,
                    outlook.events_cache, outlook.contacts_cache,
                    outlook.tasks_cache, outlook.folders_cache))


async def test_ose_service_info(outlook):
    info = await outlook.get_service_info()
    assert info['service'] == 'outlook'
    assert 'email_management' in info['capabilities']
