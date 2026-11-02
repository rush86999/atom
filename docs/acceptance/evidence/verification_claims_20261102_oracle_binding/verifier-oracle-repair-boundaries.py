import asyncio
import uuid
import pytest
from core.action_registry import action_registry
from core.assignment_executor import _action_registry_adapter
from core.oracle import register_postcondition
from core.oracle.postcondition_verifiers import _verify_connected_mutation

CONTEXT={'workspace_id':'ws-1','employee_id':'user-1','tenant_id':'t1','run_id':'r1','assignment_id':'a1'}

def _result():
 return {'status':'success','action_result':'applied','remote_id':'remote-1','payload_sha256':'b'*64,'provider_receipt':{'payload_sha256':'b'*64},'read_receipt':{'resource_id':'remote-1','coverage':'single','fields':{'id':'remote-1'}},'verification':{'status':'verified','missing_fields':[],'mismatches':[]}}

def _action():
 name='test.verifier.oracle.'+uuid.uuid4().hex
 async def handler(args,context):return _result()
 action_registry.register(name,handler,effects=[{'effect':'create'}])
 register_postcondition(name)(_verify_connected_mutation)
 return name

def test_oracle_exception_after_effect_is_not_applied(monkeypatch):
 import core.oracle as oracle
 name=_action()
 async def unavailable(*args,**kwargs):raise RuntimeError('oracle unavailable')
 monkeypatch.setattr(oracle,'validate',unavailable)
 result=asyncio.run(_action_registry_adapter({'action':name,'arguments':{}},CONTEXT))
 assert result['status']=='uncertain',result

def test_result_digest_cannot_replace_expected_request_digest():
 name=_action()
 result=asyncio.run(_action_registry_adapter({'action':name,'arguments':{'payload_sha256':'a'*64}},CONTEXT))
 assert result['status']=='uncertain',result

def test_outlook_readback_requires_same_remote_object(monkeypatch):
 from core import connected_actions as actions
 class Fake:
  async def _get_access_token(self,user_id):return 'controlled'
  async def create_draft_email(self,**kwargs):return {'id':'created-1'}
  async def get_email_by_id(self,user_id,email_id,token=None):
   return {'id':'other-object','subject':'Quote','body':{'content':'Draft body'},'toRecipients':[{'emailAddress':{'address':'buyer@example.invalid'}}],'ccRecipients':[],'bccRecipients':[]}
 monkeypatch.setattr('integrations.outlook_service.OutlookService',lambda *a,**k:Fake())
 result=asyncio.run(actions.outlook_create_draft({'to':['buyer@example.invalid'],'subject':'Quote','body':'Draft body','operation_id':'op-verifier'}, {'user_id':'user-1','tenant_id':'t1'}))
 assert result['action_result']!='applied',result
