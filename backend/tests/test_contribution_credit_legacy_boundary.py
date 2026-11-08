"""A caller-owned flag and invented receipt id are not verifier evidence."""
from core.contribution_credit import apply_credit
from core.models import AgentRegistry
from tests.test_autonomy_revocation import store


def test_legacy_helper_cannot_promote_a_claimed_receipt(store):
    _Session,db=store
    assert apply_credit(db,[{'agent_id':'agent-revocation-1','weight':1.0,
        'capability':'canvas.unproved','verified':True,
        'source_record_id':'no-such-durable-operation'}])==1
    db.expire_all()
    stats=db.get(AgentRegistry,'agent-revocation-1').configuration['capability_stats']['canvas.unproved']
    assert stats.get('verified_success',0)==0
