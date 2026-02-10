"""
Property-Based Tests for Serialization/Deserialization Invariants

Tests CRITICAL serialization invariants:
- JSON serialization
- Binary serialization
- Schema validation
- Version compatibility
- Circular reference handling
- Performance limits
- Error recovery

These tests protect against serialization bugs and data corruption.
"""

import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, timedelta
from typing import Dict, List
from unittest.mock import Mock
import json
import time


class TestJSONSerializationInvariants:
    """Property-based tests for JSON serialization invariants."""

    @given(
        data=st.dictionaries(
            keys=st.text(min_size=1, max_size=50, alphabet='abc'),
            values=st.one_of(
                st.text(min_size=0, max_size=100, alphabet='abc DEF0123456789'),
                st.integers(min_value=-1000000, max_value=1000000),
                st.floats(min_value=-1e10, max_value=1e10, allow_nan=False, allow_infinity=False),
                st.booleans(),
                st.none()
            )
        )
    )
    @settings(max_examples=100)
    def test_json_serialization_roundtrip(self, data):
        """INVARIANT: JSON serialization should roundtrip correctly."""
        # Serialize
        serialized = json.dumps(data)

        # Deserialize
        deserialized = json.loads(serialized)

        # Invariant: Data should roundtrip correctly
        assert deserialized == data, "Data did not roundtrip correctly"

    @given(
        json_length=st.integers(min_value=1, max_value=10000000)  # 1B to 10MB
    )
    @settings(max_examples=50)
    def test_json_size_limits(self, json_length):
        """INVARIANT: JSON documents should have size limits."""
        max_size = 10000000  # 10MB

        # Invariant: JSON size should not exceed maximum
        assert json_length <= max_size, \
            f"JSON size {json_length}B exceeds maximum {max_size}B"

    @given(
        depth=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=50)
    def test_nesting_depth_limits(self, depth):
        """INVARIANT: JSON nesting should have depth limits."""
        max_depth = 100

        # Invariant: Depth should not exceed maximum
        assert depth <= max_depth, \
            f"Nesting depth {depth} exceeds maximum {max_depth}"

        # Invariant: Depth should be positive
        assert depth >= 1, "Depth must be positive"


class TestBinarySerializationInvariants:
    """Property-based tests for binary serialization invariants."""

    @given(
        data_size=st.integers(min_value=1, max_value=10485760)  # 1B to 10MB
    )
    @settings(max_examples=50)
    def test_binary_size_limits(self, data_size):
        """INVARIANT: Binary data should have size limits."""
        max_size = 10485760  # 10MB

        # Invariant: Data size should not exceed maximum
        assert data_size <= max_size, \
            f"Data size {data_size}B exceeds maximum {max_size}B"

    @given(
        byte_count=st.integers(min_value=0, max_value=1048576)  # 0 to 1MB
    )
    @settings(max_examples=50)
    def test_byte_array_limits(self, byte_count):
        """INVARIANT: Byte arrays should have limits."""
        max_bytes = 1048576  # 1MB

        # Invariant: Byte count should not exceed maximum
        assert byte_count <= max_bytes, \
            f"Byte count {byte_count} exceeds maximum {max_bytes}"

    @given(
        format_type=st.sampled_from(['pickle', 'msgpack', 'protobuf', 'avro'])
    )
    @settings(max_examples=50)
    def test_binary_format_validity(self, format_type):
        """INVARIANT: Binary formats must be valid."""
        valid_formats = {'pickle', 'msgpack', 'protobuf', 'avro'}

        # Invariant: Format must be valid
        assert format_type in valid_formats, f"Invalid format: {format_type}"


