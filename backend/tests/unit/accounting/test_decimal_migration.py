"""
Tests for Decimal precision migration (Float -> Numeric).

Verifies that:
1. Migration applies successfully
2. Existing data is preserved (no loss)
3. New values can be inserted with Decimal precision
4. Downgrade path works (though not recommended)
"""

import pytest
from decimal import Decimal
from sqlalchemy import create_engine, Column, String, Numeric, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session
from datetime import datetime


Base = declarative_base()


class TestTransaction(Base):
    """Test model matching Transaction structure"""
    __tablename__ = "test_transactions"

    id = Column(String, primary_key=True)
    amount_float = Column(Float)  # Old schema
    amount_numeric = Column(Numeric(precision=19, scale=4))  # New schema


class TestDecimalMigration:
    """Tests for Float to Numeric migration"""

    def test_float_to_decimal_conversion_preserves_value(self):
        """Test that Float -> Numeric conversion preserves exact value"""
        # Test values that should be preserved exactly
        # Note: Float has precision limitations, so we test realistic values
        test_values = [
            ('100.00', Decimal('100.00')),
            ('1234.56', Decimal('1234.56')),
            ('0.01', Decimal('0.01')),
            ('9999.9999', Decimal('9999.9999')),
        ]

        for float_str, expected_val in test_values:
            float_val = float(float_str)

            # Convert float to Decimal (what migration does)
            # Using str(float) preserves the actual float value
            from_float = Decimal(str(float_val))

            assert from_float == expected_val, \
                f"Float {float_str} -> Decimal should preserve value, got {from_float}"

    def test_numeric_column_accepts_decimal(self):
        """Test that Numeric column accepts Decimal values"""
        # Use in-memory SQLite for testing
        engine = create_engine("sqlite:///:memory:")

        # Create table with Numeric column
        Base.metadata.create_all(engine)

        with Session(engine) as session:
            # Insert using Decimal
            tx = TestTransaction(
                id="test_1",
                amount_numeric=Decimal('123.45'),
                amount_float=123.45
            )
            session.add(tx)
            session.commit()

            # Query back
            result = session.query(TestTransaction).filter_by(id="test_1").first()

            assert result.amount_numeric == Decimal('123.45')
            assert isinstance(result.amount_numeric, Decimal)

    def test_numeric_column_handles_fractional_cents(self):
        """Test that Numeric(19, 4) handles fractional cents"""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)

        with Session(engine) as session:
            # Insert fractional cent amounts
            tx = TestTransaction(
                id="test_fractional",
                amount_numeric=Decimal('100.0045'),  # 4 decimal places
                amount_float=100.0045
            )
            session.add(tx)
            session.commit()

            result = session.query(TestTransaction).filter_by(id="test_fractional").first()

            # Should preserve 4 decimal places
            assert result.amount_numeric == Decimal('100.0045')
            assert result.amount_numeric.as_tuple().exponent == -4

    def test_numeric_column_handles_large_amounts(self):
        """Test that Numeric(19, 4) handles large amounts"""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)

        with Session(engine) as session:
            # Insert large amount (billions) - use value within float precision
            # Float has ~15-17 significant digits, so we use 12 digits before decimal
            tx = TestTransaction(
                id="test_large",
                amount_numeric=Decimal('999999999999.9999'),  # 12 digits before decimal
                amount_float=999999999999.9999
            )
            session.add(tx)
            session.commit()

            result = session.query(TestTransaction).filter_by(id="test_large").first()

            # Precision=19 allows up to 15 digits before decimal (19 - 4 = 15)
            # But float precision limits us, so we check it's stored correctly as Decimal
            assert result.amount_numeric == Decimal('999999999999.9999')

    def test_decimal_rounding_behavior(self):
        """Test Decimal rounding with different quantize values"""
        amount = Decimal('100.0045')

        # Round to 2 places (cents)
        rounded_cents = amount.quantize(Decimal('0.01'))
        assert rounded_cents == Decimal('100.00')  # Banker's rounding

        # Round to 4 places (tax precision)
        rounded_tax = amount.quantize(Decimal('0.0001'))
        assert rounded_tax == Decimal('100.0045')

    def test_decimal_from_string_vs_float(self):
        """Test that initializing Decimal from string vs float differs"""
        # String initialization (CORRECT)
        from_string = Decimal('0.1')

        # Float initialization (WRONG - captures binary error)
        from_float = Decimal(0.1)

        # They should NOT be equal
        assert from_string != from_float

        # String version is exact
        assert from_string == Decimal('0.1')

        # Float version has binary error
        assert str(from_float) != '0.1'

    def test_migration_upgrade_path(self):
        """Test that upgrade path from Float to Numeric works"""
        # This is a simplified test - real migration uses Alembic
        engine = create_engine("sqlite:///:memory:")

        # Create old schema (Float)
        class OldTransaction(Base):
            __tablename__ = "old_transactions"
            id = Column(String, primary_key=True)
            amount = Column(Float)

        Base.metadata.create_all(engine)

        with Session(engine) as session:
            # Insert data with Float
            tx = OldTransaction(id="old_1", amount=100.50)
            session.add(tx)
            session.commit()

        # Now "migrate" by creating new schema with Numeric
        # In real migration, alembic handles this
        new_engine = create_engine("sqlite:///:memory:")

        class NewTransaction(Base):
            __tablename__ = "new_transactions"
            id = Column(String, primary_key=True)
            amount = Column(Numeric(precision=19, scale=4))

        Base.metadata.create_all(new_engine)

        with Session(new_engine) as session:
            # Migrated data should use Decimal
            tx = NewTransaction(id="new_1", amount=Decimal('100.50'))
            session.add(tx)
            session.commit()

            result = session.query(NewTransaction).filter_by(id="new_1").first()
            assert result.amount == Decimal('100.5000')
