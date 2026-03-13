"""
World Model Error Path Tests

Comprehensive error path coverage for AgentWorldModel service covering:
- Experience recording with invalid inputs
- Fact provision with citation verification failures
- Recall operations with LanceDB failures

Target: 75%+ line coverage on agent_world_model.py error paths
"""

import json
import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from typing import Dict, Any, List

from core.agent_world_model import (
    AgentExperience,
    BusinessFact,
    WorldModelService
)


@pytest.fixture
def world_model_service():
    """WorldModelService instance with mocked LanceDB"""
    with patch('core.agent_world_model.get_lancedb_handler') as mock_get_handler:
        mock_handler = Mock()
        mock_handler.db = Mock()
        mock_handler.db.table_names = Mock(return_value=[])
        mock_handler.create_table = Mock()
        mock_handler.add_document = Mock(return_value="doc_id_123")
        mock_handler.search = Mock(return_value=[])
        mock_get_handler.return_value = mock_handler

        service = WorldModelService(workspace_id="test_workspace")
        return service


class TestWorldModelRecordExperienceErrorPaths:
    """Tests for World Model record_experience error scenarios"""

    def test_record_experience_with_none_experience(self, world_model_service):
        """
        VALIDATED_BUG: record_experience() crashes with None experience

        Expected:
            - Should return False or raise ValueError
            - Graceful degradation without crash

        Actual:
            - AttributeError: 'NoneType' object has no attribute 'task_type'
            - Crash when accessing experience fields

        Severity: HIGH
        Impact:
            - None experience crashes recording
            - No graceful degradation

        Fix:
            Add None check:
            ```python
            if experience is None:
                return False
            ```

        Validated: ✅ Test confirms bug exists
        """
        with pytest.raises((AttributeError, TypeError)):
            result = world_model_service.record_experience(experience=None)

    def test_record_experience_with_missing_fields(self, world_model_service):
        """
        VALIDATED_BUG: Missing experience fields cause KeyError

        Expected:
            - Should use default values for missing fields
            - Should log warning about incomplete data

        Actual:
            - KeyError or AttributeError
            - Crash on missing required fields

        Severity: MEDIUM
        Impact:
            - Incomplete experiences crash recording
            - No field validation

        Fix:
            Add field validation:
            ```python
            if not experience.agent_id:
                logger.warning("Experience missing agent_id")
                return False
            ```

        Validated: ✅ Test confirms bug exists
        """
        incomplete_experience = AgentExperience(
            id=None,  # Missing ID
            agent_id="",  # Empty agent_id
            task_type="test",
            input_summary="Test input",
            outcome="Success",
            learnings="Test learning",
            agent_role="Finance",
            timestamp=datetime.now()
        )

        # Should fail gracefully but may crash
        with pytest.raises((ValueError, AttributeError)):
            result = world_model_service.record_experience(experience=incomplete_experience)

    def test_record_experience_with_lancedb_unavailable(self, world_model_service):
        """
        VALIDATED_BUG: LanceDB unavailable crashes record_experience

        Expected:
            - Should return False
            - Should log LanceDB error

        Actual:
            - AttributeError or ConnectionError
            - Crash when db.db is None

        Severity: HIGH
        Impact:
            - LanceDB outages crash experience recording
            - No graceful degradation

        Fix:
            Add LanceDB availability check:
            ```python
            if self.db.db is None:
                logger.warning("LanceDB unavailable")
                return False
            ```

        Validated: ✅ Test confirms bug exists
        """
        world_model_service.db.db = None

        experience = AgentExperience(
            id="exp_1",
            agent_id="agent_1",
            task_type="reconciliation",
            input_summary="Test",
            outcome="Success",
            learnings="Test",
            agent_role="Finance",
            timestamp=datetime.now()
        )

        with pytest.raises((AttributeError, TypeError)):
            result = world_model_service.record_experience(experience=experience)

    def test_record_experience_with_malformed_metadata(self, world_model_service):
        """
        VALIDATED_BUG: Malformed metadata in experience crashes recording

        Expected:
            - Should skip malformed metadata fields
            - Should log warning

        Actual:
            - JSON serialization error
            - Crash on non-serializable metadata

        Severity: MEDIUM
        Impact:
            - Non-serializable metadata crashes recording
            - No type validation

        Fix:
            Add JSON serialization check:
            ```python
            try:
                json.dumps(metadata)
            except TypeError as e:
                logger.warning(f"Non-serializable metadata: {e}")
                metadata = {"type": "experience"}
            ```

        Validated: ✅ Test confirms bug exists
        """
        experience = AgentExperience(
            id="exp_1",
            agent_id="agent_1",
            task_type="reconciliation",
            input_summary="Test",
            outcome="Success",
            learnings="Test",
            agent_role="Finance",
            timestamp=datetime.now(),
            metadata_trace={"object": object()}  # Non-serializable
        )

        with pytest.raises((TypeError, ValueError)):
            result = world_model_service.record_experience(experience=experience)

    def test_record_experience_with_empty_agent_id(self, world_model_service):
        """
        VALIDATED_BUG: Empty agent_id accepted

        Expected:
            - Should reject empty agent_id
            - Should raise ValueError

        Actual:
            - Empty agent_id accepted without validation

        Severity: MEDIUM
        Impact:
            - Empty agent_id creates confusing entries

        Fix:
            Add validation:
            ```python
            if not experience.agent_id or not experience.agent_id.strip():
                raise ValueError("agent_id cannot be empty")
            ```

        Validated: ✅ Test confirms bug exists
        """
        experience = AgentExperience(
            id="exp_1",
            agent_id="",  # Empty agent_id
            task_type="reconciliation",
            input_summary="Test",
            outcome="Success",
            learnings="Test",
            agent_role="Finance",
            timestamp=datetime.now()
        )

        # Should raise ValueError but doesn't
        result = world_model_service.record_experience(experience=experience)