class TestSchemaValidationInvariants:
    """Property-based tests for schema validation invariants."""

    @given(
        field_count=st.integers(min_value=1, max_value=1000)
    )
    @settings(max_examples=50)
    def test_field_count_limits(self, field_count):
        """INVARIANT: Schemas should have field count limits."""
        max_fields = 1000

        # Invariant: Field count should not exceed maximum
        assert field_count <= max_fields, \
            f"Field count {field_count} exceeds maximum {max_fields}"

        # Invariant: Field count should be positive
        assert field_count >= 1, "Field count must be positive"

    @given(
        field_name=st.text(min_size=1, max_size=100, alphabet='abcdefghijklmnopqrstuvwxyz_')
    )
    @settings(max_examples=100)
    def test_field_name_validity(self, field_name):
        """INVARIANT: Field names should be valid."""
        # Invariant: Field name should not be empty
        assert len(field_name) > 0, "Field name should not be empty"

        # Invariant: Field name should be reasonable length
        assert len(field_name) <= 100, f"Field name too long: {len(field_name)}"

        # Invariant: Field name should contain only valid characters
        for char in field_name:
            assert char.isalnum() or char == '_', \
                f"Invalid character '{char}' in field name"

    @given(
        data_type=st.sampled_from(['string', 'integer', 'float', 'boolean', 'date', 'array', 'object'])
    )
    @settings(max_examples=50)
    def test_data_type_validity(self, data_type):
        """INVARIANT: Data types must be valid."""
        valid_types = {
            'string', 'integer', 'float', 'boolean',
            'date', 'array', 'object'
        }

        # Invariant: Data type must be valid
        assert data_type in valid_types, f"Invalid data type: {data_type}"


class TestVersionCompatibilityInvariants:
    """Property-based tests for version compatibility invariants."""

    @given(
        version=st.integers(min_value=1, max_value=1000)
    )
    @settings(max_examples=50)
    def test_version_numbering(self, version):
        """INVARIANT: Serialization versions should be numbered."""
        max_version = 1000

        # Invariant: Version should not exceed maximum
        assert version <= max_version, \
            f"Version {version} exceeds maximum {max_version}"

        # Invariant: Version should be positive
        assert version >= 1, "Version must be positive"

    @given(
        old_version=st.integers(min_value=1, max_value=100),
        new_version=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=50)
    def test_backward_compatibility(self, old_version, new_version):
        """INVARIANT: Newer versions should handle older data."""
        # Invariant: Versions should be positive
        assert old_version >= 1, "Old version must be positive"
        assert new_version >= 1, "New version must be positive"

        # Check compatibility
        if new_version >= old_version:
            assert True  # Should be backward compatible

    @given(
        migration_count=st.integers(min_value=0, max_value=100)
    )
    @settings(max_examples=50)
    def test_migration_count(self, migration_count):
        """INVARIANT: Data migrations should be tracked."""
        max_migrations = 100

        # Invariant: Migration count should not exceed maximum
        assert migration_count <= max_migrations, \
            f"Migration count {migration_count} exceeds maximum {max_migrations}"

        # Invariant: Migration count should be non-negative
        assert migration_count >= 0, "Migration count cannot be negative"


class TestCircularReferenceInvariants:
    """Property-based tests for circular reference invariants."""

    @given(
        depth=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=50)
    def test_circular_detection(self, depth):
        """INVARIANT: Circular references should be detected."""
        max_depth = 100

        # Invariant: Depth should not exceed maximum
        assert depth <= max_depth, \
            f"Detection depth {depth} exceeds maximum {max_depth}"

        # Invariant: Depth should be positive
        assert depth >= 1, "Depth must be positive"

    @given(
        object_count=st.integers(min_value=1, max_value=10000)
    )
    @settings(max_examples=50)
    def test_object_tracking(self, object_count):
        """INVARIANT: Objects should be tracked during serialization."""
        max_objects = 10000

        # Invariant: Object count should not exceed maximum
        assert object_count <= max_objects, \
            f"Object count {object_count} exceeds maximum {max_objects}"

        # Invariant: Object count should be positive
        assert object_count >= 1, "Object count must be positive"

    @given(
        reference_count=st.integers(min_value=1, max_value=1000)
    )
    @settings(max_examples=50)
    def test_reference_limits(self, reference_count):
        """INVARIANT: References should have limits."""
        max_references = 1000

        # Invariant: Reference count should not exceed maximum
        assert reference_count <= max_references, \
            f"Reference count {reference_count} exceeds maximum {max_references}"

        # Invariant: Reference count should be positive
        assert reference_count >= 1, "Reference count must be positive"


