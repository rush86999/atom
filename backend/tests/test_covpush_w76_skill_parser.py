# -*- coding: utf-8 -*-
"""Coverage wave 76 — core/skill_parser (SkillParser).

Pure-Python parser (no DB, no network). Covers the previously-missing lines:
189 (_auto_fix_metadata empty-body fallback), 214-217 / 256-259 (non-list
packages/node_packages normalization), 222-227 / 264-267 (invalid package
filtering), 288-309 (_validate_npm_package_format full matrix incl. scoped
packages), 327-331 (invalid package_manager -> npm), 353 (metadata-driven
python_code detection), 392-393 (unclosed ```python block), 449-451
(parse_batch per-file exception collection).
"""
from unittest.mock import patch

import pytest

from core.skill_parser import SkillParser

parser = SkillParser()


# ============================================================================
# parse_skill_file & auto-fix
# ============================================================================

class TestParseFile:
    def test_parse_valid_skill_with_frontmatter(self, tmp_path):
        path = tmp_path / "SKILL.md"
        path.write_text(
            "---\n"
            "name: My Skill\n"
            "description: Does things\n"
            "type: python\n"
            "---\n"
            "# My Skill\nbody here\n"
        )
        metadata, body = parser.parse_skill_file(str(path))
        assert metadata["name"] == "My Skill"
        assert metadata["description"] == "Does things"
        assert metadata["packages"] == []
        assert metadata["node_packages"] == []
        assert metadata["package_manager"] == "npm"
        assert metadata["skill_type"] == "python_code"
        assert "body here" in body

    def test_parse_missing_file_returns_minimal(self, tmp_path):
        metadata, body = parser.parse_skill_file(str(tmp_path / "nope.md"))
        assert metadata["name"] == "Unnamed Skill"
        assert body == ""

    def test_parse_malformed_frontmatter_returns_minimal(self, tmp_path):
        path = tmp_path / "SKILL.md"
        path.write_text("---\nname: [unclosed\n---\nbody\n")
        metadata, _ = parser.parse_skill_file(str(path))
        assert metadata["name"] == "Unnamed Skill"
        assert metadata["skill_type"] == "prompt_only"

    def test_auto_fix_missing_name(self, tmp_path):
        path = tmp_path / "SKILL.md"
        path.write_text("# Title\ncontent\n")
        metadata, _ = parser.parse_skill_file(str(path))
        assert metadata["name"] == "Unnamed Skill"
        assert metadata["description"] == "Title"

    def test_auto_fix_empty_body_uses_fallback_description(self, tmp_path):
        path = tmp_path / "SKILL.md"
        path.write_text("---\nname: X\n---\n")
        metadata, _ = parser.parse_skill_file(str(path))
        assert metadata["description"] == "No description available"

    def test_auto_fix_description_truncates_at_100_chars(self, tmp_path):
        path = tmp_path / "SKILL.md"
        long_line = "x" * 250
        path.write_text(f"---\nname: X\n---\n{long_line}\n")
        metadata, _ = parser.parse_skill_file(str(path))
        assert len(metadata["description"]) == 100


# ============================================================================
# Package extraction
# ============================================================================

class TestPackageExtraction:
    def test_extract_packages_filters_invalid_requirements(self):
        metadata = {"packages": ["numpy==1.21.0", "pandas>=1.3.0", "!!bad name!!"]}
        assert parser._extract_packages(metadata, "SKILL.md") == \
            ["numpy==1.21.0", "pandas>=1.3.0"]

    def test_extract_packages_non_list_normalized_to_empty(self):
        assert parser._extract_packages({"packages": "numpy"}, "SKILL.md") == []

    def test_extract_packages_missing_key(self):
        assert parser._extract_packages({}, "SKILL.md") == []

    def test_extract_node_packages_filters_invalid(self):
        metadata = {"node_packages": ["lodash@4.17.21", "!!bad!!"]}
        assert parser._extract_node_packages(metadata, "SKILL.md") == \
            ["lodash@4.17.21"]

    def test_extract_node_packages_non_list_normalized(self):
        assert parser._extract_node_packages(
            {"node_packages": "lodash"}, "SKILL.md") == []

    def test_extract_package_manager_valid_values(self):
        for mgr in ("npm", "yarn", "pnpm"):
            assert parser._extract_package_manager(
                {"package_manager": mgr}, "SKILL.md") == mgr

    def test_extract_package_manager_invalid_defaults_to_npm(self):
        assert parser._extract_package_manager(
            {"package_manager": "bower"}, "SKILL.md") == "npm"

    def test_extract_package_manager_missing_defaults_to_npm(self):
        assert parser._extract_package_manager({}, "SKILL.md") == "npm"


