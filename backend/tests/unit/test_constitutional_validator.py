"""
Unit tests for Constitutional Validator

Tests cover:
- Validator initialization
- Constitutional rules loading
- Episode segment validation
- Domain-specific compliance checks
- Action validation against rules
- Violation detection and scoring
- Knowledge Graph integration
- Rule violation checking
- Compliance score calculation
- Domain constraints checking
- Fallback validation
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.constitutional_validator import (
    ConstitutionalValidator,
    ViolationSeverity,
    get_constitutional_validator
)
from core.models import Episode, EpisodeSegment


@pytest.fixture
def mock_db():
    """Mock database session"""
    db = Mock(spec=Session)
    db.add = Mock()
    db.commit = Mock()
    db.rollback = Mock()
    db.refresh = Mock()
    db.query = Mock()
    return db


@pytest.fixture
def validator(mock_db):
    """Create ConstitutionalValidator instance"""
    return ConstitutionalValidator(mock_db)


@pytest.fixture
def sample_segment():
    """Create sample episode segment"""
    segment = Mock(spec=EpisodeSegment)
    segment.id = "segment_1"
    segment.segment_type = "action"
    segment.content = '{"action": "test_action", "data": "test_data"}'
    segment.timestamp = datetime.now()
    segment.metadata = {"logged": True}
    return segment


@pytest.fixture
def sample_segments():
    """Create multiple sample segments"""
    segments = []
    for i in range(3):
        segment = Mock(spec=EpisodeSegment)
        segment.id = f"segment_{i}"
        segment.segment_type = "action"
        segment.content = f'{{"action": "action_{i}", "data": "data_{i}"}}'
        segment.timestamp = datetime.now() + timedelta(seconds=i * 10)
        segment.metadata = {"logged": True}
        segments.append(segment)
    return segments


# ============================================================================
# Initialization Tests
# ============================================================================

def test_validator_initialization(validator, mock_db):
    """Test validator initializes correctly"""
    assert validator is not None
    assert validator.db == mock_db
    assert hasattr(validator, 'CONSTITUTIONAL_RULES')
    assert len(validator.CONSTITUTIONAL_RULES) > 0


def test_constitutional_rules_loaded(validator):
    """Test constitutional rules are loaded"""
    rules = validator.CONSTITUTIONAL_RULES
    assert isinstance(rules, dict)
    assert len(rules) >= 10  # Should have at least 10 rules

    # Check required rule categories
    categories = [rule.get("category") for rule in rules.values()]
    assert "safety" in categories
    assert "financial" in categories
    assert "privacy" in categories
    assert "transparency" in categories
    assert "governance" in categories


def test_rule_structure(validator):
    """Test all rules have required structure"""
    for rule_id, rule in validator.CONSTITUTIONAL_RULES.items():
        assert "category" in rule
        assert "description" in rule
        assert "severity" in rule
        assert "domains" in rule
        assert isinstance(rule["domains"], list)


def test_violation_severity_levels():
    """Test violation severity levels are defined"""
    assert hasattr(ViolationSeverity, 'CRITICAL')
    assert hasattr(ViolationSeverity, 'HIGH')
    assert hasattr(ViolationSeverity, 'MEDIUM')
    assert hasattr(ViolationSeverity, 'LOW')
    assert ViolationSeverity.CRITICAL == "critical"
    assert ViolationSeverity.HIGH == "high"
    assert ViolationSeverity.MEDIUM == "medium"
    assert ViolationSeverity.LOW == "low"


def test_get_constitutional_validator_singleton(mock_db):
    """Test singleton helper function"""
    validator1 = get_constitutional_validator(mock_db)
    validator2 = get_constitutional_validator(mock_db)
    # Should return instances (not true singleton, but helper function)
    assert validator1 is not None
    assert validator2 is not None


# ============================================================================
# validate_actions Tests
# ============================================================================

def test_validate_actions_empty_list(validator):
    """Test validation with empty segment list"""
    result = validator.validate_actions([])

    assert result["compliant"] is True
    assert result["score"] == 1.0
    assert result["violations"] == []
    assert result["total_actions"] == 0
    assert result["checked_actions"] == 0


def test_validate_actions_none_input(validator):
    """Test validation with None input"""
    result = validator.validate_actions(None)

    assert result["compliant"] is True
    assert result["score"] == 1.0
    assert result["violations"] == []
    assert result["total_actions"] == 0
    assert result["checked_actions"] == 0


def test_validate_actions_success(validator, sample_segments):
    """Test successful validation of compliant actions"""
    result = validator.validate_actions(sample_segments)

    assert "compliant" in result
    assert "score" in result
    assert "violations" in result
    assert "total_actions" in result
    assert "checked_actions" in result
    assert result["total_actions"] == 3
    assert result["checked_actions"] == 3


def test_validate_actions_with_domain(validator, sample_segments):
    """Test validation with domain-specific rules"""
    result = validator.validate_actions(sample_segments, domain="financial")

    assert result["total_actions"] == 3
    # Financial domain should filter rules
    assert isinstance(result["violations"], list)


def test_validate_actions_invalid_segment(validator):
    """Test validation handles invalid segment gracefully"""
    invalid_segment = Mock(spec=EpisodeSegment)
    invalid_segment.id = "invalid"
    invalid_segment.segment_type = "action"
    invalid_segment.content = None  # Invalid content
    invalid_segment.timestamp = datetime.now()
    invalid_segment.metadata = {}

    result = validator.validate_actions([invalid_segment])

    # Should handle gracefully, not crash
    assert "compliant" in result
    # The implementation counts the segment even if extraction fails
    # but it doesn't increment checked_actions
    assert result["checked_actions"] == 0  # Extraction failed, not checked


def test_validate_actions_all_domains(validator, sample_segments):
    """Test validation applies all domain rules when domain=None"""
    result = validator.validate_actions(sample_segments, domain=None)

    # Should check all rules with "all" domain
    assert result["total_actions"] == 3
    assert result["checked_actions"] == 3


# ============================================================================
# check_compliance Tests
# ============================================================================

def test_check_compliance_no_actions(validator):
    """Test compliance check with no actions"""
    result = validator.check_compliance("financial", [])

    assert result["compliant"] is True
    assert result["score"] == 1.0
    assert result["violations"] == []
    assert result["domain"] == "financial"


def test_check_compliance_financial_domain(validator):
    """Test financial domain compliance check"""
    actions = [
        {"action_type": "payment", "approval_required": True}
    ]

    result = validator.check_compliance("financial", actions)

    assert result["domain"] == "financial"
    assert "compliant" in result
    assert "score" in result


def test_check_compliance_healthcare_domain(validator):
    """Test healthcare domain compliance check"""
    actions = [
        {"action_type": "data_access", "authorized": True}
    ]

    result = validator.check_compliance("healthcare", actions)

    assert result["domain"] == "healthcare"
    assert isinstance(result["violations"], list)


def test_check_compliance_unknown_domain(validator):
    """Test compliance check with unknown domain"""
    actions = [{"action_type": "test"}]

    result = validator.check_compliance("unknown_domain", actions)

    # Should still process, just no domain-specific rules
    assert result["domain"] == "unknown_domain"


# ============================================================================
# calculate_score Tests
# ============================================================================

def test_calculate_score_no_violations(validator):
    """Test score calculation with no violations"""
    score = validator.calculate_score([])

    assert score == 1.0


def test_calculate_score_low_severity_violations(validator):
    """Test score calculation with low severity violations"""
    violations = [
        {"severity": ViolationSeverity.LOW},
        {"severity": ViolationSeverity.LOW}
    ]

    score = validator.calculate_score(violations)

    assert 0.9 <= score <= 1.0  # Should have minimal impact


def test_calculate_score_critical_violations(validator):
    """Test score calculation with critical violations"""
    violations = [
        {"severity": ViolationSeverity.CRITICAL},
        {"severity": ViolationSeverity.CRITICAL}
    ]

    score = validator.calculate_score(violations)

    assert 0.0 <= score < 0.8  # Should have major impact


def test_calculate_score_mixed_severity(validator):
    """Test score calculation with mixed severity violations"""
    violations = [
        {"severity": ViolationSeverity.CRITICAL},
        {"severity": ViolationSeverity.HIGH},
        {"severity": ViolationSeverity.MEDIUM},
        {"severity": ViolationSeverity.LOW}
    ]

    score = validator.calculate_score(violations)

    assert 0.0 <= score <= 1.0


def test_calculate_score_many_violations(validator):
    """Test score calculation with many violations"""
    violations = [
        {"severity": ViolationSeverity.HIGH}
        for _ in range(20)
    ]

    score = validator.calculate_score(violations)

    assert score >= 0.0  # Should not go negative


# ============================================================================
# _extract_action_data Tests
# ============================================================================

def test_extract_action_data_success(validator, sample_segment):
    """Test successful action data extraction"""
    action = validator._extract_action_data(sample_segment)

    assert action is not None
    assert action["action_type"] == "action"
    assert "content" in action
    assert "timestamp" in action
    assert "metadata" in action


def test_extract_action_data_json_content(validator):
    """Test extraction with JSON string content"""
    segment = Mock(spec=EpisodeSegment)
    segment.id = "segment_json"
    segment.segment_type = "json_action"
    segment.content = '{"key": "value", "number": 123}'
    segment.timestamp = datetime.now()
    segment.metadata = {}

    action = validator._extract_action_data(segment)

    assert action is not None
    assert action["content"]["key"] == "value"
    assert action["content"]["number"] == 123


def test_extract_action_data_dict_content(validator):
    """Test extraction with dict content"""
    segment = Mock(spec=EpisodeSegment)
    segment.id = "segment_dict"
    segment.segment_type = "dict_action"
    segment.content = {"key": "value"}  # Already a dict
    segment.timestamp = datetime.now()
    segment.metadata = {}

    action = validator._extract_action_data(segment)

    assert action is not None
    assert action["content"]["key"] == "value"


def test_extract_action_data_invalid_json(validator):
    """Test extraction handles invalid JSON gracefully"""
    segment = Mock(spec=EpisodeSegment)
    segment.id = "segment_invalid"
    segment.segment_type = "action"
    segment.content = "{invalid json"
    segment.timestamp = datetime.now()
    segment.metadata = {}

    action = validator._extract_action_data(segment)

    # Should return None on error
    assert action is None


def test_extract_action_data_missing_timestamp(validator):
    """Test extraction handles missing timestamp"""
    segment = Mock(spec=EpisodeSegment)
    segment.id = "segment_no_time"
    segment.segment_type = "action"
    segment.content = '{"test": "data"}'
    segment.timestamp = None
    segment.metadata = {}

    action = validator._extract_action_data(segment)

    assert action is not None
    assert action["timestamp"] is None


def test_extract_action_data_missing_metadata(validator):
    """Test extraction handles missing metadata"""
    segment = Mock(spec=EpisodeSegment)
    segment.id = "segment_no_meta"
    segment.segment_type = "action"
    segment.content = '{"test": "data"}'
    segment.timestamp = datetime.now()
    segment.metadata = None

    action = validator._extract_action_data(segment)

    assert action is not None
    assert action["metadata"] == {}


# ============================================================================
# _check_rule_violation Tests
# ============================================================================

def test_check_rule_violation_pii_exposure(validator):
    """Test PII exposure violation detection"""
    action = {
        "action_type": "data_access",
        "content": {"ssn": "123-45-6789", "name": "John Doe"}
    }

    violation = validator._check_rule_violation(
        action,
        "safety_no_pii_exposure",
        validator.CONSTITUTIONAL_RULES["safety_no_pii_exposure"]
    )

    assert violation is not None
    assert violation["rule_id"] == "safety_no_pii_exposure"
    assert violation["severity"] == ViolationSeverity.HIGH
    assert "PII" in violation["details"]


def test_check_rule_violation_no_pii(validator):
    """Test action without PII doesn't trigger violation"""
    action = {
        "action_type": "data_access",
        "content": {"name": "John Doe", "city": "NYC"}
    }

    violation = validator._check_rule_violation(
        action,
        "safety_no_pii_exposure",
        validator.CONSTITUTIONAL_RULES["safety_no_pii_exposure"]
    )

    assert violation is None