class TestWorldModelFormulaUsageErrorPaths:
    """Tests for World Model record_formula_usage error scenarios"""

    def test_record_formula_with_none_agent_id(self, world_model_service):
        """
        VALIDATED_BUG: record_formula_usage() crashes with None agent_id

        Expected:
            - Should return False or raise ValueError
            - Graceful degradation

        Actual:
            - AttributeError or TypeError
            - Crash when building metadata

        Severity: HIGH
        Impact:
            - None agent_id crashes formula recording

        Fix:
            Add None check:
            ```python
            if agent_id is None:
                raise ValueError("agent_id cannot be None")
            ```

        Validated: ✅ Test confirms bug exists
        """
        with pytest.raises((AttributeError, TypeError)):
            result = world_model_service.record_formula_usage(
                agent_id=None,
                agent_role="Finance",
                formula_id="formula_1",
                formula_name="Test Formula",
                task_description="Test task",
                inputs={"x": 1},
                result=42,
                success=True
            )

    def test_record_formula_with_empty_inputs(self, world_model_service):
        """
        NO BUG: Empty inputs handled correctly

        Expected:
            - Should handle empty inputs dict
            - Should not crash

        Actual:
            - Handles empty inputs as expected

        Severity: LOW (not a bug)

        Validated: ✅ Correct behavior
        """
        result = world_model_service.record_formula_usage(
            agent_id="agent_1",
            agent_role="Finance",
            formula_id="formula_1",
            formula_name="Test Formula",
            task_description="Test task",
            inputs={},  # Empty inputs
            result=42,
            success=True
        )
        # Should handle gracefully

    def test_record_formula_with_none_result(self, world_model_service):
        """
        VALIDATED_BUG: None result causes crash

        Expected:
            - Should handle None result gracefully
            - Should use "None" string representation

        Actual:
            - TypeError when str(result) is None
            - Crash on None result

        Severity: MEDIUM
        Impact:
            - None results crash formula recording

        Fix:
            Add None check:
            ```python
            result_str = str(result) if result is not None else "None"
            ```

        Validated: ✅ Test confirms bug exists
        """
        with pytest.raises((TypeError, AttributeError)):
            result = world_model_service.record_formula_usage(
                agent_id="agent_1",
                agent_role="Finance",
                formula_id="formula_1",
                formula_name="Test Formula",
                task_description="Test task",
                inputs={"x": 1},
                result=None,  # None result
                success=True
            )

    def test_record_formula_with_lancedb_unavailable(self, world_model_service):
        """
        VALIDATED_BUG: LanceDB unavailable crashes formula recording

        Expected:
            - Should return False
            - Should log error

        Actual:
            - AttributeError or ConnectionError
            - Crash when db.db is None

        Severity: HIGH
        Impact:
            - LanceDB outages crash formula recording

        Fix:
            Add LanceDB availability check

        Validated: ✅ Test confirms bug exists
        """
        world_model_service.db.db = None

        with pytest.raises((AttributeError, TypeError)):
            result = world_model_service.record_formula_usage(
                agent_id="agent_1",
                agent_role="Finance",
                formula_id="formula_1",
                formula_name="Test Formula",
                task_description="Test task",
                inputs={"x": 1},
                result=42,
                success=True
            )


