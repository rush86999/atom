from __future__ import annotations
import json
from types import SimpleNamespace
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from core.auth import get_current_user
from core.canvas_capability_service import CapabilityError, bind_dataset, current_revision, derive_operation, edit_operation, effective_operations, get_manifest, set_manifest
from core.database import Base, get_db
from core.deployment_audience import require_pilot_user
from core.models import Canvas

@pytest.fixture()
def db():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()

@pytest.fixture()
def user():
    return SimpleNamespace(id='typed-user', workspace_id='ws-typed', tenant_id='tenant-typed', role='workspace_admin', is_active=True)

def _quote_fields():
    return [{'id': 'item_id', 'label': 'Item', 'type': 'string', 'column': 'Item', 'required': True}, {'id': 'quantity', 'label': 'Quantity', 'type': 'decimal', 'column': 'Qty', 'unit': 'each', 'required': True, 'editable': True}, {'id': 'unit_price', 'label': 'Unit price', 'type': 'currency', 'column': 'Price', 'currency': 'USD', 'required': True, 'editable': True}, {'id': 'line_total', 'label': 'Line total', 'type': 'currency', 'column': 'Line Total', 'currency': 'USD', 'derived': 'quantity * unit_price', 'aggregate': 'sum', 'group_by': 'item_id'}]

def _quote_manifest():
    return {'schema_version': 2, 'base_component': 'table', 'operations': ['read', 'derive', 'edit', 'export', 'bind'], 'data_binding': {'subject_field': 'Item'}, 'fields': _quote_fields(), 'outputs': ['xlsx']}

def _service_manifest():
    return {'schema_version': 2, 'base_component': 'form', 'operations': ['read', 'derive', 'edit', 'bind'], 'data_binding': {'subject_field': 'Service'}, 'fields': [{'id': 'service', 'label': 'Service', 'type': 'string', 'column': 'Service', 'required': True}, {'id': 'hours', 'label': 'Hours', 'type': 'decimal', 'column': 'Hours', 'unit': 'hour', 'required': True, 'editable': True}, {'id': 'rate', 'label': 'Rate', 'type': 'currency', 'column': 'Rate', 'currency': 'CAD', 'required': True, 'editable': True}, {'id': 'fee_total', 'label': 'Fee total', 'type': 'currency', 'column': 'Fee Total', 'currency': 'CAD', 'derived': 'hours * rate', 'aggregate': 'sum', 'group_by': 'service'}], 'outputs': ['xlsx']}

def _queue_manifest():
    return {'schema_version': 2, 'base_component': 'queue', 'operations': ['read', 'derive', 'edit', 'select', 'bind'], 'data_binding': {'subject_field': 'Exception', 'status_field': 'Status'}, 'fields': [{'id': 'exception_id', 'label': 'Exception', 'type': 'string', 'column': 'Exception', 'required': True, 'aggregate': 'count', 'group_by': 'status'}, {'id': 'amount', 'label': 'Amount', 'type': 'currency', 'column': 'Amount', 'currency': 'USD', 'required': True, 'editable': True, 'aggregate': 'sum', 'group_by': 'status'}, {'id': 'status', 'label': 'Status', 'type': 'string', 'column': 'Status', 'required': True, 'editable': True}], 'outputs': ['xlsx']}

def _canvas(db, user, canvas_id, name, base='table'):
    row = Canvas(id=canvas_id, tenant_id=user.tenant_id, workspace_id=user.workspace_id, created_by=user.id, name=name, canvas_type=base, content={}, status='active')
    db.add(row)
    db.commit()
    return row

def _bind_and_derive(db, user, canvas, manifest, columns, rows):
    set_manifest(db, canvas, user, manifest)
    bound = bind_dataset(db, canvas, user, columns, rows, source={'file_name': f'{canvas.id}.csv'})
    result = derive_operation(db, canvas, user, expected_revision=bound['revision'], manifest_revision_value=bound['manifest']['manifest_revision'], source_version=bound['source']['source_version'])
    return (bound, result)

def _client(db, user):
    from api.canvas_capability_routes import router
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[require_pilot_user] = lambda: user
    return TestClient(app)

def test_old_open_clarification_cannot_modify_replacement_source(db, user):
    canvas = _canvas(db, user, "verify-stale", "Stale binding")
    set_manifest(db, canvas, user, _quote_manifest())
    bound = bind_dataset(db, canvas, user, ["Item", "Qty", "Price"], [["A", "", "100"]], source={"file_name":"a.csv"})
    client = _client(db,user)
    opened = client.post("/api/canvas/verify-stale/capability/derive", json={"expected_revision":bound["revision"],"manifest_revision":bound["manifest"]["manifest_revision"],"source_version":bound["source"]["source_version"]})
    cid=opened.json()["clarification"]["id"]
    replacement = bind_dataset(db, canvas, user, ["Item", "Qty", "Price"], [["B", "", "1000"]], source={"file_name":"b.csv"})
    answer=client.post(f"/api/canvas/verify-stale/capability/derive/{cid}/answer", json={"expected_revision":replacement["revision"],"answers":[{"row":2,"field_id":"quantity","value":"2"}]})
    assert answer.status_code==409, answer.text

def test_cross_currency_addition_requires_conversion(db,user):
    canvas=_canvas(db,user,"verify-units","Units")
    manifest={"schema_version":2,"base_component":"table","operations":["read","derive","bind"],"data_binding":{"subject_field":"Item"},"fields":[
        {"id":"item","type":"string","column":"Item","required":True},
        {"id":"usd","type":"currency","column":"USD","currency":"USD","required":True},
        {"id":"cad","type":"currency","column":"CAD","currency":"CAD","required":True},
        {"id":"total","type":"currency","column":"Total","currency":"USD","derived":"usd + cad","aggregate":"sum"}]}
    with pytest.raises(CapabilityError):
        _bind_and_derive(db,user,canvas,manifest,["Item","USD","CAD"],[["A","10","20"]])

def test_stale_session_answer_cannot_overwrite_other_session_source(db, user):
    from core.canvas_capability_service import answer_derive_clarification, get_dataset
    from sqlalchemy.orm import Session
    canvas = _canvas(db,user,'verify-stale-session','Stale session')
    set_manifest(db,canvas,user,_quote_manifest())
    bound=bind_dataset(db,canvas,user,['Item','Qty','Price'],[['A','','100']],source={'file_name':'a.csv'})
    client=_client(db,user)
    opened=client.post('/api/canvas/verify-stale-session/capability/derive',json={'expected_revision':bound['revision'],'manifest_revision':bound['manifest']['manifest_revision'],'source_version':bound['source']['source_version']})
    cid=opened.json()['clarification']['id']
    writer=Session(bind=db.get_bind(),expire_on_commit=False)
    replacement=writer.query(Canvas).filter(Canvas.id==canvas.id).one()
    bind_dataset(writer,replacement,user,['Item','Qty','Price'],[['B','','1000']],source={'file_name':'b.csv'})
    with pytest.raises(CapabilityError):
        answer_derive_clarification(db,canvas,user,cid,[{'row':2,'field_id':'quantity','value':'2'}],expected_revision=bound['revision'])
    writer.expire_all()
    assert get_dataset(writer.query(Canvas).filter(Canvas.id==canvas.id).one())['rows'][0][0]=='B'
    writer.close()