def test_check_rule_violation_unauthorized_payment(validator):
    """Test unauthorized payment violation detection"""
    action = {
        "action_type": "payment",
        "content": {"amount": 1000, "to": "merchant"}
    }

    violation = validator._check_rule_violation(
        action,
        "financial_no_unauthorized_payments",
        validator.CONSTITUTIONAL_RULES["financial_no_unauthorized_payments"]
    )

    assert violation is not None
    assert violation["rule_id"] == "financial_no_unauthorized_payments"
    assert violation["severity"] == ViolationSeverity.CRITICAL


def test_check_rule_violation_authorized_payment(validator):
    """Test authorized payment doesn't trigger violation"""
    action = {
        "action_type": "payment",
        "content": {"amount": 1000, "approval_required": True}
    }

    violation = validator._check_rule_violation(
        action,
        "financial_no_unauthorized_payments",
        validator.CONSTITUTIONAL_RULES["financial_no_unauthorized_payments"]
    )

    assert violation is None


def test_check_rule_violation_audit_trail_missing(validator):
    """Test missing audit trail violation detection"""
    action = {
        "action_type": "critical_action",
        "content": {"data": "value"},
        "metadata": {"logged": False}
    }

    violation = validator._check_rule_violation(
        action,
        "governance_audit_trail",
        validator.CONSTITUTIONAL_RULES["governance_audit_trail"]
    )

    assert violation is not None
    assert violation["rule_id"] == "governance_audit_trail"


