# -*- coding: utf-8 -*-
"""The reply leg must not raise on an undefined name — it fails CLOSED to a template.

Root cause this guards (2026-09-16, live): the request-entry deadline was threaded
into `_get_qwen_response` as the parameter `deadline`, but the reply-leg stage log
referenced `_deadline` (the name used one scope up, in `process_chat_message`).
That NameError was caught by the outer handler and the turn fell back to the
legacy intent router, answering

    "I've processed your request across all connected platforms."

with `model: template` — a 58 s turn delivering a canned sentence. `ast.parse`
accepts that code happily; only execution finds it, and the symptom (a template
reply) looks like a routing problem rather than a crash.

These tests are static on purpose: they catch the class without needing a live
provider, and they run in the isolated test DB.
"""
import ast
import inspect
from pathlib import Path

import integrations.chat_orchestrator as co

SRC = Path(co.__file__).read_text(encoding="utf-8")


def _function_node(name: str):
    tree = ast.parse(SRC)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"{name} not found")


def _referenced_names(node) -> set:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _assigned_names(node) -> set:
    out = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            out.add(n.id)
        elif isinstance(n, ast.arg):
            out.add(n.arg)
    return out


class TestNoUndefinedDeadlineNames:
    def test_get_qwen_response_does_not_reference_the_outer_deadline_name(self):
        node = _function_node("_get_qwen_response")
        referenced = _referenced_names(node)
        assigned = _assigned_names(node)
        assert "_deadline" not in referenced or "_deadline" in assigned, (
            "`_deadline` is the name used in process_chat_message; the reply leg "
            "receives `deadline`. Referencing the wrong one raises NameError at "
            "runtime and silently degrades the reply to a template."
        )

    def test_process_chat_message_defines_the_deadline_it_passes(self):
        node = _function_node("process_chat_message")
        referenced, assigned = _referenced_names(node), _assigned_names(node)
        assert "_deadline" in assigned, "the request deadline must be established here"
        assert "_deadline" in referenced

    def test_the_reply_leg_uses_the_parameter_name(self):
        node = _function_node("_get_qwen_response")
        src = ast.get_source_segment(SRC, node) or ""
        assert "deadline.elapsed()" in src
        assert "_deadline.elapsed()" not in src


class TestTemplateFallbackIsNotTheAnswer:
    def test_the_canned_line_is_marked_as_a_fallback(self):
        """The template reply must be recognisable so a detector can flag it.

        It reads like an answer ("I've processed your request…"), and shipped as
        one — the model field said `template` but nothing in the text did.
        """
        assert "processed your request across all connected platforms" in SRC
        # the canned response is emitted only on the fallback path
        assert "template" in SRC