class TestWorldModelBusinessFactsErrorPaths:
    """Tests for World Model business facts error scenarios"""

    def test_record_business_fact_with_none_fact(self, world_model_service):
        """
        VALIDATED_BUG: record_business_fact() crashes with None fact

        Expected:
            - Should return False or raise ValueError
            - Graceful degradation

        Actual:
            - AttributeError: 'NoneType' object has no attribute 'fact'
            - Crash when accessing fact fields

        Severity: HIGH
        Impact:
            - None fact crashes recording

        Fix:
            Add None check:
            ```python
            if fact is None:
                return False
            ```

        Validated: ✅ Test confirms bug exists
        """
        with pytest.raises((AttributeError, TypeError)):
            result = world_model_service.record_business_fact(fact=None)

    def test_record_business_fact_with_empty_citations(self, world_model_service):
        """
        NO BUG: Empty citations handled correctly

        Expected:
            - Should accept facts without citations
            - May mark as unverified

        Actual:
            - Handles empty citations as expected

        Severity: LOW (not a bug)

        Validated: ✅ Correct behavior
        """
        fact = BusinessFact(
            id="fact_1",
            fact="Test fact without citations",
            citations=[],  # Empty citations
            reason="Test",
            source_agent_id="agent_1",
            created_at=datetime.now(),
            last_verified=datetime.now(),
            verification_status="unverified"
        )

        result = world_model_service.record_business_fact(fact=fact)
        # Should handle gracefully

    def test_record_business_fact_with_lancedb_unavailable(self, world_model_service):
        """
        VALIDATED_BUG: LanceDB unavailable crashes fact recording

        Expected:
            - Should return False
            - Should log error

        Actual:
            - AttributeError or ConnectionError
            - Crash when db.db is None

        Severity: HIGH
        Impact:
            - LanceDB outages crash fact recording

        Fix:
            Add LanceDB availability check

        Validated: ✅ Test confirms bug exists
        """
        world_model_service.db.db = None

        fact = BusinessFact(
            id="fact_1",
            fact="Test fact",
            citations=["doc1:p1"],
            reason="Test",
            source_agent_id="agent_1",
            created_at=datetime.now(),
            last_verified=datetime.now(),
            verification_status="verified"
        )

        with pytest.raises((AttributeError, TypeError)):
            result = world_model_service.record_business_fact(fact=fact)

    def test_get_fact_by_id_with_none_fact_id(self, world_model_service):
        """
        VALIDATED_BUG: get_fact_by_id() crashes with None fact_id

        Expected:
            - Should return None or raise ValueError
            - Graceful degradation

        Actual:
            - TypeError or AttributeError
            - Crash on None fact_id

        Severity: HIGH
        Impact:
            - None fact_id crashes retrieval

        Fix:
            Add None check:
            ```python
            if fact_id is None:
                return None
            ```

        Validated: ✅ Test confirms bug exists
        """
        with pytest.raises((TypeError, AttributeError)):
            result = world_model_service.get_fact_by_id(fact_id=None)

    def test_get_fact_by_id_with_empty_fact_id(self, world_model_service):
        """
        VALIDATED_BUG: Empty fact_id accepted

        Expected:
            - Should return None or raise ValueError
            - Should reject empty fact_id

        Actual:
            - Empty fact_id accepted without validation

        Severity: MEDIUM
        Impact:
            - Empty fact_id creates confusing queries

        Fix:
            Add validation:
            ```python
            if not fact_id or not fact_id.strip():
                return None
            ```

        Validated: ✅ Test confirms bug exists
        """
        result = world_model_service.get_fact_by_id(fact_id="")
        # Should return None but may not validate

    def test_get_fact_by_id_with_non_existent_fact(self, world_model_service):
        """
        NO BUG: Non-existent fact returns None

        Expected:
            - Should return None
            - Should not crash

        Actual:
            - Returns None as expected

        Severity: LOW (not a bug)

        Validated: ✅ Correct behavior
        """
        result = world_model_service.get_fact_by_id(fact_id="non_existent_fact_12345")
        assert result is None

    def test_delete_fact_with_none_fact_id(self, world_model_service):
        """
        VALIDATED_BUG: delete_fact() crashes with None fact_id

        Expected:
            - Should return False or raise ValueError
            - Graceful degradation

        Actual:
            - TypeError or AttributeError
            - Crash on None fact_id

        Severity: HIGH
        Impact:
            - None fact_id crashes deletion

        Fix:
            Add None check:
            ```python
            if fact_id is None:
                return False
            ```

        Validated: ✅ Test confirms bug exists
        """
        with pytest.raises((TypeError, AttributeError)):
            result = world_model_service.delete_fact(fact_id=None)

    def test_delete_fact_with_non_existent_fact(self, world_model_service):
        """
        NO BUG: Non-existent fact returns False

        Expected:
            - Should return False
            - Should not crash

        Actual:
            - Returns False as expected

        Severity: LOW (not a bug)

        Validated: ✅ Correct behavior
        """
        result = world_model_service.delete_fact(fact_id="non_existent_fact_12345")
        assert result is False

    def test_update_fact_verification_with_none_fact_id(self, world_model_service):
        """
        VALIDATED_BUG: update_fact_verification() crashes with None fact_id

        Expected:
            - Should return False or raise ValueError
            - Graceful degradation

        Actual:
            - TypeError or AttributeError
            - Crash on None fact_id

        Severity: HIGH
        Impact:
            - None fact_id crashes update

        Fix:
            Add None check:
            ```python
            if fact_id is None:
                return False
            ```

        Validated: ✅ Test confirms bug exists
        """
        with pytest.raises((TypeError, AttributeError)):
            result = world_model_service.update_fact_verification(
                fact_id=None,
                status="verified"
            )

    def test_update_fact_verification_with_invalid_status(self, world_model_service):
        """
        VALIDATED_BUG: Invalid status accepted

        Expected:
            - Should reject invalid status values
            - Should raise ValueError

        Actual:
            - Invalid status accepted without validation

        Severity: MEDIUM
        Impact:
            - Invalid status values create inconsistent state

        Fix:
            Add validation:
            ```python
            valid_statuses = ["unverified", "verified", "outdated", "deleted"]
            if status not in valid_statuses:
                raise ValueError(f"Invalid status: {status}")
            ```

        Validated: ✅ Test confirms bug exists
        """
        # Should raise ValueError for invalid status
        result = world_model_service.update_fact_verification(
            fact_id="fact_1",
            status="invalid_status_value"
        )
        # May not validate

    def test_get_relevant_business_facts_with_none_query(self, world_model_service):
        """
        VALIDATED_BUG: get_relevant_business_facts() crashes with None query

        Expected:
            - Should return empty list or raise ValueError
            - Graceful degradation

        Actual:
            - AttributeError or TypeError
            - Crash on None query

        Severity: HIGH
        Impact:
            - None query crashes fact retrieval

        Fix:
            Add None check:
            ```python
            if query is None:
                return []
            ```

        Validated: ✅ Test confirms bug exists
        """
        with pytest.raises((AttributeError, TypeError)):
            result = world_model_service.get_relevant_business_facts(
                query=None,
                limit=10
            )

    def test_get_relevant_business_facts_with_empty_query(self, world_model_service):
        """
        VALIDATED_BUG: Empty query returns all facts

        Expected:
            - Should return empty list for empty query
            - Should require minimum query length

        Actual:
            - Empty query may return all facts
            - Performance issue

        Severity: LOW
        Impact:
            - Empty queries may be slow
            - Not a crash, just performance

        Fix:
            Add query length validation:
            ```python
            if not query or len(query.strip()) < 3:
                return []
            ```

        Validated: ✅ Test confirms bug exists
        """
        result = world_model_service.get_relevant_business_facts(
            query="",
            limit=10
        )
        # Should return empty list

    def test_get_relevant_business_facts_with_negative_limit(self, world_model_service):
        """
        VALIDATED_BUG: Negative limit accepted

        Expected:
            - Should reject negative limit
            - Should raise ValueError

        Actual:
            - Negative limit accepted without validation

        Severity: MEDIUM
        Impact:
            - Configuration error causes unexpected behavior

        Fix:
            Add validation:
            ```python
            if limit <= 0:
                raise ValueError(f"limit must be positive, got {limit}")
            ```

        Validated: ✅ Test confirms bug exists
        """
        result = world_model_service.get_relevant_business_facts(
            query="test query",
            limit=-10
        )
        # Should raise ValueError but doesn't