def test_check_rule_violation_audit_trail_present(validator):
    """Test action with audit trail doesn't trigger violation"""
    action = {
        "action_type": "critical_action",
        "content": {"data": "value"},
        "metadata": {"logged": True}
    }

    violation = validator._check_rule_violation(
        action,
        "governance_audit_trail",
        validator.CONSTITUTIONAL_RULES["governance_audit_trail"]
    )

    assert violation is None


# ============================================================================
# _calculate_compliance_score Tests
# ============================================================================

def test_calculate_compliance_score_no_violations(validator):
    """Test compliance score with no violations"""
    score = validator._calculate_compliance_score([], 10)

    assert score == 1.0


def test_calculate_compliance_score_no_actions(validator):
    """Test compliance score with no actions"""
    score = validator._calculate_compliance_score([], 0)

    assert score == 1.0


def test_calculate_compliance_score_with_violations(validator):
    """Test compliance score calculation with violations"""
    violations = [
        {"severity": ViolationSeverity.HIGH},
        {"severity": ViolationSeverity.MEDIUM}
    ]

    score = validator._calculate_compliance_score(violations, 10)

    assert 0.0 <= score <= 1.0


def test_calculate_compliance_score_critical_violations(validator):
    """Test compliance score with critical violations"""
    violations = [
        {"severity": ViolationSeverity.CRITICAL}
        for _ in range(5)
    ]

    score = validator._calculate_compliance_score(violations, 10)

    # Should be significantly reduced
    assert score < 0.5