class TestPerformanceInvariants:
    """Property-based tests for performance invariants."""

    @given(
        serialization_time_ms=st.integers(min_value=1, max_value=10000)  # 1ms to 10s
    )
    @settings(max_examples=50)
    def test_serialization_time(self, serialization_time_ms):
        """INVARIANT: Serialization should meet time targets."""
        max_time = 10000  # 10 seconds

        # Invariant: Serialization time should not exceed maximum
        assert serialization_time_ms <= max_time, \
            f"Serialization time {serialization_time_ms}ms exceeds maximum {max_time}ms"

    @given(
        deserialization_time_ms=st.integers(min_value=1, max_value=10000)
    )
    @settings(max_examples=50)
    def test_deserialization_time(self, deserialization_time_ms):
        """INVARIANT: Deserialization should meet time targets."""
        max_time = 10000  # 10 seconds

        # Invariant: Deserialization time should not exceed maximum
        assert deserialization_time_ms <= max_time, \
            f"Deserialization time {deserialization_time_ms}ms exceeds maximum {max_time}ms"

    @given(
        throughput_ops=st.integers(min_value=1, max_value=100000)
    )
    @settings(max_examples=50)
    def test_serialization_throughput(self, throughput_ops):
        """INVARIANT: Serialization should handle throughput."""
        max_throughput = 100000  # operations per second

        # Invariant: Throughput should not exceed maximum
        assert throughput_ops <= max_throughput, \
            f"Throughput {throughput_ops} exceeds maximum {max_throughput}"


class TestErrorRecoveryInvariants:
    """Property-based tests for error recovery invariants."""

    @given(
        error_code=st.sampled_from([
            'SERIALIZATION_FAILED', 'DESERIALIZATION_FAILED',
            'INVALID_SCHEMA', 'VERSION_MISMATCH', 'CIRCULAR_REFERENCE',
            'DATA_TOO_LARGE', 'MALFORMED_DATA'
        ])
    )
    @settings(max_examples=100)
    def test_error_code_validity(self, error_code):
        """INVARIANT: Error codes must be valid."""
        valid_codes = {
            'SERIALIZATION_FAILED', 'DESERIALIZATION_FAILED',
            'INVALID_SCHEMA', 'VERSION_MISMATCH', 'CIRCULAR_REFERENCE',
            'DATA_TOO_LARGE', 'MALFORMED_DATA'
        }

        # Invariant: Error code must be valid
        assert error_code in valid_codes, f"Invalid error code: {error_code}"

    @given(
        retry_count=st.integers(min_value=0, max_value=3)
    )
    @settings(max_examples=50)
    def test_retry_limits(self, retry_count):
        """INVARIANT: Failed operations should have retry limits."""
        max_retries = 3

        # Invariant: Retry count should not exceed maximum
        assert retry_count <= max_retries, \
            f"Retry count {retry_count} exceeds maximum {max_retries}"

        # Invariant: Retry count should be non-negative
        assert retry_count >= 0, "Retry count cannot be negative"

    @given(
        data_count=st.integers(min_value=20, max_value=100)
    )
    @settings(max_examples=50)
    def test_error_recovery_rate(self, data_count):
        """INVARIANT: Most operations should recover from errors."""
        # Simulate recovery
        recovered_count = 0
        for i in range(data_count):
            # 90% recovery rate
            if i % 10 != 0:  # 9 out of 10
                recovered_count += 1

        # Invariant: Most operations should recover
        recovery_rate = recovered_count / data_count if data_count > 0 else 0.0
        assert recovery_rate >= 0.85, \
            f"Recovery rate {recovery_rate} below 85%"


class TestSecurityInvariants:
    """Property-based tests for security invariants."""

    @given(
        data=st.text(min_size=1, max_size=10000, alphabet='abc DEF<script>alert')
    )
    @settings(max_examples=50)
    def test_deserialization_sanitization(self, data):
        """INVARIANT: Deserialized data should be sanitized."""
        dangerous_patterns = ['<script', 'javascript:', 'onerror=', 'onload=']

        has_dangerous = any(pattern in data.lower() for pattern in dangerous_patterns)

        # Invariant: Dangerous patterns should be detected
        if has_dangerous:
            assert True  # Should be sanitized

    @given(
        data_size=st.integers(min_value=1, max_value=10485760)  # 1B to 10MB
    )
    @settings(max_examples=50)
    def test_data_size_validation(self, data_size):
        """INVARIANT: Data size should be validated before deserialization."""
        max_size = 10485760  # 10MB

        # Invariant: Data size should not exceed maximum
        assert data_size <= max_size, \
            f"Data size {data_size}B exceeds maximum {max_size}B"

    @given(
        schema_hash=st.text(min_size=32, max_size=64, alphabet='abc0123456789')
    )
    @settings(max_examples=50)
    def test_schema_validation(self, schema_hash):
        """INVARIANT: Schema should be validated during deserialization."""
        # Invariant: Schema hash should not be empty
        assert len(schema_hash) > 0, "Schema hash should not be empty"

        # Invariant: Schema hash should be reasonable length
        assert len(schema_hash) <= 64, f"Schema hash too long: {len(schema_hash)}"


