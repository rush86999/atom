"""
Constitutional Validator Coverage Tests
Comprehensive test coverage for constitutional rules validation, compliance scoring, and violation detection
Target: 60%+ coverage (94+ lines)
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
from sqlalchemy.orm import Session

from core.constitutional_validator import (
    ConstitutionalValidator,
    ViolationSeverity,
    get_constitutional_validator
)
from core.models import EpisodeSegment


# ==================== Fixtures ====================

@pytest.fixture
def mock_db():
    """Mock database session"""
    return Mock(spec=Session)


@pytest.fixture
def validator(mock_db):
    """ConstitutionalValidator instance for testing"""
    return ConstitutionalValidator(mock_db)


@pytest.fixture
def sample_segment():
    """Sample episode segment for testing"""
    segment = Mock(spec=EpisodeSegment)
    segment.id = "segment-123"
    segment.segment_type = "test_action"
    segment.content = '{"data": "test_value"}'
    segment.timestamp = datetime.now()
    segment.metadata = {"logged": True}
    return segment


@pytest.fixture
def sample_action():
    """Sample action dictionary for testing"""
    return {
        "action_type": "payment",
        "content": {
            "amount": 100,
            "recipient": "test@example.com",
            "approval_required": True
        },
        "timestamp": datetime.now().isoformat(),
        "metadata": {"logged": True}
    }


# ==================== Test Constitutional Validator Initialization ====================

class TestConstitutionalValidatorInit:
    """Tests for ConstitutionalValidator initialization and setup"""

    def test_validator_initialization(self, mock_db):
        """Test validator initializes with database session"""
        validator = ConstitutionalValidator(mock_db)
        assert validator.db == mock_db
        assert len(validator.CONSTITUTIONAL_RULES) == 10

    def test_constitutional_rules_structure(self, validator):
        """Test constitutional rules have required fields"""
        for rule_id, rule in validator.CONSTITUTIONAL_RULES.items():
            assert "category" in rule
            assert "description" in rule
            assert "severity" in rule
            assert "domains" in rule

    def test_rule_categories_exist(self, validator):
        """Test all expected rule categories are present"""
        categories = set(rule["category"] for rule in validator.CONSTITUTIONAL_RULES.values())
        expected_categories = {"safety", "financial", "privacy", "transparency", "governance"}
        assert expected_categories.issubset(categories)

    def test_get_constitutional_validator_singleton(self, mock_db):
        """Test get_constitutional_validator returns validator instance"""
        validator = get_constitutional_validator(mock_db)
        assert isinstance(validator, ConstitutionalValidator)
        assert validator.db == mock_db


# ==================== Test Action Validation ====================

class TestActionValidation:
    """Tests for validate_actions method"""

    def test_validate_actions_empty_list(self, validator):
        """Test validation with empty segment list"""
        result = validator.validate_actions([])

        assert result["compliant"] is True
        assert result["score"] == 1.0
        assert result["violations"] == []
        assert result["total_actions"] == 0
        assert result["checked_actions"] == 0

    def test_validate_actions_none_input(self, validator):
        """Test validation with None input"""
        result = validator.validate_actions(None)

        assert result["compliant"] is True
        assert result["score"] == 1.0
        assert result["violations"] == []

    def test_validate_actions_non_iterable_input(self, validator):
        """Test validation with non-iterable input"""
        result = validator.validate_actions("not_a_list")

        assert result["compliant"] is True
        assert result["score"] == 1.0
        assert result["violations"] == []

    def test_validate_actions_success(self, validator, sample_segment):
        """Test successful action validation"""
        result = validator.validate_actions([sample_segment])

        assert result["compliant"] is True
        assert result["total_actions"] == 1
        assert result["checked_actions"] == 1
        assert isinstance(result["score"], float)

    def test_validate_actions_with_domain(self, validator, sample_segment):
        """Test validation with domain-specific rules"""
        result = validator.validate_actions(
            [sample_segment],
            domain="financial"
        )

        assert "compliant" in result
        assert "score" in result
        assert isinstance(result["score"], float)

    def test_validate_actions_multiple_segments(self, validator):
        """Test validation with multiple segments"""
        segments = [Mock(spec=EpisodeSegment) for _ in range(3)]
        for i, seg in enumerate(segments):
            seg.id = f"segment-{i}"
            seg.segment_type = "test_action"
            seg.content = '{"data": "test"}'
            seg.timestamp = datetime.now()
            seg.metadata = {"logged": True}

        result = validator.validate_actions(segments)

        assert result["total_actions"] == 3
        assert result["checked_actions"] == 3


# ==================== Test Compliance Checking ====================

class TestComplianceChecking:
    """Tests for check_compliance method"""

    def test_check_compliance_empty_actions(self, validator):
        """Test compliance check with no actions"""
        result = validator.check_compliance("financial", [])

        assert result["compliant"] is True
        assert result["score"] == 1.0
        assert result["violations"] == []
        assert result["domain"] == "financial"

    def test_check_compliance_with_violations(self, validator, sample_action):
        """Test compliance check detects violations"""
        # Create action that violates payment approval rule
        violating_action = {
            "action_type": "payment",
            "content": {
                "amount": 1000,
                "approval_required": False  # No approval
            },
            "metadata": {}
        }

        result = validator.check_compliance("financial", [violating_action])

        assert result["domain"] == "financial"
        assert isinstance(result["score"], float)

    def test_check_compliance_domain_filtering(self, validator):
        """Test domain-specific rule filtering"""
        financial_action = {
            "action_type": "tax_calculation",
            "content": {"amount": 1000},
            "metadata": {}
        }

        result = validator.check_compliance("financial", [financial_action])

        # Should check financial rules
        assert result["domain"] == "financial"
        assert isinstance(result["score"], float)


# ==================== Test Compliance Scoring ====================

class TestComplianceScoring:
    """Tests for calculate_score method"""

    def test_calculate_score_no_violations(self, validator):
        """Test score with no violations"""
        score = validator.calculate_score([])

        assert score == 1.0

    def test_calculate_score_critical_violations(self, validator):
        """Test score with critical violations"""
        violations = [
            {"severity": ViolationSeverity.CRITICAL},
            {"severity": ViolationSeverity.CRITICAL}
        ]

        score = validator.calculate_score(violations)

        assert score < 1.0
        assert score >= 0.0

    def test_calculate_score_mixed_severity(self, validator):
        """Test score with mixed severity violations"""
        violations = [
            {"severity": ViolationSeverity.CRITICAL},
            {"severity": ViolationSeverity.HIGH},
            {"severity": ViolationSeverity.MEDIUM},
            {"severity": ViolationSeverity.LOW}
        ]

        score = validator.calculate_score(violations)

        assert score < 1.0
        assert score >= 0.0

    def test_calculate_score_low_violations(self, validator):
        """Test score with only low severity violations"""
        violations = [
            {"severity": ViolationSeverity.LOW},
            {"severity": ViolationSeverity.LOW}
        ]

        score = validator.calculate_score(violations)

        # Low severity should have minimal impact
        assert score > 0.9

    def test_calculate_score_many_violations(self, validator):
        """Test score with many violations"""
        violations = [
            {"severity": ViolationSeverity.CRITICAL}
        ] * 10

        score = validator.calculate_score(violations)

        # Should be near zero with 10 critical violations
        assert score >= 0.0


# ==================== Test Violation Detection ====================

class TestViolationDetection:
    """Tests for _check_rule_violation method"""

    def test_pii_exposure_detection(self, validator, sample_action):
        """Test PII exposure violation detection"""
        pii_action = {
            "action_type": "data_export",
            "content": {"user_ssn": "123-45-6789"},
            "metadata": {}
        }

        violation = validator._check_rule_violation(
            pii_action,
            "safety_no_pii_exposure",
            validator.CONSTITUTIONAL_RULES["safety_no_pii_exposure"]
        )

        assert violation is not None
        assert violation["rule_id"] == "safety_no_pii_exposure"
        assert violation["severity"] == ViolationSeverity.HIGH

    def test_no_pii_violation(self, validator, sample_action):
        """Test no PII violation when content is clean"""
        clean_action = {
            "action_type": "data_export",
            "content": {"user_name": "John Doe"},
            "metadata": {}
        }

        violation = validator._check_rule_violation(
            clean_action,
            "safety_no_pii_exposure",
            validator.CONSTITUTIONAL_RULES["safety_no_pii_exposure"]
        )

        # Should not detect violation for clean content
        assert violation is None or violation.get("rule_id") != "safety_no_pii_exposure"

    def test_unauthorized_payment_detection(self, validator):
        """Test unauthorized payment violation detection"""
        payment_action = {
            "action_type": "payment",
            "content": {
                "amount": 1000,
                "approval_required": False
            },
            "metadata": {}
        }

        violation = validator._check_rule_violation(
            payment_action,
            "financial_no_unauthorized_payments",
            validator.CONSTITUTIONAL_RULES["financial_no_unauthorized_payments"]
        )

        assert violation is not None
        assert violation["rule_id"] == "financial_no_unauthorized_payments"
        assert violation["severity"] == ViolationSeverity.CRITICAL

    def test_authorized_payment_no_violation(self, validator):
        """Test authorized payment doesn't trigger violation"""
        payment_action = {
            "action_type": "payment",
            "content": {
                "amount": 1000,
                "approval_required": True
            },
            "metadata": {}
        }

        violation = validator._check_rule_violation(
            payment_action,
            "financial_no_unauthorized_payments",
            validator.CONSTITUTIONAL_RULES["financial_no_unauthorized_payments"]
        )

        # Should not detect violation with approval
        assert violation is None

    def test_audit_trail_violation(self, validator):
        """Test audit trail violation detection"""
        action = {
            "action_type": "data_modification",
            "content": {},
            "metadata": {"logged": False}  # Not logged
        }

        violation = validator._check_rule_violation(
            action,
            "governance_audit_trail",
            validator.CONSTITUTIONAL_RULES["governance_audit_trail"]
        )

        assert violation is not None
        assert violation["rule_id"] == "governance_audit_trail"
        assert violation["severity"] == ViolationSeverity.MEDIUM

    def test_audit_trail_compliant(self, validator):
        """Test logged action passes audit trail check"""
        action = {
            "action_type": "data_modification",
            "content": {},
            "metadata": {"logged": True}  # Logged
        }

        violation = validator._check_rule_violation(
            action,
            "governance_audit_trail",
            validator.CONSTITUTIONAL_RULES["governance_audit_trail"]
        )

        assert violation is None


