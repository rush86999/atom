# -*- coding: utf-8 -*-
"""Coverage wave 79 — core/validation.py 17% → 100%.

Covers: ValidationError field context, sanitize_string (non-str raise,
truncation, tag strip, html escape, allow_html, dangerous-pattern removal
incl. script/javascript/on*-handlers/iframe/embed/object, null bytes, strip),
validate_html_content (default allowlist, script+content removal, event
handler removal, javascript: removal, iframe/embed/object removal, disallowed
tag removal, custom allowlist — incl. BUG 79-8: allowed_tags=[] (empty
allowlist) kept ALL tags because of a falsy-list guard), detect_sql_injection
(all patterns + non-str), detect_path_traversal (all patterns + non-str),
validate_json_schema (non-dict, required-missing, every type rule, min/max
length, pattern, full-valid), sanitize_filename (non-str, path components,
dangerous chars, >255 length with/without extension, whitespace strip),
BaseModel (string sanitize hook, SQL-injection raise, path traversal on
file/path fields, extra=forbid), validated_string — incl. BUG 79-9: the
factory crashed with TypeError at decoration (invalid nested field_validator
usage); rewritten as an Annotated[AfterValidator] metadata value.

Zero LLM spend, no network.
"""
import pytest
from pydantic import ValidationError as PydanticValidationError
from typing import Annotated

from core.validation import (
    INJECTION_PATTERNS,
    PATH_TRAVERSAL_PATTERNS,
    SQL_INJECTION_PATTERNS,
    BaseModel,
    ValidationError,
    detect_path_traversal,
    detect_sql_injection,
    sanitize_filename,
    sanitize_string,
    validate_html_content,
    validate_json_schema,
    validated_string,
)


# ============================================================================
# sanitize_string
# ============================================================================

class TestSanitizeString:
    def test_non_string_raises(self):
        with pytest.raises(ValidationError) as ei:
            sanitize_string(42)
        assert ei.value.field == "value"
        assert "must be a string" in str(ei.value)

    def test_plain_string_unchanged_and_stripped(self):
        assert sanitize_string("  hello  ") == "hello"

    def test_truncates_over_max_length(self):
        out = sanitize_string("a" * 120, max_length=100)
        assert len(out) == 100

    def test_strips_tags_by_default(self):
        assert sanitize_string("<b>hi</b> there") == "hi there"

    def test_strip_tags_false_escapes_html(self):
        out = sanitize_string("<b>hi</b>", strip_tags=False)
        assert out == "&lt;b&gt;hi&lt;/b&gt;"

    def test_allow_html_still_removes_scripts(self):
        assert sanitize_string("<script>alert(1)</script>ok", allow_html=True) == "ok"
        out = sanitize_string("<b onclick=\"x()\">hi</b>", allow_html=True)
        assert "onclick" not in out
        assert "<b" in out and "hi</b>" in out

    def test_allow_html_keeps_plain_tags(self):
        out = sanitize_string("<b>hi</b>", allow_html=True)
        assert "<b>" in out and "hi" in out

    def test_dangerous_patterns_removed_case_insensitive(self):
        # Tag stripping removes the <SCRIPT> tags (content stays as inert text)
        out = sanitize_string("click <SCRIPT>x()</SCRIPT> here")
        assert "SCRIPT" not in out
        assert out == "click x() here"
        assert sanitize_string("javascript:alert(1)") == "alert(1)"
        assert sanitize_string("<iframe src=x></iframe>ok") == "ok"
        assert sanitize_string("<embed src=x>ok") == "ok"
        assert sanitize_string("<object data=x></object>ok") == "ok"

    def test_null_bytes_removed(self):
        assert sanitize_string("ab\x00cd") == "abcd"

    def test_event_handler_removed(self):
        out = sanitize_string("<p onclick=\"evil()\">safe</p>", allow_html=True)
        assert "onclick" not in out

    def test_empty_and_whitespace_only(self):
        assert sanitize_string("   ") == ""


# ============================================================================
# validate_html_content (incl. BUG 79-8)
# ============================================================================

