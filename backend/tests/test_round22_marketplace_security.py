"""
TDD regression tests for Round 22 bug hunt - Marketplace & skills supply chain.

Covers:
- BUG R22-1: package_routes approve/ban/install — NO auth (supply-chain takeover)
- BUG R22-2: marketplace_routes install — NO auth
- BUG R22-3: skill_routes import/execute/promote — NO auth
- BUG R22-4: skill_dynamic_loader accepts arbitrary path (path traversal → arbitrary code exec)
- BUG R22-5: package_routes leaks str(e) in HTTPException detail
"""

from __future__ import annotations

import inspect


def _route_auth_dependencies(func) -> list[str]:
    deps = []
    for p in inspect.signature(func).parameters.values():
        if p.default is inspect.Parameter.empty:
            continue
        if hasattr(p.default, "dependency"):
            name = getattr(p.default.dependency, "__name__", "") or p.default.dependency.__class__.__name__
            deps.append(name)
        elif hasattr(p.default, "__name__"):
            deps.append(p.default.__name__)
    return deps


def _has_auth_dependency(func) -> bool:
    deps = _route_auth_dependencies(func)
    markers = ("get_current_user", "verify_token", "require_user", "require_auth",
               "get_current_active_user", "require_admin", "require_permission",
               "require_governance")
    return any(any(m in d for m in markers) for d in deps)


# ---------------------------------------------------------------------------
# BUG R22-1: package_routes missing auth
# ---------------------------------------------------------------------------


class TestPackageRoutesRequireAuth:
    """Critical package approval/install routes must require auth."""

    def test_approve_package_requires_auth(self):
        from api import package_routes as mod
        assert _has_auth_dependency(mod.approve_package), (
            "POST /approve has no auth — unauthenticated package approval (supply-chain takeover)"
        )

    def test_install_packages_requires_auth(self):
        from api import package_routes as mod
        assert _has_auth_dependency(mod.install_packages), (
            "POST /install has no auth — unauthenticated package installation"
        )


# ---------------------------------------------------------------------------
# BUG R22-2: marketplace_routes install — no auth
# ---------------------------------------------------------------------------


class TestMarketplaceInstallRequiresAuth:
    def test_install_marketplace_skill_requires_auth(self):
        from api import marketplace_routes as mod
        assert _has_auth_dependency(mod.install_marketplace_skill), (
            "POST /skills/{id}/install has no auth — unauthenticated skill install"
        )


# ---------------------------------------------------------------------------
# BUG R22-3: skill_routes missing auth
# ---------------------------------------------------------------------------


class TestSkillRoutesRequireAuth:
    def test_import_skill_requires_auth(self):
        from api import skill_routes as mod
        assert _has_auth_dependency(mod.import_skill), (
            "POST /import has no auth — unauthenticated skill import (arbitrary code loading)"
        )

    def test_execute_skill_requires_auth(self):
        from api import skill_routes as mod
        assert _has_auth_dependency(mod.execute_skill), (
            "POST /execute has no auth — unauthenticated skill execution"
        )

    def test_promote_skill_requires_auth(self):
        from api import skill_routes as mod
        assert _has_auth_dependency(mod.promote_skill), (
            "POST /promote has no auth — unauthenticated skill promotion to Active"
        )


# ---------------------------------------------------------------------------
# BUG R22-4: skill_dynamic_loader path traversal
# ---------------------------------------------------------------------------


class TestSkillDynamicLoaderPathValidation:
    """load_skill must not accept arbitrary paths (path traversal → RCE)."""

    def test_load_skill_validates_path(self):
        from core import skill_dynamic_loader as mod

        src = inspect.getsource(mod.SkillDynamicLoader.load_skill)
        # Must validate that the resolved path stays under an allowed skills directory.
        assert (
            "resolve()" in src
            or "allowed" in src.lower()
            or "skills_dir" in src
            or "SKILLS_DIR" in src
            or "base_dir" in src
        ), (
            "skill_dynamic_loader.load_skill accepts an arbitrary skill_path with no "
            "containment check — path traversal to load arbitrary .py (RCE)"
        )


# ---------------------------------------------------------------------------
# BUG R22-5: package_routes str(e) leaks
# ---------------------------------------------------------------------------


class TestPackageRoutesNoStrELeak:
    """package_routes must not embed str(e) in HTTPException detail."""

    def test_no_str_e_in_http_exceptions(self):
        from api import package_routes as mod
        src = inspect.getsource(mod)
        bad = []
        for i, line in enumerate(src.split("\n"), start=1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            if not ("HTTPException" in line or "internal_error" in line):
                continue
            if ("detail=str(e)" in line
                or 'detail=f"' in line and ("{e}" in line or "{str(e)}" in line)
                or "internal_error(str(e)" in line):
                bad.append(i)
        assert not bad, (
            f"package_routes leaks str(e) at lines {bad}"
        )
