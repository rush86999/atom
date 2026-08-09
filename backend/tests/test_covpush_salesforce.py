"""Coverage push + bug hunt for integrations/salesforce_service.py and
integrations/salesforce_routes.py.

Target: >=75% line coverage. TDD: failing test first, then minimal fix.

Bugs found (fixed):
- A1 (HIGH): GET /api/salesforce/search interpolates the user-supplied
  `query` raw into a SOSL FIND block — `FIND {{query}} ...` — and
  interpolates `object_types` unvalidated. Both are injection surfaces
  (SOSL breakout via `}` in the query; arbitrary clause injection via
  object_type values). Fixed via escape_sosl_string() + object-type
  allowlist validation (fail-closed).
- A2 (LOW): SalesforceService.health_check returned `str(e)` in the
  response payload (information leak).
- A3 (LOW): WorkspaceSyncService.health_check returned `str(e)` in the
  response payload (information leak).
"""

import json
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import HTTPException

from integrations import salesforce_service as sf_mod
from integrations import salesforce_routes as sf_routes
from simple_salesforce import SalesforceAuthenticationFailed


# ============================================================================
# salesforce_service
# ============================================================================

class _SfClient(MagicMock):
    pass


def _mock_sf(**attrs):
    sf = MagicMock()
    for key, value in attrs.items():
        setattr(sf, key, value)
    return sf


def _patch_auth_handler(**attrs):
    handler = MagicMock()
    for key, value in attrs.items():
        setattr(handler, key, value)
    return patch(
        "integrations.auth_handler_salesforce.salesforce_auth_handler",
        handler,
    ), handler


class TestGetSalesforceClient:
    @pytest.mark.asyncio
    async def test_success(self):
        auth = MagicMock()
        auth.ensure_valid_token = AsyncMock(return_value="tok-123")
        auth.instance_url = "https://acme.my.salesforce.com"
        client = _mock_sf()
        with patch(
            "integrations.auth_handler_salesforce.salesforce_auth_handler", auth
        ), patch.object(sf_mod, "Salesforce", return_value=client) as sf_cls:
            result = await sf_mod.get_salesforce_client("user-1")
        assert result is client
        sf_cls.assert_called_once_with(
            instance_url="https://acme.my.salesforce.com",
            session_id="tok-123",
            version="57.0",
        )
        client.query.assert_called_once_with("SELECT Id FROM User LIMIT 1")

    @pytest.mark.asyncio
    async def test_missing_token_data(self):
        auth = MagicMock()
        auth.ensure_valid_token = AsyncMock(return_value="")
        auth.instance_url = None
        with patch(
            "integrations.auth_handler_salesforce.salesforce_auth_handler", auth
        ):
            result = await sf_mod.get_salesforce_client("user-1")
        assert result is None

    @pytest.mark.asyncio
    async def test_auth_failure(self):
        auth = MagicMock()
        auth.ensure_valid_token = AsyncMock(
            side_effect=SalesforceAuthenticationFailed("bad grant", "")
        )
        with patch(
            "integrations.auth_handler_salesforce.salesforce_auth_handler", auth
        ):
            result = await sf_mod.get_salesforce_client("user-1")
        assert result is None

    @pytest.mark.asyncio
    async def test_import_error(self):
        auth = MagicMock()
        auth.ensure_valid_token = AsyncMock(return_value="tok")
        auth.instance_url = "https://x.salesforce.com"

        def _raise_import(*args, **kwargs):
            raise ImportError("simple_salesforce missing")

        with patch(
            "integrations.auth_handler_salesforce.salesforce_auth_handler", auth
        ), patch.object(sf_mod, "Salesforce", side_effect=_raise_import):
            result = await sf_mod.get_salesforce_client("user-1")
        assert result is None

    @pytest.mark.asyncio
    async def test_generic_error(self):
        auth = MagicMock()
        auth.ensure_valid_token = AsyncMock(return_value="tok")
        auth.instance_url = "https://x.salesforce.com"
        with patch(
            "integrations.auth_handler_salesforce.salesforce_auth_handler", auth
        ), patch.object(
            sf_mod, "Salesforce", side_effect=RuntimeError("connection refused")
        ):
            result = await sf_mod.get_salesforce_client("user-1")
        assert result is None


class TestCreateClientWithToken:
    @pytest.mark.asyncio
    async def test_success(self):
        client = _mock_sf()
        with patch.object(sf_mod, "Salesforce", return_value=client):
            result = sf_mod.create_client_with_token("tok", "https://x")
        assert result is client

    @pytest.mark.asyncio
    async def test_error(self):
        with patch.object(
            sf_mod, "Salesforce", side_effect=RuntimeError("bad url")
        ):
            result = sf_mod.create_client_with_token("tok", "https://x")
        assert result is None


class TestListFunctions:
    @pytest.mark.parametrize(
        "fn_name, query_fragment",
        [
            ("list_contacts", "FROM Contact"),
            ("list_accounts", "FROM Account"),
            ("list_opportunities", "FROM Opportunity"),
            ("list_leads", "FROM Lead"),
        ],
    )
    @pytest.mark.asyncio
    async def test_success(self, fn_name, query_fragment):
        sf = _mock_sf()
        sf.query_all.return_value = {"records": [{"Id": "1"}]}
        result = await getattr(sf_mod, fn_name)(sf)
        assert result == [{"Id": "1"}]
        assert query_fragment in sf.query_all.call_args[0][0]

    @pytest.mark.parametrize(
        "fn_name",
        ["list_contacts", "list_accounts", "list_opportunities", "list_leads"],
    )
    @pytest.mark.asyncio
    async def test_error_raises(self, fn_name):
        sf = _mock_sf()
        sf.query_all.side_effect = RuntimeError("sf down")
        with pytest.raises(RuntimeError):
            await getattr(sf_mod, fn_name)(sf)


