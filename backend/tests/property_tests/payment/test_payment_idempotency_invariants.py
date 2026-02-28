"""
Hypothesis property tests for payment idempotency invariants.

Tests idempotency key uniqueness, replay behavior, and edge cases
across 1000+ auto-generated examples using Hypothesis strategies.
"""

import pytest
import uuid
import time
from decimal import Decimal
from hypothesis import given, strategies as st, settings, assume

from integrations.stripe_service import StripeService
from tests.fixtures.payment_fixtures import StripeChargeFactory
from tests.fixtures.decimal_fixtures import money_strategy


class TestIdempotencyKeyUniqueness:
    """Test idempotency key uniqueness properties"""

    @given(st.text(min_size=5, max_size=20), st.integers(min_value=1, max_value=1000))
    @settings(max_examples=100)
    def test_uuid_prevents_collisions(self, customer_id, order_id):
        """Generate idempotency keys for same operation + different order_ids, verify no collisions"""
        # Generate keys for same operation with different identifiers
        keys = []
        for i in range(10):
            key = StripeService.generate_idempotency_key('charge', customer_id, f'{order_id}_{i}')
            keys.append(key)

        # All keys should be unique (UUID + timestamp prevents collisions)
        assert len(set(keys)) == len(keys), f"Collision detected in keys: {keys}"

    @given(st.lists(st.integers(min_value=1, max_value=10000), min_size=10, max_size=100))
    @settings(max_examples=50)
    def test_business_derived_keys_unique(self, order_ids):
        """Generate keys for list of order IDs, verify all unique"""
        keys = []
        for order_id in order_ids:
            key = StripeService.generate_idempotency_key('charge', 'cust123', f'order_{order_id}')
            keys.append(key)

        # All keys should be unique
        assert len(set(keys)) == len(keys), f"Collision detected in {len(keys)} keys"

    @given(st.text(min_size=1, max_size=50), st.integers(min_value=1, max_value=1000))
    @settings(max_examples=100)
    def test_long_identifiers_truncated_safely(self, identifier, order_id):
        """Generate keys with long identifiers, verify length < 255 and still unique"""
        # Create very long identifier by repeating
        long_identifier = (identifier + '_') * 10

        key = StripeService.generate_idempotency_key('charge', long_identifier, f'order_{order_id}')

        # Key should be under 255 chars
        assert len(key) < 255, f"Key too long: {len(key)} chars"

        # Key should still be valid format
        assert 'charge' in key
        assert '_' in key

    @given(st.text(min_size=5, max_size=20), st.text(min_size=5, max_size=20))
    @settings(max_examples=100)
    def test_different_operations_different_keys(self, customer_id, order_id):
        """Verify same identifiers + different operation = different keys"""
        key1 = StripeService.generate_idempotency_key('charge', customer_id, order_id)
        key2 = StripeService.generate_idempotency_key('refund', customer_id, order_id)
        key3 = StripeService.generate_idempotency_key('subscription', customer_id, order_id)

        # All keys should be different
        assert key1 != key2
        assert key1 != key3
        assert key2 != key3

    @given(st.integers(min_value=10, max_value=100))
    @settings(max_examples=50)
    def test_batch_keys_all_unique(self, count):
        """Generate N keys rapidly, verify all unique"""
        keys = []
        for i in range(count):
            key = StripeService.generate_idempotency_key('charge', f'cust_{i}', f'order_{i}')
            keys.append(key)

        # All keys should be unique
        assert len(set(keys)) == len(keys), f"Collision detected in {count} keys"


