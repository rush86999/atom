import asyncio, json
from datetime import datetime, timezone
from urllib.parse import quote
import pytest
from core.workflow_event_source_adapters import DeltaResetRequired, OutlookMailSourceAdapter
from integrations.microsoft365_service import Microsoft365Service

BASE = 'https://graph.microsoft.com/v1.0'
U, F = 'user-id', "folder'id"
B = {'user_id': U, 'folder_id': F}
C = {'access_token': 'token'}
T = BASE + '/users/' + quote(U, safe='') + '/mailFolders/' + quote(F, safe='') + '/messages/delta'
N = T + '?$skiptoken=opaque%2Fvalue'
O = BASE + "/users('user-id')/mailFolders('folder%27id')/messages/delta?$deltatoken=opaque%2Bvalue"

class G:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    async def __call__(self, method, url, token, *args, **kwargs):
        self.calls.append((method, url, token, args, kwargs))
        return self.responses.pop(0)

def make(responses):
    s = Microsoft365Service(config={})
    s._make_graph_request = G(responses)
    return s, s._make_graph_request

def ids():
    return [{'status': 'success', 'data': {'id': U}}, {'status': 'success', 'data': {'id': F}}]

def page(actual, cursor=None):
    return asyncio.run(OutlookMailSourceAdapter(service=actual).read_delta_page(B, C, cursor))

def test_resolve_is_scoped():
    s, g = make(ids())
    assert asyncio.run(OutlookMailSourceAdapter(service=s).resolve_delta_binding(C)) == B
    assert [c[1] for c in g.calls] == [BASE + '/me?$select=id', BASE + '/me/mailFolders/Inbox?$select=id']
    assert all(c[2:] == ('token', (), {}) for c in g.calls)

def test_initial_and_empty_next_page():
    s, g = make(ids() + [{'status': 'success', 'data': {'value': [], '@odata.nextLink': N}}])
    assert page(s) == {'items': [], 'cursor': N, 'complete': False}
    assert g.calls[2][1] == T + '?changeType=created&$select=id,createdDateTime&$top=50'
    assert g.calls[2][2:] == ('token', (), {})

def test_odata_cursor_is_forwarded_and_unchanged_delta_is_done():
    s, g = make(ids() + [{'status': 'success', 'data': {'value': [], '@odata.deltaLink': O}}])
    assert page(s, O) == {'items': [], 'cursor': O, 'complete': True}
    assert g.calls[2][1] == O

def test_changed_binding_is_refused():
    s, g = make([{'status': 'success', 'data': {'id': 'other'}}, {'status': 'success', 'data': {'id': F}}])
    with pytest.raises(ValueError): page(s, N)
    assert len(g.calls) == 2

def test_urls_links_and_loops_are_rejected():
    bad = [BASE + '/users/other/mailFolders/folder%27id/messages/delta', BASE + '/users/user-id/mailFolders/other/messages/delta',
           BASE + '/users/user-id/mailFolders/folder%27id/messages/delta#x', 'https://evil/v1.0/users/user-id/mailFolders/folder%27id/messages/delta',
           'http://graph.microsoft.com/v1.0/users/user-id/mailFolders/folder%27id/messages/delta', 'https://graph.microsoft.com:444/v1.0/users/user-id/mailFolders/folder%27id/messages/delta',
           'https://u:p@graph.microsoft.com/v1.0/users/user-id/mailFolders/folder%27id/messages/delta', BASE + '/users/user-id/mailFolders/folder%27id/messages/delta/%2e%2e']
    for cursor in bad:
        s, g = make(ids())
        with pytest.raises(ValueError): page(s, cursor)
        assert len(g.calls) == 2
    bad_pages = [{}, {'value': [], '@odata.nextLink': 1}, {'value': [], '@odata.nextLink': ''},
                 {'value': [], '@odata.nextLink': N, '@odata.deltaLink': N}, {'value': []},
                 {'value': 'x', '@odata.nextLink': N}, {'value': [{}] * 101, '@odata.nextLink': N},
                 {'value': [], '@odata.deltaLink': 'https://evil/cursor'}]
    for data in bad_pages:
        s, _ = make(ids() + [{'status': 'success', 'data': data}])
        with pytest.raises(ValueError): page(s)
    s, _ = make(ids() + [{'status': 'success', 'data': {'value': [], '@odata.nextLink': N}}])
    with pytest.raises(ValueError): page(s, N)

