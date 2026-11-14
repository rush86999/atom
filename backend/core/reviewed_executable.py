"""Benign reviewed executable skills.

A reviewed Memento candidate is normally applied as a *prompt* skill: the
generated code is never written, imported or run.  This module adds the
narrow, explicit executable exception:

* only code that passes a conservative static ``benign deterministic
  computation`` policy can be applied for execution;
* the exact reviewed code is embedded (with a fixed trusted harness) in a
  registry package, and the package/registry rows are bound to the review
  revision + candidate digest + tenant/workspace/agent;
* execution goes through the existing ``SkillRegistryService`` ->
  ``HazardSandbox`` Docker path; there is no subprocess fallback.

The policy is intentionally an AST allowlist rather than a blacklist.  It
admits pure arithmetic/collection/string computations and rejects imports,
attribute access to dunders, filesystem/network/process primitives, classes,
decorators, lambdas and ``while True``.
"""
from __future__ import annotations

import ast
import hashlib
import json
from typing import Any, Dict, List, Optional

BENIGN_POLICY_SCHEMA = "atom-reviewed-executable-policy-1"
EXECUTABLE_BINDING_SCHEMA = "atom-reviewed-executable-binding-1"
EXECUTABLE_HARNESS_REVISION = "atom-reviewed-executable-harness-1"
EXECUTABLE_RECEIPT_SCHEMA = "atom-reviewed-executable-receipt-1"
EXECUTABLE_ENTRYPOINT = "execute"

MAX_SOURCE_BYTES = 16_000
MAX_AST_NODES = 2_000
MAX_REASONS = 12

# Concrete AST nodes a benign computation may contain.  Anything not listed is
# refused (fail closed) — this deliberately excludes Import, ClassDef, Lambda,
# With, Try, Raise, Global/Nonlocal, Yield/Await and every statement that can
# reach the interpreter, filesystem, process table or network.
_ALLOWED_NODE_NAMES = frozenset({
    "Module", "FunctionDef", "arguments", "arg", "Return", "Assign",
    "AnnAssign", "AugAssign", "If", "For", "While", "Break", "Continue",
    "Pass", "Assert", "Expr", "Constant", "Name", "BinOp", "UnaryOp",
    "BoolOp", "Compare", "IfExp", "List", "Tuple", "Set", "Dict",
    "Subscript", "Slice", "Attribute", "Starred", "Call", "keyword",
    "ListComp", "SetComp", "DictComp", "GeneratorExp", "comprehension",
    "JoinedStr", "FormattedValue",
    "Load", "Store", "Del",
    "Add", "Sub", "Mult", "Div", "FloorDiv", "Mod", "Pow", "LShift",
    "RShift", "BitOr", "BitXor", "BitAnd", "MatMult",
    "UAdd", "USub", "Not", "Invert",
    "And", "Or",
    "Eq", "NotEq", "Lt", "LtE", "Gt", "GtE", "Is", "IsNot", "In", "NotIn",
})

# Calls are limited to pure, in-memory builtins.  A call to a function defined
# in the reviewed source is also allowed (see ``assess_benign_code``).
_ALLOWED_BUILTINS = frozenset({
    "abs", "all", "any", "bin", "bool", "chr", "dict", "divmod",
    "enumerate", "filter", "float", "format", "frozenset", "hex", "int",
    "isinstance", "len", "list", "map", "max", "min", "oct", "ord", "pow",
    "range", "repr", "reversed", "round", "set", "sorted", "str", "sum",
    "tuple", "zip",
})

_DENIED_NAMES = frozenset({
    "__import__", "breakpoint", "callable", "classmethod", "compile",
    "delattr", "eval", "exec", "exit", "getattr", "globals", "hasattr",
    "help", "id", "input", "iter", "locals", "memoryview", "next",
    "object", "open", "print", "property", "quit", "setattr", "staticmethod",
    "super", "type", "vars",
})

# Method/attribute names that can traverse the interpreter object graph even
# without a dunder token in the source (``"{0.__class__}".format(x)``,
# generator ``gi_frame``/``f_globals`` chains, ...).  Benign computations use
# collection/string methods, never these.
_DENIED_ATTRIBUTES = frozenset({
    "format", "format_map", "mro", "subclasses", "gi_frame", "gi_code",
    "cr_frame", "cr_code", "ag_frame", "ag_code", "f_globals", "f_locals",
    "f_back", "tb_frame", "tb_next", "func_globals", "func_code",
})


