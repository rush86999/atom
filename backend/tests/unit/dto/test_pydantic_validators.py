"""
Tests for Pydantic custom validators (trace, accounting, audit_trail, constitutional)

Ensures validation logic works correctly for domain-specific validators
with edge case testing and error handling.
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Any
from unittest.mock import Mock, MagicMock

from core.trace_validator import TraceValidator, TraceMetrics
from core.accounting_validator import (
    validate_double_entry,
    check_balance_sheet,
    validate_journal_entries,
    DoubleEntryValidationError,
    EntryType
)
from core.constitutional_validator import ConstitutionalValidator, ViolationSeverity
from core.audit_trail_validator import AuditTrailValidator


# ==================== TRACE VALIDATOR TESTS ====================

class TestTraceValidator:
    """Test TraceValidator for evidence checking and hallucination detection"""

    def test_trace_metrics_structure(self):
        """Test TraceMetrics has all required fields"""
        from core.trajectory import ExecutionTrace, TraceStep, TraceStepType

        # Create mock trace
        trace = Mock(spec=ExecutionTrace)
        trace.steps = []
        trace.request = "Simple request"
        trace.duration_ms = Mock(return_value=1000)

        validator = TraceValidator()
        metrics = validator.analyze_trace(trace)

        assert hasattr(metrics, 'step_count')
        assert hasattr(metrics, 'duration_ms')
        assert hasattr(metrics, 'tool_calls')
        assert hasattr(metrics, 'step_efficiency')
        assert hasattr(metrics, 'hallucination_score')
        print("✓ test_trace_metrics_structure")

    def test_hallucination_score_with_evidence_needed(self):
        """Test hallucination risk when evidence is needed but no tool calls"""
        from core.trajectory import ExecutionTrace, TraceStep, TraceStepType

        # Create trace requesting facts but no tool calls
        trace = Mock(spec=ExecutionTrace)
        trace.request = "Find facts about climate change"
        trace.steps = []  # No tool calls
        trace.duration_ms = Mock(return_value=100)

        validator = TraceValidator()
        metrics = validator.analyze_trace(trace)

        # Should have high hallucination risk
        assert metrics.hallucination_score == 1.0
        print("✓ test_hallucination_score_with_evidence_needed")

    def test_hallucination_score_with_tool_calls(self):
        """Test low hallucination risk when tool calls present"""
        from core.trajectory import ExecutionTrace, TraceStep, TraceStepType

        # Create trace with tool calls
        tool_step = Mock(spec=TraceStep)
        tool_step.type = TraceStepType.TOOL_CALL

        trace = Mock(spec=ExecutionTrace)
        trace.request = "Search for information"
        trace.steps = [tool_step]
        trace.duration_ms = Mock(return_value=100)

        validator = TraceValidator()
        metrics = validator.analyze_trace(trace)

        # Should have low hallucination risk
        assert metrics.hallucination_score == 0.0
        print("✓ test_hallucination_score_with_tool_calls")

    def test_validate_evidence_returns_warnings(self):
        """Test validate_evidence returns list of warnings"""
        from core.trajectory import ExecutionTrace, TraceStep, TraceStepType

        trace = Mock(spec=ExecutionTrace)
        trace.request = "Find facts"
        trace.steps = []
        trace.duration_ms = Mock(return_value=100)

        validator = TraceValidator()
        warnings = validator.validate_evidence(trace)

        assert isinstance(warnings, list)
        assert len(warnings) > 0  # Should have hallucination warning
        print("✓ test_validate_evidence_returns_warnings")


# ==================== ACCOUNTING VALIDATOR TESTS ====================

class TestAccountingValidator:
    """Test double-entry bookkeeping validation with Decimal arithmetic"""

    def test_valid_double_entry(self):
        """Test accept valid debit/credit entries"""
        entries = [
            {"account_id": "acc_1", "type": EntryType.DEBIT, "amount": Decimal("100.00")},
            {"account_id": "acc_2", "type": EntryType.CREDIT, "amount": Decimal("100.00")}
        ]

        result = validate_double_entry(entries)

        assert result["balanced"] is True
        assert result["debits"] == Decimal("100.00")
        assert result["credits"] == Decimal("100.00")
        print("✓ test_valid_double_entry")

    def test_invalid_double_entry_unequal_amounts(self):
        """Test reject when debits != credits"""
        entries = [
            {"account_id": "acc_1", "type": EntryType.DEBIT, "amount": Decimal("100.00")},
            {"account_id": "acc_2", "type": EntryType.CREDIT, "amount": Decimal("90.00")}
        ]

        try:
            validate_double_entry(entries)
            assert False, "Should have raised DoubleEntryValidationError"
        except DoubleEntryValidationError as e:
            assert e.difference == Decimal("10.00")
            print("✓ test_invalid_double_entry_unequal_amounts")

    def test_invalid_negative_amounts(self):
        """Test reject negative amounts"""
        entries = [
            {"account_id": "acc_1", "type": EntryType.DEBIT, "amount": Decimal("-50.00")},
            {"account_id": "acc_2", "type": EntryType.CREDIT, "amount": Decimal("-50.00")}
        ]

        try:
            validate_double_entry(entries)
            assert False, "Should have raised DoubleEntryValidationError"
        except DoubleEntryValidationError:
            print("✓ test_invalid_negative_amounts")

    def test_accounting_decimal_precision(self):
        """Test Decimal precision rounding to 2 places"""
        entries = [
            {"account_id": "acc_1", "type": EntryType.DEBIT, "amount": Decimal("100.123")},
            {"account_id": "acc_2", "type": EntryType.CREDIT, "amount": Decimal("100.123")}
        ]

        result = validate_double_entry(entries)

        # Should round to 2 decimal places
        assert result["debits"] == Decimal("100.12")
        assert result["credits"] == Decimal("100.12")
        print("✓ test_accounting_decimal_precision")

    def test_check_balance_sheet_valid(self):
        """Test balance sheet equation: Assets = Liabilities + Equity"""
        balance_sheet = {
            "assets": [Decimal("100.00")],
            "liabilities": [Decimal("50.00")],
            "equity": [Decimal("50.00")]
        }

        result = check_balance_sheet(balance_sheet)

        assert result["balanced"] is True
        assert result["discrepancy"] is None
        print("✓ test_check_balance_sheet_valid")

    def test_check_balance_sheet_invalid(self):
        """Test reject when balance sheet doesn't balance"""
        balance_sheet = {
            "assets": [Decimal("100.00")],
            "liabilities": [Decimal("30.00")],
            "equity": [Decimal("50.00")]
        }

        result = check_balance_sheet(balance_sheet)

        assert result["balanced"] is False
        assert result["discrepancy"] == Decimal("20.00")
        print("✓ test_check_balance_sheet_invalid")

    def test_validate_journal_entries_missing_fields(self):
        """Test detect missing required fields"""
        entries = [
            {"account_id": "acc_1", "type": EntryType.DEBIT},  # missing amount
            {"amount": Decimal("100.00")}  # missing account_id and type
        ]

        errors = validate_journal_entries(entries)

        assert len(errors) > 0
        assert any("amount" in error for error in errors)
        assert any("account_id" in error for error in errors)
        print("✓ test_validate_journal_entries_missing_fields")

    def test_validate_journal_entries_invalid_amount(self):
        """Test detect invalid amount format"""
        entries = [
            {"account_id": "acc_1", "type": EntryType.DEBIT, "amount": "invalid"}
        ]

        errors = validate_journal_entries(entries)

        assert len(errors) > 0
        assert any("invalid amount" in error.lower() for error in errors)
        print("✓ test_validate_journal_entries_invalid_amount")