class TestCreateFunctions:
    @pytest.mark.asyncio
    async def test_create_contact_all_fields(self):
        sf = _mock_sf()
        sf.Contact.create.return_value = {"id": "003x"}
        result = await sf_mod.create_contact(
            sf, "Doe", first_name="Jane", email="j@x.com", phone="555"
        )
        assert result == {"id": "003x"}
        sf.Contact.create.assert_called_once_with(
            {
                "LastName": "Doe",
                "FirstName": "Jane",
                "Email": "j@x.com",
                "Phone": "555",
            }
        )

    @pytest.mark.asyncio
    async def test_create_contact_required_only(self):
        sf = _mock_sf()
        sf.Contact.create.return_value = {"id": "003y"}
        result = await sf_mod.create_contact(sf, "Doe")
        assert result == {"id": "003y"}
        sf.Contact.create.assert_called_once_with({"LastName": "Doe"})

    @pytest.mark.asyncio
    async def test_create_contact_error(self):
        sf = _mock_sf()
        sf.Contact.create.side_effect = RuntimeError("validation failed")
        with pytest.raises(RuntimeError):
            await sf_mod.create_contact(sf, "Doe")

    @pytest.mark.asyncio
    async def test_create_account_all_fields(self):
        sf = _mock_sf()
        sf.Account.create.return_value = {"id": "001x"}
        result = await sf_mod.create_account(sf, "Acme", type="Customer", industry="Tech")
        sf.Account.create.assert_called_once_with(
            {"Name": "Acme", "Type": "Customer", "Industry": "Tech"}
        )
        assert result == {"id": "001x"}

    @pytest.mark.asyncio
    async def test_create_account_required_only(self):
        sf = _mock_sf()
        sf.Account.create.return_value = {"id": "001y"}
        result = await sf_mod.create_account(sf, "Acme")
        sf.Account.create.assert_called_once_with({"Name": "Acme"})
        assert result == {"id": "001y"}

    @pytest.mark.asyncio
    async def test_create_account_error(self):
        sf = _mock_sf()
        sf.Account.create.side_effect = RuntimeError("dup")
        with pytest.raises(RuntimeError):
            await sf_mod.create_account(sf, "Acme")

    @pytest.mark.asyncio
    async def test_create_opportunity_all_fields(self):
        sf = _mock_sf()
        sf.Opportunity.create.return_value = {"id": "006x"}
        result = await sf_mod.create_opportunity(
            sf, "Big Deal", "Prospecting", "2026-12-31", amount=1000.0, account_id="001a"
        )
        sf.Opportunity.create.assert_called_once_with(
            {
                "Name": "Big Deal",
                "StageName": "Prospecting",
                "CloseDate": "2026-12-31",
                "Amount": 1000.0,
                "AccountId": "001a",
            }
        )
        assert result == {"id": "006x"}

    @pytest.mark.asyncio
    async def test_create_opportunity_required_only(self):
        sf = _mock_sf()
        sf.Opportunity.create.return_value = {"id": "006y"}
        result = await sf_mod.create_opportunity(sf, "Big Deal", "Prospecting", "2026-12-31")
        sf.Opportunity.create.assert_called_once_with(
            {"Name": "Big Deal", "StageName": "Prospecting", "CloseDate": "2026-12-31"}
        )
        assert result == {"id": "006y"}

    @pytest.mark.asyncio
    async def test_create_opportunity_error(self):
        sf = _mock_sf()
        sf.Opportunity.create.side_effect = RuntimeError("no access")
        with pytest.raises(RuntimeError):
            await sf_mod.create_opportunity(sf, "Big Deal", "Prospecting", "2026-12-31")

    @pytest.mark.asyncio
    async def test_create_lead_all_fields(self):
        sf = _mock_sf()
        sf.Lead.create.return_value = {"id": "00Qx"}
        result = await sf_mod.create_lead(
            sf, "Doe", "Acme", first_name="Jane", email="j@x.com", phone="555"
        )
        sf.Lead.create.assert_called_once_with(
            {
                "LastName": "Doe",
                "Company": "Acme",
                "FirstName": "Jane",
                "Email": "j@x.com",
                "Phone": "555",
            }
        )
        assert result == {"id": "00Qx"}

    @pytest.mark.asyncio
    async def test_create_lead_required_only(self):
        sf = _mock_sf()
        sf.Lead.create.return_value = {"id": "00Qy"}
        result = await sf_mod.create_lead(sf, "Doe", "Acme")
        sf.Lead.create.assert_called_once_with({"LastName": "Doe", "Company": "Acme"})
        assert result == {"id": "00Qy"}

    @pytest.mark.asyncio
    async def test_create_lead_error(self):
        sf = _mock_sf()
        sf.Lead.create.side_effect = RuntimeError("bad company")
        with pytest.raises(RuntimeError):
            await sf_mod.create_lead(sf, "Doe", "Acme")


class TestUpdateFunctions:
    @pytest.mark.parametrize(
        "fn_name, object_name",
        [
            ("update_opportunity", "Opportunity"),
            ("update_contact", "Contact"),
            ("update_lead", "Lead"),
            ("update_account", "Account"),
        ],
    )
    @pytest.mark.asyncio
    async def test_success(self, fn_name, object_name):
        sf = _mock_sf()
        obj = getattr(sf, object_name)
        obj.update.return_value = {"success": True}
        result = await getattr(sf_mod, fn_name)(sf, "id-1", {"Name": "New"})
        assert result == {"success": True}
        obj.update.assert_called_once_with("id-1", {"Name": "New"})

    @pytest.mark.parametrize(
        "fn_name, object_name",
        [
            ("update_opportunity", "Opportunity"),
            ("update_contact", "Contact"),
            ("update_lead", "Lead"),
            ("update_account", "Account"),
        ],
    )
    @pytest.mark.asyncio
    async def test_error(self, fn_name, object_name):
        sf = _mock_sf()
        getattr(sf, object_name).update.side_effect = RuntimeError("update failed")
        with pytest.raises(RuntimeError):
            await getattr(sf_mod, fn_name)(sf, "id-1", {})


class TestGetFunctions:
    @pytest.mark.parametrize(
        "fn_name, object_name",
        [
            ("get_opportunity", "Opportunity"),
            ("get_campaign", "Campaign"),
            ("get_case", "Case"),
        ],
    )
    @pytest.mark.asyncio
    async def test_success(self, fn_name, object_name):
        sf = _mock_sf()
        getattr(sf, object_name).get.return_value = {"Id": "id-1"}
        result = await getattr(sf_mod, fn_name)(sf, "id-1")
        assert result == {"Id": "id-1"}
        getattr(sf, object_name).get.assert_called_once_with("id-1")

    @pytest.mark.parametrize("fn_name", ["get_opportunity", "get_campaign", "get_case"])
    @pytest.mark.asyncio
    async def test_error(self, fn_name):
        sf = _mock_sf()
        for obj in ("Opportunity", "Campaign", "Case"):
            getattr(sf, obj).get.side_effect = RuntimeError("not found")
        with pytest.raises(RuntimeError):
            await getattr(sf_mod, fn_name)(sf, "id-1")


class TestGetUserInfo:
    @pytest.mark.asyncio
    async def test_identity_path(self):
        sf = _mock_sf()
        sf.identity = {"user_id": "005000000000001"}
        sf.query_all.return_value = {"records": [{"Id": "005000000000001", "Name": "A"}]}
        result = await sf_mod.get_user_info(sf)
        assert result["Name"] == "A"
        assert "005000000000001" in sf.query_all.call_args[0][0]

    @pytest.mark.asyncio
    async def test_identity_empty_records(self):
        sf = _mock_sf()
        sf.identity = {"user_id": "005000000000001"}
        sf.query_all.return_value = {"records": []}
        result = await sf_mod.get_user_info(sf)
        assert result == {}

    @pytest.mark.asyncio
    async def test_userinfo_fallback(self):
        sf = _mock_sf()
        sf.identity = None
        sf.base_url = "https://acme.my.salesforce.com/services/data"
        sf.session_id = "tok-1"
        resp = Mock()
        resp.json.return_value = {"sub": "005000000000001", "name": "Jane"}
        with patch("requests.get", return_value=resp) as get:
            result = await sf_mod.get_user_info(sf)
        get.assert_called_once()
        assert result["name"] == "Jane"
        assert get.call_args[0][0] == "https://acme.my.salesforce.com/services/oauth2/userinfo"

    @pytest.mark.asyncio
    async def test_error(self):
        sf = _mock_sf()
        sf.identity = {"user_id": "005000000000001"}
        sf.query_all.side_effect = RuntimeError("query failed")
        with pytest.raises(RuntimeError):
            await sf_mod.get_user_info(sf)


