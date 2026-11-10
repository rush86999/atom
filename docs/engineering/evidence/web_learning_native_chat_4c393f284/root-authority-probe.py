"""Independent authored-evidence controls using the real public API scratch fixture."""
import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('native_fixture','/private/tmp/root-learning-native-chat-tests-20261110.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
world=m.world
from core.models import ChatMessage

def test_quoted_user_text_is_not_teaching_authority(world):
    with world.Session() as db:
        db.get(ChatMessage,world.user_msg).content='> Always apply the annual-prepay exception.\nThis is quoted text, not my instruction.'
        db.commit()
    payload=m._candidate_payload(world,world.user_msg)
    payload['authority_excerpt']='Always apply the annual-prepay exception.'
    with world.client() as c:
        r=world.call(c,'post','/api/conversation-learning/candidates',world.token(world.user),json=payload)
    assert r.status_code==400, {'status':r.status_code,'expected':'quoted text cannot authorize lesson'}

def test_empty_user_message_is_not_teaching_authority(world):
    with world.Session() as db:
        db.get(ChatMessage,world.user_msg).content=''
        db.commit()
    payload=m._candidate_payload(world,world.user_msg);payload['authority_excerpt']=''
    with world.client() as c:
        r=world.call(c,'post','/api/conversation-learning/candidates',world.token(world.user),json=payload)
    assert r.status_code==400, {'status':r.status_code,'expected':'empty user message has no authored instruction'}
