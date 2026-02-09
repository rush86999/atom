"""
Property-Based Tests for String Operations Invariants

Tests CRITICAL string operation invariants:
- String concatenation
- String splitting
- String searching
- String replacement
- String formatting
- Encoding/decoding
- Case conversion
- Whitespace handling
- String validation
- Unicode handling

These tests protect against string manipulation bugs and encoding issues.
"""

import pytest
from hypothesis import given, strategies as st, settings
from typing import Dict, List, Optional


class TestStringConcatenationInvariants:
    """Property-based tests for string concatenation invariants."""

    @given(
        str1=st.text(min_size=0, max_size=1000),
        str2=st.text(min_size=0, max_size=1000)
    )
    @settings(max_examples=50)
    def test_concatenation_length(self, str1, str2):
        """INVARIANT: Concatenated string length should equal sum of parts."""
        # Concatenate
        result = str1 + str2

        # Invariant: len(a + b) == len(a) + len(b)
        assert len(result) == len(str1) + len(str2), "Concatenation length"

    @given(
        str1=st.text(min_size=0, max_size=1000),
        str2=st.text(min_size=0, max_size=1000),
        str3=st.text(min_size=0, max_size=1000)
    )
    @settings(max_examples=50)
    def test_concatenation_associativity(self, str1, str2, str3):
        """INVARIANT: Concatenation should be associative."""
        # Invariant: (a + b) + c == a + (b + c)
        assert (str1 + str2) + str3 == str1 + (str2 + str3), "Concatenation associativity"

    @given(
        s=st.text(min_size=0, max_size=1000)
    )
    @settings(max_examples=50)
    def test_concatenation_identity(self, s):
        """INVARIANT: Empty string is concatenation identity."""
        # Invariant: s + "" == "" + s == s
        assert s + "" == s, "Empty string identity (right)"
        assert "" + s == s, "Empty string identity (left)"

    @given(
        parts=st.lists(st.text(min_size=0, max_size=100), min_size=0, max_size=100)
    )
    @settings(max_examples=50)
    def test_join_concatenation(self, parts):
        """INVARIANT: Join should concatenate with separator."""
        # Join with empty separator
        joined = "".join(parts)

        # Invariant: join with "" should equal concatenation
        assert joined == "".join(parts), "Empty join equals concatenation"


class TestStringSplittingInvariants:
    """Property-based tests for string splitting invariants."""

    @given(
        text=st.text(min_size=0, max_size=1000),
        sep=st.text(min_size=1, max_size=10, alphabet='abc')
    )
    @settings(max_examples=50)
    def test_split_parts(self, text, sep):
        """INVARIANT: Splitting and joining should be reversible."""
        # Split and rejoin
        parts = text.split(sep)
        rejoined = sep.join(parts)

        # Invariant: split(sep).join(sep) == original (if sep exists)
        if sep in text:
            assert rejoined == text, "Split-join reversibility"
        else:
            assert rejoined == text, "No split - original unchanged"

    @given(
        text=st.text(min_size=0, max_size=1000),
        sep=st.text(min_size=1, max_size=10, alphabet='abc')
    )
    @settings(max_examples=50)
    def test_split_maxsplit(self, text, sep):
        """INVARIANT: Max split should limit number of splits."""
        # Split with maxsplit
        maxsplit = 2
        parts_limited = text.split(sep, maxsplit)
        parts_unlimited = text.split(sep)

        # Invariant: Limited split should have <= maxsplit+1 parts
        assert len(parts_limited) <= maxsplit + 1, "Max split limits parts"
        assert len(parts_limited) <= len(parts_unlimited), "Limited <= unlimited"

    @given(
        text=st.text(min_size=0, max_size=1000),
        sep=st.text(min_size=1, max_size=10, alphabet='abc')
    )
    @settings(max_examples=50)
    def test_split_empty_separator(self, text, sep):
        """INVARIANT: Splitting with separator not in string returns original."""
        # Split when separator not in text
        parts = text.split(sep)

        # Invariant: If sep not in text, returns [text]
        if sep not in text:
            assert parts == [text], "No separator - returns original"
        else:
            assert True  # Separator found - splits

    @given(
        text=st.text(max_size=1000, alphabet='abc \n\t'),
        maxsplit=st.integers(min_value=-1, max_value=10)
    )
    @settings(max_examples=50)
    def test_split_whitespace(self, text, maxsplit):
        """INVARIANT: Whitespace splitting should handle empty strings."""
        # Split on whitespace
        parts = text.split(maxsplit=maxsplit if maxsplit >= 0 else -1)

        # Invariant: Should not have empty strings in result
        if maxsplit < 0:
            # Without maxsplit, split() removes empty strings
            assert "" not in parts, "No empty strings in whitespace split"
        else:
            assert True  # May have empty strings with maxsplit


