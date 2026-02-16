"""
Tests for SkillParser - lenient SKILL.md parsing with auto-fix.

Tests cover:
- Valid skill parsing with YAML frontmatter
- Auto-fix for missing required fields (name, description)
- Skill type detection (prompt_only vs python_code)
- Python code extraction from markdown body
- Function signature extraction using AST
- Malformed YAML handling (graceful degradation)
"""

import tempfile
from pathlib import Path

import pytest

from core.skill_parser import SkillParser


@pytest.fixture
def parser():
    """Create SkillParser instance for testing."""
    return SkillParser()


@pytest.fixture
def valid_skill_file(tmp_path):
    """Create a valid SKILL.md file with YAML frontmatter."""
    content = """---
name: Test Skill
description: A test skill for parsing
version: 1.0.0
author: Test Author
---

# Test Skill

This is a test skill for parsing.

## Instructions

Use this skill to test parsing.
"""
    file_path = tmp_path / "SKILL.md"
    file_path.write_text(content)
    return str(file_path)


@pytest.fixture
def python_skill_file(tmp_path):
    """Create a SKILL.md file with Python code."""
    content = """---
name: Python Skill
description: A skill with Python code
---

# Python Skill

This skill contains Python code.

```python
def execute_search(query: str, limit: int = 10):
    '''Search the web and return results.'''
    pass

def main():
    print("Hello from skill")
```
"""
    file_path = tmp_path / "python_skill.md"
    file_path.write_text(content)
    return str(file_path)


@pytest.fixture
def missing_name_file(tmp_path):
    """Create a SKILL.md file with missing name field."""
    content = """---
description: A skill without name
---

# Untitled Skill

This skill has no name in frontmatter.
"""
    file_path = tmp_path / "no_name.md"
    file_path.write_text(content)
    return str(file_path)


@pytest.fixture
def missing_description_file(tmp_path):
    """Create a SKILL.md file with missing description field."""
    content = """---
name: My Skill
---

# My Skill

This is the first line of the body.
"""
    file_path = tmp_path / "no_desc.md"
    file_path.write_text(content)
    return str(file_path)


@pytest.fixture
def malformed_yaml_file(tmp_path):
    """Create a SKILL.md file with malformed YAML."""
    content = """---
name: Bad YAML
description: This YAML is malformed
    invalid indentation: [
---

# Bad YAML

This file has malformed frontmatter.
"""
    file_path = tmp_path / "bad_yaml.md"
    file_path.write_text(content)
    return str(file_path)


class TestSkillParserBasics:
    """Test basic SkillParser functionality."""

    def test_parser_initialization(self, parser):
        """Test that parser initializes successfully."""
        assert parser is not None
        assert hasattr(parser, 'parse_skill_file')
        assert hasattr(parser, '_auto_fix_metadata')
        assert hasattr(parser, '_detect_skill_type')

    def test_parse_valid_skill_with_frontmatter(self, parser, valid_skill_file):
        """Test successful parse of valid SKILL.md file."""
        metadata, body = parser.parse_skill_file(valid_skill_file)

        assert metadata is not None
        assert metadata['name'] == 'Test Skill'
        assert metadata['description'] == 'A test skill for parsing'
        assert metadata['version'] == '1.0.0'
        assert metadata['author'] == 'Test Author'
        assert 'Test Skill' in body
        assert 'This is a test skill' in body


class TestAutoFix:
    """Test auto-fix behavior for missing required fields."""

    def test_parse_missing_name_auto_fixes(self, parser, missing_name_file):
        """Test that missing name defaults to 'Unnamed Skill'."""
        metadata, body = parser.parse_skill_file(missing_name_file)

        assert metadata['name'] == 'Unnamed Skill'
        assert metadata['description'] == 'A skill without name'

    def test_parse_missing_description_autogenerates(self, parser, missing_description_file):
        """Test that missing description is auto-generated from first line."""
        metadata, body = parser.parse_skill_file(missing_description_file)

        assert metadata['name'] == 'My Skill'
        # Description strips # headers
        assert 'My Skill' in metadata['description']

    def test_missing_description_truncates_to_100_chars(self, parser, tmp_path):
        """Test that auto-generated description is truncated to 100 chars."""
        long_first_line = "A" * 200
        content = f"""---
name: Long Description Skill
---

{long_first_line}

More content here.
"""
        file_path = tmp_path / "long_desc.md"
        file_path.write_text(content)

        metadata, body = parser.parse_skill_file(str(file_path))

        assert len(metadata['description']) <= 100
        assert metadata['description'] == "A" * 100


