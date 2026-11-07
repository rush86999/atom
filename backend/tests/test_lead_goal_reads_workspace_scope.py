"""A direct goal lookup must have the same visibility as its scoped list."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from core.auth import get_current_user
from core.database import get_db
from core.models import User
from tests.test_goal_utility_target import world, _add_goal

@pytest.mark.parametrize('suffix',['','/utility'])
@pytest.mark.parametrize('workspace,expected',[('ws',200),('peer-workspace',404)])
def test_goal_direct_reads_match_workspace_visibility(world,suffix,workspace,expected):
    from api.goal_routes import router
    _add_goal(world['factory'])
    with world['factory']() as db:
        user=User(id='reader',email='reader-scope@example.test',first_name='Reader',last_name='Scope',role='member',status='active',is_active=True,workspace_id=workspace,tenant_id='t')
        db.add(user);db.commit()
    app=FastAPI();app.include_router(router)
    session=world['factory']()
    app.dependency_overrides[get_current_user]=lambda:user
    app.dependency_overrides[get_db]=lambda:session
    try:
        with TestClient(app) as client:
            response=client.get('/api/goals/g-1'+suffix)
        assert response.status_code==expected,(workspace,suffix,response.status_code,response.text)
    finally:session.close()