# ============================================================================
# validate_with_knowledge_graph Tests
# ============================================================================

def test_validate_with_knowledge_graph_fallback(validator):
    """Test validation falls back when KG unavailable"""
    with patch('core.constitutional_validator.KnowledgeGraphService', side_effect=ImportError):
        action = {"action_type": "test_action"}

        result = validator.validate_with_knowledge_graph(
            agent_id="agent_123",
            action=action,
            context={}
        )

        assert result["validation_method"] == "fallback"
        assert "compliant" in result
        assert "violations" in result


def test_validate_with_knowledge_graph_success(validator):
    """Test validation with Knowledge Graph service"""
    mock_kg_service = Mock()
    mock_kg_service.get_applicable_rules = Mock(return_value=[
        {
            "id": "rule_1",
            "name": "Test Rule",
            "description": "Test description",
            "severity": "medium",
            "category": "test",
            "conditions": {}
        }
    ])

    with patch('core.constitutional_validator.KnowledgeGraphService', return_value=mock_kg_service):
        action = {"action_type": "test_action"}

        result = validator.validate_with_knowledge_graph(
            agent_id="agent_123",
            action=action,
            context={}
        )

        assert result["validation_method"] in ["knowledge_graph", "fallback"]


def test_validate_with_knowledge_graph_exception(validator):
    """Test validation handles KG exceptions gracefully"""
    mock_kg_service = Mock()
    mock_kg_service.get_applicable_rules = Mock(side_effect=Exception("KG error"))

    with patch('core.constitutional_validator.KnowledgeGraphService', return_value=mock_kg_service):
        action = {"action_type": "test_action"}

        result = validator.validate_with_knowledge_graph(
            agent_id="agent_123",
            action=action,
            context={}
        )

        # Should fall back to pattern-based validation
        assert result["validation_method"] == "fallback"