class TestSkillTypeDetection:
    """Test skill type detection (prompt_only vs python_code)."""

    def test_detect_python_code_skill(self, parser, python_skill_file):
        """Test detection of python_code skill type."""
        metadata, body = parser.parse_skill_file(python_skill_file)

        assert metadata['skill_type'] == 'python_code'

    def test_detect_prompt_only_skill(self, parser, valid_skill_file):
        """Test that skills without Python code default to prompt_only."""
        metadata, body = parser.parse_skill_file(valid_skill_file)

        assert metadata['skill_type'] == 'prompt_only'

    def test_detect_python_case_insensitive(self, parser, tmp_path):
        """Test that ```Python is also detected (case insensitive)."""
        content = """---
name: Case Test
---

# Test

```Python
print("hello")
```
"""
        file_path = tmp_path / "case_test.md"
        file_path.write_text(content)

        metadata, body = parser.parse_skill_file(str(file_path))

        assert metadata['skill_type'] == 'python_code'


class TestPythonCodeExtraction:
    """Test Python code block extraction."""

    def test_extract_python_code_single_block(self, parser, python_skill_file):
        """Test extraction of single Python code block."""
        _, body = parser.parse_skill_file(python_skill_file)
        code_blocks = parser.extract_python_code(body)

        assert len(code_blocks) == 1
        assert 'def execute_search' in code_blocks[0]
        assert 'def main' in code_blocks[0]

    def test_extract_python_code_multiple_blocks(self, parser, tmp_path):
        """Test extraction of multiple Python code blocks."""
        content = """---
name: Multi Block
---

# First Block

```python
def first():
    pass
```

# Second Block

```python
def second():
    pass
```
"""
        file_path = tmp_path / "multi_block.md"
        file_path.write_text(content)

        _, body = parser.parse_skill_file(str(file_path))
        code_blocks = parser.extract_python_code(body)

        assert len(code_blocks) == 2
        assert 'def first' in code_blocks[0]
        assert 'def second' in code_blocks[1]

    def test_extract_function_signatures(self, parser):
        """Test extraction of function signatures from Python code."""
        code = """
def execute_search(query: str, limit: int = 10):
    '''Search the web and return results.'''
    pass

def main():
    '''Main entry point.'''
    print("Hello")
"""
        signatures = parser.extract_function_signatures(code)

        assert len(signatures) == 2

        # Check execute_search
        exec_search = next(s for s in signatures if s['name'] == 'execute_search')
        assert exec_search['args'] == ['query', 'limit']
        assert 'Search the web' in exec_search['docstring']

        # Check main
        main_func = next(s for s in signatures if s['name'] == 'main')
        assert main_func['args'] == []
        assert 'Main entry point' in main_func['docstring']


class TestErrorHandling:
    """Test error handling and graceful degradation."""

    def test_malformed_yaml_skips_gracefully(self, parser, malformed_yaml_file):
        """Test that malformed YAML doesn't crash parser."""
        # Should not raise exception
        metadata, body = parser.parse_skill_file(malformed_yaml_file)

        # Should return minimal valid metadata
        assert metadata is not None
        assert 'name' in metadata

    def test_nonexistent_file_returns_empty_metadata(self, parser):
        """Test that nonexistent file returns minimal metadata."""
        metadata, body = parser.parse_skill_file('/nonexistent/file.md')

        assert metadata['name'] == 'Unnamed Skill'
        assert body == ""

    def test_invalid_python_syntax_returns_empty_list(self, parser):
        """Test that invalid Python syntax is handled gracefully."""
        invalid_code = "def foo(\n"  # Incomplete function

        signatures = parser.extract_function_signatures(invalid_code)

        assert signatures == []


class TestBatchParsing:
    """Test batch parsing functionality."""

    def test_parse_batch_multiple_files(self, parser, valid_skill_file, python_skill_file):
        """Test parsing multiple files in batch."""
        result = parser.parse_batch([valid_skill_file, python_skill_file])

        assert result['success_count'] == 2
        assert result['failure_count'] == 0
        assert len(result['skills']) == 2
        assert len(result['errors']) == 0

    def test_parse_batch_with_failures(self, parser, valid_skill_file, malformed_yaml_file):
        """Test batch parsing with some failures."""
        result = parser.parse_batch([valid_skill_file, malformed_yaml_file])

        # Should have at least one success (valid_skill_file)
        assert result['success_count'] >= 1
        # May have failures depending on how malformed_yaml_file is handled
        assert isinstance(result['failure_count'], int)
        assert len(result['skills']) == result['success_count']
