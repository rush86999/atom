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
