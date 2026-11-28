"""Native connector adapters for the shared source enrollment lifecycle.

Only connector-specific API/resource translation lives here; ownership,
reservations, retries and local activation remain in the general services.
"""
from datetime import datetime, timedelta, timezone
import hashlib
from urllib.parse import quote
from core.workflow_event_source_enrollment import EnrollmentRefused


class OutlookMailSourceAdapter:
    event_types = ('message.created',)
    oauth_provider = 'microsoft'

    def __init__(self, source='outlook', service=None):
        if source not in ('outlook', 'microsoft365'):
            raise ValueError('Unsupported native mail source')
        self.source = source
        if service is None:
            from integrations.microsoft365_service import Microsoft365Service
            service = Microsoft365Service(config={})
        self.service = service

    def material(self, document):
        prepared = datetime.fromisoformat(document['prepared_at'])
        if prepared.tzinfo is None:
            raise ValueError('Source preparation time has no timezone')
        return {'resource': "/me/mailFolders('Inbox')/messages", 'change_type': 'created,deleted',
                'callback_url': document['callback_url'],
                'expires_at': (prepared + timedelta(hours=71)).astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}

    async def create(self, document, credentials, client_state):
        plan = self.material(document)
        response = await self.service.create_subscription(credentials['access_token'],
            plan['resource'], plan['change_type'], plan['callback_url'], plan['expires_at'],
            client_state=client_state)
        if response.get('status') != 'success':
            code = response.get('code')
            if type(code) is int and code in (400, 401, 403, 404, 409, 422):
                raise EnrollmentRefused('Provider refused source enrollment')
            raise ValueError('Provider enrollment outcome is unavailable')
        data = response.get('data')
        return {'subscription_id': data.get('id') if isinstance(data, dict) else None}

    async def read(self, subscription_id, credentials):
        token = credentials.get('access_token')
        if not isinstance(token, str) or not token:
            return None
        response = await self.service._make_graph_request('GET',
            self.service.base_url + '/subscriptions/' + quote(subscription_id, safe=''), token)
        return response.get('data') if response.get('status') == 'success' else None

    def renewal_material(self, document, *, now):
        """Freeze a new lease separately; never mutate the enrollment plan."""
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise ValueError('Renewal time has no timezone')
        plan = self.material(document)
        return dict(plan, expires_at=(now + timedelta(hours=71)).astimezone(
            timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))

    def _renewal_plan(self, document, plan):
        original = self.material(document)
        if (not isinstance(plan, dict) or set(plan) != set(original)
                or any(plan.get(key) != original[key] for key in original if key != 'expires_at')):
            raise ValueError('Renewal material does not match enrollment')
        try:
            expiry = datetime.fromisoformat(plan['expires_at'].replace('Z', '+00:00'))
        except (ValueError, TypeError, AttributeError):
            raise ValueError('Renewal expiry is invalid') from None
        if expiry.tzinfo is None:
            raise ValueError('Renewal expiry has no timezone')
        return plan

    async def renew(self, document, credentials, plan):
        """One native PATCH only; the durable caller owns claims and recovery.

        Do not use the legacy renew_subscription wrapper: it catches ambiguous
        transport failures and logs exception text. Preserve uncertainty here.
        """
        plan = self._renewal_plan(document, plan)
        subscription_id = document.get('provider_subscription_id')
        token = credentials.get('access_token')
        if (not isinstance(subscription_id, str) or not subscription_id.strip()
                or not isinstance(token, str) or not token.strip()):
            raise ValueError('Renewal target or credential is unavailable')
        expiry = datetime.fromisoformat(plan['expires_at'].replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        if not now < expiry <= now + timedelta(hours=71):
            raise ValueError('Renewal expiry is outside the native lease window')
        response = await self.service._make_graph_request('PATCH', self.service.base_url +
            '/subscriptions/' + quote(subscription_id, safe=''), token,
            {'expirationDateTime': plan['expires_at']})
        if response.get('status') != 'success':
            code = response.get('code')
            if type(code) is int and code in (400, 401, 403, 404, 409, 422):
                raise EnrollmentRefused('Provider refused source renewal')
            raise ValueError('Provider renewal outcome is unavailable')
        # A success acknowledgement is not lease proof; the caller must GET.
        return {'subscription_id': subscription_id}

    def verify_renewal(self, document, receipt, observed, plan):
        """Verify a frozen lease supplied by the durable renewal arbiter."""
        try:
            plan = self._renewal_plan(document, plan)
        except ValueError:
            return False
        if (not isinstance(receipt, dict) or not isinstance(document.get('provider_subscription_id'), str)
                or not document['provider_subscription_id'].strip()
                or receipt.get('subscription_id') != document['provider_subscription_id']):
            return False
        return self._verify_plan(document, receipt, observed, plan)

    async def message_event(self, notification, credentials):
        """Fetch real content; keep mutable read/flag metadata out of created-event identity."""
        message_id = (notification.get('resourceData') or {}).get('id')
        if not isinstance(message_id, str) or not message_id:
            raise ValueError('Notification message identity is unavailable')
        fields = ['id', 'subject', 'from', 'toRecipients', 'ccRecipients', 'body',
                  'receivedDateTime', 'internetMessageId', 'hasAttachments']
        response = await self.service._make_graph_request('GET', self.service.base_url +
            '/me/messages/' + quote(message_id, safe='') + '?$select=' + ','.join(fields),
            credentials['access_token'])
        message = response.get('data') if response.get('status') == 'success' else None
        if not isinstance(message, dict) or message.get('id') != message_id:
            raise ValueError('Notification content is unavailable or mismatched')
        payload = {key: message[key] for key in fields if key in message}
        payload['message_id'] = message_id
        return {'event_type': 'message.created', 'provider_event_id': 'message.created:' + message_id,
                'payload': payload}

    def verify(self, document, receipt, observed):
        return self._verify_plan(document, receipt, observed, self.material(document))

    def _verify_plan(self, document, receipt, observed, plan):
        if not isinstance(observed, dict) or observed.get('id') != receipt['subscription_id']:
            return False
        if any(observed.get(k) != plan[v] for k, v in (
                ('resource', 'resource'), ('changeType', 'change_type'), ('notificationUrl', 'callback_url'))):
            return False
        try:
            expiry = datetime.fromisoformat(str(observed.get('expirationDateTime', '')).replace('Z', '+00:00'))
            expected_expiry = datetime.fromisoformat(plan['expires_at'].replace('Z', '+00:00'))
            if (expiry.tzinfo is None or expiry <= datetime.now(timezone.utc)
                    or expiry != expected_expiry):
                return False
        except ValueError:
            return False
        # Graph documents clientState as write-only/null on reads. Do not
        # invent a returned value; the actual callback must prove delivery.
        returned_state = observed.get('clientState')
        if returned_state is not None:
            if (not isinstance(returned_state, str)
                    or hashlib.sha256(returned_state.encode()).hexdigest() != document['receiver_state_digest']):
                return False
        return True


def source_adapter(source):
    if source in ('outlook', 'microsoft365'):
        return OutlookMailSourceAdapter(source)
    raise ValueError('Source enrollment is not supported by a registered adapter')


def source_event_catalog():
    return {source: [{'key': 'message.created', 'label': 'New email'}]
            for source in ('outlook', 'microsoft365')}