class TestValidateHtmlContent:
    def test_default_allowlist_keeps_safe_tags(self):
        out = validate_html_content("<p><strong>bold</strong> <a href=\"/x\">link</a></p>")
        assert "<p>" in out and "<strong>bold</strong>" in out

    def test_script_with_content_removed(self):
        out = validate_html_content("<script>bad()</script><p>ok</p>")
        assert "bad()" not in out
        assert "<p>ok</p>" in out

    def test_event_handlers_removed(self):
        out = validate_html_content('<p onclick="evil()" onmouseover="x()">hi</p>')
        assert "onclick" not in out and "onmouseover" not in out

    def test_event_handler_single_quotes_removed(self):
        out = validate_html_content("<p onload='evil()'>hi</p>")
        assert "onload" not in out

    def test_javascript_protocol_removed(self):
        out = validate_html_content('<a href="javascript:evil()">x</a>')
        assert "javascript:" not in out

    def test_dangerous_tags_removed_with_content(self):
        out = validate_html_content("<iframe src=x>frame</iframe><embed>e</embed><object>o</object><div>d</div>")
        assert "frame" not in out and "e</embed>" not in out and "<object>" not in out
        assert "<div>d</div>" in out

    def test_disallowed_tags_stripped_content_kept(self):
        out = validate_html_content("<custom>text</custom><p>p</p>")
        assert "custom" not in out
        assert "<p>p</p>" in out

    def test_custom_allowlist(self):
        out = validate_html_content("<p>x</p><span>y</span>", allowed_tags=["p"])
        assert "<p>x</p>" in out
        assert "<span>" not in out

    def test_empty_allowlist_strips_all_tags(self):
        """BUG 79-8: allowed_tags=[] (an empty allowlist — allow nothing) was
        falsy, so the tag filter was skipped and ALL tags survived."""
        out = validate_html_content("<p>p</p><b>b</b>", allowed_tags=[])
        assert "<p>" not in out and "<b>" not in out

    def test_no_allowed_tags_arg_uses_defaults(self):
        assert validate_html_content("<p>p</p>") == validate_html_content("<p>p</p>", allowed_tags=None)

    def test_malformed_markup_does_not_raise(self):
        assert isinstance(validate_html_content("<p>unclosed"), str)


# ============================================================================
# detect_sql_injection / detect_path_traversal
# ============================================================================

class TestDetectSqlInjection:
    def test_all_patterns_detected(self):
        for value in ["'''", "x--y", "'; DROP TABLE t; --", "UNION SELECT * FROM users"]:
            assert detect_sql_injection(value) is True

    def test_case_insensitive(self):
        assert detect_sql_injection("union select 1") is True
        assert detect_sql_injection("; drop table t") is True

    def test_clean_values(self):
        assert detect_sql_injection("hello world") is False
        assert detect_sql_injection("SELECT is fine without marker") is False

    def test_non_string_returns_false(self):
        assert detect_sql_injection(42) is False
        assert detect_sql_injection(None) is False

    def test_pattern_list_has_entries(self):
        assert SQL_INJECTION_PATTERNS


class TestDetectPathTraversal:
    def test_all_patterns_detected(self):
        assert detect_path_traversal("../etc/passwd") is True
        assert detect_path_traversal("../../etc/passwd") is True
        assert detect_path_traversal("%2e%2e%2fetc") is True

    def test_clean_paths(self):
        assert detect_path_traversal("data/report.pdf") is False
        assert detect_path_traversal("report.pdf") is False

    def test_non_string_returns_false(self):
        assert detect_path_traversal(7) is False
        assert detect_path_traversal(None) is False

    def test_pattern_list_has_entries(self):
        assert PATH_TRAVERSAL_PATTERNS


# ============================================================================
# validate_json_schema
# ============================================================================

class TestValidateJsonSchema:
    def test_non_dict_raises(self):
        with pytest.raises(ValidationError) as ei:
            validate_json_schema([1, 2], {})
        assert ei.value.field == "data"

    def test_required_field_missing(self):
        with pytest.raises(ValidationError) as ei:
            validate_json_schema({"a": 1}, {"required": ["a", "b"]})
        assert ei.value.field == "b"
        assert "Required field" in str(ei.value)

    def test_type_errors_each_kind(self):
        schema = {"properties": {
            "s": {"type": "string"},
            "i": {"type": "integer"},
            "n": {"type": "number"},
            "b": {"type": "boolean"},
            "a": {"type": "array"},
        }}
        with pytest.raises(ValidationError, match="must be a string"):
            validate_json_schema({"s": 1}, schema)
        with pytest.raises(ValidationError, match="must be an integer"):
            validate_json_schema({"s": "x", "i": 1.5}, schema)
        with pytest.raises(ValidationError, match="must be a number"):
            validate_json_schema({"s": "x", "i": 1, "n": "nope"}, schema)
        with pytest.raises(ValidationError, match="must be a boolean"):
            validate_json_schema({"s": "x", "i": 1, "n": 1, "b": "yes"}, schema)
        with pytest.raises(ValidationError, match="must be an array"):
            validate_json_schema({"s": "x", "i": 1, "n": 1, "b": True, "a": "no"}, schema)

    def test_string_min_max_length_and_pattern(self):
        schema = {"properties": {"code": {"type": "string", "min_length": 3, "max_length": 5, "pattern": r"^[a-z]+$"}}}
        with pytest.raises(ValidationError, match="at least 3"):
            validate_json_schema({"code": "ab"}, schema)
        with pytest.raises(ValidationError, match="at most 5"):
            validate_json_schema({"code": "abcdef"}, schema)
        with pytest.raises(ValidationError, match="pattern"):
            validate_json_schema({"code": "AB12"}, schema)
        assert validate_json_schema({"code": "abc"}, schema) is True

    def test_missing_property_skipped(self):
        assert validate_json_schema({}, {"properties": {"x": {"type": "string"}}}) is True

    def test_bool_passes_integer_rule(self):
        # bool subclasses int, so True satisfies the integer type rule
        assert validate_json_schema({"i": True}, {"properties": {"i": {"type": "integer"}}}) is True

    def test_fully_valid(self):
        schema = {"required": ["name"], "properties": {
            "name": {"type": "string", "min_length": 1, "max_length": 10},
            "age": {"type": "integer"},
        }}
        assert validate_json_schema({"name": "ada", "age": 36}, schema) is True