# ==================== CONSTITUTIONAL VALIDATOR TESTS ====================

class TestConstitutionalValidator:
    """Test constitutional compliance validation with mock rules"""

    def test_constitutional_rules_defined(self):
        """Test all constitutional rules are defined with required fields"""
        required_keys = {"category", "description", "severity", "domains"}

        for rule_id, rule in ConstitutionalValidator.CONSTITUTIONAL_RULES.items():
            assert required_keys.issubset(rule.keys()), f"Rule {rule_id} missing fields"

        print("✓ test_constitutional_rules_defined")

    def test_violation_severity_levels(self):
        """Test violation severity constants are defined"""
        assert hasattr(ViolationSeverity, 'CRITICAL')
        assert hasattr(ViolationSeverity, 'HIGH')
        assert hasattr(ViolationSeverity, 'MEDIUM')
        assert hasattr(ViolationSeverity, 'LOW')
        print("✓ test_violation_severity_levels")

    def test_validate_actions_with_none_segments(self):
        """Test handle None or empty episode segments"""
        db = Mock()
        validator = ConstitutionalValidator(db)

        result = validator.validate_actions(None)

        assert result["compliant"] is True
        assert result["score"] == 1.0
        assert result["total_actions"] == 0
        print("✓ test_validate_actions_with_none_segments")

    def test_validate_actions_with_empty_list(self):
        """Test handle empty segments list"""
        db = Mock()
        validator = ConstitutionalValidator(db)

        result = validator.validate_actions([])

        assert result["compliant"] is True
        assert result["violations"] == []
        print("✓ test_validate_actions_with_empty_list")

    def test_calculate_score_no_violations(self):
        """Test compliance score with no violations"""
        db = Mock()
        validator = ConstitutionalValidator(db)

        score = validator.calculate_score([])

        assert score == 1.0
        print("✓ test_calculate_score_no_violations")

    def test_calculate_score_with_violations(self):
        """Test compliance score decreases with violations"""
        db = Mock()
        validator = ConstitutionalValidator(db)

        violations = [
            {"severity": ViolationSeverity.CRITICAL},
            {"severity": ViolationSeverity.HIGH}
        ]

        score = validator.calculate_score(violations)

        # Score should be < 1.0 due to violations
        assert score < 1.0
        assert score >= 0.0
        print("✓ test_calculate_score_with_violations")

    def test_check_compliance_by_domain(self):
        """Test domain-specific compliance check"""
        db = Mock()
        validator = ConstitutionalValidator(db)

        actions = [{"action_type": "payment", "content": {"amount": 100}}]
        result = validator.check_compliance("financial", actions)

        assert "compliant" in result
        assert "score" in result
        assert "violations" in result
        assert result["domain"] == "financial"
        print("✓ test_check_compliance_by_domain")