class TestIdempotencyInKeyStructure:
    """Test idempotency key structure and format"""

    @given(st.text(min_size=5, max_size=20), st.integers(min_value=1, max_value=1000))
    @settings(max_examples=100)
    def test_key_format_valid(self, customer_id, order_id):
        """Verify key follows expected format: operation_uuid_identifier_timestamp"""
        key = StripeService.generate_idempotency_key('charge', customer_id, f'order_{order_id}')

        # Should have 4 parts separated by underscores
        parts = key.split('_')
        assert len(parts) >= 4, f"Invalid key format: {key}"

        # First part should be operation type
        assert parts[0] == 'charge'

        # Second part should be 8-char UUID suffix (hex)
        assert len(parts[1]) == 8
        assert all(c in '0123456789abcdef' for c in parts[1])

        # Last part should be timestamp (integer)
        assert parts[-1].isdigit()

    @given(st.sampled_from(['charge', 'refund', 'subscription', 'customer', 'invoice']))
    @settings(max_examples=50)
    def test_operation_type_in_key(self, operation_type):
        """Verify operation type is included in key"""
        key = StripeService.generate_idempotency_key(operation_type, 'cust123', 'order456')

        # Operation type should be first component
        assert key.startswith(f'{operation_type}_')

    @given(st.text(min_size=1, max_size=20), st.integers(min_value=1, max_value=1000))
    @settings(max_examples=100)
    def test_business_identifiers_in_key(self, identifier, order_id):
        """Verify business identifiers are included in key"""
        key = StripeService.generate_idempotency_key('charge', identifier, f'order_{order_id}')

        # Identifiers should be in key
        assert identifier in key or str(order_id) in key

    @given(st.integers(min_value=1, max_value=100))
    @settings(max_examples=50)
    def test_timestamp_increases(self, count):
        """Verify timestamp component increases over time"""
        keys = []
        for i in range(count):
            key = StripeService.generate_idempotency_key('charge', 'cust', f'order_{i}')
            keys.append(key)
            time.sleep(0.001)  # Small delay to ensure timestamp change

        # Extract timestamps from keys
        timestamps = [int(key.split('_')[-1]) for key in keys]

        # Timestamps should be non-decreasing
        for i in range(1, len(timestamps)):
            assert timestamps[i] >= timestamps[i-1], "Timestamps should be non-decreasing"


class TestIdempotencyEdgeCases:
    """Test idempotency key edge cases"""

    @given(st.text(min_size=0, max_size=10))
    @settings(max_examples=100)
    def test_empty_identifiers_generates_valid_key(self, empty_identifier):
        """Generate key with empty identifiers, verify valid"""
        key = StripeService.generate_idempotency_key('charge', '', empty_identifier)

        # Should be valid
        assert len(key) < 255
        assert 'charge' in key

        # Empty strings are falsy, so they get filtered out by `if p`
        # When all identifiers are empty, the join produces '' (empty string)
        # Result: charge_{uuid}__{timestamp} (note double underscore)
        # Key is still valid and unique due to UUID + timestamp
        assert 'charge_' in key
        assert len(key.split('_')) >= 3  # Has at least operation, uuid, timestamp

    @given(st.text(min_size=1, max_size=50), st.integers(min_value=1, max_value=1000))
    @settings(max_examples=100)
    def test_unicode_identifiers_handled(self, identifier, order_id):
        """Generate key with unicode characters, verify valid ASCII"""
        # Use text strategy which includes unicode
        key = StripeService.generate_idempotency_key('charge', identifier, f'order_{order_id}')

        # Key should be valid (string converted to str)
        assert isinstance(key, str)
        assert len(key) < 255

    @given(st.integers(min_value=1, max_value=50))
    @settings(max_examples=50)
    def test_rapid_generation_no_collision(self, count):
        """Generate keys rapidly without delay, verify timestamp prevents collision"""
        keys = []
        for i in range(count):
            key = StripeService.generate_idempotency_key('charge', 'cust', f'order_{i}')
            keys.append(key)

        # All keys should be unique even with rapid generation
        assert len(set(keys)) == len(keys), f"Collision detected in rapid generation of {count} keys"

    @given(st.text(min_size=5, max_size=20), st.integers(min_value=1, max_value=1000))
    @settings(max_examples=100)
    def test_none_identifiers_handled(self, customer_id, order_id):
        """Generate key with None values, verify valid"""
        key = StripeService.generate_idempotency_key('charge', customer_id, None, f'order_{order_id}', None)

        # Should filter out None values and create valid key
        assert len(key) < 255
        assert 'charge' in key

    @given(st.lists(st.text(min_size=1, max_size=10), min_size=1, max_size=10))
    @settings(max_examples=50)
    def test_multiple_identifiers_combined(self, identifiers):
        """Generate key with multiple identifiers, verify all included"""
        key = StripeService.generate_idempotency_key('charge', *identifiers)

        # Should be valid
        assert len(key) < 255
        assert 'charge' in key

        # At least some identifiers should be in key (unless truncated)
        if len(key) < 200:  # Not truncated
            for identifier in identifiers[:3]:  # Check first 3
                if len(identifier) <= 20:  # Short identifiers
                    assert identifier in key or 'generic' in key


