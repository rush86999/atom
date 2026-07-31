"""Audit: find ALL FastAPI router endpoints lacking authentication.

Round 38's audit_governance_auth.py only inspected endpoints decorated with
@require_governance. This scanner walks every @router.{get,post,put,delete,
patch,websocket} handler and reports endpoints that have neither:

  1. An auth dependency param (current_user/current_admin/user with
     Depends(get_current_user|require_*)) at the function level, nor
  2. A router-level dependencies=[Depends(get_current_user|require_*)] at
     file scope.

Endpoints are grouped by "risk tier":
  - PUBLIC_WHITELIST: known-public routers (auth, health, webhooks with
    signature verification, static, docs) — expected, ignored.
  - REVIEW: everything else with no auth. Needs manual triage.
"""
import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Routers known to be intentionally public (auth bootstrap, health checks,
# signature-verified webhooks, oauth redirects, static/docs).
PUBLIC_ROUTER_HINTS = (
    "auth",
    "health",
    "webhook",
    "oauth",
    "docs",
    "static",
    "callback",
    "bootstrap",
    "stripe",
)

METHODS = ("get", "post", "put", "delete", "patch", "websocket")


def decorator_names(decorator_list):
    names = []
    for d in decorator_list:
        if isinstance(d, ast.Call):
            n = d.func
        else:
            n = d
        if isinstance(n, ast.Attribute):
            names.append(n.attr)
        elif isinstance(n, ast.Name):
            names.append(n.id)
    return names


def param_names(func_def):
    args = func_def.args
    names = [a.arg for a in args.posonlyargs + args.args]
    if args.vararg:
        names.append(args.vararg.arg)
    names += [a.arg for a in args.kwonlyargs]
    if args.kwarg:
        names.append(args.kwarg.arg)
    return names


def is_depends_call(expr):
    if expr is None or not isinstance(expr, ast.Call):
        return False
    f = expr.func
    while isinstance(f, ast.Attribute):
        f = f.attr
    if not isinstance(f, ast.Name) or f.id != "Depends":
        return False
    if not expr.args:
        return False
    inner = expr.args[0]
    while isinstance(inner, ast.Attribute):
        inner = inner.attr
    if isinstance(inner, ast.Name):
        n = inner.id
        # require_permission(Permission.X) — the inner arg is an Attribute
        # (Permission.AGENT_RUN), so match any require_* factory call.
        return (
            n.startswith(("get_current", "require_"))
            or n in {"get_super_admin", "get_admin", "get_current_admin",
                     "get_tenant_user", "get_current_tenant", "get_api_key_user"}
        )
    if isinstance(inner, str):
        # Depends("auth_dependency") style strings
        return inner.startswith(("get_current", "require_"))
    return False


def func_auth(func_def):
    """True if a param named current_user/current_admin/user has auth Depends."""
    args = func_def.args
    pos_args = args.posonlyargs + args.args
    n_pos = len(pos_args)
    n_defaults = len(args.defaults)
    defaults = [None] * (n_pos - n_defaults) + list(args.defaults)
    kw_defaults = [None] * (len(args.kwonlyargs) - len(args.kw_defaults)) + list(args.kw_defaults)
    for i, a in enumerate(pos_args):
        if a.arg in ("current_user", "current_admin", "admin", "user"):
            if is_depends_call(defaults[i] if i < len(defaults) else None):
                return True
    for i, a in enumerate(args.kwonlyargs):
        if a.arg in ("current_user", "current_admin", "admin", "user"):
            if is_depends_call(kw_defaults[i]):
                return True
    return False


def router_level_auth(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "router":
                    if isinstance(node.value, ast.Call):
                        for kw in node.value.keywords:
                            if kw.arg == "dependencies":
                                src = ast.unparse(kw.value)
                                if "get_current_user" in src or "require_" in src:
                                    return True
    return False


def main():
    targets = list((ROOT / "api").rglob("*.py"))
    print(f"Scanning {len(targets)} API files...\n")
    review = []
    whitelisted = []
    for path in sorted(targets):
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:
            continue
        rl_auth = router_level_auth(tree)
        is_public = any(hint in path.name for hint in PUBLIC_ROUTER_HINTS)
        for node in ast.walk(tree):
            if not isinstance(node, ast.AsyncFunctionDef) and not isinstance(node, ast.FunctionDef):
                continue
            decs = decorator_names(node.decorator_list)
            route_decs = [d for d in decs if d in METHODS]
            if not route_decs:
                continue
            has_auth = func_auth(node)
            has_governance = any(
                d.startswith("require_") for d in decs
            )
            if rl_auth or has_auth or has_governance:
                continue
            rel = path.relative_to(ROOT)
            line = node.lineno
            entry = f"{rel}:{line} {node.name} [{'/'.join(route_decs)}]"
            if is_public:
                whitelisted.append(entry)
            else:
                review.append(entry)
    print("=== NO AUTH (review) ===")
    for e in review:
        print(f"  [!!] {e}")
    print(f"\nTotal review: {len(review)} | whitelisted public: {len(whitelisted)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
