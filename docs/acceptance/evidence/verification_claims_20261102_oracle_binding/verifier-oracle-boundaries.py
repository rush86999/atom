import asyncio
import pytest
from core.oracle import validate
import core.oracle.postcondition_verifiers

def _good():
 return {"action_result":"applied","remote_id":"est-1","payload_sha256":"a"*64,"read_receipt":{"resource_id":"est-1","coverage":"single","fields":{"estimate_id":"est-1"}},"verification":{"status":"verified"},"provider_receipt":{"payload_sha256":"a"*64}}

@pytest.mark.parametrize("variant",["missing_verification","empty_verification","digest_disagreement"])
def test_oracle_refuses_unverified_or_inconsistent_receipt(variant):
 payload=_good()
 if variant=="missing_verification":payload.pop("verification")
 elif variant=="empty_verification":payload["verification"]={}
 else:payload["provider_receipt"]={"payload_sha256":"b"*64}
 outcome=asyncio.run(validate("connected.books.create_estimate",payload))
 assert outcome.verified is False,outcome