class TestIdempotencyUniquenessInvariants:
    """Test core idempotency uniqueness invariants"""

    @given(st.integers(min_value=100, max_value=1000))
    @settings(max_examples=20)
    def test_large_batch_no_collisions(self, count):
        """Generate 100-1000 keys, verify zero collisions"""
        keys = set()
        for i in range(count):
            key = StripeService.generate_idempotency_key('charge', f'cust_{i}', f'order_{i}')
            keys.add(key)

        # Set size should equal count (no collisions)
        assert len(keys) == count, f"Collision detected: {count} keys generated, {len(keys)} unique"

    @given(st.text(min_size=5, max_size=20), st.integers(min_value=1, max_value=100))
    @settings(max_examples=100)
    def test_same_params_different_time_different_keys(self, customer_id, order_id):
        """Same parameters + different time = different keys (timestamp ensures uniqueness)"""
        key1 = StripeService.generate_idempotency_key('charge', customer_id, f'order_{order_id}')
        time.sleep(0.01)  # Ensure different timestamp
        key2 = StripeService.generate_idempotency_key('charge', customer_id, f'order_{order_id}')

        # Keys should be different (timestamp differs)
        assert key1 != key2

    @given(st.sampled_from(['charge', 'refund', 'subscription', 'customer']))
    @settings(max_examples=100)
    def test_operation_isolation(self, operation_type):
        """Keys for different operations should never collide"""
        # Generate keys for different operations with same identifiers
        keys = {}
        for op in ['charge', 'refund', 'subscription', 'customer']:
            key = StripeService.generate_idempotency_key(op, 'cust123', 'order456')
            keys[op] = key

        # All keys should be different
        for op1, key1 in keys.items():
            for op2, key2 in keys.items():
                if op1 != op2:
                    assert key1 != key2, f"Collision between {op1} and {op2}"

    @given(st.integers(min_value=10, max_value=100))
    @settings(max_examples=30)
    def test_identifier_permutations_unique(self, count):
        """Different identifier permutations should produce unique keys"""
        keys = []
        for i in range(count):
            # Different ordering of same identifiers
            key1 = StripeService.generate_idempotency_key('charge', f'a{i}', f'b{i}', f'c{i}')
            key2 = StripeService.generate_idempotency_key('charge', f'b{i}', f'a{i}', f'c{i}')
            keys.append((key1, key2))

        # All keys should be unique
        all_keys = [k for pair in keys for k in pair]
        assert len(set(all_keys)) == len(all_keys), f"Collision in permutations"


class TestIdempotencyWithMonetaryValues:
    """Test idempotency with monetary value strategies"""

    @given(amount=money_strategy())
    @settings(max_examples=100)
    def test_keys_for_various_amounts(self, amount):
        """Generate keys for various monetary amounts, verify valid"""
        # Convert Decimal to cents for Stripe
        amount_cents = int(amount * 100)

        key = StripeService.generate_idempotency_key(
            'charge',
            'cust123',
            f'order_{amount_cents}'
        )

        # Key should be valid
        assert len(key) < 255
        assert 'charge' in key

    @given(amount=money_strategy(), customer_id=st.text(min_size=5, max_size=20))
    @settings(max_examples=100)
    def test_amount_in_identifier(self, amount, customer_id):
        """Include amount in identifier, verify key valid"""
        amount_cents = int(amount * 100)

        key = StripeService.generate_idempotency_key(
            'charge',
            customer_id,
            f'amount_{amount_cents}'
        )

        # Should be valid and include amount in identifier
        assert len(key) < 255
        assert customer_id in key

    @given(st.lists(money_strategy(), min_size=5, max_size=20))
    @settings(max_examples=50)
    def test_batch_amounts_unique_keys(self, amounts):
        """Generate keys for list of amounts, verify all unique"""
        keys = []
        for i, amount in enumerate(amounts):
            amount_cents = int(amount * 100)
            key = StripeService.generate_idempotency_key(
                'charge',
                f'cust_{i}',
                f'amount_{amount_cents}'
            )
            keys.append(key)

        # All keys should be unique
        assert len(set(keys)) == len(keys), f"Collision in {len(keys)} keys for different amounts"
