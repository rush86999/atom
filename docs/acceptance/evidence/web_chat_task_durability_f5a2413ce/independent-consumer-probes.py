"""Independent actual intent consumer controls with real scratch task rows."""
import importlib.util
from pathlib import Path
from core import user_task_service
from core.models import UserTask
from core.atom_agent_endpoints import ChatRequest,handle_task_intent
import asyncio
backend=Path(user_task_service.__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('root_task_fixtures',backend/'tests/api/test_chat_task_durability.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
env=b.env

def invoke(env,title,request_id):
 request=ChatRequest(message='Create a local task',user_id=env['user'].id,context={'request_id':request_id})
 return asyncio.run(handle_task_intent('CREATE_TASK',{'title':title},request,current_user=env['user'],db=env['db']))

def test_unspecified_local_platform_does_not_change_from_title_word(env):
 result=invoke(env,'Prepare Asana training notes','root-local-title')
 assert result['success'] is True,'A title naming a product is not an external-provider request'
 row=env['db'].query(UserTask).one()
 assert row.title=='Prepare Asana training notes'

def test_identical_consumer_retry_without_due_date_keeps_one_task(env):
 first=invoke(env,'Review tomorrow staffing','root-repeat-intent')
 second=invoke(env,'Review tomorrow staffing','root-repeat-intent')
 assert first['success'] and second['success']
 assert first['response']['data']['task']['id']==second['response']['data']['task']['id']
 row=env['db'].query(UserTask).one()
 assert row.due_date is None

def test_changed_consumer_material_does_not_replay_prior_success(env):
 first=invoke(env,'Review original item','root-changed-intent')
 second=invoke(env,'Review changed item','root-changed-intent')
 assert first['success'] and not second['success']
 assert env['db'].query(UserTask).one().title=='Review original item'
