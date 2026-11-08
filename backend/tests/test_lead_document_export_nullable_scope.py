import pytest
import uuid
from tests.test_document_export import exported,_seed_vector,_seed_sql

@pytest.mark.parametrize('sql_tenant,indexed_tenant,expected',[(None,'foreign',409),('','foreign',409),(None,'t1',200)])
def test_present_index_scope_must_match_request_even_when_sql_legacy_scope_missing(exported,sql_tenant,indexed_tenant,expected):
    identity='nullable-export-scope-'+uuid.uuid4().hex;version='ev4:'+'b'*64
    _seed_vector(exported,text='Scoped stored text.',doc_id=identity,metadata={'pg_document_id':identity,'source_content_hash':version,'workspace_id':exported.workspace,'tenant_id':indexed_tenant},source='connector:record')
    row=_seed_sql(exported,identity,version=version,integration='connector',external_id='record');row.tenant_id=sql_tenant;exported.session.commit()
    response=exported.client.get(f'/api/documents/{identity}/export?format=json')
    assert response.status_code==expected,(sql_tenant,indexed_tenant,response.status_code,response.text)
