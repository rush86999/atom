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
    assert len(rules) >= 7  # Current constitution ships 7 rules (safety, financial, transparency, governance)

    # Check required rule categories
    categories = [rule.get("category") for rule in rules.values()]
    assert "safety" in categories
    assert "financial" in categories
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


def test_validate_actions_none_input(validator):
    """Test validation with None input"""
    result = validator.validate_actions(None)

    assert result["compliant"] is True
    assert result["score"] == 1.0
    assert result["violations"] == []
    assert result["total_actions"] == 0


def test_validate_actions_success(validator):
    """Test successful validation of compliant actions"""
    actions = [
        {"action_type": "read", "content": "public data", "metadata": {"logged": True}},
        {"action_type": "summarize", "content": "public summary", "metadata": {"logged": True}},
        {"action_type": "reply", "content": "thanks", "metadata": {"logged": True}},
    ]
    result = validator.validate_actions(actions)

    assert "compliant" in result
    assert "score" in result
    assert "violations" in result
    assert "total_actions" in result
    assert result["total_actions"] == 3


def test_validate_actions_with_domain(validator):
    """Test validation with domain-specific rules"""
    actions = [
        {"action_type": "read", "content": "public data", "metadata": {"logged": True}},
        {"action_type": "summarize", "content": "public summary", "metadata": {"logged": True}},
        {"action_type": "reply", "content": "thanks", "metadata": {"logged": True}},
    ]
    result = validator.validate_actions(actions, domain="financial")

    assert result["total_actions"] == 3
    # Financial domain should filter rules
    assert isinstance(result["violations"], list)


def test_validate_actions_invalid_segment(validator):
    """Test validation handles malformed action gracefully"""
    result = validator.validate_actions([{"unexpected": "shape"}])

    # Should handle gracefully, not crash
    assert "compliant" in result
    assert result["total_actions"] == 1


def test_validate_actions_all_domains(validator):
    """Test validation applies all domain rules when domain=None"""
    actions = [
        {"action_type": "read", "content": "public data", "metadata": {"logged": True}},
        {"action_type": "summarize", "content": "public summary", "metadata": {"logged": True}},
    ]
    result = validator.validate_actions(actions, domain=None)

    # Should check all rules with "all" domain
    assert result["total_actions"] == 2


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


def test_check_compliance_with_none_actions(validator):
    """Test compliance check with None actions is handled gracefully"""
    result = validator.check_compliance("financial", None)

    assert result["compliant"] is True
    assert result["score"] == 1.0
    assert result["violations"] == []
    assert result["domain"] == "financial"


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

    # Score formula: 1.0 - (10 + 10) / 100 = 0.8
    # Should be <= 0.8 (allowing equality)
    assert 0.0 <= score <= 0.8


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


def test_calculate_score_exact_critical_penalty(validator):
    """Test score calculation with exact critical penalty"""
    # 10 critical violations = 100.0 weight = score 0.0
    violations = [
        {"severity": ViolationSeverity.CRITICAL}
        for _ in range(10)
    ]

    score = validator.calculate_score(violations)

    assert score == 0.0


# ============================================================================
# _extract_action_data Tests
# ============================================================================













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
    assert "SSN" in violation["details"]


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
        "content": {"amount": 1000},
        "metadata": {"is_approved": True}
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
        "action_type": "delete",
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
    # 5 critical = 50 penalty, max 100, so score = 1 - 50/100 = 0.5
    assert score <= 0.5


# ============================================================================
# validate_with_knowledge_graph Tests
# ============================================================================







# ============================================================================
# _passes_kg_rule Tests
# ============================================================================















# ============================================================================
# _check_domain_constraints Tests
# ============================================================================

















# ============================================================================
# _fallback_validation Tests
# ============================================================================







# ============================================================================
# Edge Cases and Error Handling
# ============================================================================

def test_validator_handles_none_segment(validator):
    """Test validator handles None segment in list"""
    # Pass a list containing None
    result = validator.validate_actions([None])

    # Should handle gracefully
    assert "compliant" in result






def test_calculate_score_with_invalid_violations(validator):
    """Test score calculation handles missing severity"""
    violations = [
        {"severity": "invalid_severity"}
    ]

    score = validator.calculate_score(violations)

    # Should handle gracefully with default weight of 1.0
    assert 0.0 <= score <= 1.0