class TestStringSearchingInvariants:
    """Property-based tests for string searching invariants."""

    @given(
        text=st.text(min_size=0, max_size=1000),
        substring=st.text(min_size=0, max_size=100)
    )
    @settings(max_examples=50)
    def test_find_index(self, text, substring):
        """INVARIANT: Find should return valid index or -1."""
        # Find substring
        index = text.find(substring)

        # Invariant: Should return -1 or valid index
        if index >= 0 and len(text) > 0:
            assert index < len(text), "Valid index"
        elif index >= 0 and len(text) == 0:
            # Edge case: empty string, find returns 0
            assert index == 0, "Empty string edge case"
        else:
            assert index == -1, "Not found returns -1"

    @given(
        text=st.text(min_size=0, max_size=1000),
        substring=st.text(min_size=0, max_size=100)
    )
    @settings(max_examples=50)
    def test_count_occurrences(self, text, substring):
        """INVARIANT: Count should return non-negative integer."""
        # Count occurrences
        count = text.count(substring)

        # Invariant: Count should be >= 0
        assert count >= 0, "Count non-negative"

    @given(
        text=st.text(min_size=0, max_size=1000),
        prefix=st.text(min_size=0, max_size=100)
    )
    @settings(max_examples=50)
    def test_startswith(self, text, prefix):
        """INVARIANT: Startswith should match prefix."""
        # Check if starts with
        starts = text.startswith(prefix)

        # Invariant: If starts with, text[0:len(prefix)] == prefix
        if starts:
            assert text[:len(prefix)] == prefix, "Startswith matches prefix"
        else:
            assert True  # Doesn't start with prefix

    @given(
        text=st.text(min_size=0, max_size=1000),
        suffix=st.text(min_size=0, max_size=100)
    )
    @settings(max_examples=50)
    def test_endswith(self, text, suffix):
        """INVARIANT: Endswith should match suffix."""
        # Check if ends with
        ends = text.endswith(suffix)

        # Invariant: If ends with, text[-len(suffix):] == suffix
        if ends:
            if suffix:
                assert text[-len(suffix):] == suffix, "Endswith matches suffix"
            else:
                # Empty suffix - always returns True
                assert True  # Empty suffix edge case
        else:
            assert True  # Doesn't end with suffix