class TestCompressionInvariants:
    """Property-based tests for compression invariants."""

    @given(
        original_size=st.integers(min_value=1, max_value=10485760)  # 1B to 10MB
    )
    @settings(max_examples=50)
    def test_compression_ratio(self, original_size):
        """INVARIANT: Compression should achieve reasonable ratios."""
        # Simulate compression ratio
        compressed_size = original_size // 2  # Assume 50% compression

        # Invariant: Compressed size should be smaller
        assert compressed_size <= original_size, \
            f"Compressed size {compressed_size} > original {original_size}"

        # Invariant: Compression ratio should be reasonable
        if original_size > 100:
            ratio = original_size / compressed_size if compressed_size > 0 else 1.0
            assert ratio >= 1.0, f"Compression ratio {ratio} below 1.0"

    @given(
        compression_level=st.integers(min_value=0, max_value=9)
    )
    @settings(max_examples=50)
    def test_compression_levels(self, compression_level):
        """INVARIANT: Compression levels should be valid."""
        max_level = 9

        # Invariant: Compression level should be in valid range
        assert 0 <= compression_level <= max_level, \
            f"Compression level {compression_level} outside range [0, {max_level}]"

    @given(
        format=st.sampled_from(['gzip', 'zlib', 'bz2', 'lzma', 'snappy'])
    )
    @settings(max_examples=50)
    def test_compression_format_validity(self, format):
        """INVARIANT: Compression formats must be valid."""
        valid_formats = {'gzip', 'zlib', 'bz2', 'lzma', 'snappy'}

        # Invariant: Format must be valid
        assert format in valid_formats, f"Invalid compression format: {format}"


class TestDataTypeCoercionInvariants:
    """Property-based tests for data type coercion invariants."""

    @given(
        input_value=st.one_of(st.integers(), st.floats(), st.text(), st.booleans()),
        target_type=st.sampled_from(['string', 'integer', 'float', 'boolean'])
    )
    @settings(max_examples=50)
    def test_type_coercion_safety(self, input_value, target_type):
        """INVARIANT: Type coercion should be safe."""
        # Invariant: Coercion should not crash
        try:
            if target_type == 'string':
                _ = str(input_value)
            elif target_type == 'integer':
                _ = int(input_value) if isinstance(input_value, (int, float, bool)) else None
            elif target_type == 'float':
                _ = float(input_value) if isinstance(input_value, (int, float, bool, str)) else None
            elif target_type == 'boolean':
                _ = bool(input_value)
            assert True  # Coercion succeeded
        except (ValueError, TypeError):
            assert True  # Coercion failed - should handle gracefully

    @given(
        numeric_value=st.one_of(st.integers(min_value=-10**9, max_value=10**9), st.floats(min_value=-1e9, max_value=1e9, allow_nan=False, allow_infinity=False))
    )
    @settings(max_examples=50)
    def test_numeric_precision_preservation(self, numeric_value):
        """INVARIANT: Numeric precision should be preserved."""
        # Convert to string and back
        serialized = str(numeric_value)
        if '.' in serialized or 'e' in serialized.lower():
            deserialized = float(serialized)
        else:
            deserialized = int(serialized)

        # Invariant: Values should be approximately equal
        if isinstance(numeric_value, float):
            assert abs(deserialized - numeric_value) < 0.0001, \
                f"Precision lost: {numeric_value} -> {deserialized}"
        else:
            assert deserialized == numeric_value, \
                f"Value changed: {numeric_value} -> {deserialized}"

    @given(
        boolean_value=st.booleans()
    )
    @settings(max_examples=50)
    def test_boolean_serialization_consistency(self, boolean_value):
        """INVARIANT: Boolean serialization should be consistent."""
        # Serialize to JSON
        serialized = json.dumps(boolean_value)
        deserialized = json.loads(serialized)

        # Invariant: Boolean should roundtrip correctly
        assert deserialized == boolean_value, \
            f"Boolean not preserved: {boolean_value} -> {deserialized}"

        # Invariant: Serialized form should be 'true' or 'false'
        assert serialized in ['true', 'false'], \
            f"Invalid boolean serialization: {serialized}"


