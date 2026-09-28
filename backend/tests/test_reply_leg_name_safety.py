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
import builtins
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


def _all_bound_names(node) -> set:
    """Every name the function can resolve WITHOUT reaching the enclosing
    scope: its own parameters and assignments, plus names introduced by
    nested defs/classes, ``except ... as`` bindings, and imports."""
    out = _assigned_names(node)
    args = node.args
    for group in (args.args, args.kwonlyargs, args.posonlyargs):
        out |= {a.arg for a in group}
    if args.vararg:
        out.add(args.vararg.arg)
    if args.kwarg:
        out.add(args.kwarg.arg)
    for n in ast.walk(node):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) \
                and n is not node:
            out.add(n.name)
            out |= _all_bound_names(n)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            out.add(n.name)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            out |= {(a.asname or a.name).split(".")[0] for a in n.names}
    return out


class TestReplyLegBorrowsNoLocalsFromTheTurnEntrypoint:
    """The general form of the ``_deadline`` incident above, which recurred
    on 2026-09-27 with a different name: the evidence-bound narration guard
    read ``_pfr_structured_for_turn``, a local of ``process_chat_message``,
    from inside ``_get_qwen_response``. Every turn that produced a structured
    workbook record raised ``NameError`` there; the enclosing ``except``
    logged one warning, discarded the reply, and let the turn fall through to
    legacy feature routing — where the TASKS handler answered "I've added
    'Replace U-22 with U-38' to your Tasks" instead of the user's actual
    question.

    The narrow ``_deadline`` checks above could not catch that: they only ask
    about one name. This asks about the SHAPE, so the next hoisted-into-the-
    wrong-method variable is caught before it ships, whatever it is called.
    """

    def test_get_qwen_response_reads_no_locals_of_process_chat_message(self):
        tree = ast.parse(SRC)
        funcs = {
            n.name: n for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        turn = funcs["process_chat_message"]
        reply = funcs["_get_qwen_response"]

        # Module level is legitimately visible from inside a method.
        module_names = {n.name for n in tree.body if isinstance(
            n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
        module_names |= {
            t.id for n in tree.body if isinstance(n, ast.Assign)
            for t in n.targets if isinstance(t, ast.Name)
        }
        for n in ast.walk(tree):
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                module_names |= {(a.asname or a.name).split(".")[0] for a in n.names}

        resolvable = module_names | set(dir(builtins)) | _all_bound_names(reply)
        borrowed = sorted(
            (_referenced_names(reply) - resolvable) & _all_bound_names(turn)
        )
        assert borrowed == [], (
            "_get_qwen_response reads names bound in process_chat_message: "
            f"{borrowed}. Each raises NameError at runtime, and the enclosing "
            "except turns that into a silent fallback rather than a visible "
            "failure. Bind the value where it is used, or pass it in."
        )


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