# ==================== AUDIT TRAIL VALIDATOR TESTS ====================

class TestAuditTrailValidator:
    """Test SOX audit trail completeness validation"""

    def test_validate_completeness_returns_structure(self):
        """Test validate_completeness returns required fields"""
        db = Mock()
        db.query.return_value.filter.return_value.all.return_value = []

        validator = AuditTrailValidator(db)
        result = validator.validate_completeness()

        assert "complete" in result
        assert "total_operations" in result
        assert "audited_operations" in result
        assert "coverage_percentage" in result
        assert "validated_at" in result
        print("✓ test_validate_completeness_returns_structure")

    def test_validate_required_fields_checks_all_fields(self):
        """Test validate_required_fields checks all SOX mandatory fields"""
        db = Mock()
        # Create mock audit with all required fields
        mock_audit = Mock()
        mock_audit.id = "test_id"
        mock_audit.timestamp = datetime.now()
        mock_audit.user_id = "user_1"
        mock_audit.account_id = "acc_1"
        mock_audit.action_type = "create"
        mock_audit.success = True
        mock_audit.agent_maturity = "AUTONOMOUS"
        mock_audit.sequence_number = 1
        mock_audit.entry_hash = "hash123"

        db.query.return_value.limit.return_value.all.return_value = [mock_audit]

        validator = AuditTrailValidator(db)
        result = validator.validate_required_fields(limit=1)

        assert result["valid"] is True
        assert result["total_checked"] == 1
        assert result["valid_entries"] == 1
        print("✓ test_validate_required_fields_checks_all_fields")

    def test_validate_required_fields_detects_missing(self):
        """Test validate_required_fields detects missing fields"""
        db = Mock()
        # Create mock audit missing some fields
        mock_audit = Mock()
        mock_audit.id = "test_id"
        mock_audit.timestamp = None  # Missing
        mock_audit.user_id = "user_1"
        mock_audit.account_id = "acc_1"
        mock_audit.action_type = "create"
        mock_audit.success = True
        mock_audit.agent_maturity = None  # Missing
        mock_audit.sequence_number = 1
        mock_audit.entry_hash = "hash123"

        # Setup hasattr to return False for missing fields
        def has_attr_side_effect(attr):
            return attr not in ['timestamp', 'agent_maturity']

        type(mock_audit).timestamp = property(lambda self: None)
        type(mock_audit).agent_maturity = property(lambda self: None)

        db.query.return_value.limit.return_value.all.return_value = [mock_audit]

        validator = AuditTrailValidator(db)
        result = validator.validate_required_fields(limit=1)

        assert result["valid"] is False
        assert len(result["invalid_entries"]) > 0
        print("✓ test_validate_required_fields_detects_missing")

    def test_get_audit_statistics_structure(self):
        """Test audit statistics returns correct structure"""
        db = Mock()
        db.query.return_value.filter.return_value.all.return_value = []

        validator = AuditTrailValidator(db)
        result = validator.get_audit_statistics()

        assert "total_audits" in result
        assert "by_action_type" in result
        assert "by_agent_maturity" in result
        assert "success_rate" in result
        assert "generated_at" in result
        print("✓ test_get_audit_statistics_structure")

    def test_check_missing_audits_empty_account(self):
        """Test check_missing_audits with no audits for account"""
        db = Mock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        validator = AuditTrailValidator(db)
        gaps = validator.check_missing_audits("acc_123")

        assert isinstance(gaps, list)
        assert len(gaps) == 0
        print("✓ test_check_missing_audits_empty_account")

    def test_validate_sequence_monotonicity(self):
        """Test sequence numbers increase monotonically"""
        from core.models import FinancialAudit

        db = Mock()

        # Create mock audits with sequence 1, 2, 4 (gap at 3)
        audit1 = Mock(spec=FinancialAudit)
        audit1.sequence_number = 1
        audit1.timestamp = datetime.now()

        audit2 = Mock(spec=FinancialAudit)
        audit2.sequence_number = 2
        audit2.timestamp = datetime.now()

        audit3 = Mock(spec=FinancialAudit)
        audit3.sequence_number = 4  # Gap!
        audit3.timestamp = datetime.now()

        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            audit1, audit2, audit3
        ]

        validator = AuditTrailValidator(db)
        result = validator.validate_sequence_monotonicity("acc_123")

        assert result["valid"] is False
        assert len(result["violations"]) > 0
        assert result["violations"][0]["expected_sequence"] == 3
        assert result["violations"][0]["actual_sequence"] == 4
        print("✓ test_validate_sequence_monotonicity")


if __name__ == "__main__":
    # Run all tests
    test_classes = [
        TestTraceValidator,
        TestAccountingValidator,
        TestConstitutionalValidator,
        TestAuditTrailValidator
    ]

    total_tests = 0
    passed_tests = 0
    failed_tests = []

    for test_class in test_classes:
        instance = test_class()
        test_methods = [m for m in dir(instance) if m.startswith('test_')]

        for method_name in test_methods:
            total_tests += 1
            try:
                method = getattr(instance, method_name)
                method()
                passed_tests += 1
            except Exception as e:
                failed_tests.append(f"{test_class.__name__}.{method_name}: {e}")

    print(f"\n{'='*60}")
    print(f"Tests run: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {len(failed_tests)}")
    if failed_tests:
        print(f"\nFailed tests:")
        for failure in failed_tests:
            print(f"  - {failure}")
        sys.exit(1)
    else:
        print("\n✓ All validator tests passed!")
        sys.exit(0)