class ReviewedExecutableExecutionError(ValueError):
    """Execution refused/failed; ``receipt`` carries what the sandbox saw."""

    def __init__(self, message: str, receipt: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.receipt = receipt


def sha256_text(value: Any) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        default=str)


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def registered_executable_code(generated_code: Any) -> str:
    """The exact source registered for execution: reviewed code + harness.

    The harness is fixed, reviewed platform code.  It calls the single
    ``execute(inputs)`` entry point, prints the deterministic JSON result and
    echoes a per-execution nonce only when the Docker sandbox injects one.
    The candidate's own source is never modified.
    """
    body = str(generated_code or "").rstrip("\n")
    harness = (
        "\n\n"
        "# --- atom reviewed executable harness (trusted, fixed) ---\n"
        'if "execute" not in globals():\n'
        '    raise RuntimeError('
        '"reviewed executable skill requires execute(inputs)")\n'
        "_atom_result = execute(inputs)\n"
        "print(json.dumps(_atom_result, sort_keys=True, "
        'separators=(",", ":"), default=str))\n'
        '_atom_nonce = globals().get("__atom_sandbox_nonce__")\n'
        "if _atom_nonce:\n"
        '    print("__atom_sandbox_nonce__=" + str(_atom_nonce))\n'
    )
    return body + harness


def _reason(reasons: List[str], value: str) -> None:
    if value not in reasons and len(reasons) < MAX_REASONS:
        reasons.append(value)


def assess_benign_code(code: Any) -> Dict[str, Any]:
    """Statically decide whether ``code`` is a benign deterministic computation.

    Returns a stable assessment dict (never raises).  ``eligible`` is the only
    authorization signal; ``reasons`` explains every refusal.
    """
    source = str(code or "")
    assessment: Dict[str, Any] = {
        "schema": BENIGN_POLICY_SCHEMA,
        "eligible": False,
        "entrypoint": EXECUTABLE_ENTRYPOINT,
        "harness_revision": EXECUTABLE_HARNESS_REVISION,
        "code_sha256": sha256_text(source),
        "node_count": 0,
        "reasons": [],
    }
    reasons: List[str] = assessment["reasons"]

    raw = source.encode("utf-8", errors="replace")
    if not source.strip():
        _reason(reasons, "empty_source")
        return assessment
    if len(raw) > MAX_SOURCE_BYTES:
        _reason(reasons, "source_too_large")
        return assessment

    try:
        tree = ast.parse(source, filename="<reviewed-executable>", mode="exec")
    except SyntaxError as exc:
        _reason(reasons, f"syntax_error: {exc.msg}")
        return assessment

    nodes = list(ast.walk(tree))
    assessment["node_count"] = len(nodes)
    if len(nodes) > MAX_AST_NODES:
        _reason(reasons, "ast_too_large")

    local_functions = {
        node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    if EXECUTABLE_ENTRYPOINT not in local_functions:
        _reason(reasons, "missing_entrypoint: execute(inputs)")

    # Top-level code may only define functions (plus a module docstring).
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            continue
        if (isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)):
            continue
        _reason(reasons, f"top_level_{type(node).__name__.lower()}")

    for node in nodes:
        name = type(node).__name__
        if name not in _ALLOWED_NODE_NAMES:
            _reason(reasons, f"node_{name.lower()}")

        if isinstance(node, ast.FunctionDef):
            if node.decorator_list:
                _reason(reasons, "decorator")
            if node.name == EXECUTABLE_ENTRYPOINT:
                args = node.args
                positional = len(args.posonlyargs) + len(args.args)
                if (positional != 1 or args.vararg or args.kwarg
                        or args.kwonlyargs):
                    _reason(reasons, "entrypoint_signature: execute(inputs)")
                elif args.defaults or args.kw_defaults:
                    _reason(reasons, "entrypoint_defaults")
            continue

        if isinstance(node, ast.Name):
            if node.id.startswith("__"):
                _reason(reasons, f"dunder_name: {node.id}")
            elif node.id in _DENIED_NAMES:
                _reason(reasons, f"denied_name: {node.id}")
            continue

        if isinstance(node, ast.Attribute):
            if str(node.attr).startswith("_"):
                _reason(reasons, f"dunder_attribute: {node.attr}")
            elif str(node.attr) in _DENIED_ATTRIBUTES:
                _reason(reasons, f"denied_attribute: {node.attr}")
            continue

        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                if (func.id not in _ALLOWED_BUILTINS
                        and func.id not in local_functions):
                    _reason(reasons, f"denied_call: {func.id}")
            elif isinstance(func, ast.Attribute):
                if str(func.attr).startswith("_"):
                    _reason(reasons, f"denied_call: .{func.attr}")
            else:
                _reason(reasons, "indirect_call")
            continue

        if isinstance(node, ast.While):
            test = node.test
            if isinstance(test, ast.Constant) and test.value in (True, 1):
                _reason(reasons, "unbounded_while")

    assessment["eligible"] = not reasons
    return assessment