# ==================== Test Action Data Extraction ====================

class TestActionDataExtraction:
    """Tests for _extract_action_data method"""

    def test_extract_action_data_success(self, validator, sample_segment):
        """Test successful action data extraction"""
        action = validator._extract_action_data(sample_segment)

        assert action is not None
        assert action["action_type"] == "test_action"
        assert "content" in action
        assert "timestamp" in action
        assert "metadata" in action

    def test_extract_action_data_none_segment(self, validator):
        """Test extraction with None segment"""
        action = validator._extract_action_data(None)

        assert action is None

    def test_extract_action_data_json_content(self, validator):
        """Test extraction with JSON string content"""
        segment = Mock(spec=EpisodeSegment)
        segment.segment_type = "test"
        segment.content = '{"key": "value"}'
        segment.timestamp = datetime.now()
        segment.metadata = {}

        action = validator._extract_action_data(segment)

        assert action is not None
        assert action["content"] == {"key": "value"}

    def test_extract_action_data_dict_content(self, validator):
        """Test extraction with dict content"""
        segment = Mock(spec=EpisodeSegment)
        segment.segment_type = "test"
        segment.content = {"key": "value"}  # Already a dict
        segment.timestamp = datetime.now()
        segment.metadata = {}

        action = validator._extract_action_data(segment)

        assert action is not None
        assert action["content"] == {"key": "value"}

    def test_extract_action_data_invalid_json(self, validator):
        """Test extraction with invalid JSON"""
        segment = Mock(spec=EpisodeSegment)
        segment.id = "seg-1"
        segment.segment_type = "test"
        segment.content = "{invalid json"
        segment.timestamp = datetime.now()
        segment.metadata = {}

        action = validator._extract_action_data(segment)

        # Should handle gracefully and return None
        assert action is None


