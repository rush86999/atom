# -*- coding: utf-8 -*-
"""Coverage wave 83 — core/openclaw_parser.py to >=95% (pure parsing logic;
frontmatter parsing real for well-formed docs, patched for malformed YAML;
zero LLM spend, zero network).

Covers:
- parse_skill_md: happy path (all metadata fields), missing required fields,
  malformed frontmatter → ValueError, non-dict metadata values.
- _extract_python_blocks: found / none / CRLF content.
- validate_python_syntax: valid, SyntaxError with line info.
- extract_npm_dependencies: ES6 imports (named/default/namespace/side-effect),
  relative import filtering, require() calls, scoped packages, package.json
  dependencies block, non-package.json content.
- _extract_dependencies: requirements list (str/int filtering), node_packages,
  openclaw metadata install (uv/npm/bins), non-dict metadata, non-list install,
  non-dict steps.
"""
import pytest
from unittest.mock import patch

from core.openclaw_parser import OpenClawParser

parser = OpenClawParser()

SKILL_TEMPLATE = """---
name: my-skill
description: Does something cool
author: @dev
version: 2.1.0
homepage: https://example.com
---

# Body
```python
def greet():
    return "hi"
```
"""


# ============================================================================
# parse_skill_md
# ============================================================================

def test_parse_skill_md_happy_path():
    result = parser.parse_skill_md(SKILL_TEMPLATE)
    assert result["name"] == "my-skill"
    assert result["description"] == "Does something cool"
    assert result["author"] == "@dev"
    assert result["version"] == "2.1.0"
    assert result["homepage"] == "https://example.com"
    assert result["body"].startswith("# Body")
    assert result["code_blocks"] == ['def greet():\n    return "hi"\n']
    assert result["dependencies"] == {"python": [], "npm": [], "bins": []}
    assert result["raw_md"] == SKILL_TEMPLATE
    assert isinstance(result["metadata"], dict)


def test_parse_skill_md_defaults_for_optional_fields():
    content = "---\nname: n\ndescription: d\n---\nbody"
    result = parser.parse_skill_md(content)
    assert result["author"] == "Unknown"
    assert result["version"] == "1.0.0"
    assert result["homepage"] is None


def test_parse_skill_md_missing_required_fields():
    with pytest.raises(ValueError) as exc:
        parser.parse_skill_md("---\nname: only-name\n---\nbody")
    assert "Missing required fields in frontmatter: description" in str(exc.value)


def test_parse_skill_md_malformed_frontmatter_wrapped():
    with patch("frontmatter.loads", side_effect=RuntimeError("bad yaml")):
        with pytest.raises(ValueError) as exc:
            parser.parse_skill_md("garbage")
    assert "Failed to parse SKILL.md" in str(exc.value)


def test_parse_skill_md_value_error_re_raised():
    # Our own ValueError must NOT be wrapped/reworded.
    with pytest.raises(ValueError) as exc:
        parser.parse_skill_md("---\nname: x\n---\n")
    assert "name: x" not in str(exc.value)  # wrapped form would include parse details
    assert "Missing required fields" in str(exc.value)


def test_parse_skill_md_non_string_fields_accepted():
    content = "---\nname: num-skill\ndescription: d\nversion: 1\n---\n"
    result = parser.parse_skill_md(content)
    assert result["version"] == 1


# ============================================================================
# _extract_python_blocks
# ============================================================================

def test_extract_python_blocks_multiple():
    md = "a\n```python\nprint(1)\n```\nb\n```python\nprint(2)\n```"
    assert parser._extract_python_blocks(md) == ["print(1)\n", "print(2)\n"]


def test_extract_python_blocks_none():
    assert parser._extract_python_blocks("no code here") == []


def test_extract_python_blocks_crlf_does_not_match():
    assert parser._extract_python_blocks("```python\r\nx = 1\r\n```") == []


def test_extract_python_blocks_other_languages_ignored():
    md = "```javascript\nvar x = 1;\n```"
    assert parser._extract_python_blocks(md) == []


# ============================================================================
# validate_python_syntax
# ============================================================================

def test_validate_python_syntax_valid():
    valid, err = parser.validate_python_syntax("def f():\n    return 1\n")
    assert valid is True and err == ""


def test_validate_python_syntax_invalid():
    valid, err = parser.validate_python_syntax("def f(:\n")
    assert valid is False
    assert err.startswith("Line ")


# ============================================================================
# extract_npm_dependencies
# ============================================================================

def test_extract_npm_imports_and_requires():
    code = """
import React from 'react';
import { useState } from 'react-hooks';
import * as d3 from 'd3';
import 'side-effect';
import helper from './relative';
import other from '/abs/rel';
const x = require('lodash');
const y = require('@scope/pkg');
"""
    deps = parser.extract_npm_dependencies(code, "MyComponent")
    assert deps == ["@scope/pkg", "d3", "lodash", "react", "react-hooks", "side-effect"]
    assert "./relative" not in deps
    assert "/abs/rel" not in deps


def test_extract_npm_package_json_dependencies():
    code = '''
const pkg = {
  "dependencies": {
    "axios": "^1.2.0",
    "@mui/material": "^5.0.0",
    "lodash": "4.17.21"
  }
}
'''
    deps = parser.extract_npm_dependencies(code, "MyComponent")
    assert deps == ["@mui/material", "axios", "lodash"]


def test_extract_npm_no_deps():
    assert parser.extract_npm_dependencies("const x = 1;", "C") == []


def test_extract_npm_package_json_parse_error_silently_ignored():
    import core.openclaw_parser as mod
    code = 'const s = "dependencies: {"'
    with patch.object(mod.re, "search", side_effect=RuntimeError("bad regex")):
        assert parser.extract_npm_dependencies(code, "C") == []


# ============================================================================
# _extract_dependencies
# ============================================================================

def test_extract_dependencies_requirements_and_node_packages():
    metadata = {
        "requirements": ["requests", "numpy", 1, 2.5, None],
        "node_packages": ["react", "lodash", 7, None],
    }
    deps = parser._extract_dependencies(metadata)
    assert deps["python"] == ["requests", "numpy", "1", "2.5"]
    assert deps["npm"] == ["react", "lodash", "7"]
    assert deps["bins"] == []


def test_extract_dependencies_openclaw_install_steps():
    metadata = {
        "metadata": {
            "openclaw": {
                "install": [
                    {"id": "u1", "kind": "uv", "package": "nano-pdf"},
                    {"id": "n1", "kind": "npm", "package": "pdf-lib"},
                    {"kind": "bins", "bins": ["ffmpeg", 2, None]},
                    {"kind": "uv"},  # no package
                    "not-a-dict",
                ]
            }
        }
    }
    deps = parser._extract_dependencies(metadata)
    assert deps["python"] == ["nano-pdf"]
    assert deps["npm"] == ["pdf-lib"]
    assert deps["bins"] == ["ffmpeg", "2"]


def test_extract_dependencies_metadata_not_dict():
    deps = parser._extract_dependencies({"metadata": "flat"})
    assert deps == {"python": [], "npm": [], "bins": []}


def test_extract_dependencies_openclaw_install_not_list():
    deps = parser._extract_dependencies({"metadata": {"openclaw": {"install": "nope"}}})
    assert deps["python"] == []


def test_extract_dependencies_empty():
    deps = parser._extract_dependencies({})
    assert deps == {"python": [], "npm": [], "bins": []}