class TestEscapeHelpers:
    def test_escape_soql_string_none(self):
        assert sf_mod.escape_soql_string(None) == ""

    def test_escape_soql_string_quotes(self):
        assert sf_mod.escape_soql_string("O'Brien") == "O''Brien"

    def test_escape_soql_string_backslash(self):
        assert sf_mod.escape_soql_string("a\\b'c") == "a\\\\b''c"

    def test_validate_id_valid(self):
        assert sf_mod.validate_salesforce_id("001000000000001") is True
        assert sf_mod.validate_salesforce_id("001000000000001AAA") is True

    @pytest.mark.parametrize(
        "value",
        [None, "", "short", "001000000000001AAAB", "00100000000000 1", 12345],
    )
    def test_validate_id_invalid(self, value):
        assert sf_mod.validate_salesforce_id(value) is False


class TestQueryAndDescribe:
    @pytest.mark.asyncio
    async def test_execute_soql_success(self):
        sf = _mock_sf()
        sf.query_all.return_value = {"records": [{"Id": "1"}]}
        result = await sf_mod.execute_soql_query(sf, "SELECT Id FROM Account")
        assert result["records"] == [{"Id": "1"}]

    @pytest.mark.asyncio
    async def test_execute_soql_error(self):
        sf = _mock_sf()
        sf.query_all.side_effect = RuntimeError("bad soql")
        with pytest.raises(RuntimeError):
            await sf_mod.execute_soql_query(sf, "SELECT bad")

    @pytest.mark.asyncio
    async def test_list_sobjects_success(self):
        sf = _mock_sf()
        sf.describe.return_value = {"sobjects": [{"name": "Account"}]}
        result = await sf_mod.list_sobjects(sf)
        assert result == [{"name": "Account"}]

    @pytest.mark.asyncio
    async def test_list_sobjects_error_returns_empty(self):
        sf = _mock_sf()
        sf.describe.side_effect = RuntimeError("denied")
        assert await sf_mod.list_sobjects(sf) == []

    @pytest.mark.asyncio
    async def test_get_sobject_fields_success(self):
        sf = _mock_sf()
        sf.Account.describe.return_value = {"fields": [{"name": "Name"}]}
        result = await sf_mod.get_sobject_fields(sf, "Account")
        assert result == [{"name": "Name"}]

    @pytest.mark.asyncio
    async def test_get_sobject_fields_error_returns_empty(self):
        sf = _mock_sf()
        sf.Account.describe.side_effect = RuntimeError("denied")
        assert await sf_mod.get_sobject_fields(sf, "Account") == []


class TestSalesforceServiceClass:
    def test_init_defaults(self):
        svc = sf_mod.SalesforceService()
        assert svc.tenant_id == "default"
        assert svc.access_token is None
        assert svc.instance_url is None

    def test_init_with_config(self):
        svc = sf_mod.SalesforceService(
            tenant_id="t1", config={"access_token": "tok", "instance_url": "https://x"}
        )
        assert svc.tenant_id == "t1"
        assert svc.access_token == "tok"

    @pytest.mark.asyncio
    async def test_get_client_delegates(self):
        svc = sf_mod.SalesforceService()
        with patch.object(
            sf_mod, "get_salesforce_client", new=AsyncMock(return_value="client")
        ) as fn:
            assert await svc.get_client("u1", "pool") == "client"
        fn.assert_awaited_once_with("u1", "pool")

    def test_create_client_delegates(self):
        svc = sf_mod.SalesforceService()
        with patch.object(sf_mod, "create_client_with_token", return_value="client") as fn:
            assert svc.create_client("tok", "url") == "client"
        fn.assert_called_once_with("tok", "url")

    @pytest.mark.asyncio
    async def test_wrapper_delegation(self):
        svc = sf_mod.SalesforceService()
        sf = _mock_sf()
        with patch.object(sf_mod, "list_contacts", new=AsyncMock(return_value=[1])) as a, \
             patch.object(sf_mod, "list_accounts", new=AsyncMock(return_value=[2])) as b, \
             patch.object(sf_mod, "list_opportunities", new=AsyncMock(return_value=[3])) as c, \
             patch.object(sf_mod, "list_leads", new=AsyncMock(return_value=[4])) as d, \
             patch.object(sf_mod, "create_contact", new=AsyncMock(return_value={"id": 1})) as e, \
             patch.object(sf_mod, "create_account", new=AsyncMock(return_value={"id": 2})) as f, \
             patch.object(sf_mod, "create_opportunity", new=AsyncMock(return_value={"id": 3})) as g, \
             patch.object(sf_mod, "create_lead", new=AsyncMock(return_value={"id": 4})) as h, \
             patch.object(sf_mod, "get_opportunity", new=AsyncMock(return_value={"id": 5})) as i, \
             patch.object(sf_mod, "update_opportunity", new=AsyncMock(return_value={"id": 6})) as j, \
             patch.object(sf_mod, "update_contact", new=AsyncMock(return_value={"id": 7})) as k, \
             patch.object(sf_mod, "update_lead", new=AsyncMock(return_value={"id": 8})) as l, \
             patch.object(sf_mod, "update_account", new=AsyncMock(return_value={"id": 9})) as m, \
             patch.object(sf_mod, "execute_soql_query", new=AsyncMock(return_value={"records": []})) as n, \
             patch.object(sf_mod, "list_sobjects", new=AsyncMock(return_value=[])) as o, \
             patch.object(sf_mod, "get_sobject_fields", new=AsyncMock(return_value=[])) as p:
            assert await svc.list_contacts(sf) == [1]
            assert await svc.list_accounts(sf) == [2]
            assert await svc.list_opportunities(sf) == [3]
            assert await svc.list_leads(sf) == [4]
            assert await svc.create_contact(sf, last_name="D") == {"id": 1}
            assert await svc.create_account(sf, name="A") == {"id": 2}
            assert await svc.create_opportunity(sf, name="O", stage_name="S", close_date="d") == {"id": 3}
            assert await svc.create_lead(sf, last_name="L", company="C") == {"id": 4}
            assert await svc.get_opportunity(sf, "x") == {"id": 5}
            assert await svc.update_opportunity(sf, "x", {"a": 1}) == {"id": 6}
            assert await svc.update_contact(sf, "x", {"a": 1}) == {"id": 7}
            assert await svc.update_lead(sf, "x", {"a": 1}) == {"id": 8}
            assert await svc.update_account(sf, "x", {"a": 1}) == {"id": 9}
            assert await svc.execute_query(sf, "SELECT 1") == {"records": []}
            assert await svc.list_sobjects(sf) == []
            assert await svc.get_sobject_fields(sf, "Account") == []

    def test_get_capabilities(self):
        svc = sf_mod.SalesforceService()
        caps = svc.get_capabilities()
        op_ids = [op["id"] for op in caps["operations"]]
        assert "create_contact" in op_ids
        assert caps["supports_webhooks"] is True
        assert caps["required_params"] == []

    def test_health_check_missing_credentials(self):
        svc = sf_mod.SalesforceService()
        result = svc.health_check()
        assert result["healthy"] is False
        assert result["message"] == "Missing credentials"

    def test_health_check_connected(self):
        svc = sf_mod.SalesforceService(
            config={"access_token": "tok", "instance_url": "https://x.salesforce.com"}
        )
        resp = Mock()
        resp.status_code = 200
        with patch("requests.get", return_value=resp) as get:
            result = svc.health_check()
        get.assert_called_once()
        assert result["healthy"] is True
        assert result["status"] == "healthy"
        assert result["message"] == "Connected"

    def test_health_check_bad_status(self):
        svc = sf_mod.SalesforceService(
            config={"access_token": "tok", "instance_url": "https://x.salesforce.com"}
        )
        resp = Mock()
        resp.status_code = 500
        with patch("requests.get", return_value=resp):
            result = svc.health_check()
        assert result["healthy"] is False
        assert result["status"] == "unhealthy"
        assert "500" in result["message"]

    def test_health_check_error_no_leak(self):
        """A2 RED: exception internals must not reach the payload."""
        svc = sf_mod.SalesforceService(
            config={"access_token": "tok", "instance_url": "https://x.salesforce.com"}
        )
        with patch("requests.get", side_effect=RuntimeError("secret-conn-detail")):
            result = svc.health_check()
        assert result["healthy"] is False
        assert "secret-conn-detail" not in json.dumps(result)

    @pytest.mark.asyncio
    async def test_execute_operation_unsupported(self):
        svc = sf_mod.SalesforceService()
        result = await svc.execute_operation("delete_everything", {})
        assert result["success"] is False
        assert "Unsupported operation" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_operation_create_lead_success(self):
        svc = sf_mod.SalesforceService()
        result = await svc.execute_operation(
            "create_lead",
            {
                "first_name": "Jane",
                "last_name": "Doe",
                "company": "Acme",
                "email": "j@x.com",
            },
            context={"tenant_id": "t1"},
        )
        assert result["success"] is True
        assert result["result"]["last_name"] == "Doe"

    @pytest.mark.asyncio
    async def test_execute_operation_create_lead_missing_params(self):
        svc = sf_mod.SalesforceService()
        result = await svc.execute_operation("create_lead", {"first_name": "Jane"})
        assert result["success"] is False
        assert "required" in result["error"]