# ============================================================================
# _passes_kg_rule Tests
# ============================================================================

def test_passes_kg_rule_allowed_actions(validator):
    """Test rule with allowed actions filter"""
    rule = {
        "conditions": {
            "allowed_actions": ["read", "list"]
        }
    }

    result = validator._passes_kg_rule(
        rule,
        {"action_type": "read"},
        {}
    )

    assert result is True


def test_passes_kg_rule_forbidden_action(validator):
    """Test rule with forbidden actions"""
    rule = {
        "conditions": {
            "forbidden_actions": ["delete", "destroy"]
        }
    }

    result = validator._passes_kg_rule(
        rule,
        {"action_type": "delete"},
        {}
    )

    assert result is False


def test_passes_kg_rule_allowed_action_not_in_list(validator):
    """Test action not in allowed list fails"""
    rule = {
        "conditions": {
            "allowed_actions": ["read", "list"]
        }
    }

    result = validator._passes_kg_rule(
        rule,
        {"action_type": "delete"},
        {}
    )

    assert result is False


def test_passes_kg_rule_no_restrictions(validator):
    """Test rule without action restrictions passes"""
    rule = {
        "conditions": {}
    }

    result = validator._passes_kg_rule(
        rule,
        {"action_type": "any_action"},
        {}
    )

    assert result is True


def test_passes_kg_rule_domain_constraints(validator):
    """Test domain-specific constraints"""
    rule = {
        "conditions": {
            "domain_conditions": {
                "financial": {
                    "requires_approval": True
                }
            }
        }
    }

    # Action without approval in financial domain
    result = validator._passes_kg_rule(
        rule,
        {"action_type": "payment", "approved": False},
        {"domain": "financial"}
    )

    assert result is False


def test_passes_kg_rule_permissions_required(validator):
    """Test required permissions check"""
    rule = {
        "conditions": {
            "required_permissions": ["admin", "finance"]
        }
    }

    # User without required permissions
    result = validator._passes_kg_rule(
        rule,
        {"action_type": "admin_action"},
        {"permissions": ["user"]}
    )

    assert result is False


def test_passes_kg_rule_has_permissions(validator):
    """Test action with required permissions passes"""
    rule = {
        "conditions": {
            "required_permissions": ["admin", "finance"]
        }
    }

    result = validator._passes_kg_rule(
        rule,
        {"action_type": "admin_action"},
        {"permissions": ["admin", "finance", "user"]}
    )

    assert result is True


# ============================================================================
# _check_domain_constraints Tests
# ============================================================================

def test_check_domain_constraints_pii_restriction(validator):
    """Test PII data restriction"""
    constraints = {
        "data_restrictions": ["pii"]
    }

    action = {
        "action_type": "data_access",
        "content": {"ssn": "123-45-6789"}
    }

    result = validator._check_domain_constraints(action, constraints)

    assert result is False


def test_check_domain_constraints_phi_restriction_unauthorized(validator):
    """Test PHI restriction without authorization"""
    constraints = {
        "data_restrictions": ["phi"]
    }

    action = {
        "action_type": "medical_access",
        "content": {"patient_id": "12345", "diagnosis": "condition"},
        "authorized": False
    }

    result = validator._check_domain_constraints(action, constraints)

    assert result is False