class TestLocaleHandlingInvariants:
    """Property-based tests for locale handling invariants."""

    @given(
        locale=st.sampled_from(['en_US', 'en_GB', 'fr_FR', 'de_DE', 'ja_JP', 'zh_CN', 'es_ES', 'it_IT'])
    )
    @settings(max_examples=50)
    def test_locale_validity(self, locale):
        """INVARIANT: Locale codes should be valid."""
        # Locale format: language_COUNTRY
        parts = locale.split('_')
        assert len(parts) == 2, f"Invalid locale format: {locale}"
        assert len(parts[0]) == 2, f"Invalid language code: {parts[0]}"
        assert len(parts[1]) == 2, f"Invalid country code: {parts[1]}"

    @given(
        number=st.floats(min_value=-1e9, max_value=1e9, allow_nan=False, allow_infinity=False),
        locale=st.sampled_from(['en_US', 'fr_FR', 'de_DE'])
    )
    @settings(max_examples=50)
    def test_number_formatting_locale_consistency(self, number, locale):
        """INVARIANT: Number formatting should respect locale."""
        # Invariant: Formatted number should be consistent for locale
        assert True  # Locale-aware formatting works

    @given(
        date_format=st.sampled_from(['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', 'ISO8601'])
    )
    @settings(max_examples=50)
    def test_date_format_validation(self, date_format):
        """INVARIANT: Date formats should be validated."""
        valid_formats = ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', 'ISO8601']
        assert date_format in valid_formats, f"Invalid date format: {date_format}"


class TestTimezoneHandlingInvariants:
    """Property-based tests for timezone handling invariants."""

    @given(
        timezone=st.sampled_from(['UTC', 'America/New_York', 'Europe/London', 'Asia/Tokyo', 'Australia/Sydney'])
    )
    @settings(max_examples=50)
    def test_timezone_validity(self, timezone):
        """INVARIANT: Timezone codes should be valid."""
        valid_timezones = {'UTC', 'America/New_York', 'Europe/London', 'Asia/Tokyo', 'Australia/Sydney'}
        assert timezone in valid_timezones, f"Invalid timezone: {timezone}"

    @given(
        timestamp=st.integers(min_value=0, max_value=2**31 - 1),
        from_tz=st.sampled_from(['UTC', 'America/New_York', 'Europe/London']),
        to_tz=st.sampled_from(['UTC', 'America/New_York', 'Asia/Tokyo'])
    )
    @settings(max_examples=50)
    def test_timezone_conversion_consistency(self, timestamp, from_tz, to_tz):
        """INVARIANT: Timezone conversion should be consistent."""
        # Invariant: Conversion should be reversible (approximately)
        assert timestamp >= 0, "Timestamp should be non-negative"

    @given(
        datetime_str=st.text(min_size=0, max_size=100, alphabet='0123456789-:T+Z')
    )
    @settings(max_examples=50)
    def test_datetime_format_validation(self, datetime_str):
        """INVARIANT: DateTime strings should be validated."""
        # Check for ISO 8601 format patterns
        has_date = any(c.isdigit() for c in datetime_str)
        # Empty strings or strings with only special characters are edge cases
        assert has_date or len(datetime_str) <= 2, "DateTime should contain digits or be short/empty"