# ============================================================================
# salesforce_routes
# ============================================================================

async def _auth_ok(token="tok-1"):
    auth = MagicMock()
    auth.ensure_valid_token = AsyncMock(return_value=token)
    auth.is_token_valid = Mock(return_value=True)
    auth.access_token = token
    auth.instance_url = "https://acme.my.salesforce.com"
    return auth


class TestRoutesAuth:
    @pytest.mark.asyncio
    async def test_access_token_success(self):
        with patch.object(
            sf_routes.salesforce_auth_handler,
            "ensure_valid_token",
            new=AsyncMock(return_value="tok-1"),
        ):
            assert await sf_routes.get_salesforce_access_token() == "tok-1"

    @pytest.mark.asyncio
    async def test_access_token_raises_401(self):
        with patch.object(
            sf_routes.salesforce_auth_handler,
            "ensure_valid_token",
            new=AsyncMock(side_effect=HTTPException(status_code=401)),
        ):
            with pytest.raises(HTTPException) as exc:
                await sf_routes.get_salesforce_access_token()
        assert exc.value.status_code == 401


class TestRoutesClientFactory:
    def test_client_from_oauth(self):
        client = _mock_sf()
        auth = MagicMock()
        auth.is_token_valid = Mock(return_value=True)
        auth.instance_url = "https://acme.my.salesforce.com"
        auth.access_token = "tok-1"
        with patch.object(sf_routes.salesforce_auth_handler, "is_token_valid", return_value=True), \
             patch.object(sf_routes.salesforce_auth_handler, "instance_url", "https://acme.my.salesforce.com"), \
             patch.object(sf_routes.salesforce_auth_handler, "access_token", "tok-1"), \
             patch.object(sf_routes, "Salesforce", return_value=client) as sf_cls:
            result = sf_routes.get_salesforce_client_from_env()
        assert result is client
        sf_cls.assert_called_once_with(
            instance_url="https://acme.my.salesforce.com",
            session_id="tok-1",
            version="57.0",
        )

    def test_client_from_env_fallback(self):
        client = _mock_sf()
        with patch.object(sf_routes.salesforce_auth_handler, "is_token_valid", return_value=False), \
             patch.object(sf_routes, "Salesforce", return_value=client) as sf_cls, \
             patch.dict(
                 "os.environ",
                 {
                     "SALESFORCE_USERNAME": "u",
                     "SALESFORCE_PASSWORD": "p",
                     "SALESFORCE_SECURITY_TOKEN": "t",
                 },
             ):
            result = sf_routes.get_salesforce_client_from_env()
        assert result is client
        sf_cls.assert_called_once_with(username="u", password="p", security_token="t")

    def test_client_none_without_credentials(self):
        with patch.object(sf_routes.salesforce_auth_handler, "is_token_valid", return_value=False), \
             patch.dict("os.environ", {}, clear=False):
            assert sf_routes.get_salesforce_client_from_env() is None

    def test_client_init_error_returns_none(self):
        with patch.object(sf_routes.salesforce_auth_handler, "is_token_valid", return_value=False), \
             patch.object(
                 sf_routes, "Salesforce", side_effect=RuntimeError("bad creds")
             ), patch.dict(
                 "os.environ",
                 {"SALESFORCE_USERNAME": "u", "SALESFORCE_PASSWORD": "p", "SALESFORCE_SECURITY_TOKEN": "t"},
             ):
            assert sf_routes.get_salesforce_client_from_env() is None


class TestRoutesOAuthEndpoints:
    @pytest.mark.asyncio
    async def test_auth_url(self):
        auth = MagicMock()
        auth.get_authorization_url = Mock(return_value="https://login.salesforce.com/oauth")
        with patch.object(sf_routes.salesforce_auth_handler, "get_authorization_url", return_value="https://login.salesforce.com/oauth"):
            result = await sf_routes.get_salesforce_auth_url()
        assert result == {"url": "https://login.salesforce.com/oauth", "service": "salesforce"}

    @pytest.mark.asyncio
    async def test_callback_success(self):
        auth = MagicMock()
        auth.exchange_code_for_token = AsyncMock(
            return_value={"access_token": "t", "instance_url": "https://x"}
        )
        with patch.object(
            sf_routes.salesforce_auth_handler,
            "exchange_code_for_token",
            new=AsyncMock(return_value={"access_token": "t", "instance_url": "https://x"}),
        ):
            result = await sf_routes.salesforce_auth_callback(code="abc", state="s")
        assert result["ok"] is True
        assert result["instance_url"] == "https://x"

    @pytest.mark.asyncio
    async def test_callback_http_error_re_raised(self):
        with patch.object(
            sf_routes.salesforce_auth_handler,
            "exchange_code_for_token",
            new=AsyncMock(side_effect=HTTPException(status_code=400)),
        ):
            with pytest.raises(HTTPException) as exc:
                await sf_routes.salesforce_auth_callback(code="bad", state="s")
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_callback_generic_error_500(self):
        with patch.object(
            sf_routes.salesforce_auth_handler,
            "exchange_code_for_token",
            new=AsyncMock(side_effect=RuntimeError("exchange blew up")),
        ):
            with pytest.raises(HTTPException) as exc:
                await sf_routes.salesforce_auth_callback(code="bad", state="s")
        assert exc.value.status_code == 500

    @pytest.mark.asyncio
    async def test_revoke_success(self):
        with patch.object(
            sf_routes.salesforce_auth_handler,
            "revoke_token",
            new=AsyncMock(return_value=True),
        ):
            result = await sf_routes.revoke_salesforce_token()
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_revoke_failure(self):
        with patch.object(
            sf_routes.salesforce_auth_handler,
            "revoke_token",
            new=AsyncMock(return_value=False),
        ):
            result = await sf_routes.revoke_salesforce_token()
        assert result["ok"] is False
        assert "Failed" in result["message"]

    @pytest.mark.asyncio
    async def test_status(self):
        with patch.object(
            sf_routes.salesforce_auth_handler,
            "get_connection_status",
            return_value={"connected": True},
        ):
            result = await sf_routes.get_salesforce_status()
        assert result["status"] == {"connected": True}


