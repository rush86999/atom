"""Independent same-workspace private-source candidate controls."""
import sys
sys.path.insert(0,'/private/tmp/atom-web-task-project-20261109/backend/tests/api')
from test_conversation_learning_native_chat import world,_candidate_payload
from core.models import User,ConversationEvent

def setup_owner_candidate_and_peer(w):
    with w.Session() as db:
        db.add(User(id='same-workspace-peer',email='peer@example.invalid',first_name='Peer',last_name='Reviewer',tenant_id=w.tenant,workspace_id=w.ws,role='member',status='active',is_active=True,hashed_password='unused-scratch'))
        db.commit()
    with w.client() as c:
        r=w.call(c,'post','/api/conversation-learning/candidates',w.token(w.user),json=_candidate_payload(w,w.user_msg))
    assert r.status_code==200,r.text
    with w.Session() as db:before=db.query(ConversationEvent).filter_by(conversation_id=w.chat).count()
    return r.json()['candidate']['candidate_id'],before

def test_same_workspace_peer_cannot_read_or_invalidate_private_chat_candidate(world):
    cid,before=setup_owner_candidate_and_peer(world)
    with world.client() as c:
        r=world.call(c,'get',f'/api/conversation-learning/candidates/{cid}',world.token('same-workspace-peer'),params={'thread_id':world.chat,'source_kind':'native_chat'})
    with world.Session() as db:after=db.query(ConversationEvent).filter_by(conversation_id=world.chat).count()
    assert r.status_code==404,{'status':r.status_code,'events_before':before,'events_after':after}
    assert after==before

def test_same_workspace_peer_cannot_reject_private_chat_candidate(world):
    cid,before=setup_owner_candidate_and_peer(world)
    with world.client() as c:
        r=world.call(c,'post',f'/api/conversation-learning/candidates/{cid}/reject',world.token('same-workspace-peer'),json={'thread_id':world.chat,'source_kind':'native_chat','reviewer':'peer','reason':'synthetic unauthorized attempt'})
    with world.Session() as db:after=db.query(ConversationEvent).filter_by(conversation_id=world.chat).count()
    assert r.status_code==404,{'status':r.status_code,'events_before':before,'events_after':after}
    assert after==before