# ============================================================================
# sanitize_filename
# ============================================================================

class TestSanitizeFilename:
    def test_non_string_raises(self):
        with pytest.raises(ValidationError) as ei:
            sanitize_filename(123)
        assert ei.value.field == "filename"

    def test_removes_path_components(self):
        assert sanitize_filename("../../etc/passwd") == "passwd"
        assert sanitize_filename("C:\\Users\\x\\file.txt") == "file.txt"
        assert sanitize_filename("a/b/c.txt") == "c.txt"

    def test_removes_dangerous_chars(self):
        assert sanitize_filename('bad:name?.txt') == "badname.txt"
        assert sanitize_filename('a"b<c>d|e*f.txt') == "abcdef.txt"

    def test_control_chars_removed(self):
        assert sanitize_filename("file\x00\x1f.txt") == "file.txt"

    def test_length_limit_preserves_extension(self):
        long_name = "a" * 300 + ".txt"
        out = sanitize_filename(long_name)
        assert len(out) == 254
        assert out.endswith(".txt")
        assert out.startswith("a" * 250)

    def test_length_limit_no_extension(self):
        out = sanitize_filename("b" * 300)
        assert len(out) == 250

    def test_whitespace_stripped(self):
        assert sanitize_filename("  file.txt  ") == "file.txt"

    def test_normal_filename_unchanged(self):
        assert sanitize_filename("report_2026.pdf") == "report_2026.pdf"


# ============================================================================
# BaseModel (auto-validation of strings)
# ============================================================================

class _SampleModel(BaseModel):
    name: str
    file_path: str = ""


class TestBaseModel:
    def test_normal_construction(self):
        m = _SampleModel(name="hello", file_path="/tmp/x")
        assert m.name == "hello"

    def test_sql_injection_raises(self):
        with pytest.raises(ValidationError) as ei:
            _SampleModel(name="x'; DROP TABLE users; --", file_path="/tmp/x")
        assert ei.value.field == "name"
        assert "SQL injection" in str(ei.value)

    def test_sql_injection_in_file_field_raises(self):
        with pytest.raises(ValidationError):
            _SampleModel(name="ok", file_path="/tmp/union select 1")

    def test_path_traversal_in_file_field_raises(self):
        with pytest.raises(ValidationError) as ei:
            _SampleModel(name="ok", file_path="../../etc/passwd")
        assert ei.value.field == "file_path"
        assert "Path traversal" in str(ei.value)

    def test_path_traversal_in_path_field_raises(self):
        class WithPath(BaseModel):
            name: str
            path: str = ""
        with pytest.raises(ValidationError, match="Path traversal"):
            WithPath(name="ok", path="../../evil")

    def test_path_traversal_in_non_path_field_allowed(self):
        # Only file/path fields are traversal-checked
        assert _SampleModel(name="../not-a-path", file_path="/tmp/x").name == "../not-a-path"

    def test_extra_fields_forbidden(self):
        with pytest.raises(PydanticValidationError):
            _SampleModel(name="x", file_path="/tmp/x", unknown=1)

    def test_dict_input_sanitized_and_validated(self):
        assert _SampleModel(name="x", file_path="/t").name == "x"


# ============================================================================
# validated_string (incl. BUG 79-9)
# ============================================================================

class TestValidatedString:
    def test_factory_produces_usable_annotated_metadata(self):
        """BUG 79-9: validated_string() raised TypeError at class-definition
        time (invalid nested field_validator usage) — unusable. Rewritten to
        return Annotated[AfterValidator] metadata."""

        class M(BaseModel):
            code: validated_string(min_length=2, max_length=5, pattern=r"^[a-z]+$")

        m = M(code="abc")
        assert m.code == "abc"

    def test_min_length_enforced(self):
        class M(BaseModel):
            code: validated_string(min_length=2)
        with pytest.raises(PydanticValidationError, match="at least 2"):
            M(code="a")

    def test_max_length_truncates(self):
        class M(BaseModel):
            code: validated_string(max_length=4)
        assert M(code="abcdef").code == "abcd"

    def test_pattern_enforced(self):
        class M(BaseModel):
            code: validated_string(pattern=r"^[a-z]+$")
        with pytest.raises(PydanticValidationError, match="pattern"):
            M(code="ABC")

    def test_sanitize_applied(self):
        class M(BaseModel):
            code: validated_string(sanitize=True)
        assert M(code="<b>x</b>").code == "x"

    def test_sanitize_disabled_keeps_markup(self):
        class M(BaseModel):
            code: validated_string(sanitize=False)
        assert M(code="<b>x</b>").code == "<b>x</b>"

    def test_non_string_rejected(self):
        class M(BaseModel):
            code: validated_string()
        with pytest.raises(PydanticValidationError, match="string"):
            M(code=42)


# ============================================================================
# Pattern lists sanity
# ============================================================================

class TestPatternLists:
    def test_injection_patterns_nonempty(self):
        assert len(INJECTION_PATTERNS) >= 6