def test_check_domain_constraints_phi_restriction_authorized(validator):
    """Test PHI restriction with authorization passes"""
    constraints = {
        "data_restrictions": ["phi"]
    }

    action = {
        "action_type": "medical_access",
        "content": {"patient_id": "12345"},
        "authorized": True
    }

    result = validator._check_domain_constraints(action, constraints)

    assert result is True


def test_check_domain_constraints_max_amount(validator):
    """Test max amount constraint for payments"""
    constraints = {
        "max_amount": 1000
    }

    action = {
        "action_type": "payment",
        "content": {"amount": 1500}
    }

    result = validator._check_domain_constraints(action, constraints)

    assert result is False


def test_check_domain_constraints_within_amount(validator):
    """Test payment within max amount passes"""
    constraints = {
        "max_amount": 1000
    }

    action = {
        "action_type": "payment",
        "content": {"amount": 500}
    }

    result = validator._check_domain_constraints(action, constraints)

    assert result is True


def test_check_domain_constraints_requires_approval(validator):
    """Test approval requirement constraint"""
    constraints = {
        "requires_approval": True
    }

    action = {
        "action_type": "critical_action",
        "approved": False
    }

    result = validator._check_domain_constraints(action, constraints)

    assert result is False


def test_check_domain_constraints_approved(validator):
    """Test approved action passes constraint"""
    constraints = {
        "requires_approval": True
    }

    action = {
        "action_type": "critical_action",
        "approved": True
    }

    result = validator._check_domain_constraints(action, constraints)

    assert result is True


def test_check_domain_constraints_no_constraints(validator):
    """Test action passes when no constraints"""
    constraints = {}

    action = {
        "action_type": "any_action",
        "content": {"data": "value"}
    }

    result = validator._check_domain_constraints(action, constraints)

    assert result is True


# ============================================================================
# _fallback_validation Tests
# ============================================================================

def test_fallback_validation_compliant_action(validator):
    """Test fallback validation for compliant action"""
    action = {
        "action_type": "read_data",
        "content": {"data": "value"},
        "metadata": {"logged": True}
    }

    result = validator._fallback_validation(action, {})

    assert result["compliant"] is True
    assert result["validation_method"] == "fallback"
    assert result["total_rules_checked"] == len(validator.CONSTITUTIONAL_RULES)


def test_fallback_validation_violating_action(validator):
    """Test fallback validation detects violations"""
    action = {
        "action_type": "payment",
        "content": {"amount": 1000},
        "metadata": {}
    }

    result = validator._fallback_validation(action, {})

    # Should detect unauthorized payment
    assert "compliant" in result
    assert "violations" in result


def test_fallback_validation_multiple_violations(validator):
    """Test fallback validation detects multiple violations"""
    action = {
        "action_type": "payment",
        "content": {"ssn": "123-45-6789", "amount": 1000},
        "metadata": {"logged": False}
    }

    result = validator._fallback_validation(action, {})

    # Should detect multiple violations
    assert len(result["violations"]) >= 1


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================

def test_validator_handles_malformed_segments(validator):
    """Test validator handles malformed segments gracefully"""
    malformed_segments = [None, {}, "invalid", 123]

    for segment in malformed_segments:
        result = validator.validate_actions([segment] if segment else [])
        # Should not crash
        assert "compliant" in result


def test_check_compliance_with_none_actions(validator):
    """Test compliance check with None actions"""
    result = validator.check_compliance("financial", None)

    assert result["compliant"] is True


def test_calculate_score_with_invalid_violations(validator):
    """Test score calculation handles missing severity"""
    violations = [
        {"severity": "invalid_severity"}
    ]

    score = validator.calculate_score(violations)

    # Should handle gracefully
    assert 0.0 <= score <= 1.0


def test_validate_actions_with_non_iterable(validator):
    """Test validation with non-iterable input"""
    result = validator.validate_actions("not_a_list")

    # Should handle gracefully
    assert "compliant" in result