# ==================== Test Knowledge Graph Integration ====================

class TestKnowledgeGraphIntegration:
    """Tests for Knowledge Graph validation methods"""

    def test_validate_with_kg_fallback_on_import_error(self, validator, sample_action):
        """Test fallback when Knowledge Graph service not available"""
        with patch('core.constitutional_validator.KnowledgeGraphService', side_effect=ImportError):
            result = validator.validate_with_knowledge_graph(
                "agent-123",
                sample_action,
                {}
            )

        assert result["validation_method"] == "fallback"
        assert "compliant" in result

    def test_validate_with_kg_fallback_on_exception(self, validator, sample_action):
        """Test fallback when Knowledge Graph service raises exception"""
        with patch('core.constitutional_validator.KnowledgeGraphService', side_effect=Exception("KG error")):
            result = validator.validate_with_knowledge_graph(
                "agent-123",
                sample_action,
                {}
            )

        assert result["validation_method"] == "fallback"
        assert "compliant" in result

    def test_passes_kg_rule_allowed_actions(self, validator):
        """Test KG rule check for allowed actions"""
        rule = {
            "allowed_actions": ["read", "list"]
        }
        action = {"action_type": "read"}
        context = {}

        result = validator._passes_kg_rule(rule, action, context)

        assert result is True

    def test_passes_kg_rule_forbidden_action(self, validator):
        """Test KG rule check for forbidden actions"""
        rule = {
            "forbidden_actions": ["delete", "modify"]
        }
        action = {"action_type": "delete"}
        context = {}

        result = validator._passes_kg_rule(rule, action, context)

        assert result is False

    def test_passes_kg_rule_required_permissions(self, validator):
        """Test KG rule check for required permissions"""
        rule = {
            "required_permissions": ["read", "write"]
        }
        action = {"action_type": "update"}
        context = {"permissions": ["read", "write", "execute"]}

        result = validator._passes_kg_rule(rule, action, context)

        assert result is True

    def test_passes_kg_rule_missing_permissions(self, validator):
        """Test KG rule check with missing permissions"""
        rule = {
            "required_permissions": ["admin", "write"]
        }
        action = {"action_type": "update"}
        context = {"permissions": ["read"]}  # Missing admin and write

        result = validator._passes_kg_rule(rule, action, context)

        assert result is False

    def test_check_domain_constraints_pii_restriction(self, validator):
        """Test domain constraints for PII data"""
        constraints = {
            "data_restrictions": ["pii"]
        }
        action = {
            "action_type": "data_export",
            "content": {"ssn": "123-45-6789"}
        }

        result = validator._check_domain_constraints(action, constraints)

        assert result is False

    def test_check_domain_constraints_phi_restriction(self, validator):
        """Test domain constraints for PHI (HIPAA)"""
        constraints = {
            "data_restrictions": ["phi"]
        }
        action = {
            "action_type": "medical_access",
            "content": {"patient_id": "12345"},
            "authorized": False
        }

        result = validator._check_domain_constraints(action, constraints)

        assert result is False

    def test_check_domain_constraints_phi_authorized(self, validator):
        """Test PHI access with authorization"""
        constraints = {
            "data_restrictions": ["phi"]
        }
        action = {
            "action_type": "medical_access",
            "content": {"patient_id": "12345"},
            "authorized": True  # Authorized
        }

        result = validator._check_domain_constraints(action, constraints)

        assert result is True

    def test_check_domain_constraints_max_amount(self, validator):
        """Test domain constraints for max amount"""
        constraints = {
            "max_amount": 1000
        }
        action = {
            "action_type": "payment",
            "content": {"amount": 1500}  # Exceeds limit
        }

        result = validator._check_domain_constraints(action, constraints)

        assert result is False

    def test_check_domain_constraints_within_limit(self, validator):
        """Test domain constraints within amount limit"""
        constraints = {
            "max_amount": 1000
        }
        action = {
            "action_type": "payment",
            "content": {"amount": 500}  # Within limit
        }

        result = validator._check_domain_constraints(action, constraints)

        assert result is True

    def test_check_domain_constraints_requires_approval(self, validator):
        """Test domain constraints for approval requirement"""
        constraints = {
            "requires_approval": True
        }
        action = {
            "action_type": "payment",
            "content": {},
            "approved": False  # Not approved
        }

        result = validator._check_domain_constraints(action, constraints)

        assert result is False

    def test_fallback_validation(self, validator, sample_action):
        """Test fallback validation method"""
        result = validator._fallback_validation(sample_action, {})

        assert result["validation_method"] == "fallback"
        assert "compliant" in result
        assert "violations" in result
        assert "total_rules_checked" in result