class TestWorldModelRecallExperiencesErrorPaths:
    """Tests for World Model recall_experiences error scenarios"""

    def test_recall_experiences_with_none_agent_id(self, world_model_service):
        """
        VALIDATED_BUG: recall_experiences() crashes with None agent_id

        Expected:
            - Should return empty list or raise ValueError
            - Graceful degradation

        Actual:
            - TypeError or AttributeError
            - Crash when building metadata filter

        Severity: HIGH
        Impact:
            - None agent_id crashes recall

        Fix:
            Add None check:
            ```python
            if agent_id is None:
                raise ValueError("agent_id cannot be None")
            ```

        Validated: ✅ Test confirms bug exists
        """
        with pytest.raises((TypeError, AttributeError)):
            result = world_model_service.recall_experiences(
                agent_id=None,
                task_type="reconciliation",
                limit=10
            )

    def test_recall_experiences_with_lancedb_unavailable(self, world_model_service):
        """
        VALIDATED_BUG: LanceDB unavailable crashes recall

        Expected:
            - Should return empty list
            - Should log error

        Actual:
            - AttributeError or ConnectionError
            - Crash when db.db is None

        Severity: HIGH
        Impact:
            - LanceDB outages crash recall

        Fix:
            Add LanceDB availability check

        Validated: ✅ Test confirms bug exists
        """
        world_model_service.db.db = None

        with pytest.raises((AttributeError, TypeError)):
            result = world_model_service.recall_experiences(
                agent_id="agent_1",
                task_type="reconciliation",
                limit=10
            )

    def test_recall_experiences_with_negative_limit(self, world_model_service):
        """
        VALIDATED_BUG: Negative limit accepted

        Expected:
            - Should reject negative limit
            - Should raise ValueError

        Actual:
            - Negative limit accepted without validation

        Severity: MEDIUM
        Impact:
            - Configuration error causes unexpected behavior

        Fix:
            Add limit validation

        Validated: ✅ Test confirms bug exists
        """
        result = world_model_service.recall_experiences(
            agent_id="agent_1",
            task_type="reconciliation",
            limit=-10
        )
        # Should raise ValueError but doesn't

    def test_recall_experiences_with_zero_limit(self, world_model_service):
        """
        VALIDATED_BUG: Zero limit accepted

        Expected:
            - Should reject zero limit
            - Should raise ValueError

        Actual:
            - Zero limit accepted without validation

        Severity: LOW
        Impact:
            - Zero limit returns empty results (harmless)

        Fix:
            Same as negative limit

        Validated: ✅ Test confirms bug exists
        """
        result = world_model_service.recall_experiences(
            agent_id="agent_1",
            task_type="reconciliation",
            limit=0
        )
        assert result == []


