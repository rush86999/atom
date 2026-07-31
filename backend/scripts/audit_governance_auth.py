"""Audit: find require_governance-decorated endpoints missing auth or with broken governance wiring.

Checks each endpoint function decorated with @require_governance (or convenience wrappers):
  1. Has a 'request: Request' parameter named exactly 'request' (governance wiring)
  2. Has a 'db' parameter (governance wiring)
  3. Has current_user/current_admin Depends(get_current_user|require_*) (auth)
"""
import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

DECORATORS = {
    "require_governance",
    "require_browser_governance",
    "require_canvas_governance",
    "require_device_governance",
    "require_financial_governance",
}


def decorator_names(decorator_list):
    names = []
    for d in decorator_list:
        if isinstance(d, ast.Call):
            n = d.func
        else:
            n = d
        while isinstance(n, ast.Attribute):
            n = n.attr
        if isinstance(n, ast.Name):
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


def has_auth_dep(func_def):
    """Check for current_user/current_admin parameter with a Depends(get_current_user|require_*) default."""
    args = func_def.args
    pos_args = args.posonlyargs + args.args
    n_pos = len(pos_args)
    n_defaults = len(args.defaults)
    defaults = [None] * (n_pos - n_defaults) + list(args.defaults)
    defaults += [None] * (len(args.kwonlyargs) - len(args.kw_defaults)) + [
        d for d in args.kw_defaults if d is not None
    ] if len(args.kwonlyargs) > len(args.kw_defaults) else list(args.kw_defaults)

    def _is_depends_call(expr):
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
            # get_current_user, require_super_admin, require_admin, require_role
            return inner.id.startswith(("get_current", "require_"))
        return False

    for i, a in enumerate(pos_args):
        if a.arg in ("current_user", "current_admin", "user"):
            if _is_depends_call(defaults[i] if i < len(defaults) else None):
                return True
    for i, a in enumerate(args.kwonlyargs):
        if a.arg in ("current_user", "current_admin", "user"):
            d = args.kw_defaults[i] if i < len(args.kw_defaults) else None
            if _is_depends_call(d):
                return True
    # Router-level dependency check is handled separately (dependencies=[...])
    return False


def router_level_auth(tree):
    """Detect router-level dependencies=[Depends(get_current_user)] on the router in this file."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "router":
                    if isinstance(node.value, ast.Call):
                        for kw in node.value.keywords:
                            if kw.arg == "dependencies":
                                src = ast.unparse(kw.value)
                                if "get_current_user" in src:
                                    return True
    return False


def main():
    targets = list((ROOT / "api").rglob("*.py"))
    print(f"Scanning {len(targets)} API files...\n")
    issues = []
    for path in sorted(targets):
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:
            continue
        rl_auth = router_level_auth(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.AsyncFunctionDef):
                continue
            decs = decorator_names(node.decorator_list)
            if not any(d in DECORATORS for d in decs):
                continue
            names = param_names(node)
            has_request = "request" in names
            has_http_request = "http_request" in names
            has_db = "db" in names
            auth = has_auth_dep(node)
            status = "OK"
            problems = []
            if not has_request and not has_http_request:
                problems.append("NO request param")
            if not has_db:
                problems.append("NO db param")
            if not auth and not rl_auth:
                problems.append("NO AUTH")
            if has_http_request and not has_request:
                problems.append("request->http_request MISMATCH")
            if problems:
                status = "!!"
                issues.append((path, node.name, problems))
            print(f"[{status}] {path.relative_to(ROOT)}:{node.lineno} {node.name} -> {problems if problems else 'ok'}")
    print(f"\nTotal endpoints with issues: {len(issues)}")
    for path, name, problems in issues:
        print(f"  {path.relative_to(ROOT)}:{name} {problems}")


if __name__ == "__main__":
    sys.exit(main())