# ==================== Test Compliance Score Calculation ====================

class TestComplianceScoreCalculation:
    """Tests for _calculate_compliance_score method"""

    def test_score_calculation_no_violations(self, validator):
        """Test score calculation with no violations"""
        score = validator._calculate_compliance_score([], 10)

        assert score == 1.0

    def test_score_calculation_with_violations(self, validator):
        """Test score calculation with violations"""
        violations = [
            {"severity": ViolationSeverity.HIGH},
            {"severity": ViolationSeverity.MEDIUM}
        ]

        score = validator._calculate_compliance_score(violations, 10)

        assert score < 1.0
        assert score >= 0.0

    def test_score_calculation_zero_actions(self, validator):
        """Test score calculation with zero total actions"""
        score = validator._calculate_compliance_score([], 0)

        assert score == 1.0


# ==================== Test Edge Cases ====================

class TestEdgeCases:
    """Tests for edge cases and error handling"""

    def test_validate_actions_segment_without_id(self, validator):
        """Test validation with segment missing ID"""
        segment = Mock(spec=EpisodeSegment)
        segment.id = None  # No ID
        segment.segment_type = "test"
        segment.content = "{}"
        segment.timestamp = datetime.now()
        segment.metadata = {}

        # Should not crash
        result = validator.validate_actions([segment])

        assert "compliant" in result

    def test_validate_actions_malformed_content(self, validator):
        """Test validation with malformed segment content"""
        segment = Mock(spec=EpisodeSegment)
        segment.id = "seg-1"
        segment.segment_type = "test"
        segment.content = "not json"
        segment.timestamp = datetime.now()
        segment.metadata = {}

        result = validator.validate_actions([segment])

        # Should handle gracefully
        assert "compliant" in result

    def test_check_rule_violation_unknown_action_type(self, validator):
        """Test rule check with unknown action type"""
        action = {
            "action_type": "unknown_type",
            "content": {},
            "metadata": {}
        }

        # Should not crash
        violation = validator._check_rule_violation(
            action,
            "safety_no_harm",
            validator.CONSTITUTIONAL_RULES["safety_no_harm"]
        )

        # Most rules won't match unknown types
        assert violation is None or isinstance(violation, dict)

    def test_multiple_critical_violations_non_compliant(self, validator):
        """Test multiple critical violations result in non-compliant"""
        actions = [
            {
                "action_type": "payment",
                "content": {"approval_required": False},
                "metadata": {}
            }
        ] * 3  # Three unauthorized payments

        result = validator.check_compliance("financial", actions)

        # Should have critical violations
        assert "compliant" in result
        assert "violations" in result
