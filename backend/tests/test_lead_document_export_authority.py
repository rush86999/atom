import pytest
from tests.test_document_export import exported, _seed_vector, _seed_sql

@pytest.mark.parametrize('change', ['matching','indexed_workspace','indexed_tenant','unknown_freshness'])
def test_export_rejects_contradictory_extraction_scope_and_unknown_freshness(exported,change):
    doc_id='lead-export-'+change
    version='ev4:'+'a'*64
    meta={'pg_document_id':doc_id,'source_content_hash':version,'workspace_id':exported.workspace,'tenant_id':'t1'}
    if change=='indexed_workspace': meta['workspace_id']='foreign-workspace'
    if change=='indexed_tenant': meta['tenant_id']='foreign-tenant'
    _seed_vector(exported,text='Current scoped document.',doc_id=doc_id,metadata=meta,source='connector:document')
    row=_seed_sql(exported,doc_id,version=version,integration='connector',external_id='connector-record')
    if change=='unknown_freshness':
        row.freshness_status='';exported.session.commit()
    response=exported.client.get(f'/api/documents/{doc_id}/export?format=json')
    if change=='matching':
        assert response.status_code==200,response.text
    else:
        assert response.status_code in (403,404,409),(change,response.status_code,response.text)