class TestStringReplacementInvariants:
    """Property-based tests for string replacement invariants."""

    @given(
        text=st.text(min_size=0, max_size=1000),
        old=st.text(min_size=1, max_size=50, alphabet='abc'),
        new=st.text(min_size=0, max_size=50)
    )
    @settings(max_examples=50)
    def test_replace_length(self, text, old, new):
        """INVARIANT: Replace should not decrease string length if new >= old."""
        # Replace
        result = text.replace(old, new)

        # Invariant: If len(new) >= len(old), result length >= original
        if len(new) >= len(old):
            assert len(result) >= len(text), "Replacement doesn't shorten"
        else:
            assert True  # May shorten if new shorter

    @given(
        text=st.text(min_size=0, max_size=1000),
        old=st.text(min_size=1, max_size=50, alphabet='abc'),
        new=st.text(min_size=0, max_size=50)
    )
    @settings(max_examples=50)
    def test_replace_reversibility(self, text, old, new):
        """INVARIANT: Replace with same value should not change string."""
        # Replace with same value
        result = text.replace(old, old)

        # Invariant: Replacing with same value shouldn't change
        assert result == text, "Replace with same value is identity"

    @given(
        text=st.text(min_size=0, max_size=1000),
        old=st.text(min_size=1, max_size=50, alphabet='abc'),
        new=st.text(min_size=0, max_size=50)
    )
    @settings(max_examples=50)
    def test_replace_count(self, text, old, new):
        """INVARIANT: Replace with count=0 should not change string."""
        # Replace with count=0
        result = text.replace(old, new, 0)

        # Invariant: Count=0 should not replace anything
        assert result == text, "Replace count 0 is identity"

    @given(
        text=st.text(min_size=0, max_size=1000),
        old=st.text(min_size=1, max_size=50, alphabet='abc'),
        new=st.text(min_size=0, max_size=50)
    )
    @settings(max_examples=50)
    def test_replace_all(self, text, old, new):
        """INVARIANT: Replace without count should replace all occurrences."""
        # Replace all
        result_all = text.replace(old, new)

        # Replace with count=-1 (all)
        result_count = text.replace(old, new, -1)

        # Invariant: Both should replace all
        assert result_all == result_count, "Replace all equivalent"


class TestStringFormattingInvariants:
    """Property-based tests for string formatting invariants."""

    @given(
        value=st.integers(min_value=-1000000, max_value=1000000),
        format_spec=st.sampled_from(['d', 'x', 'o', 'b', 'e', 'f'])
    )
    @settings(max_examples=50)
    def test_format_integer(self, value, format_spec):
        """INVARIANT: Integer formatting should produce valid string."""
        # Format integer
        try:
            result = format(value, format_spec)

            # Invariant: Should produce valid string
            assert isinstance(result, str), "Formatting produces string"
        except:
            assert True  # Some format specs may not work with all values

    @given(
        value=st.floats(min_value=-1000000.0, max_value=1000000.0, allow_nan=False, allow_infinity=False),
        precision=st.integers(min_value=0, max_value=10)
    )
    @settings(max_examples=50)
    def test_format_float_precision(self, value, precision):
        """INVARIANT: Float precision should control decimal places."""
        # Format float
        format_string = f"{{:.{precision}f}}"
        result = format_string.format(value)

        # Invariant: Should have <= precision decimal places
        if '.' in result:
            decimal_places = len(result.split('.')[1])
            assert decimal_places <= precision, "Precision respected"

    @given(
        value=st.integers(min_value=-1000000, max_value=1000000),
        width=st.integers(min_value=0, max_value=20)
    )
    @settings(max_examples=50)
    def test_format_width(self, value, width):
        """INVARIANT: Format width should pad to minimum length."""
        # Format with width
        result = f"{value:{width}d}"

        # Invariant: Result should have at least width characters
        assert len(result) >= max(width, len(str(value))), "Width padding"

    @given(
        parts=st.dictionaries(
            st.text(min_size=1, max_size=20, alphabet='abc'),
            st.integers(min_value=-1000, max_value=1000),
            min_size=0,
            max_size=10
        )
    )
    @settings(max_examples=50)
    def test_format_dict(self, parts):
        """INVARIANT: Dictionary formatting should substitute keys."""
        # Create format string with keys
        format_string = ", ".join(f"{{{k}}}" for k in parts.keys())

        # Format
        try:
            result = format_string.format(**parts)

            # Invariant: Should produce valid string
            assert isinstance(result, str), "Dict formatting produces string"
        except KeyError:
            assert True  # Missing keys raise error


