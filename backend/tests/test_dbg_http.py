import asyncio
from unittest.mock import Mock, patch
import integrations.gmail_service as mod

def test_dbg_http():
    svc = mod.GmailService.__new__(mod.GmailService)
    svc.tenant_id = "default"; svc.config = {}; svc.service = None
    svc.scopes = []; svc.credentials_path = "c.json"; svc.token_path = "t.json"
    service = Mock()
    page1 = Mock(); page1.execute.return_value = {"messages": [{"id": "m1"}], "nextPageToken": "p2"}
    page2 = Mock(); page2.execute.side_effect = mod.HttpError(Mock(status=500), b"")
    service.users.return_value.messages.return_value.list.side_effect = [page1, page2]
    svc._get_service_with_token = Mock(return_value=service)
    svc.get_message = Mock(return_value={"id": "m1"})
    res = svc.get_messages(max_results=10)
    assert res == [{"id": "m1"}]
    import traceback
    print("list call count:", service.users.return_value.messages.return_value.list.call_count)
