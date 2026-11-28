"""Server-owned event binding activation cutoffs for future catch-up admission.

This is not an authentication boundary. Callers use persisted, scoped workflow
material; incoming editor timestamps must never select a catch-up window.
"""
from datetime import datetime, timezone
import hashlib
import json


def binding_digest(subscription):
    if not isinstance(subscription, dict):
        return None
    fields = ('id', 'connection_id', 'source', 'event_type')
    if any(not isinstance(subscription.get(k), str) or not subscription[k] for k in fields):
        return None
    return hashlib.sha256(json.dumps({k: subscription[k] for k in fields},
        sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def activation_cutoff(workflow, subscription):
    if (not isinstance(workflow, dict) or not isinstance(subscription, dict)
            or workflow.get('enabled') is not True or subscription.get('enabled') is not True):
        return None
    digest = binding_digest(subscription)
    if digest is None:
        return None
    entries = workflow.get('event_activation')
    entry = entries.get(subscription['id']) if isinstance(entries, dict) else None
    if not digest or not isinstance(entry, dict) or set(entry) != {'binding_digest', 'active_since'}:
        return None
    if entry['binding_digest'] != digest or not isinstance(entry['active_since'], str):
        return None
    try:
        value = datetime.fromisoformat(entry['active_since'].replace('Z', '+00:00'))
        return value.astimezone(timezone.utc) if value.tzinfo is not None else None
    except ValueError:
        return None


def bind_activation(material, baseline=None):
    """Preserve only unchanged active bindings in unchanged owner scope."""
    previous = baseline if isinstance(baseline, dict) else {}
    same_scope = all(material.get(k) == previous.get(k) for k in
        ('id', 'workflow_id', 'tenant_id', 'workspace_id', 'created_by'))
    prior_subscriptions = previous.get('event_subscriptions')
    prior_subscriptions = prior_subscriptions if isinstance(prior_subscriptions, (list, tuple)) else []
    old = {s['id']: s for s in prior_subscriptions
           if isinstance(s, dict) and isinstance(s.get('id'), str)}
    entries = {}
    now = datetime.now(timezone.utc).isoformat()
    if material.get('enabled') is True:
        subscriptions = material.get('event_subscriptions') or []
        for subscription in subscriptions:
            if not isinstance(subscription, dict) or subscription.get('enabled') is not True:
                continue
            digest = binding_digest(subscription)
            if digest is None:
                raise ValueError('Invalid event activation binding')
            prior = old.get(subscription['id'])
            cutoff = (activation_cutoff(previous, prior) if same_scope and isinstance(prior, dict)
                      and binding_digest(prior) == digest else None)
            entries[subscription['id']] = {'binding_digest': digest,
                'active_since': cutoff.isoformat() if cutoff is not None else now}
    if entries:
        material['event_activation'] = entries
    else:
        material.pop('event_activation', None)