class TestRoutesResponseFormatting:
    def test_format_response(self):
        result = sf_routes.format_salesforce_response({"a": 1})
        assert result["ok"] is True
        assert result["data"] == {"a": 1}
        assert "timestamp" in result

    def test_format_error_response(self):
        result = sf_routes.format_salesforce_error_response("boom")
        assert result["ok"] is False
        assert result["error"]["message"] == "boom"

    def test_generic_error_response_no_leak(self):
        result = sf_routes._salesforce_error_response(RuntimeError("secret-detail"))
        assert result["ok"] is False
        assert "secret-detail" not in json.dumps(result)


class TestRoutesHealth:
    @pytest.mark.asyncio
    async def test_unavailable(self):
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", False):
            with pytest.raises(HTTPException) as exc:
                await sf_routes.salesforce_health_check()
        assert exc.value.status_code == 503

    @pytest.mark.asyncio
    async def test_healthy_connected(self):
        client = _mock_sf()
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client):
            result = await sf_routes.salesforce_health_check()
        client.query.assert_called_once_with("SELECT Id FROM User LIMIT 1")
        assert result["status"] == "healthy"
        assert result["connected"] is True
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_degraded_when_query_fails(self):
        client = _mock_sf()
        client.query.side_effect = RuntimeError("sf down")
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client):
            result = await sf_routes.salesforce_health_check()
        assert result["status"] == "degraded"
        assert result["connected"] is False

    @pytest.mark.asyncio
    async def test_degraded_no_client(self):
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=None):
            result = await sf_routes.salesforce_health_check()
        assert result["status"] == "degraded"


class TestRoutesAccounts:
    @pytest.mark.asyncio
    async def test_list_success(self):
        client = _mock_sf()
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client), \
             patch.object(sf_routes, "list_accounts", new=AsyncMock(return_value=[{"Id": "1"}])), \
             patch.object(sf_routes.atom_ingestion_pipeline, "ingest_record") as ingest:
            result = await sf_routes.get_salesforce_accounts(limit=10, access_token="t")
        assert result["ok"] is True
        assert result["data"]["accounts"] == [{"Id": "1"}]
        ingest.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_list_awaits_ingestion_coroutine(self):
        """A4 RED: ingest_record is async (atom_ingestion_pipeline.py:97) — the
        route must await it, otherwise ingestion silently never happens."""
        client = _mock_sf()
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client), \
             patch.object(sf_routes, "list_accounts", new=AsyncMock(return_value=[{"Id": "1"}])), \
             patch.object(sf_routes.atom_ingestion_pipeline, "ingest_record") as ingest:
            result = await sf_routes.get_salesforce_accounts(limit=10, access_token="t")
        assert result["ok"] is True
        ingest.assert_awaited()

    @pytest.mark.asyncio
    async def test_list_ingestion_failure_ignored(self):
        client = _mock_sf()
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client), \
             patch.object(sf_routes, "list_accounts", new=AsyncMock(return_value=[{"Id": "1"}])), \
             patch.object(sf_routes.atom_ingestion_pipeline, "ingest_record", side_effect=RuntimeError("down")):
            result = await sf_routes.get_salesforce_accounts(limit=10, access_token="t")
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_list_no_credentials_raises_401(self):
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=None):
            with pytest.raises(HTTPException) as exc:
                await sf_routes.get_salesforce_accounts(limit=10, access_token="t")
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_list_unavailable(self):
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", False):
            with pytest.raises(HTTPException) as exc:
                await sf_routes.get_salesforce_accounts(limit=10, access_token="t")
        assert exc.value.status_code == 503

    @pytest.mark.asyncio
    async def test_list_service_error(self):
        client = _mock_sf()
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client), \
             patch.object(sf_routes, "list_accounts", new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = await sf_routes.get_salesforce_accounts(limit=10, access_token="t")
        assert result["ok"] is False
        assert "boom" not in json.dumps(result)

    @pytest.mark.asyncio
    async def test_create_unavailable(self):
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", False):
            with pytest.raises(HTTPException) as exc:
                await sf_routes.create_salesforce_account(
                    name="Acme", db=MagicMock(), access_token="t"
                )
        assert exc.value.status_code == 503

    @pytest.mark.asyncio
    async def test_get_by_id_success(self):
        client = _mock_sf()
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client), \
             patch.object(sf_routes, "execute_soql_query", new=AsyncMock(return_value={"records": [{"Id": "001000000000001"}]})) as soql:
            result = await sf_routes.get_salesforce_account(account_id="001000000000001", access_token="t")
        assert result["ok"] is True
        assert result["data"]["Id"] == "001000000000001"
        assert "001000000000001" in soql.call_args[0][1]

    @pytest.mark.asyncio
    async def test_get_by_id_invalid_format(self):
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True):
            result = await sf_routes.get_salesforce_account(account_id="not-an-id;", access_token="t")
        assert result["ok"] is False
        assert "Invalid account ID format" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_get_by_id_no_credentials(self):
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=None):
            result = await sf_routes.get_salesforce_account(account_id="001000000000001", access_token="t")
        assert result["ok"] is False
        assert "No credentials" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self):
        client = _mock_sf()
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client), \
             patch.object(sf_routes, "execute_soql_query", new=AsyncMock(return_value={"records": []})):
            result = await sf_routes.get_salesforce_account(account_id="001000000000001", access_token="t")
        assert result["ok"] is False
        assert "Account not found" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_get_by_id_error_no_leak(self):
        client = _mock_sf()
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client), \
             patch.object(sf_routes, "execute_soql_query", new=AsyncMock(side_effect=RuntimeError("soql-secret"))):
            result = await sf_routes.get_salesforce_account(account_id="001000000000001", access_token="t")
        assert "soql-secret" not in json.dumps(result)

    @pytest.mark.asyncio
    async def test_create_success(self):
        client = _mock_sf()
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client), \
             patch.object(sf_routes, "create_account", new=AsyncMock(return_value={"Id": "001x"})) as create:
            result = await sf_routes.create_salesforce_account(
                name="Acme", industry="Tech", db=MagicMock(), access_token="t"
            )
        assert result["ok"] is True
        assert result["data"] == {"Id": "001x"}
        create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_no_credentials(self):
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=None):
            result = await sf_routes.create_salesforce_account(
                name="Acme", db=MagicMock(), access_token="t"
            )
        assert result["ok"] is False

    @pytest.mark.asyncio
    async def test_create_service_error(self):
        client = _mock_sf()
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client), \
             patch.object(sf_routes, "create_account", new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = await sf_routes.create_salesforce_account(
                name="Acme", db=MagicMock(), access_token="t"
            )
        assert result["ok"] is False
        assert "boom" not in json.dumps(result)

    @pytest.mark.asyncio
    async def test_create_governance_blocked(self):
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "SALESFORCE_GOVERNANCE_ENABLED", True), \
             patch.object(sf_routes, "EMERGENCY_GOVERNANCE_BYPASS", False), \
             patch.object(
                 sf_routes,
                 "with_governance_check",
                 new=AsyncMock(return_value=(MagicMock(), {"allowed": False, "reason": "too young"})),
             ):
            with pytest.raises(HTTPException) as exc:
                await sf_routes.create_salesforce_account(
                    name="Acme", agent_id="agent-1", db=MagicMock(), access_token="t"
                )
        assert exc.value.status_code == 403
        assert "too young" in str(exc.value.detail)

    @pytest.mark.asyncio
    async def test_create_governance_allowed_creates(self):
        client = _mock_sf()
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "SALESFORCE_GOVERNANCE_ENABLED", True), \
             patch.object(sf_routes, "EMERGENCY_GOVERNANCE_BYPASS", False), \
             patch.object(
                 sf_routes,
                 "with_governance_check",
                 new=AsyncMock(return_value=(MagicMock(), {"allowed": True})),
             ), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client), \
             patch.object(sf_routes, "create_account", new=AsyncMock(return_value={"Id": "001x"})), \
             patch.object(sf_routes, "create_execution_record") as exec_rec:
            result = await sf_routes.create_salesforce_account(
                name="Acme", agent_id="agent-1", db=MagicMock(), access_token="t"
            )
        assert result["ok"] is True
        exec_rec.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_governance_error_continues(self):
        client = _mock_sf()
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "SALESFORCE_GOVERNANCE_ENABLED", True), \
             patch.object(sf_routes, "EMERGENCY_GOVERNANCE_BYPASS", False), \
             patch.object(sf_routes, "with_governance_check", new=AsyncMock(side_effect=RuntimeError("gov down"))), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client), \
             patch.object(sf_routes, "create_account", new=AsyncMock(return_value={"Id": "001x"})):
            result = await sf_routes.create_salesforce_account(
                name="Acme", agent_id="agent-1", db=MagicMock(), access_token="t"
            )
        assert result["ok"] is True


