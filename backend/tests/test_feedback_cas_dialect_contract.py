"""The actual JSONColumn CAS expressions must compile on both supported dialects."""
from types import SimpleNamespace
import pytest
from sqlalchemy import and_,select
from sqlalchemy.dialects import postgresql,sqlite
from core.learning_llm_router import LearningBasedRouter,RoutingFeedback
from core.models import LLMRoutingFeedback

@pytest.mark.parametrize("dialect", ["postgresql", "sqlite"])
@pytest.mark.parametrize("business", [True, False])
def test_actual_jsoncolumn_cas_preserves_receipt_and_revision(dialect,business):
    row=SimpleNamespace(id="row-a",tenant_id="tenant-a",success=True,quality_satisfied=True,user_satisfaction=.8)
    feedback=RoutingFeedback(routing_result_id="generation-a",tenant_id="tenant-a",model_id="model-a",task_type="general",success=False,quality_satisfied=False,cost_within_budget=True,provider_id="provider-a",workspace_id="workspace-a",capability_profile="profile-a",capability_profile_version="version-a")
    stored={"evaluation_revision":7}
    predicates=LearningBasedRouter._annotation_cas_predicates(dialect,row,stored,feedback,business_binding=business)
    compiled=select(LLMRoutingFeedback.id).where(and_(*predicates)).compile(dialect=postgresql.dialect() if dialect=="postgresql" else sqlite.dialect())
    values=list(compiled.params.values())
    for required in ["row-a","generation-a","model-a","tenant-a",7]:assert required in values
    for binding in ["provider-a","workspace-a","profile-a","version-a"]:
        assert (binding in values) is business
    assert "coalesce" in str(compiled).lower()
    if dialect=="postgresql":
        assert "->>" in str(compiled)
        # ``->>`` is type-blind; business bindings additionally pin the JSON
        # type to string. 123 and "123" then no longer share a predicate.
        assert ("jsonb_typeof" in str(compiled)) is business
        if business:assert "string" in values
    else:assert "json_extract" in str(compiled)


def test_unknown_annotation_dialect_still_refuses():
    row=SimpleNamespace(id="row-a",tenant_id="tenant-a",success=True,quality_satisfied=True,user_satisfaction=None)
    feedback=RoutingFeedback(routing_result_id="generation-a",tenant_id="tenant-a",model_id="model-a",task_type="general",success=True,quality_satisfied=True,cost_within_budget=True)
    assert LearningBasedRouter._annotation_cas_predicates("unsupported",row,{},feedback,business_binding=False) is None
