"""After acceptance, a missing current revision cannot certify the old pin."""
import pytest
from tests.test_assignment_routes import route_env
from tests.test_lead_wait_source_progress_and_extraction import test_valid_indexed_source_version_is_not_a_binary_file_digest as _valid_current

@pytest.mark.parametrize('missing', [None, ''])
def test_current_authority_loses_revision_after_accepted_read(route_env, tmp_path, monkeypatch, missing):
    from core.assignment_executor import AssignmentExecutor
    from core.models import IngestedDocument
    original = AssignmentExecutor._source_consumption_gap
    def after_revision_removed(self, assignment, record):
        db=route_env['db']
        row=db.query(IngestedDocument).filter(IngestedDocument.id=='lead-indexed-current').one()
        row.source_content_hash=missing
        db.commit()
        problem=original(self,assignment,record)
        assert problem is not None, 'missing authoritative source revision certified an old accepted indexed receipt'
        return None
    monkeypatch.setattr(AssignmentExecutor,'_source_consumption_gap',after_revision_removed)
    _valid_current(route_env,tmp_path,monkeypatch,'ev4')