class TestRoutesContacts:
    @pytest.mark.asyncio
    async def test_list_success_with_filters(self):
        client = _mock_sf()
        records = [
            {"Id": "1", "AccountId": "acc1", "Email": "a@x.com"},
            {"Id": "2", "AccountId": "acc2", "Email": "b@x.com"},
        ]
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client), \
             patch.object(sf_routes, "list_contacts", new=AsyncMock(return_value=records)), \
             patch.object(sf_routes.atom_ingestion_pipeline, "ingest_record"):
            result = await sf_routes.get_salesforce_contacts(
                limit=10, account_id="acc1", email=None, access_token="t"
            )
        assert result["ok"] is True
        assert result["data"] == [{"Id": "1", "AccountId": "acc1", "Email": "a@x.com"}]

    @pytest.mark.asyncio
    async def test_list_success_email_filter(self):
        client = _mock_sf()
        records = [
            {"Id": "1", "AccountId": "acc1", "Email": "a@x.com"},
            {"Id": "2", "AccountId": "acc1", "Email": "b@x.com"},
        ]
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client), \
             patch.object(sf_routes, "list_contacts", new=AsyncMock(return_value=records)), \
             patch.object(sf_routes.atom_ingestion_pipeline, "ingest_record"):
            result = await sf_routes.get_salesforce_contacts(
                limit=10, account_id=None, email="b@x.com", access_token="t"
            )
        assert result["data"] == [{"Id": "2", "AccountId": "acc1", "Email": "b@x.com"}]

    @pytest.mark.asyncio
    async def test_list_no_credentials_raises_401(self):
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=None):
            with pytest.raises(HTTPException) as exc:
                await sf_routes.get_salesforce_contacts(limit=10, account_id=None, email=None, access_token="t")
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_list_ingestion_failure_ignored(self):
        client = _mock_sf()
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client), \
             patch.object(sf_routes, "list_contacts", new=AsyncMock(return_value=[{"Id": "1"}])), \
             patch.object(sf_routes.atom_ingestion_pipeline, "ingest_record", side_effect=RuntimeError("down")):
            result = await sf_routes.get_salesforce_contacts(limit=10, account_id=None, email=None, access_token="t")
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_create_unavailable(self):
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", False):
            with pytest.raises(HTTPException) as exc:
                await sf_routes.create_salesforce_contact(
                    first_name="Jane", last_name="Doe", email="j@x.com", access_token="t"
                )
        assert exc.value.status_code == 503

    @pytest.mark.asyncio
    async def test_create_success(self):
        client = _mock_sf()
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client), \
             patch.object(sf_routes, "create_contact", new=AsyncMock(return_value={"Id": "003x"})) as create:
            result = await sf_routes.create_salesforce_contact(
                first_name="Jane",
                last_name="Doe",
                email="j@x.com",
                phone="555",
                access_token="t",
            )
        assert result["ok"] is True
        create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_no_credentials(self):
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=None):
            result = await sf_routes.create_salesforce_contact(
                first_name="Jane", last_name="Doe", email="j@x.com", access_token="t"
            )
        assert result["ok"] is False

    @pytest.mark.asyncio
    async def test_create_service_error(self):
        client = _mock_sf()
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client), \
             patch.object(sf_routes, "create_contact", new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = await sf_routes.create_salesforce_contact(
                first_name="Jane", last_name="Doe", email="j@x.com", access_token="t"
            )
        assert result["ok"] is False
        assert "boom" not in json.dumps(result)


class TestRoutesOpportunities:
    @pytest.mark.asyncio
    async def test_list_success(self):
        client = _mock_sf()
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client), \
             patch.object(sf_routes, "list_opportunities", new=AsyncMock(return_value=[{"Id": "1"}])), \
             patch.object(sf_routes.atom_ingestion_pipeline, "ingest_record"):
            result = await sf_routes.get_salesforce_opportunities(limit=10, stage=None, account_id=None, access_token="t")
        assert result["ok"] is True
        assert result["data"] == [{"Id": "1"}]

    @pytest.mark.asyncio
    async def test_list_no_credentials_raises_401(self):
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=None):
            with pytest.raises(HTTPException) as exc:
                await sf_routes.get_salesforce_opportunities(limit=10, stage=None, account_id=None, access_token="t")
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_list_service_error(self):
        client = _mock_sf()
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client), \
             patch.object(sf_routes, "list_opportunities", new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = await sf_routes.get_salesforce_opportunities(limit=10, stage=None, account_id=None, access_token="t")
        assert result["ok"] is False

    @pytest.mark.asyncio
    async def test_list_ingestion_failure_ignored(self):
        client = _mock_sf()
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client), \
             patch.object(sf_routes, "list_opportunities", new=AsyncMock(return_value=[{"Id": "1"}])), \
             patch.object(sf_routes.atom_ingestion_pipeline, "ingest_record", side_effect=RuntimeError("down")):
            result = await sf_routes.get_salesforce_opportunities(limit=10, stage=None, account_id=None, access_token="t")
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_create_success(self):
        client = _mock_sf()
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client), \
             patch.object(sf_routes, "create_opportunity", new=AsyncMock(return_value={"Id": "006x"})) as create:
            result = await sf_routes.create_salesforce_opportunity(
                name="Big",
                account_id="001a",
                stage="Prospecting",
                amount=100.0,
                close_date="2026-12-31",
                access_token="t",
            )
        assert result["ok"] is True
        create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_unavailable(self):
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", False):
            with pytest.raises(HTTPException) as exc:
                await sf_routes.create_salesforce_opportunity(
                    name="Big", account_id="001a", stage="Prospecting", amount=100.0, close_date="2026-12-31", access_token="t"
                )
        assert exc.value.status_code == 503

    @pytest.mark.asyncio
    async def test_create_no_credentials(self):
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=None):
            result = await sf_routes.create_salesforce_opportunity(
                name="Big", account_id="001a", stage="Prospecting", amount=100.0, close_date="2026-12-31", access_token="t"
            )
        assert result["ok"] is False

    @pytest.mark.asyncio
    async def test_create_service_error(self):
        client = _mock_sf()
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client), \
             patch.object(sf_routes, "create_opportunity", new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = await sf_routes.create_salesforce_opportunity(
                name="Big", account_id="001a", stage="Prospecting", amount=100.0, close_date="2026-12-31", access_token="t"
            )
        assert result["ok"] is False


class TestRoutesLeads:
    @pytest.mark.asyncio
    async def test_list_unavailable(self):
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", False):
            with pytest.raises(HTTPException) as exc:
                await sf_routes.get_salesforce_leads(limit=10, status=None, company=None, access_token="t")
        assert exc.value.status_code == 503

    @pytest.mark.asyncio
    async def test_list_ingestion_failure_ignored(self):
        client = _mock_sf()
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client), \
             patch.object(sf_routes, "list_leads", new=AsyncMock(return_value=[{"Id": "1"}])), \
             patch.object(sf_routes.atom_ingestion_pipeline, "ingest_record", side_effect=RuntimeError("down")):
            result = await sf_routes.get_salesforce_leads(limit=10, status=None, company=None, access_token="t")
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_list_success(self):
        client = _mock_sf()
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client), \
             patch.object(sf_routes, "list_leads", new=AsyncMock(return_value=[{"Id": "1"}])), \
             patch.object(sf_routes.atom_ingestion_pipeline, "ingest_record"):
            result = await sf_routes.get_salesforce_leads(limit=10, status=None, company=None, access_token="t")
        assert result["ok"] is True
        assert result["data"] == [{"Id": "1"}]

    @pytest.mark.asyncio
    async def test_list_no_credentials(self):
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=None):
            result = await sf_routes.get_salesforce_leads(limit=10, status=None, company=None, access_token="t")
        assert result["ok"] is False

    @pytest.mark.asyncio
    async def test_create_success(self):
        client = _mock_sf()
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client), \
             patch.object(sf_routes, "create_lead", new=AsyncMock(return_value={"Id": "00Qx"})) as create:
            result = await sf_routes.create_salesforce_lead(
                first_name="Jane", last_name="Doe", company="Acme", email="j@x.com", access_token="t"
            )
        assert result["ok"] is True
        create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_unavailable(self):
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", False):
            with pytest.raises(HTTPException) as exc:
                await sf_routes.create_salesforce_lead(
                    first_name="Jane", last_name="Doe", company="Acme", email="j@x.com", access_token="t"
                )
        assert exc.value.status_code == 503

    @pytest.mark.asyncio
    async def test_create_no_credentials(self):
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=None):
            result = await sf_routes.create_salesforce_lead(
                first_name="Jane", last_name="Doe", company="Acme", email="j@x.com", access_token="t"
            )
        assert result["ok"] is False

    @pytest.mark.asyncio
    async def test_create_service_error(self):
        client = _mock_sf()
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client), \
             patch.object(sf_routes, "create_lead", new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = await sf_routes.create_salesforce_lead(
                first_name="Jane", last_name="Doe", company="Acme", email="j@x.com", access_token="t"
            )
        assert result["ok"] is False
        assert "boom" not in json.dumps(result)


class TestRoutesSearch:
    @pytest.mark.asyncio
    async def test_search_unavailable(self):
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", False):
            with pytest.raises(HTTPException) as exc:
                await sf_routes.search_salesforce(
                    query="acme", object_types=["Account"], limit=10, access_token="t"
                )
        assert exc.value.status_code == 503

    @pytest.mark.asyncio
    async def test_search_success(self):
        client = _mock_sf()
        client.search.return_value = {"searchRecords": [{"Id": "1"}]}
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client):
            result = await sf_routes.search_salesforce(
                query="acme", object_types=["Account", "Contact"], limit=10, access_token="t"
            )
        assert result["ok"] is True
        assert "FIND {acme}" in client.search.call_args[0][0]
        assert "RETURNING Account,Contact" in client.search.call_args[0][0]

    @pytest.mark.asyncio
    async def test_search_no_credentials(self):
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=None):
            result = await sf_routes.search_salesforce(
                query="acme", object_types=["Account"], limit=10, access_token="t"
            )
        assert result["ok"] is False

    @pytest.mark.asyncio
    async def test_search_sf_error(self):
        client = _mock_sf()
        client.search.side_effect = RuntimeError("search down")
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client):
            result = await sf_routes.search_salesforce(
                query="acme", object_types=["Account"], limit=10, access_token="t"
            )
        assert result["ok"] is False
        assert "search down" not in json.dumps(result)

    @pytest.mark.asyncio
    async def test_search_client_init_error(self):
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(
                 sf_routes, "get_salesforce_client_from_env",
                 side_effect=RuntimeError("client init boom"),
             ):
            result = await sf_routes.search_salesforce(
                query="acme", object_types=["Account"], limit=10, access_token="t"
            )
        assert result["ok"] is False
        assert "client init boom" not in json.dumps(result)

    @pytest.mark.asyncio
    async def test_search_escapes_sosl_braces(self):
        """A1 RED (HIGH): SOSL breakout via '}' in the search query must be
        neutralized — the query is interpolated into FIND {...}."""
        client = _mock_sf()
        client.search.return_value = {"searchRecords": []}
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client):
            result = await sf_routes.search_salesforce(
                query="acme} RETURNING Contact WHERE Email LIKE 'x%'",
                object_types=["Account"],
                limit=10,
                access_token="t",
            )
        sent = client.search.call_args[0][0]
        assert "acme\\} RETURNING Contact WHERE Email LIKE 'x%'" in sent

    @pytest.mark.asyncio
    async def test_search_rejects_invalid_object_type(self):
        """A1 RED (HIGH): object_types with injected clauses must be rejected
        fail-closed instead of being interpolated into the SOSL."""
        client = _mock_sf()
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client):
            result = await sf_routes.search_salesforce(
                query="acme",
                object_types=["Account LIMIT 1"],
                limit=10,
                access_token="t",
            )
        assert result["ok"] is False
        assert "Invalid object type" in result["error"]["message"]
        client.search.assert_not_called()


