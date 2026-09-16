# -*- coding: utf-8 -*-
"""Office-file ownership boundary (audit item 7, last clause).

The audit's deferred item reads "per-user ownership inside the office-files
directory". This file pins exactly what the current boundary IS, so that
"single-tenancy" is not mistaken for an access-control decision:

  * every office endpoint is AUTHENTICATED (router-level dependency), and
  * containment is PATH-based, not OWNER-based: any authenticated user may
    name any file under ``ATOM_OFFICE_DIR``.

The second point is a characterization, not an endorsement. It is pinned so
the current behaviour is explicit, and so that moving to per-user scoping is a
deliberate change that flips these assertions rather than a silent one.

Resolution recorded in
``docs/audits/2026-09-16_verification_and_corrections.md``: the flat namespace
is a real per-user exposure in a multi-user install; it is not fixed here
because office file paths are persisted on canvas rows, so a per-user subtree
is a migration, not a validator tweak.
"""
import os
from pathlib import Path

import pytest

from api.office_routes import _require_office_path, router
from core.office_service import _validate_office_path


@pytest.fixture()
def office_dir(tmp_path, monkeypatch):
    root = tmp_path / "office"
    root.mkdir()
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(root))
    return root


class TestAuthenticatedSurface:
    def test_every_office_endpoint_requires_a_user(self):
        """Router-level dependency — individual handlers need not repeat it,
        so this is the only place the guarantee can be checked."""
        deps = [getattr(d, "dependency", None) for d in router.dependencies]
        names = {getattr(d, "__name__", str(d)) for d in deps if d is not None}
        assert "get_current_user" in names, (
            "the office router no longer requires authentication; every "
            "endpoint reads/writes user-supplied paths")

    def test_no_office_route_declares_its_own_anonymous_handler(self):
        """A handler that overrides auth in the signature would defeat the
        router-level dependency."""
        import inspect

        for route in router.routes:
            endpoint = getattr(route, "endpoint", None)
            if endpoint is None:
                continue
            params = inspect.signature(endpoint).parameters
            if "current_user" in params:
                # An explicit dependency is fine; it must not be optional.
                default = params["current_user"].default
                assert getattr(default, "dependency", None) is not None, (
                    f"{route.path} declares current_user without a dependency")


class TestContainmentStillHolds:
    def test_path_inside_office_dir_is_accepted(self, office_dir):
        target = office_dir / "quote.xlsx"
        target.write_bytes(b"x")
        assert _validate_office_path(str(target)) == str(target.resolve())
        assert _require_office_path(str(target)) == str(target.resolve())

    def test_traversal_outside_office_dir_is_rejected(self, office_dir, tmp_path):
        outside = tmp_path / "secrets.json"
        outside.write_text("{}")
        with pytest.raises(ValueError):
            _validate_office_path(str(outside))

    def test_sibling_prefix_is_not_treated_as_inside(self, tmp_path, monkeypatch):
        """'/office-evil' must not pass a naive startswith check."""
        root = tmp_path / "office"
        evil = tmp_path / "office-evil"
        root.mkdir()
        evil.mkdir()
        (evil / "x.xlsx").write_bytes(b"x")
        monkeypatch.setenv("ATOM_OFFICE_DIR", str(root))
        with pytest.raises(ValueError):
            _validate_office_path(str(evil / "x.xlsx"))


class TestOwnershipIsNotEnforcedByContainment:
    """Characterization: containment and ownership are different properties."""

    def test_any_authenticated_users_file_is_reachable_by_path(self, office_dir):
        """Two different owners' files live in ONE namespace, and the
        validator accepts either path — it has no owner parameter at all."""
        import inspect

        alice = office_dir / "alice" / "budget.xlsx"
        bob = office_dir / "bob" / "budget.xlsx"
        alice.parent.mkdir()
        bob.parent.mkdir()
        alice.write_bytes(b"a")
        bob.write_bytes(b"b")

        # Both are accepted: the boundary cannot distinguish owners.
        assert _validate_office_path(str(alice))
        assert _validate_office_path(str(bob))

        params = inspect.signature(_validate_office_path).parameters
        assert list(params) == ["file_path"], (
            "the validator gained parameters — if an owner/user dimension was "
            "added, update this characterization and the audit note")

    def test_office_dir_is_a_single_flat_root(self, office_dir, monkeypatch):
        """No per-user segment is imposed by the base directory."""
        monkeypatch.setenv("ATOM_OFFICE_DIR", str(office_dir))
        resolved = Path(_validate_office_path(str(office_dir / "x.xlsx")))
        assert resolved.parent == office_dir.resolve()
        assert os.environ["ATOM_OFFICE_DIR"] == str(office_dir)


class TestTeamVsPerUserOwnership:
    """Owner decision 2026-09-16: team vs per-user depends on whether the
    file is shared (canvas-linked / integration-origin) or 3rd-party-app
    owned. Canvas-linked files are TEAM (the canvas panel is the auth
    surface). Integration files are TEAM (workspace data)."""

    def test_canvas_linked_file_is_team(self):
        from api.office_routes import _resolve_file_owner
        from core.models import CanvasContext

        class _Ctx:
            canvas_id = "c1"

        class _CanvasQ:
            def filter(self, *a, **k):
                self_ctx = _Ctx()
                # CanvasContext.current_state is a column, .contains() is
                # the SQLAlchemy operator — simulate it matching
                return self
            def first(self):
                return _Ctx()

        class _NoneQ:
            def filter(self, *a, **k):
                return self
            def first(self):
                return None

        class _Db:
            def query(self, model):
                return _CanvasQ() if model is CanvasContext else _NoneQ()

        info = _resolve_file_owner(_Db(), "/some/file.xlsx")
        assert info["ownership"] == "team"
        assert info["origin"] == "canvas"

    def test_default_is_team(self):
        from api.office_routes import _resolve_file_owner

        class _Q:
            def filter(self, *a, **k):
                return self
            def first(self):
                return None

        class _Db:
            def query(self, model):
                return _Q()

        info = _resolve_file_owner(_Db(), "/some/manual.xlsx")
        assert info["ownership"] == "team"
        assert info["origin"] == "default"