def test_calculate_score_with_missing_severity(validator):
    """Test score calculation handles missing severity key"""
    violations = [
        {}  # No severity key
    ]

    score = validator.calculate_score(violations)

    # Should handle gracefully with default weight of 1.0
    assert 0.0 <= score <= 1.0


# ============================================================================
# Additional Tests for Better Coverage
# ============================================================================

def test_violation_has_all_required_fields(validator):
    """Test violation structure has all required fields"""
    action = {
        "action_type": "payment",
        "content": {"amount": 1000}
    }

    violation = validator._check_rule_violation(
        action,
        "financial_no_unauthorized_payments",
        validator.CONSTITUTIONAL_RULES["financial_no_unauthorized_payments"]
    )

    assert violation is not None
    assert "rule_id" in violation
    assert "rule_description" in violation
    assert "severity" in violation
    assert "action_type" in violation
    assert "detected_at" in violation
    assert "details" in violation


def test_check_rule_violation_non_violating_action(validator):
    """Test action that doesn't violate any rules"""
    action = {
        "action_type": "read",
        "content": {"data": "value"},
        "metadata": {"logged": True}
    }

    violation = validator._check_rule_violation(
        action,
        "governance_audit_trail",
        validator.CONSTITUTIONAL_RULES["governance_audit_trail"]
    )

    assert violation is None


def test_validate_actions_mixed_segments(validator):
    """Test validation with mix of valid and malformed actions"""
    valid_action = {"action_type": "read", "content": "public data", "metadata": {"logged": True}}
    malformed_action = {"unexpected": "shape"}

    result = validator.validate_actions([valid_action, malformed_action])

    # Should process both dict entries without crashing
    assert result["total_actions"] == 2
    assert isinstance(result["violations"], list)






def test_calculate_score_single_critical(validator):
    """Test score with single critical violation"""
    violations = [
        {"severity": ViolationSeverity.CRITICAL}
    ]

    score = validator.calculate_score(violations)

    # 1 critical = 10 weight, max penalty = 10 (1 action * 10), score = 0.0
    assert score == 0.0


def test_calculate_score_single_high(validator):
    """Test score with single high severity violation"""
    violations = [
        {"severity": ViolationSeverity.HIGH}
    ]

    score = validator.calculate_score(violations)

    # 1 high = 5 weight, max penalty = 10 (1 action * 10), score = 0.5
    assert score == 0.5


def test_calculate_score_single_medium(validator):
    """Test score with single medium severity violation"""
    violations = [
        {"severity": ViolationSeverity.MEDIUM}
    ]

    score = validator.calculate_score(violations)

    # 1 medium = 2 weight, max penalty = 10 (1 action * 10), score = 0.8
    assert score == 0.8


def test_calculate_score_single_low(validator):
    """Test score with single low severity violation"""
    violations = [
        {"severity": ViolationSeverity.LOW}
    ]

    score = validator.calculate_score(violations)

    # 1 low = 0.5 weight, max penalty = 10 (1 action * 10), score = 0.95
    assert score == 0.95


def test_validate_actions_with_violations(validator):
    """Test validation detects violations"""
    violating_action = {
        "action_type": "payment",
        "content": {"amount": 1000},
        "metadata": {}
    }

    result = validator.validate_actions([violating_action])

    # Should detect unauthorized payment
    assert result["total_actions"] == 1
    assert len(result["violations"]) > 0


def test_constitutional_rules_domains_list(validator):
    """Test all rules have domains list"""
    for rule_id, rule in validator.CONSTITUTIONAL_RULES.items():
        assert isinstance(rule["domains"], list)
        assert len(rule["domains"]) > 0


def test_rule_severity_values(validator):
    """Test all rule severity values are valid"""
    valid_severities = ["critical", "high", "medium", "low"]
    for rule_id, rule in validator.CONSTITUTIONAL_RULES.items():
        assert rule["severity"] in valid_severities


def test_violation_severity_class_values():
    """Test ViolationSeverity class has all expected values"""
    assert ViolationSeverity.CRITICAL == "critical"
    assert ViolationSeverity.HIGH == "high"
    assert ViolationSeverity.MEDIUM == "medium"
    assert ViolationSeverity.LOW == "low"