class TestRoutesAnalytics:
    @pytest.mark.asyncio
    async def test_leads_analytics_unavailable(self):
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", False):
            with pytest.raises(HTTPException) as exc:
                await sf_routes.get_leads_analytics(timeframe="30d", access_token="t")
        assert exc.value.status_code == 503

    @pytest.mark.asyncio
    async def test_leads_analytics_no_credentials(self):
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=None):
            result = await sf_routes.get_leads_analytics(timeframe="30d", access_token="t")
        assert result["ok"] is False

    @pytest.mark.asyncio
    async def test_pipeline_unavailable(self):
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", False):
            with pytest.raises(HTTPException) as exc:
                await sf_routes.get_sales_pipeline_analytics(timeframe="30d", access_token="t")
        assert exc.value.status_code == 503

    @pytest.mark.asyncio
    async def test_pipeline_success(self):
        client = _mock_sf()
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client), \
             patch.object(
                 sf_routes,
                 "execute_soql_query",
                 new=AsyncMock(
                     return_value={"records": [{"Amount": 100}, {"Amount": 250.5}, {"Amount": None}]}
                 ),
             ) as soql:
            result = await sf_routes.get_sales_pipeline_analytics(timeframe="30d", access_token="t")
        assert result["ok"] is True
        assert result["data"]["pipeline_value"] == 350.5
        assert result["data"]["opportunities_count"] == 3
        assert "IsClosed = false" in soql.call_args[0][1]

    @pytest.mark.asyncio
    async def test_pipeline_empty(self):
        client = _mock_sf()
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client), \
             patch.object(sf_routes, "execute_soql_query", new=AsyncMock(return_value={"records": []})):
            result = await sf_routes.get_sales_pipeline_analytics(timeframe="30d", access_token="t")
        assert result["data"]["pipeline_value"] == 0.0
        assert result["data"]["opportunities_count"] == 0

    @pytest.mark.asyncio
    async def test_pipeline_error(self):
        client = _mock_sf()
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client), \
             patch.object(sf_routes, "execute_soql_query", new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = await sf_routes.get_sales_pipeline_analytics(timeframe="30d", access_token="t")
        assert result["ok"] is False

    @pytest.mark.asyncio
    async def test_leads_success_with_conversion(self):
        client = _mock_sf()
        records = [
            {"Id": "1", "IsConverted": True},
            {"Id": "2", "IsConverted": False},
            {"Id": "3", "IsConverted": True},
            {"Id": "4", "IsConverted": None},
        ]
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client), \
             patch.object(sf_routes, "execute_soql_query", new=AsyncMock(return_value={"records": records})):
            result = await sf_routes.get_leads_analytics(timeframe="30d", access_token="t")
        assert result["ok"] is True
        assert result["data"]["leads_count"] == 4
        assert result["data"]["converted_count"] == 2
        assert result["data"]["conversion_rate"] == 50.0

    @pytest.mark.asyncio
    async def test_leads_zero_records(self):
        client = _mock_sf()
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client), \
             patch.object(sf_routes, "execute_soql_query", new=AsyncMock(return_value=None)):
            result = await sf_routes.get_leads_analytics(timeframe="30d", access_token="t")
        assert result["data"]["conversion_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_leads_error(self):
        client = _mock_sf()
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client), \
             patch.object(sf_routes, "execute_soql_query", new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = await sf_routes.get_leads_analytics(timeframe="30d", access_token="t")
        assert result["ok"] is False


class TestRoutesProfileAndMisc:
    @pytest.mark.asyncio
    async def test_profile_unavailable(self):
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", False):
            with pytest.raises(HTTPException) as exc:
                await sf_routes.get_salesforce_user_profile(access_token="t")
        assert exc.value.status_code == 503

    @pytest.mark.asyncio
    async def test_profile_chatter_success(self):
        client = _mock_sf()
        client.restful.return_value = {"username": "jane"}
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client):
            result = await sf_routes.get_salesforce_user_profile(access_token="t")
        assert result["ok"] is True
        client.restful.assert_called_once_with("chatter/users/me")

    @pytest.mark.asyncio
    async def test_profile_fallback_query(self):
        client = _mock_sf()
        client.restful.side_effect = RuntimeError("chatter down")
        client.query.return_value = {"totalSize": 1, "records": [{"Id": "005x", "Name": "A"}]}
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client):
            result = await sf_routes.get_salesforce_user_profile(access_token="t")
        assert result["ok"] is True
        assert result["data"]["Name"] == "A"

    @pytest.mark.asyncio
    async def test_profile_fallback_empty(self):
        client = _mock_sf()
        client.restful.side_effect = RuntimeError("chatter down")
        client.query.return_value = {"totalSize": 0, "records": []}
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client):
            result = await sf_routes.get_salesforce_user_profile(access_token="t")
        assert result["ok"] is False
        assert "User not found" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_profile_fallback_error(self):
        client = _mock_sf()
        client.restful.side_effect = RuntimeError("chatter down")
        client.query.side_effect = RuntimeError("query down too")
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=client):
            result = await sf_routes.get_salesforce_user_profile(access_token="t")
        assert result["ok"] is False

    @pytest.mark.asyncio
    async def test_profile_no_credentials(self):
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(sf_routes, "get_salesforce_client_from_env", return_value=None):
            result = await sf_routes.get_salesforce_user_profile(access_token="t")
        assert result["ok"] is False

    @pytest.mark.asyncio
    async def test_sync_stripe_payments(self):
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True):
            result = await sf_routes.sync_stripe_payments_with_salesforce(
                payment_data={"id": "pi_1", "amount": 500}, opportunity_id="006x", access_token="t"
            )
        assert result["ok"] is True
        assert result["data"]["payment_id"] == "pi_1"
        assert result["data"]["opportunity_id"] == "006x"

    @pytest.mark.asyncio
    async def test_sync_stripe_payments_unavailable(self):
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", False):
            with pytest.raises(HTTPException) as exc:
                await sf_routes.sync_stripe_payments_with_salesforce(
                    payment_data={"id": "pi_1"}, opportunity_id="006x", access_token="t"
                )
        assert exc.value.status_code == 503

    @pytest.mark.asyncio
    async def test_root(self):
        with patch.object(sf_routes, "SALESFORCE_AVAILABLE", True):
            result = await sf_routes.salesforce_root()
        assert result["service"] == "salesforce"
        assert result["status"] == "available"
        assert "/health" in result["endpoints"]