def executable_binding(
    candidate: Any,
    *,
    review: Dict[str, Any],
    tenant_id: str,
    workspace_id: str,
    agent_id: str,
    registered_code: str,
) -> Dict[str, Any]:
    """Exact binding stored on the registry rows and re-checked at execution."""
    return {
        "schema": EXECUTABLE_BINDING_SCHEMA,
        "candidate_id": str(candidate.id),
        "review_revision": int(review.get("review_revision") or 0),
        "review_digest": str(review.get("digest") or ""),
        "candidate_code_sha256": sha256_text(candidate.generated_code),
        "executable_code_sha256": sha256_text(registered_code),
        "harness_revision": EXECUTABLE_HARNESS_REVISION,
        "entrypoint": EXECUTABLE_ENTRYPOINT,
        "tenant_id": str(tenant_id or ""),
        "workspace_id": str(workspace_id or ""),
        "agent_id": str(agent_id or ""),
    }


def verify_executable_artifact(
    *,
    binding: Any,
    candidate: Any,
    registered_code: str,
    tenant_id: str,
    workspace_id: str,
    agent_id: str,
    registry_execution_id: str,
    review_digest: str,
) -> Dict[str, Any]:
    """Re-derive every layer of the executable binding or raise.

    ``review_digest`` is the caller's recomputation of the current candidate
    material through ``core.reviewed_improvement._binding_digest``; comparing
    it here proves the candidate has not changed since review.
    """
    if not isinstance(binding, dict) or not binding:
        raise ValueError("reviewed_executable_not_approved: binding missing")
    if str(binding.get("schema") or "") != EXECUTABLE_BINDING_SCHEMA:
        raise ValueError(
            "reviewed_executable_artifact_changed: unsupported binding schema")
    if (str(binding.get("tenant_id") or "") != str(tenant_id or "")
            or str(binding.get("workspace_id") or "") != str(workspace_id or "")
            or str(binding.get("agent_id") or "") != str(agent_id or "")):
        raise ValueError(
            "reviewed_executable_workspace_mismatch: artifact is bound to "
            "another tenant/workspace/employee")
    if candidate is None:
        raise ValueError(
            "reviewed_executable_not_approved: reviewed candidate missing")
    if str(getattr(candidate, "id", "") or "") != str(
            binding.get("candidate_id") or ""):
        raise ValueError(
            "reviewed_executable_artifact_changed: candidate identity differs")
    if str(getattr(candidate, "validation_status", "") or "") != "promoted":
        raise ValueError(
            "reviewed_executable_not_approved: candidate is not promoted")

    result = candidate.validation_result if isinstance(
        candidate.validation_result, dict) else {}
    review = result.get("review") if isinstance(result.get("review"), dict) else {}
    applied = result.get("applied") if isinstance(
        result.get("applied"), dict) else {}

    revision = _safe_int(binding.get("review_revision"))
    if _safe_int(review.get("review_revision")) != revision:
        raise ValueError(
            "reviewed_executable_artifact_changed: review revision differs")
    if str(review.get("digest") or "") != str(
            binding.get("review_digest") or ""):
        raise ValueError(
            "reviewed_executable_artifact_changed: review digest differs")
    if str(review_digest or "") != str(review.get("digest") or ""):
        raise ValueError(
            "reviewed_executable_artifact_changed: candidate material changed "
            "after review")
    if (str(applied.get("candidate_id") or "")
            != str(binding.get("candidate_id") or "")):
        raise ValueError(
            "reviewed_executable_artifact_changed: applied candidate differs")
    if _safe_int(applied.get("review_revision")) != revision:
        raise ValueError(
            "reviewed_executable_artifact_changed: applied revision differs")
    if str(applied.get("review_digest") or "") != str(
            binding.get("review_digest") or ""):
        raise ValueError(
            "reviewed_executable_artifact_changed: applied review digest differs")
    if str(applied.get("execution_kind") or "") != "reviewed_executable":
        raise ValueError(
            "reviewed_executable_not_approved: candidate was not applied "
            "executably")
    if str(applied.get("registry_execution_id") or "") != str(
            registry_execution_id or ""):
        raise ValueError(
            "reviewed_executable_artifact_changed: registry record differs")
    if str(applied.get("executable_code_sha256") or "") != str(
            binding.get("executable_code_sha256") or ""):
        raise ValueError(
            "reviewed_executable_artifact_changed: applied code digest differs")

    candidate_sha = sha256_text(candidate.generated_code)
    if candidate_sha != str(binding.get("candidate_code_sha256") or ""):
        raise ValueError(
            "reviewed_executable_artifact_changed: candidate code changed")
    expected_code = registered_executable_code(candidate.generated_code)
    if sha256_text(registered_code) != str(
            binding.get("executable_code_sha256") or ""):
        raise ValueError(
            "reviewed_executable_artifact_changed: registered code digest differs")
    if str(registered_code or "").rstrip("\n") != expected_code.rstrip("\n"):
        raise ValueError(
            "reviewed_executable_artifact_changed: registered code is not the "
            "reviewed code")

    assessment = assess_benign_code(candidate.generated_code)
    if not assessment["eligible"]:
        raise ValueError(
            "reviewed_executable_policy_rejected: "
            + "; ".join(assessment["reasons"][:5]))

    return {
        "schema": EXECUTABLE_RECEIPT_SCHEMA,
        "verified": True,
        "candidate_id": str(candidate.id),
        "review_revision": revision,
        "review_digest": str(review.get("digest") or ""),
        "candidate_code_sha256": candidate_sha,
        "executable_code_sha256": sha256_text(registered_code),
        "registry_execution_id": str(registry_execution_id or ""),
        "tenant_id": str(tenant_id or ""),
        "workspace_id": str(workspace_id or ""),
        "agent_id": str(agent_id or ""),
        "entrypoint": EXECUTABLE_ENTRYPOINT,
        "harness_revision": EXECUTABLE_HARNESS_REVISION,
    }


