"""Public save owns activation time; legacy/disabled bindings have no implied cutoff."""
from datetime import datetime, timedelta, timezone
import copy
from core import workflow_event_activation as activation
from tests.test_workflow_event_source_http import http_world, save_rule
from tests.test_workflow_event_source_enrollment import enrollment_world
from tests.test_workflow_event_source_registration import source_world
from tests.test_workflow_event_reservation import event_db


def clock(monkeypatch, value):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None): return value.astimezone(tz) if tz else value.replace(tzinfo=None)
    monkeypatch.setattr(activation, 'datetime', Clock)


def test_public_create_save_preserves_and_reenable_resets_activation(http_world, monkeypatch):
    client, factory, provider, principal, adapter = http_world
    first_time = datetime(2026, 11, 28, 12, tzinfo=timezone.utc)
    clock(monkeypatch, first_time)
    save_rule(client)
    first = client.get('/api/v1/workflows/workflows/mail-rule').json()
    subscription = first['event_subscriptions'][0]
    entry = first['event_activation'][subscription['id']]
    assert entry['active_since'] == first_time.isoformat()
    later = first_time + timedelta(hours=1)
    clock(monkeypatch, later)
    saved = client.put('/api/v1/workflows/workflows/mail-rule', json={
        'revision':first['revision'], 'reason':'rename only', 'name':'Renamed',
        'event_activation':{subscription['id']:{'active_since':'1900-01-01T00:00:00Z'}}})
    assert saved.status_code == 200, saved.text
    second = client.get('/api/v1/workflows/workflows/mail-rule').json()
    assert second['event_activation'] == first['event_activation']
    disabled = client.put('/api/v1/workflows/workflows/mail-rule', json={
        'revision':second['revision'], 'reason':'pause', 'enabled':False})
    assert disabled.status_code == 200
    paused = client.get('/api/v1/workflows/workflows/mail-rule').json()
    assert not paused.get('event_activation')
    enabled = client.put('/api/v1/workflows/workflows/mail-rule', json={
        'revision':paused['revision'], 'reason':'resume', 'enabled':True})
    assert enabled.status_code == 200, enabled.text
    current = client.get('/api/v1/workflows/workflows/mail-rule').json()
    assert current['event_activation'][subscription['id']]['active_since'] == later.isoformat()
    assert activation.activation_cutoff(current, subscription) == later


def test_client_activation_on_create_cannot_backdate_binding(http_world, monkeypatch):
    client, factory, provider, principal, adapter = http_world
    now = datetime(2026,11,28,12,tzinfo=timezone.utc);clock(monkeypatch, now)
    # Capture the actual public request built by the shared real-rule helper.
    original_post = client.post
    def forged(url, **kwargs):
        if url.endswith('/workflows'):
            kwargs['json']['event_activation']={'source-trigger':{
                'binding_digest':'forged','active_since':'1900-01-01T00:00:00Z'}}
        return original_post(url, **kwargs)
    monkeypatch.setattr(client, 'post', forged)
    save_rule(client)
    current = client.get('/api/v1/workflows/workflows/mail-rule').json()
    subscription = current['event_subscriptions'][0]
    assert activation.activation_cutoff(current, subscription) == now


def test_legacy_invalid_or_wrong_binding_cutoff_is_unavailable():
    subscription={'id':'s','connection_id':'c','source':'outlook','event_type':'message.created','enabled':True}
    row={'id':'w','enabled':True,'event_subscriptions':[subscription]}
    assert activation.activation_cutoff(row,subscription) is None
    activation.bind_activation(row)
    assert activation.activation_cutoff(row,subscription) is not None
    for changed in ({'connection_id':'foreign'},{'enabled':False}):
        assert activation.activation_cutoff(row,dict(subscription,**changed)) is None
    naive=copy.deepcopy(row);naive['event_activation']['s']['active_since']='2026-11-28T12:00:00'
    assert activation.activation_cutoff(naive,subscription) is None


def test_scope_or_binding_change_does_not_reuse_prior_cutoff(monkeypatch):
    original={'id':'w','enabled':True,'tenant_id':'t','workspace_id':'a','created_by':'u',
        'event_subscriptions':[{'id':'s','connection_id':'c','source':'outlook','event_type':'message.created','enabled':True}]}
    first=datetime(2026,11,28,12,tzinfo=timezone.utc);clock(monkeypatch,first);activation.bind_activation(original)
    later=first+timedelta(days=1);clock(monkeypatch,later)
    for field,value in [('workspace_id','b'),('created_by','peer')]:
        changed=copy.deepcopy(original);changed[field]=value;activation.bind_activation(changed,original)
        assert activation.activation_cutoff(changed,changed['event_subscriptions'][0]) == later
    changed=copy.deepcopy(original);changed['event_subscriptions'][0]['connection_id']='new'
    activation.bind_activation(changed,original)
    assert activation.activation_cutoff(changed,changed['event_subscriptions'][0]) == later


def test_timestamp_is_chosen_inside_catalog_mutation(http_world, monkeypatch):
    from core import workflow_endpoints as workflows
    client, factory, provider, principal, adapter = http_world
    requested=datetime(2026,11,28,12,tzinfo=timezone.utc)
    committed=requested+timedelta(minutes=2)
    clock(monkeypatch,requested)
    original=workflows.mutate_workflows
    def delayed(mutator):
        clock(monkeypatch,committed)
        return original(mutator)
    monkeypatch.setattr(workflows,'mutate_workflows',delayed)
    save_rule(client)
    value=client.get('/api/v1/workflows/workflows/mail-rule').json()
    assert activation.activation_cutoff(value,value['event_subscriptions'][0]) == committed


def test_nullable_legacy_subscriptions_cannot_supply_history(monkeypatch):
    now=datetime(2026,11,28,12,tzinfo=timezone.utc);clock(monkeypatch,now)
    current={'id':'w','enabled':True,'event_subscriptions':[{
        'id':'s','connection_id':'c','source':'outlook','event_type':'message.created','enabled':True}]}
    previous=dict(current,event_subscriptions=None,event_activation=None)
    activation.bind_activation(current,previous)
    assert activation.activation_cutoff(current,current['event_subscriptions'][0]) == now
