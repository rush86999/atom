"""Native connector adapters for the shared source enrollment lifecycle.

Only connector-specific API/resource translation lives here; ownership,
reservations, retries and local activation remain in the general services.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from urllib.parse import quote, unquote, urlsplit
from core.workflow_event_source_enrollment import EnrollmentRefused


class DeltaResetRequired(Exception):
    """Provider invalidated the cursor; never silently advance coverage."""

def _id(value):
    if (not isinstance(value, str) or not value or value.strip() != value
            or any(ord(c) < 32 or ord(c) == 127 for c in value)
            or any(p in ('.', '..') for p in value.replace('\\', '/').split('/'))):
        raise ValueError('Delta binding id is invalid')
    return value

def _odata(segment, name):
    prefix = name + '('
    if not segment.casefold().startswith(prefix.casefold()) or not segment.endswith(')'):
        return None
    value = segment[len(prefix):-1]
    if len(value) > 1 and value[0] == value[-1] == "'":
        value = value[1:-1]
    return unquote(value) if value else None

def _path_id(parts, name):
    if not parts: raise ValueError('Delta cursor is invalid')
    head = parts.pop(0)
    if head.casefold() == name:
        if not parts: raise ValueError('Delta cursor is invalid')
        return unquote(parts.pop(0))
    return _odata(head, name)

def _cursor(cursor, user_id, folder_id):
    if not isinstance(cursor, str) or not cursor or any(c.isspace() for c in cursor):
        raise ValueError('Delta cursor is invalid')
    try:
        parts = urlsplit(cursor); port = parts.port
    except ValueError:
        raise ValueError('Delta cursor is invalid') from None
    if (parts.scheme.lower() != 'https' or parts.hostname != 'graph.microsoft.com'
            or parts.username is not None or parts.password is not None
            or parts.fragment or (port is not None and port != 443)):
        raise ValueError('Delta cursor is invalid')
    path = parts.path.split('/')
    if (len(path) < 3 or path[0] or path[1] != 'v1.0'
            or any(p in ('.', '..') for p in unquote(parts.path).replace('\\', '/').split('/'))):
        raise ValueError('Delta cursor is invalid')
    parts = path[2:]
    if _path_id(parts, 'users') != user_id or _path_id(parts, 'mailfolders') != folder_id:
        raise ValueError('Delta cursor is invalid')
    if (len(parts) != 2 or parts[0].casefold() != 'messages'
            or parts[1].casefold() != 'delta'):
        raise ValueError('Delta cursor is invalid')
    return cursor

def _reset_required(response):
    body = response.get('message')
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except (TypeError, ValueError):
            return False
    error = body.get('error') if isinstance(body, dict) else None
    return isinstance(error, dict) and error.get('code') == 'syncStateNotFound'


class OutlookMailSourceAdapter:
    event_types = ('message.created',)
    oauth_provider = 'microsoft'
    binds_provider_identity = True
    registration_options = {'message_id_type': 'immutable'}
    lifecycle_events = ('reauthorizationRequired', 'missed', 'subscriptionRemoved')

    def __init__(self, source='outlook', service=None):
        if source not in ('outlook', 'microsoft365'):
            raise ValueError('Unsupported native mail source')
        self.source = source
        if service is None:
            from integrations.microsoft365_service import Microsoft365Service
            service = Microsoft365Service(config={})
        self.service = service

    @staticmethod
    def _token(credentials):
        token = credentials.get('access_token') if isinstance(credentials, dict) else None
        if (not isinstance(token, str) or not token.strip()
                or any(ord(c) < 32 or ord(c) == 127 for c in token)):
            raise ValueError('Delta credentials are unavailable')
        return token

    async def _delta_request(self, token, url, *, immutable_ids=False):
        # Opaque cursors and transport exceptions may contain credentials. Keep
        # them out of caller-visible errors; cancellation still propagates.
        try:
            return await self.service._make_graph_request('GET', url, token,
                **({'prefer_immutable_id': True} if immutable_ids else {}))
        except Exception:
            raise ValueError('Delta transport is unavailable') from None

    async def _resolve_id(self, token, path):
        response = await self._delta_request(token, 'https://graph.microsoft.com/v1.0' + path)
        data = response.get('data') if isinstance(response, dict) and response.get('status') == 'success' else None
        if not isinstance(data, dict):
            raise ValueError('Delta binding is unavailable')
        return _id(data.get('id'))

    async def resolve_delta_binding(self, credentials):
        token = self._token(credentials)
        return {'user_id': await self._resolve_id(token, '/me?$select=id'),
                'folder_id': await self._resolve_id(token, '/me/mailFolders/Inbox?$select=id')}

    async def read_delta_page(self, binding, credentials, cursor=None):
        if not isinstance(binding, dict):
            raise ValueError('Delta binding is unavailable')
        user_id, folder_id = _id(binding.get('user_id')), _id(binding.get('folder_id'))
        token = self._token(credentials)
        fresh = await self.resolve_delta_binding(credentials)
        if fresh != {'user_id': user_id, 'folder_id': folder_id}:
            raise ValueError('Delta binding changed')
        if cursor is None:
            url = ('https://graph.microsoft.com/v1.0/users/' + quote(user_id, safe='')
                   + '/mailFolders/' + quote(folder_id, safe='')
                   + '/messages/delta?changeType=created&$select=id,createdDateTime&$top=50')
        else:
            url = _cursor(cursor, user_id, folder_id)
        response = await self._delta_request(token, url, immutable_ids=True)
        if not isinstance(response, dict) or response.get('status') != 'success':
            if isinstance(response, dict) and (
                    (type(response.get('code')) is int and response['code'] == 410)
                    or _reset_required(response)):
                raise DeltaResetRequired('Delta cursor must be reset') from None
            raise ValueError('Delta page is unavailable') from None
        page = response.get('data'); values = page.get('value') if isinstance(page, dict) else None
        if not isinstance(values, list) or len(values) > 100: raise ValueError('Delta page is malformed') from None
        nxt, delta = page.get('@odata.nextLink'), page.get('@odata.deltaLink')
        if ((nxt is not None and (not isinstance(nxt, str) or not nxt))
                or (delta is not None and (not isinstance(delta, str) or not delta))):
            raise ValueError('Delta page links are malformed') from None
        if (nxt is None) == (delta is None):
            raise ValueError('Delta page must have one continuation') from None
        if nxt is not None:
            _cursor(nxt, user_id, folder_id)
            if cursor is not None and nxt == cursor:
                raise ValueError('Delta page cursor loop') from None
            link, complete = nxt, False
        else:
            _cursor(delta, user_id, folder_id)
            link, complete = delta, True
        items = []
        for row in values:
            if not isinstance(row, dict): raise ValueError('Delta page entry is malformed') from None
            if '@removed' in row:
                continue
            message_id, created = row.get('id'), row.get('createdDateTime')
            if (not isinstance(message_id, str) or not message_id
                    or message_id.strip() != message_id
                    or any(ord(c) < 32 or ord(c) == 127 for c in message_id)):
                raise ValueError('Delta entry identity is invalid') from None
            if not isinstance(created, str) or not created:
                raise ValueError('Delta entry time is invalid') from None
            try:
                stamp = datetime.fromisoformat(created.replace('Z', '+00:00'))
            except (TypeError, ValueError):
                raise ValueError('Delta entry time is invalid') from None
            if stamp.tzinfo is None:
                raise ValueError('Delta entry time is invalid') from None
            items.append({'id': message_id, 'created_at': stamp.astimezone(timezone.utc)})
        return {'items': items, 'cursor': link, 'complete': complete}

    @staticmethod
    def provider_binding(value):
        if not isinstance(value, dict) or set(value) != {'user_id', 'folder_id'}:
            raise ValueError('Native provider binding is invalid')
        return {name: _id(value[name]) for name in ('user_id', 'folder_id')}

    @staticmethod
    def _immutable_ids(document):
        if document is None or 'source_options' not in document:
            return False
        if document['source_options'] != {'message_id_type': 'immutable'}:
            raise ValueError('Native source identity mode is invalid')
        OutlookMailSourceAdapter.provider_binding(document.get('provider_binding'))
        return True

    def event_identity(self, message_id, *, document=None):
        message_id = _id(message_id)
        if self._immutable_ids(document):
            # Namespace by provider principal, not source generation, folder or
            # mutable message content. Connection/source scope is in the
            # existing event reservation key.
            principal = self.provider_binding(document['provider_binding'])['user_id']
            return 'message.created:' + hashlib.sha256(principal.encode()).hexdigest() + ':' + message_id
        return 'message.created:' + message_id

    def material(self, document):
        prepared = datetime.fromisoformat(document['prepared_at'])
        if prepared.tzinfo is None:
            raise ValueError('Source preparation time has no timezone')
        material = {'resource': "/me/mailFolders('Inbox')/messages", 'change_type': 'created,deleted',
                'callback_url': document['callback_url'],
                'expires_at': (prepared + timedelta(hours=71)).astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
        if 'provider_binding' in document:
            binding = self.provider_binding(document['provider_binding'])
            material['resource'] = ('/users/' + quote(binding['user_id'], safe='')
                + '/mailFolders/' + quote(binding['folder_id'], safe='') + '/messages')
        if document.get('lifecycle_events'):
            material['lifecycle_callback_url'] = document['callback_url']
        if self._immutable_ids(document):
            material['message_id_type'] = 'immutable'
        return material

    async def create(self, document, credentials, client_state):
        plan = self.material(document)
        lifecycle_kwargs = {}
        if 'lifecycle_callback_url' in plan:
            lifecycle_kwargs['lifecycle_notification_url'] = plan['lifecycle_callback_url']
        if plan.get('message_id_type') == 'immutable':
            lifecycle_kwargs['immutable_ids'] = True
        response = await self.service.create_subscription(credentials['access_token'],
            plan['resource'], plan['change_type'], plan['callback_url'], plan['expires_at'],
            client_state=client_state, **lifecycle_kwargs)
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

    async def message_event(self, notification, credentials, *, document=None):
        """Fetch real content; keep mutable read/flag metadata out of created-event identity."""
        message_id = (notification.get('resourceData') or {}).get('id')
        if not isinstance(message_id, str) or not message_id:
            raise ValueError('Notification message identity is unavailable')
        message_id = _id(message_id)
        fields = ['id', 'subject', 'from', 'toRecipients', 'ccRecipients', 'body',
                  'receivedDateTime', 'internetMessageId', 'hasAttachments']
        immutable_ids = self._immutable_ids(document)
        owner_path = '/me'
        if immutable_ids:
            binding = self.provider_binding(document['provider_binding'])
            owner_path = '/users/' + quote(binding['user_id'], safe='')
        response = await self.service._make_graph_request('GET', self.service.base_url +
            owner_path + '/messages/' + quote(message_id, safe='') + '?$select=' + ','.join(fields),
            credentials['access_token'], **({'prefer_immutable_id': True} if immutable_ids else {}))
        message = response.get('data') if response.get('status') == 'success' else None
        if not isinstance(message, dict) or message.get('id') != message_id:
            raise ValueError('Notification content is unavailable or mismatched')
        payload = {key: message[key] for key in fields if key in message}
        payload['message_id'] = message_id
        return {'event_type': 'message.created', 'provider_event_id': self.event_identity(message_id, document=document),
                'payload': payload}

    def verify(self, document, receipt, observed):
        return self._verify_plan(document, receipt, observed, self.material(document))

    def _verify_plan(self, document, receipt, observed, plan):
        if not isinstance(observed, dict) or observed.get('id') != receipt['subscription_id']:
            return False
        if any(observed.get(k) != plan[v] for k, v in (
                ('resource', 'resource'), ('changeType', 'change_type'), ('notificationUrl', 'callback_url'))):
            return False
        if ('lifecycle_callback_url' in plan
                and observed.get('lifecycleNotificationUrl') != plan['lifecycle_callback_url']):
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