class TestValidateNpmFormat:
    def test_none_or_non_string_rejected(self):
        assert parser._validate_npm_package_format(None) is False
        assert parser._validate_npm_package_format(42) is False

    def test_empty_and_whitespace_rejected(self):
        assert parser._validate_npm_package_format("") is False
        assert parser._validate_npm_package_format("   ") is False

    def test_plain_name_accepted(self):
        assert parser._validate_npm_package_format("lodash") is True

    def test_name_with_version_range_accepted(self):
        assert parser._validate_npm_package_format("express@^4.18.0") is True
        assert parser._validate_npm_package_format("pkg@>=1.2.3") is True
        assert parser._validate_npm_package_format("pkg@<2.0.0") is True

    def test_scoped_package_without_version_rejected(self):
        # "@scope/name" has no second @ -> invalid per current rules
        assert parser._validate_npm_package_format("@scope/name") is False

    def test_scoped_package_with_version_accepted(self):
        assert parser._validate_npm_package_format("@scope/name@1.0.0") is True

    def test_lone_at_sign_rejected(self):
        assert parser._validate_npm_package_format("@") is False

    def test_invalid_characters_rejected(self):
        assert parser._validate_npm_package_format("bad name!") is False
        assert parser._validate_npm_package_format("pkg;rm") is False


# ============================================================================
# Skill type detection & code extraction
# ============================================================================

class TestSkillTypeAndCode:
    def test_detect_python_via_body_fence_case_insensitive(self):
        assert parser._detect_skill_type({}, "text\n```PYTHON\nx=1\n```\n") == \
            "python_code"

    def test_detect_python_via_metadata_type(self):
        assert parser._detect_skill_type({"type": "python"}, "text") == \
            "python_code"

    def test_detect_python_via_metadata_language(self):
        assert parser._detect_skill_type({"language": "python"}, "text") == \
            "python_code"

    def test_detect_prompt_only_default(self):
        assert parser._detect_skill_type({}, "just instructions") == \
            "prompt_only"

    def test_extract_python_code_multiple_blocks_and_unclosed(self):
        body = (
            "```python\na = 1\n```\n"
            "text\n"
            "``` Python\nb = 2\n"  # alternate fence + never closed
        )
        blocks = parser.extract_python_code(body)
        assert blocks[0] == "a = 1"
        assert blocks[1].strip() == "b = 2"  # unclosed block treated as complete

    def test_extract_python_code_no_blocks(self):
        assert parser.extract_python_code("no code here") == []

    def test_extract_function_signatures_ast(self):
        code = (
            "def foo(a, b=1):\n"
            '    """Doc here."""\n'
            "    return a + b\n\n"
            "async def bar(*args, **kwargs):\n"
            "    pass\n"
        )
        sigs = parser.extract_function_signatures(code)
        assert sigs[0] == {"name": "foo", "args": ["a", "b"],
                           "docstring": "Doc here."}
        # note: async def is ast.AsyncFunctionDef, so only `foo` is extracted
        assert len(sigs) == 1
        assert sigs[0]["name"] == "foo"

    def test_extract_function_signatures_invalid_syntax(self):
        assert parser.extract_function_signatures("def broken(:") == []

    def test_parse_batch_counts_success_and_failure(self, tmp_path):
        good = tmp_path / "good.md"
        good.write_text("---\nname: Good\n---\nbody\n")
        missing = tmp_path / "missing.md"
        result = parser.parse_batch([str(good), str(missing)])
        # parse_skill_file degrades gracefully (minimal metadata) instead of
        # raising, so both paths count as successes in the batch summary.
        assert result["success_count"] == 2
        assert result["failure_count"] == 0
        assert len(result["skills"]) == 2
        assert result["errors"] == []

    def test_parse_batch_unexpected_exception_collected(self, tmp_path):
        good = tmp_path / "good.md"
        good.write_text("---\nname: Good\n---\nbody\n")
        with patch.object(parser, "parse_skill_file",
                          side_effect=RuntimeError("boom")):
            result = parser.parse_batch([str(good)])
        assert result["success_count"] == 0
        assert result["failure_count"] == 1
        assert "boom" in result["errors"][0]

    def test_parse_batch_empty_input(self):
        result = parser.parse_batch([])
        assert result == {"skills": [], "success_count": 0,
                          "failure_count": 0, "errors": []}