def test_reset_and_unavailable_errors_are_typed_and_safe():
    reset = [{'status': 'error', 'code': 410, 'message': 'secret'},
             {'status': 'error', 'code': 400, 'message': json.dumps({'error': {'code': 'syncStateNotFound'}})}]
    for response in reset:
        s, _ = make(ids() + [response])
        with pytest.raises(DeltaResetRequired) as exc: page(s, N)
        assert str(exc.value) == 'Delta cursor must be reset'
    s, _ = make(ids() + [{'status': 'error', 'code': 500, 'message': 'token secret'}])
    with pytest.raises(ValueError) as exc: page(s, N)
    assert str(exc.value) == 'Delta page is unavailable'

def test_rows_are_normalized_tombstones_ignored_and_bad_rows_refused():
    good = {'value': [{'@removed': {'reason': 'deleted'}},
                      {'id': 'm1', 'createdDateTime': '2026-01-02T03:04:05+02:00'}],
            '@odata.deltaLink': N}
    s, _ = make(ids() + [{'status': 'success', 'data': good}])
    assert page(s) == {'items': [{'id': 'm1', 'created_at': datetime(2026, 1, 2, 1, 4, 5, tzinfo=timezone.utc)}],
                       'cursor': N, 'complete': True}
    bad = [{'createdDateTime': '2026-01-01T00:00:00Z'}, {'id': '', 'createdDateTime': '2026-01-01T00:00:00Z'},
           {'id': 'm1'}, {'id': 'm1', 'createdDateTime': 'bad'},
           {'id': 'm1', 'createdDateTime': '2026-01-01T00:00:00'}, {'id': 1, 'createdDateTime': '2026-01-01T00:00:00Z'},
           'not-an-object']
    for row in bad:
        s, _ = make(ids() + [{'status': 'success', 'data': {'value': [row], '@odata.deltaLink': N}}])
        with pytest.raises(ValueError): page(s)

def test_credentials_have_no_global_fallback():
    for credentials in (None, {}, {'access_token': ''}, {'access_token': '  '}):
        s, g = make([])
        with pytest.raises(ValueError): asyncio.run(OutlookMailSourceAdapter(service=s).resolve_delta_binding(credentials))
        assert g.calls == []
def test_legacy_material_is_unchanged():
    adapter = OutlookMailSourceAdapter(service=object())
    assert adapter.material({'prepared_at': '2026-01-01T00:00:00+00:00', 'callback_url': 'https://cb'}) == {
        'resource': "/me/mailFolders('Inbox')/messages", 'change_type': 'created,deleted',
        'callback_url': 'https://cb', 'expires_at': '2026-01-03T23:00:00Z'}


@pytest.mark.parametrize('suffix', ['#fragment', '/%2e%2e', '/extra', '?x=has space'])
def test_cursor_rejects_unsafe_suffix_before_transport(suffix):
    service, wire = make(ids())
    with pytest.raises(ValueError):
        page(service, T + suffix)
    assert len(wire.calls) == 2


def test_transport_exception_is_safe_and_cancellation_propagates(caplog):
    service, wire = make(ids())
    async def broken(*args, **kwargs):
        raise RuntimeError('private-token opaque-cursor')
    service._make_graph_request = broken
    with pytest.raises(ValueError, match='Delta transport is unavailable') as caught:
        page(service)
    assert 'private-token' not in str(caught.value)
    assert 'opaque-cursor' not in caplog.text
    async def cancelled(*args, **kwargs):
        raise asyncio.CancelledError()
    service._make_graph_request = cancelled
    with pytest.raises(asyncio.CancelledError):
        page(service)


@pytest.mark.parametrize('cursor', [
    T.replace(U, U.upper()), T.replace('v1.0', 'beta'),
    T.replace('graph.microsoft.com', 'graph.microsoft.com.evil'),
    T.replace('/users/', '/me/'), T.replace('/messages/', '/messages/%2e%2e/'),
])
def test_binding_and_endpoint_are_exact(cursor):
    service, wire = make(ids())
    with pytest.raises(ValueError):
        page(service, cursor)
    assert len(wire.calls) == 2