def _yaml_frontmatter(frontmatter: Dict[str, Any]) -> str:
    try:
        import yaml

        return yaml.safe_dump(
            frontmatter, sort_keys=False, default_flow_style=False,
            allow_unicode=True).strip()
    except Exception:  # noqa: BLE001 - deterministic fallback
        return "\n".join(
            f"{key}: {json.dumps(value, ensure_ascii=True)}"
            for key, value in frontmatter.items())


def executable_skill_markdown(
    candidate: Any, *, review: Dict[str, Any], registered_code: str,
) -> str:
    """SKILL.md for the executable package (exactly one python fence)."""
    name = str(candidate.skill_name or "")
    description = str(candidate.skill_description or "").strip()
    failure = candidate.failure_pattern or {}
    if not isinstance(failure, dict):
        failure = {}
    instructions = (
        description
        or str(failure.get("failure_summary") or "").strip()
        or "Run the reviewed deterministic computation."
    )
    revision = int(review.get("review_revision") or 0)
    digest = str(review.get("digest") or "")
    frontmatter = {
        "name": name,
        "description": description or instructions,
        "version": "1.0.0",
        "author": "Memento-Skills",
        "type": "python",
        "entrypoint": EXECUTABLE_ENTRYPOINT,
        "review_revision": revision,
        "review_digest": digest,
        "candidate_code_sha256": sha256_text(candidate.generated_code),
        "executable_code_sha256": sha256_text(registered_code),
        "tags": ["memento", "reviewed", "executable"],
    }
    return (
        "---\n"
        f"{_yaml_frontmatter(frontmatter)}\n"
        "---\n\n"
        f"# {name}\n\n"
        f"{description or instructions}\n\n"
        "## Reviewed executable\n\n"
        "This skill is a reviewed benign deterministic computation. It runs "
        "only inside the isolated Docker sandbox; there is no host fallback.\n\n"
        "## Instructions\n"
        f"{instructions}\n\n"
        "## Provenance\n"
        f"- candidate: {candidate.id}\n"
        f"- source episode: {candidate.source_episode_id}\n"
        f"- entrypoint: {EXECUTABLE_ENTRYPOINT}(inputs)\n"
        f"- review revision: {revision}\n"
        f"- review digest: {digest}\n"
        f"- approved code sha256: {sha256_text(candidate.generated_code)}\n"
        f"- registered code sha256: {sha256_text(registered_code)}\n\n"
        "```python\n"
        f"{registered_code}\n"
        "```\n"
    )
