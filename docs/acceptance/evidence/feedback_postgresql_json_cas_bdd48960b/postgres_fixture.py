"""Reuse exact production feedback race controls on private PostgreSQL, not SQLite."""
import os
import pytest
from sqlalchemy import create_engine,text
from sqlalchemy.orm import Session as RealSession,sessionmaker
from tests.test_employee_feedback_interleaving import *
from tests.test_employee_business_feedback import fresh_router
from core.llm.capability_profiles import reset_capability_evidence_cache

@pytest.fixture()
def feedback_db(tmp_path,monkeypatch):
    import core.database as database
    from core.models import Tenant,LLMRoutingFeedback
    url=os.environ['ATOM_PRIVATE_PG_URL'];expected=os.environ['ATOM_PRIVATE_PG_DATA']
    engine=create_engine(url,connect_args={'options':'-c statement_timeout=8000 -c lock_timeout=3000'})
    with engine.connect() as c:
        got=c.execute(text("SELECT current_setting('data_directory'),inet_server_addr()::text")).one()
        assert got[0]==expected and got[1] is None
    sessions=[]
    class TrackedSession(RealSession):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs);sessions.append(self)
    factory=sessionmaker(bind=engine,class_=TrackedSession)
    with factory() as s:
        s.query(LLMRoutingFeedback).delete()
        if s.get(Tenant,'tenant-ctrl') is None:s.add(Tenant(id='tenant-ctrl',name='scratch',subdomain='scratch-feedback'))
        s.commit()
    monkeypatch.setattr(database,'SessionLocal',factory)
    reset_capability_evidence_cache()
    try:yield {'engine':engine,'Session':factory,'path':expected}
    finally:
        reset_capability_evidence_cache()
        for s in sessions:s.close()
        engine.dispose()