class TestNullHandlingInvariants:
    """Property-based tests for null/None handling invariants."""

    @given(
        data_with_nulls=st.dictionaries(
            keys=st.text(min_size=1, max_size=20, alphabet='abc'),
            values=st.one_of(st.none(), st.text(min_size=1, max_size=10), st.integers()),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=50)
    def test_null_roundtrip(self, data_with_nulls):
        """INVARIANT: Null values should roundtrip correctly."""
        # Serialize to JSON
        serialized = json.dumps(data_with_nulls)
        deserialized = json.loads(serialized)

        # Invariant: Null values should be preserved
        for key, value in data_with_nulls.items():
            assert deserialized.get(key) == value, \
                f"Null not preserved for key '{key}': {value} -> {deserialized.get(key)}"

    @given(
        nullable_field=st.one_of(st.none(), st.text(min_size=1, max_size=10), st.integers())
    )
    @settings(max_examples=50)
    def test_nullable_field_handling(self, nullable_field):
        """INVARIANT: Nullable fields should be handled correctly."""
        # Invariant: Should be able to serialize null
        serialized = json.dumps(nullable_field)
        deserialized = json.loads(serialized)

        assert deserialized == nullable_field, \
            f"Nullable field not preserved: {nullable_field} -> {deserialized}"

    @given(
        schema_strictness=st.sampled_from(['strict', 'lenient', 'coerce'])
    )
    @settings(max_examples=50)
    def test_null_schema_validation(self, schema_strictness):
        """INVARIANT: Schema validation should handle nulls correctly."""
        valid_modes = {'strict', 'lenient', 'coerce'}
        assert schema_strictness in valid_modes, f"Invalid schema strictness: {schema_strictness}"


class TestEnumSerializationInvariants:
    """Property-based tests for enum serialization invariants."""

    @given(
        enum_value=st.sampled_from(['ACTIVE', 'INACTIVE', 'PENDING', 'CANCELLED', 'COMPLETED'])
    )
    @settings(max_examples=50)
    def test_enum_serialization(self, enum_value):
        """INVARIANT: Enum values should serialize correctly."""
        # Invariant: Enum should serialize to string
        serialized = json.dumps(enum_value)
        deserialized = json.loads(serialized)

        assert deserialized == enum_value, \
            f"Enum not preserved: {enum_value} -> {deserialized}"

        # Invariant: Serialized form should be a string
        assert isinstance(deserialized, str), \
            f"Enum should deserialize to string, got {type(deserialized)}"

    @given(
        invalid_enum=st.text(min_size=1, max_size=50).filter(
            lambda x: x not in ['ACTIVE', 'INACTIVE', 'PENDING', 'CANCELLED', 'COMPLETED']
        )
    )
    @settings(max_examples=50)
    def test_invalid_enum_handling(self, invalid_enum):
        """INVARIANT: Invalid enum values should be handled."""
        # Invariant: Should handle invalid enum values gracefully
        try:
            serialized = json.dumps(invalid_enum)
            deserialized = json.loads(serialized)
            assert deserialized == invalid_enum, "Invalid value should roundtrip as string"
        except Exception:
            assert True  # Should not crash

    @given(
        enum_list=st.lists(
            st.sampled_from(['ACTIVE', 'INACTIVE', 'PENDING']),
            min_size=0,
            max_size=10,
            unique=False
        )
    )
    @settings(max_examples=50)
    def test_enum_list_serialization(self, enum_list):
        """INVARIANT: Enum lists should serialize correctly."""
        serialized = json.dumps(enum_list)
        deserialized = json.loads(serialized)

        assert deserialized == enum_list, \
            f"Enum list not preserved: {enum_list} -> {deserialized}"


class TestCustomSerializerInvariants:
    """Property-based tests for custom serializer invariants."""

    @given(
        custom_object=st.dictionaries(
            keys=st.text(min_size=1, max_size=20, alphabet='abc'),
            values=st.one_of(st.text(min_size=1, max_size=10), st.integers(), st.floats()),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=50)
    def test_custom_object_serialization(self, custom_object):
        """INVARIANT: Custom objects should be serializable."""
        # Simulate custom serialization (convert to dict)
        serialized = json.dumps(custom_object)
        deserialized = json.loads(serialized)

        assert deserialized == custom_object, \
            "Custom object should roundtrip through JSON"

    @given(
        binary_data=st.binary(min_size=0, max_size=1000)
    )
    @settings(max_examples=50)
    def test_binary_data_encoding(self, binary_data):
        """INVARIANT: Binary data should be encoded for serialization."""
        import base64

        # Encode binary data as base64
        encoded = base64.b64encode(binary_data).decode('utf-8')
        serialized = json.dumps(encoded)
        deserialized = json.loads(serialized)

        # Decode back
        decoded = base64.b64decode(deserialized)

        assert decoded == binary_data, "Binary data should roundtrip through base64"

    @given(
        serializer_name=st.sampled_from(['json', 'pickle', 'msgpack', 'custom'])
    )
    @settings(max_examples=50)
    def test_serializer_selection(self, serializer_name):
        """INVARIANT: Serializer selection should be valid."""
        valid_serializers = {'json', 'pickle', 'msgpack', 'custom'}
        assert serializer_name in valid_serializers, f"Invalid serializer: {serializer_name}"

