"""Recovery must be available at the exact auth router mounted by normal main."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from api.auth_routes import router


@pytest.fixture
def recovery_client():
    # This is the same router main_api_app mounts. It does not mount the
    # unrelated safe-app core auth router or perform a mail/provider action.
    app=FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize('path',['forgot-password','verify-token','reset-password'])
def test_normal_mounted_auth_recovery_route_has_its_validation_boundary(recovery_client,path):
    response=recovery_client.post('/api/auth/'+path,json={})
    assert response.status_code==422,response.text


def test_normal_recovery_mount_reuses_one_existing_handler_per_path():
    from core.auth_endpoints import forgot_password,verify_token,reset_password
    expected={'/api/auth/forgot-password':forgot_password,
              '/api/auth/verify-token':verify_token,
              '/api/auth/reset-password':reset_password}
    for path,handler in expected.items():
        matches=[route for route in router.routes if route.path==path and 'POST' in route.methods]
        assert len(matches)==1
        assert matches[0].endpoint is handler