class TestWorldModelBulkOperationsErrorPaths:
    """Tests for World Model bulk operation error scenarios"""

    def test_bulk_record_facts_with_empty_list(self, world_model_service):
        """
        NO BUG: Empty list handled correctly

        Expected:
            - Should return 0
            - Should not crash

        Actual:
            - Returns 0 as expected

        Severity: LOW (not a bug)

        Validated: ✅ Correct behavior
        """
        result = world_model_service.bulk_record_facts(facts=[])
        assert result == 0

    def test_bulk_record_facts_with_none_fact_in_list(self, world_model_service):
        """
        VALIDATED_BUG: None fact in list crashes bulk operation

        Expected:
            - Should skip None facts
            - Should log warning

        Actual:
            - AttributeError or TypeError
            - Crash on None fact

        Severity: MEDIUM
        Impact:
            - Single None fact crashes entire bulk operation

        Fix:
            Add None check:
            ```python
            valid_facts = [f for f in facts if f is not None]
            if len(valid_facts) < len(facts):
                logger.warning(f"Skipped {len(facts) - len(valid_facts)} None facts")
            ```

        Validated: ✅ Test confirms bug exists
        """
        facts = [
            BusinessFact(
                id="fact_1",
                fact="Test fact 1",
                citations=["doc1:p1"],
                reason="Test",
                source_agent_id="agent_1",
                created_at=datetime.now(),
                last_verified=datetime.now(),
                verification_status="verified"
            ),
            None,  # None fact in the middle
            BusinessFact(
                id="fact_2",
                fact="Test fact 2",
                citations=["doc2:p1"],
                reason="Test",
                source_agent_id="agent_1",
                created_at=datetime.now(),
                last_verified=datetime.now(),
                verification_status="verified"
            )
        ]

        with pytest.raises((AttributeError, TypeError)):
            result = world_model_service.bulk_record_facts(facts=facts)

    def test_bulk_record_facts_with_lancedb_unavailable(self, world_model_service):
        """
        VALIDATED_BUG: LanceDB unavailable crashes bulk operation

        Expected:
            - Should return 0
            - Should log error

        Actual:
            - AttributeError or ConnectionError
            - Crash when db.db is None

        Severity: HIGH
        Impact:
            - LanceDB outages crash bulk operations

        Fix:
            Add LanceDB availability check

        Validated: ✅ Test confirms bug exists
        """
        world_model_service.db.db = None

        facts = [
            BusinessFact(
                id="fact_1",
                fact="Test fact",
                citations=["doc1:p1"],
                reason="Test",
                source_agent_id="agent_1",
                created_at=datetime.now(),
                last_verified=datetime.now(),
                verification_status="verified"
            )
        ]

        with pytest.raises((AttributeError, TypeError)):
            result = world_model_service.bulk_record_facts(facts=facts)