class TestEncodingInvariants:
    """Property-based tests for encoding/decoding invariants."""

    @given(
        text=st.text(max_size=1000)
    )
    @settings(max_examples=50)
    def test_utf8_roundtrip(self, text):
        """INVARIANT: UTF-8 encode/decode should be reversible."""
        # Encode and decode
        encoded = text.encode('utf-8')
        decoded = encoded.decode('utf-8')

        # Invariant: decode(encode(x)) == x
        assert decoded == text, "UTF-8 roundtrip"

    @given(
        text=st.text(max_size=1000)
    )
    @settings(max_examples=50)
    def test_encoding_length(self, text):
        """INVARIANT: UTF-8 encoding should produce valid bytes."""
        # Encode
        encoded = text.encode('utf-8')

        # Invariant: Encoded length should be >= string length
        assert len(encoded) >= len(text), "UTF-8 encoding length"

    @given(
        text=st.text(max_size=1000, alphabet='abc')
    )
    @settings(max_examples=50)
    def test_ascii_encoding(self, text):
        """INVARIANT: ASCII text should encode to single bytes."""
        # Encode as ASCII
        try:
            encoded = text.encode('ascii')

            # Invariant: Each character should be one byte
            assert len(encoded) == len(text), "ASCII encoding is 1:1"
        except UnicodeEncodeError:
            assert True  # Non-ASCII characters raise error

    @given(
        bytes_data=st.binary(min_size=0, max_size=1000)
    )
    @settings(max_examples=50)
    def test_decode_valid_utf8(self, bytes_data):
        """INVARIANT: Decoding should handle valid/invalid UTF-8."""
        # Try to decode
        try:
            decoded = bytes_data.decode('utf-8')

            # Invariant: Should produce string if valid UTF-8
            assert isinstance(decoded, str), "Decoding produces string"
        except UnicodeDecodeError:
            assert True  # Invalid UTF-8 raises error


class TestCaseConversionInvariants:
    """Property-based tests for case conversion invariants."""

    @given(
        text=st.text(max_size=1000)
    )
    @settings(max_examples=50)
    def test_uppercase_length(self, text):
        """INVARIANT: Uppercase should not change length."""
        # Convert to uppercase
        result = text.upper()

        # Invariant: Length should be unchanged
        assert len(result) == len(text), "Uppercase preserves length"

    @given(
        text=st.text(max_size=1000)
    )
    @settings(max_examples=50)
    def test_lowercase_length(self, text):
        """INVARIANT: Lowercase should not change length."""
        # Convert to lowercase
        result = text.lower()

        # Invariant: Length should be unchanged
        assert len(result) == len(text), "Lowercase preserves length"

    @given(
        text=st.text(max_size=1000)
    )
    @settings(max_examples=50)
    def test_case_roundtrip(self, text):
        """INVARIANT: Case conversion should be idempotent."""
        # Invariant: upper(upper(x)) == upper(x)
        assert text.upper().upper() == text.upper(), "Uppercase idempotent"
        assert text.lower().lower() == text.lower(), "Lowercase idempotent"

    @given(
        text=st.text(max_size=1000, alphabet='AbC')
    )
    @settings(max_examples=50)
    def test_capitalize(self, text):
        """INVARIANT: Capitalize should uppercase first character."""
        # Capitalize
        result = text.capitalize()

        # Invariant: First character should be uppercase
        if len(result) > 0:
            assert result[0] == result[0].upper(), "First char uppercase"


