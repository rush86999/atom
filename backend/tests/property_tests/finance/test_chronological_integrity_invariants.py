"""
Property-based tests for chronological integrity (AUD-02).

SOX compliance requirement AUD-02: "Chronological Integrity: Audit timestamps
are monotonically increasing, with no gaps in sequence numbers."

This test suite uses Hypothesis to generate thousands of test cases validating:
1. Timestamps are monotonically increasing (no backward jumps)
2. Sequence numbers have no gaps (sequence_number[i+1] = sequence_number[i] + 1)
3. Gap detection algorithm correctly identifies missing sequences
4. Multiple accounts maintain independent sequences
5. Time gap detection identifies unusual delays
6. Comprehensive integrity check validates all aspects

Test Strategy:
- Use Hypoosis strategies to generate random audit entries
- Validate invariants hold across all generated examples
- Test edge cases: single entry, multiple accounts, large gaps
- Verify gap detection with intentional gaps
- Check per-account isolation
"""

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from decimal import Decimal
import uuid
import time
import hashlib

from core.models import FinancialAudit, FinancialAccount, User
from core.chronological_integrity import ChronologicalIntegrityValidator


@pytest.mark.usefixtures("db_session")
class TestChronologicalIntegrityInvariants:
    """Property-based tests for chronological integrity (AUD-02)."""

    @pytest.fixture(autouse=True)
    def setup_validator(self, db_session):
        """Initialize validator before each test."""
        self.validator = ChronologicalIntegrityValidator(db_session)
        self.db = db_session

    @given(
        num_entries=st.integers(min_value=2, max_value=50)
    )
    @settings(max_examples=100)
    def test_timestamps_are_monotonic(self, num_entries):
        """
        Verify: Audit timestamps are monotonically increasing.

        Invariant: For all i, timestamp[i] >= timestamp[i-1]

        This test creates audit entries with natural time delays
        and validates that timestamps never go backward within
        each account.

        Example: 50 entries with 1ms delay between each
        Expected: All timestamps in ascending order
        """
        # Create user
        user = User(id=str(uuid.uuid4()), email=f"test_{uuid.uuid4()}@example.com")
        self.db.add(user)
        self.db.commit()

        account_id = str(uuid.uuid4())

        # Create audit entries with natural delays
        for i in range(num_entries):
            audit = FinancialAudit(
                id=str(uuid.uuid4()),
                timestamp=datetime.utcnow(),  # Server will set exact time
                user_id=user.id,
                account_id=account_id,
                action_type='create',
                changes={},
                old_values=None,
                new_values={'index': i},
                success=True,
                agent_maturity='AUTONOMOUS',
                governance_check_passed=True,
                required_approval=False,
                approval_granted=None,
                sequence_number=i + 1,
                entry_hash=hashlib.sha256(f"{account_id}_{i}".encode()).hexdigest(),
                prev_hash=hashlib.sha256(f"{account_id}_{i-1}".encode()).hexdigest() if i > 0 else ''
            )
            self.db.add(audit)
            # Small delay to ensure different timestamps
            time.sleep(0.001)

        self.db.commit()

        # Validate monotonicity
        result = self.validator.validate_monotonicity(account_id=account_id)

        assert result['is_monotonic'], \
            f"Timestamps not monotonic: {result['violations']}"
        assert len(result['violations']) == 0
        assert result['total_entries'] == num_entries
        assert result['accounts_checked'] == 1

    @given(
        num_entries=st.integers(min_value=5, max_value=100)
    )
    @settings(max_examples=100)
    def test_sequence_numbers_have_no_gaps(self, num_entries):
        """
        Verify: Sequence numbers have no gaps.

        Invariant: sequence_number[i] = sequence_number[i-1] + 1

        This test creates sequential audit entries and validates
        that there are no gaps in the sequence numbers.

        Example: 50 entries with sequence 1, 2, 3, ..., 50
        Expected: No gaps detected
        """
        user = User(id=str(uuid.uuid4()), email=f"test_{uuid.uuid4()}@example.com")
        self.db.add(user)
        self.db.commit()

        account_id = str(uuid.uuid4())

        # Create sequential audit entries
        for i in range(num_entries):
            audit = FinancialAudit(
                id=str(uuid.uuid4()),
                timestamp=datetime.utcnow(),
                user_id=user.id,
                account_id=account_id,
                action_type='create',
                changes={},
                old_values=None,
                new_values={'index': i},
                success=True,
                agent_maturity='AUTONOMOUS',
                governance_check_passed=True,
                required_approval=False,
                approval_granted=None,
                sequence_number=i + 1,  # Sequential
                entry_hash=hashlib.sha256(f"{account_id}_{i}".encode()).hexdigest(),
                prev_hash=hashlib.sha256(f"{account_id}_{i-1}".encode()).hexdigest() if i > 0 else "" if i > 0 else ''
            )
            self.db.add(audit)

        self.db.commit()

        # Check for gaps
        result = self.validator.detect_gaps(account_id=account_id)

        assert not result['has_gaps'], \
            f"Found gaps: {result['gaps']}"
        assert result['total_gaps'] == 0
        assert len(result['accounts_with_gaps']) == 0

    @given(
        gap_position=st.integers(min_value=1, max_value=10),
        gap_size=st.integers(min_value=1, max_value=5)
    )
    @settings(max_examples=50)
    def test_gap_detection_works(self, gap_position, gap_size):
        """
        Verify: Gap detection identifies missing sequence numbers.

        Create entries with intentional gap, verify detection finds it.

        Example: Create entries 1-5, skip 3 entries, create entries 9-13
        Expected: Detect gap from sequence 5 to sequence 9 (gap_size = 3)
        """
        assume(gap_position < 20)  # Keep test bounded

        user = User(id=str(uuid.uuid4()), email=f"test_{uuid.uuid4()}@example.com")
        self.db.add(user)
        self.db.commit()

        account_id = str(uuid.uuid4())

        # Create entries before gap
        for i in range(gap_position):
            audit = FinancialAudit(
                id=str(uuid.uuid4()),
                timestamp=datetime.utcnow(),
                user_id=user.id,
                account_id=account_id,
                action_type='create',
                changes={},
                old_values=None,
                new_values={'index': i},
                success=True,
                agent_maturity='AUTONOMOUS',
                governance_check_passed=True,
                required_approval=False,
                approval_granted=None,
                sequence_number=i + 1,
                entry_hash=hashlib.sha256(f"{account_id}_{i}".encode()).hexdigest(),
                prev_hash=hashlib.sha256(f"{account_id}_{i-1}".encode()).hexdigest() if i > 0 else "" if i > 0 else ''
            )
            self.db.add(audit)

        # Skip gap_size entries

        # Create entries after gap
        for i in range(gap_position + gap_size, gap_position + gap_size + 5):
            audit = FinancialAudit(
                id=str(uuid.uuid4()),
                timestamp=datetime.utcnow(),
                user_id=user.id,
                account_id=account_id,
                action_type='create',
                changes={},
                old_values=None,
                new_values={'index': i},
                success=True,
                agent_maturity='AUTONOMOUS',
                governance_check_passed=True,
                required_approval=False,
                approval_granted=None,
                sequence_number=i + 1,
                entry_hash=hashlib.sha256(f"{account_id}_{i}".encode()).hexdigest(),
                prev_hash=hashlib.sha256(f"{account_id}_{i-1}".encode()).hexdigest() if i > 0 else "" if i > 0 else ''
            )
            self.db.add(audit)

        self.db.commit()

        # Detect gaps
        result = self.validator.detect_gaps(account_id=account_id)

        assert result['has_gaps'], "Should detect gap"
        assert result['total_gaps'] >= 1
        assert any(g['gap_size'] == gap_size for g in result['gaps']), \
            f"Expected gap_size {gap_size}, got: {result['gaps']}"

    @given(
        num_accounts=st.integers(min_value=2, max_value=10),
        entries_per_account=st.integers(min_value=3, max_value=20)
    )
    @settings(max_examples=50)
    def test_multiple_accounts_maintain_independent_sequences(
        self, num_accounts, entries_per_account
    ):
        """
        Verify: Each account maintains independent sequence numbering.

        Invariant: Account A's sequence doesn't affect Account B's sequence

        This test creates multiple accounts, each with their own
        sequence starting from 1. Validates that sequences are
        independent and don't interfere with each other.

        Example: Account A has sequences 1-10, Account B has sequences 1-10
        Expected: Each account validates independently with no gaps
        """
        user = User(id=str(uuid.uuid4()), email=f"test_{uuid.uuid4()}@example.com")
        self.db.add(user)
        self.db.commit()

        account_ids = [str(uuid.uuid4()) for _ in range(num_accounts)]

        # Create entries for each account
        for account_idx, account_id in enumerate(account_ids):
            for entry_idx in range(entries_per_account):
                audit = FinancialAudit(
                    id=str(uuid.uuid4()),
                    timestamp=datetime.utcnow(),
                    user_id=user.id,
                    account_id=account_id,
                    action_type='create',
                    changes={},
                    old_values=None,
                    new_values={'account': account_idx, 'entry': entry_idx},
                    success=True,
                    agent_maturity='AUTONOMOUS',
                    governance_check_passed=True,
                    required_approval=False,
                    approval_granted=None,
                    sequence_number=entry_idx + 1,  # Each account starts at 1
                    entry_hash=hashlib.sha256(f"{account_id}_{entry_idx}".encode()).hexdigest(),
                    prev_hash=hashlib.sha256(f"{account_id}_{entry_idx-1}".encode()).hexdigest() if entry_idx > 0 else "" if entry_idx > 0 else ''
                )
                self.db.add(audit)

        self.db.commit()

        # Validate each account independently
        for account_id in account_ids:
            result = self.validator.validate_monotonicity(account_id=account_id)
            assert result['is_monotonic'], \
                f"Account {account_id} failed monotonicity: {result['violations']}"

            gap_result = self.validator.detect_gaps(account_id=account_id)
            assert not gap_result['has_gaps'], \
                f"Account {account_id} has gaps: {gap_result['gaps']}"

    @given(
        gap_seconds=st.integers(min_value=10, max_value=300)  # 10 sec to 5 min
    )
    @settings(max_examples=50)
    def test_time_gap_detection(self, gap_seconds):
        """
        Verify: Time gap detection identifies unusual delays.

        Create entries with specific time gap, verify detection.

        Example: Entry 1 at T0, Entry 2 at T0 + 120 seconds
        Threshold: 60 seconds
        Expected: Detect time gap of 120 seconds
        """
        user = User(id=str(uuid.uuid4()), email=f"test_{uuid.uuid4()}@example.com")
        self.db.add(user)
        self.db.commit()

        account_id = str(uuid.uuid4())
        now = datetime.utcnow()

        # First entry
        audit1 = FinancialAudit(
            id=str(uuid.uuid4()),
            timestamp=now,
            user_id=user.id,
            account_id=account_id,
            action_type='create',
            changes={},
            old_values=None,
            new_values={'step': 1},
            success=True,
            agent_maturity='AUTONOMOUS',
            governance_check_passed=True,
            required_approval=False,
            approval_granted=None,
            sequence_number=1,
            entry_hash=hashlib.sha256(b"entry_1").hexdigest(),  # Pad to 64 chars
            prev_hash=''
        )
        self.db.add(audit1)

        # Second entry after gap
        audit2 = FinancialAudit(
            id=str(uuid.uuid4()),
            timestamp=now + timedelta(seconds=gap_seconds),
            user_id=user.id,
            account_id=account_id,
            action_type='update',
            changes={},
            old_values={'step': 1},
            new_values={'step': 2},
            success=True,
            agent_maturity='AUTONOMOUS',
            governance_check_passed=True,
            required_approval=False,
            approval_granted=None,
            sequence_number=2,
            entry_hash=hashlib.sha256(b"entry_2").hexdigest(),
            prev_hash="hash_1" + "0" * 58
        )
        self.db.add(audit2)

        self.db.commit()

        # Detect time gaps with threshold lower than gap_seconds
        result = self.validator.detect_time_gaps(
            account_id=account_id,
            threshold_seconds=max(1, gap_seconds // 2)  # Half the gap
        )

        assert result['has_time_gaps'], "Should detect time gap"
        assert result['total_gaps'] >= 1
        assert any(g['gap_seconds'] >= gap_seconds * 0.9 for g in result['time_gaps']), \
            f"Expected gap >= {gap_seconds * 0.9}s, got: {result['time_gaps']}"

    @given(
        num_entries=st.integers(min_value=5, max_value=30)
    )
    @settings(max_examples=50)
    def test_comprehensive_integrity_check(self, num_entries):
        """
        Verify: Comprehensive integrity check validates all aspects.

        This test runs the full validate_integrity() check which combines:
        - Monotonic timestamp validation
        - Sequence gap detection
        - Out-of-order detection
        - Time gap detection (informational)

        Example: 20 sequential entries with natural delays
        Expected: is_valid=True, all sub-checks pass
        """
        user = User(id=str(uuid.uuid4()), email=f"test_{uuid.uuid4()}@example.com")
        self.db.add(user)
        self.db.commit()

        account_id = str(uuid.uuid4())

        # Create clean audit trail
        for i in range(num_entries):
            audit = FinancialAudit(
                id=str(uuid.uuid4()),
                timestamp=datetime.utcnow(),
                user_id=user.id,
                account_id=account_id,
                action_type='create',
                changes={},
                old_values=None,
                new_values={'index': i},
                success=True,
                agent_maturity='AUTONOMOUS',
                governance_check_passed=True,
                required_approval=False,
                approval_granted=None,
                sequence_number=i + 1,
                entry_hash=hashlib.sha256(f"{account_id}_{i}".encode()).hexdigest(),
                prev_hash=hashlib.sha256(f"{account_id}_{i-1}".encode()).hexdigest() if i > 0 else "" if i > 0 else ''
            )
            self.db.add(audit)
            time.sleep(0.001)  # Ensure different timestamps

        self.db.commit()

        # Run comprehensive check
        result = self.validator.validate_integrity(account_id=account_id)

        assert result['is_valid'], f"Integrity check failed: {result}"
        assert result['monotonicity']['is_monotonic'], "Monotonicity check failed"
        assert not result['sequence_gaps']['has_gaps'], "Sequence gaps detected"
        assert not result['out_of_order']['has_out_of_order'], "Out-of-order entries detected"
        # Time gaps are informational, not a validity violation
        assert 'time_gaps' in result
        assert 'validated_at' in result

    def test_single_account_maintains_integrity(self):
        """
        Verify: Single account with multiple entries maintains integrity.

        Edge case: Account with exactly 1 entry should pass validation.
        """
        user = User(id=str(uuid.uuid4()), email=f"test_{uuid.uuid4()}@example.com")
        self.db.add(user)
        self.db.commit()

        account_id = str(uuid.uuid4())

        audit = FinancialAudit(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            user_id=user.id,
            account_id=account_id,
            action_type='create',
            changes={},
            old_values=None,
            new_values={'test': 'data'},
            success=True,
            agent_maturity='AUTONOMOUS',
            governance_check_passed=True,
            required_approval=False,
            approval_granted=None,
            sequence_number=1,
            entry_hash=hashlib.sha256(b"entry_1").hexdigest(),
            prev_hash=''
        )
        self.db.add(audit)
        self.db.commit()

        result = self.validator.validate_integrity(account_id=account_id)

        assert result['is_valid'], "Single entry should be valid"
        assert result['monotonicity']['is_monotonic']
        assert not result['sequence_gaps']['has_gaps']

    @given(
        num_accounts=st.integers(min_value=1, max_value=5)
    )
    @settings(max_examples=20)
    def test_cross_account_contamination(self, num_accounts):
        """
        Verify: One account's gaps don't affect another account's validation.

        Create Account A with gaps, Account B without gaps.
        Validate that Account B passes validation even though Account A fails.

        Example: Account A missing sequences 3-5, Account B has perfect sequence
        Expected: Account A fails, Account B passes (independent validation)
        """
        user = User(id=str(uuid.uuid4()), email=f"test_{uuid.uuid4()}@example.com")
        self.db.add(user)
        self.db.commit()

        # Account with gaps
        account_with_gaps = str(uuid.uuid4())
        for i in [1, 2, 6, 7, 8]:  # Missing 3, 4, 5
            audit = FinancialAudit(
                id=str(uuid.uuid4()),
                timestamp=datetime.utcnow(),
                user_id=user.id,
                account_id=account_with_gaps,
                action_type='create',
                changes={},
                old_values=None,
                new_values={'index': i},
                success=True,
                agent_maturity='AUTONOMOUS',
                governance_check_passed=True,
                required_approval=False,
                approval_granted=None,
                sequence_number=i,
                entry_hash=hashlib.sha256(f"gap_{i}".encode()).hexdigest(),
                prev_hash=hashlib.sha256(f"gap_{i-1}".encode()).hexdigest() if i > 1 else "" if i > 1 else ''
            )
            self.db.add(audit)

        # Account without gaps
        account_without_gaps = str(uuid.uuid4())
        for i in range(1, 11):
            audit = FinancialAudit(
                id=str(uuid.uuid4()),
                timestamp=datetime.utcnow(),
                user_id=user.id,
                account_id=account_without_gaps,
                action_type='create',
                changes={},
                old_values=None,
                new_values={'index': i},
                success=True,
                agent_maturity='AUTONOMOUS',
                governance_check_passed=True,
                required_approval=False,
                approval_granted=None,
                sequence_number=i,
                entry_hash=hashlib.sha256(f"clean_{i}".encode()).hexdigest(),
                prev_hash=hashlib.sha256(f"clean_{i-1}".encode()).hexdigest() if i > 1 else "" if i > 1 else ''
            )
            self.db.add(audit)

        self.db.commit()

        # Validate account with gaps
        result_gaps = self.validator.detect_gaps(account_id=account_with_gaps)
        assert result_gaps['has_gaps'], "Should detect gaps"

        # Validate account without gaps
        result_no_gaps = self.validator.detect_gaps(account_id=account_without_gaps)
        assert not result_no_gaps['has_gaps'], "Should not have gaps"
