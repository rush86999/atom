"""Read real report bytes and bound result receipts around an information wait."""
import hashlib
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree
from tests.test_assignment_routes import route_env
import tests.test_task_wait_independent_work as case


def test_wait_holds_physical_output_then_publishes_current_verified_results(route_env,tmp_path,monkeypatch):
    seen=[];original=case._applied_artifacts
    def observe(assignment):
        seen.append(assignment)
        requested=Path(assignment['provenance']['requested_output_path'])
        assert requested.is_relative_to(tmp_path),'all report effects must remain in scratch'
        if not case._reconciliation(assignment):
            assert not requested.exists(),'a physical partial report exists before the missing invoice is answered'
        return original(assignment)
    monkeypatch.setattr(case,'_applied_artifacts',observe)
    case.test_independent_work_does_not_release_a_premature_final_artifact(route_env,tmp_path,monkeypatch)
    final=seen[-1];reports=original(final);assert len(reports)==1
    step=reports[0];blob=step['result']['artifact'];path=Path(blob['path'])
    assert path.exists() and path.is_relative_to(tmp_path)
    assert hashlib.sha256(path.read_bytes()).hexdigest()==blob['sha256']
    with ZipFile(path) as doc:
        tree=ElementTree.fromstring(doc.read('word/document.xml'))
    text=' '.join(n.text or '' for n in tree.iter() if n.tag.endswith('}t'))
    assert '105.00' in text and '270.00' in text,'the usable final document must contain BOTH verified business results'
    assert case.PO in text,'the document must identify the reconciled purchase order'
    business=[s for s in final['steps'] if s['adapter'] in ('quote.calculate','invoice.reconcile') and s['status']=='applied']
    bound={r['step_id'] for r in step['requires'] if r.get('kind')=='receipt' and r.get('require')=='verified'}
    assert {s['step_id'] for s in business}<=bound,'every composed business result must be receipt-bound'