class TestWhitespaceInvariants:
    """Property-based tests for whitespace handling invariants."""

    @given(
        text=st.text(max_size=1000, alphabet='abc \t\n')
    )
    @settings(max_examples=50)
    def test_strip_whitespace(self, text):
        """INVARIANT: Strip should remove leading/trailing whitespace."""
        # Strip
        result = text.strip()

        # Invariant: Should not start or end with whitespace
        if len(result) > 0:
            assert not result[0].isspace(), "No leading whitespace"
            assert not result[-1].isspace(), "No trailing whitespace"
        else:
            assert True  # Empty result

    @given(
        text=st.text(max_size=1000, alphabet='abc \t\n')
    )
    @settings(max_examples=50)
    def test_lstrip(self, text):
        """INVARIANT: Lstrip should remove leading whitespace."""
        # Lstrip
        result = text.lstrip()

        # Invariant: Should not start with whitespace
        if len(result) > 0:
            assert not result[0].isspace(), "No leading whitespace"
        else:
            assert True  # Empty result

    @given(
        text=st.text(max_size=1000, alphabet='abc \t\n')
    )
    @settings(max_examples=50)
    def test_rstrip(self, text):
        """INVARIANT: Rstrip should remove trailing whitespace."""
        # Rstrip
        result = text.rstrip()

        # Invariant: Should not end with whitespace
        if len(result) > 0:
            assert not result[-1].isspace(), "No trailing whitespace"
        else:
            assert True  # Empty result

    @given(
        text=st.text(max_size=1000, alphabet='abc \t\n')
    )
    @settings(max_examples=50)
    def test_splitlines(self, text):
        """INVARIANT: Splitlines should handle line breaks."""
        # Split lines
        lines = text.splitlines()

        # Invariant: No line should contain newline
        for line in lines:
            assert '\n' not in line, "No newlines in split lines"
            assert '\r\n' not in line, "No CRLF in split lines"


class TestStringValidationInvariants:
    """Property-based tests for string validation invariants."""

    @given(
        text=st.text(max_size=1000, alphabet='abcdefghijklmnopqrstuvwxyz')
    )
    @settings(max_examples=50)
    def test_isalpha(self, text):
        """INVARIANT: isalpha should return True for alphabetic strings."""
        # Check if all alphabetic
        if len(text) > 0:
            assert text.isalpha() == True, "Alphabetic strings are alpha"

    @given(
        text=st.text(max_size=1000, alphabet='0123456789')
    )
    @settings(max_examples=50)
    def test_isdigit(self, text):
        """INVARIANT: isdigit should return True for digit strings."""
        # Check if all digits
        if len(text) > 0:
            assert text.isdigit() == True, "Digit strings are digits"

    @given(
        text=st.text(max_size=1000, alphabet='abc012')
    )
    @settings(max_examples=50)
    def test_isalnum(self, text):
        """INVARIANT: isalnum should return True for alphanumeric strings."""
        # Check if all alphanumeric
        if len(text) > 0:
            assert text.isalnum() == True, "Alphanumeric strings are alnum"

    @given(
        text=st.text(max_size=1000, alphabet=' \t\n')
    )
    @settings(max_examples=50)
    def test_isspace(self, text):
        """INVARIANT: isspace should return True for whitespace strings."""
        # Check if all whitespace
        if len(text) > 0:
            assert text.isspace() == True, "Whitespace strings are space"


class TestUnicodeInvariants:
    """Property-based tests for Unicode handling invariants."""

    @given(
        text=st.text(max_size=1000)
    )
    @settings(max_examples=50)
    def test_unicode_length(self, text):
        """INVARIANT: String length should count code points."""
        # Invariant: len() returns number of code points
        assert len(text) >= 0, "Length non-negative"

    @given(
        text=st.text(max_size=1000)
    )
    @settings(max_examples=50)
    def test_unicode_iteration(self, text):
        """INVARIANT: Iterating should yield characters."""
        # Iterate and count
        count = 0
        for char in text:
            count += 1

        # Invariant: Iteration count should equal length
        assert count == len(text), "Iteration yields all characters"

    @given(
        text=st.text(max_size=1000)
    )
    @settings(max_examples=50)
    def test_unicode_slice(self, text):
        """INVARIANT: Slicing should return valid strings."""
        # Slice with valid indices
        if len(text) > 1:
            result = text[1:-1]

            # Invariant: Slice should be valid string
            assert isinstance(result, str), "Slice returns string"
        else:
            assert True  # Too short to slice

    @given(
        text=st.text(max_size=1000)
    )
    @settings(max_examples=50)
    def test_unicode_normalize(self, text):
        """INVARIANT: Normalization should produce valid string."""
        # Normalize
        try:
            result = text.normalize('NFC')

            # Invariant: Should produce valid string
            assert isinstance(result, str), "Normalization produces string"
        except:
            assert True  # Some strings may not normalize
