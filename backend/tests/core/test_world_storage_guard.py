"""Tests for core/world_storage_guard.py — the worlds storage preflight and
the maintenance interlock.

The failure modes under test are the ones that are INVISIBLE at runtime:

* a worlds root that is a plain local directory when the config says it must
  be a drive-backed symlink (every ``world.mkdir(parents=True,
  exist_ok=True)`` would succeed and quietly produce an empty world);
* a dangling worlds symlink after the drive is unplugged;
* a volume that is the wrong device, or absent;
* a maintenance lock that a second session must observe (stopping processes
  is not enough — supervisors respawn them);
* internal world symlinks that are already broken, or anchored back at the
  canonical root, both of which ``rsync -a`` copies verbatim without
  complaint.

Every test builds its own tmp tree and redirects CONFIG_PATH/LOCK_PATH, so
nothing here can touch the real worlds storage or the real lock.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from core import world_storage_guard as G


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _write_config(tmp_path: Path, monkeypatch, **overrides) -> Path:
    """Point the guard at a tmp config; return the config path."""
    cfg_path = tmp_path / "world_storage.json"
    raw = {
        "enabled": True,
        "layout": "local",
        "worlds": {"root": "data/acceptance_worlds"},
        "volume": {},
        "symlink_sample": 0,
        "fail_on_broken_symlinks": False,
    }
    raw.update(overrides)
    cfg_path.write_text(json.dumps(raw))
    monkeypatch.setattr(G, "CONFIG_PATH", cfg_path)
    return cfg_path


def _isolate(monkeypatch, tmp_path: Path) -> None:
    """Redirect EVERY lock path, not just the config.

    The interlock adds a flock registry. If a test leaves it pointing at
    backend/config/, the suite contends for the REAL production lock — and a
    pytest process that registered as a "launcher" would then block a genuine
    maintenance window. Redirect all four, and export the env var so any child
    process resolves the same paths.
    """
    monkeypatch.setattr(G, "LOCK_PATH", tmp_path / G.LOCK_PATH.name)
    monkeypatch.setattr(G, "REGISTRY_LOCK_PATH", tmp_path / G.REGISTRY_LOCK_PATH.name)
    monkeypatch.setattr(G, "RUNNERS_DIR", tmp_path / G.RUNNERS_DIR.name)
    monkeypatch.delenv(G.BYPASS_ENV, raising=False)
    monkeypatch.setenv("ATOM_WORLD_STORAGE_PATHS", str(tmp_path))


def _fake_diskutil(monkeypatch, name: str, uuid: str) -> None:
    """Replace diskutil so volume identity is deterministic and offline."""

    def _run(cmd, *a, **kw):
        if cmd[:2] == ["diskutil", "info"]:
            out = f"   Volume Name:   {name}\n   Volume UUID:   {uuid}\n"
            return subprocess.CompletedProcess(cmd, 0, out.encode(), b"")
        return subprocess.CompletedProcess(cmd, 1, b"", b"")

    monkeypatch.setattr(G.subprocess, "run", _run)


# ---------------------------------------------------------------------------
# default-off behaviour: the guard must never break an unconfigured install
# ---------------------------------------------------------------------------
def test_missing_config_is_a_noop(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setattr(G, "CONFIG_PATH", tmp_path / "does-not-exist.json")
    report = G.preflight()
    assert report.ok
    assert "not checked" in " ".join(report.checks)


def test_disabled_config_is_a_noop(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    _write_config(tmp_path, monkeypatch, enabled=False)
    report = G.preflight()
    assert report.ok
    assert "not checked" in " ".join(report.checks)


# ---------------------------------------------------------------------------
# the silent-empty-world case
# ---------------------------------------------------------------------------
def test_local_dir_rejected_when_drive_symlink_required(tmp_path, monkeypatch):
    """A real directory in place of the symlink is the dangerous state.

    Every launcher mkdir's the world, so this must be a hard refusal, not a
    warning — otherwise the run "passes" against a brand-new empty world.
    """
    _isolate(monkeypatch, tmp_path)
    root = tmp_path / "acceptance_worlds"
    root.mkdir()
    cfg = G.WorldStorageConfig(
        enabled=True,
        layout=G.LAYOUT_DRIVE_SYMLINK,
        root=root,
        link_target=tmp_path / "elsewhere",
        volume_mount=tmp_path,
        volume_name="Seagate",
        volume_uuid="UUID-1",
        symlink_sample=-1,
    )
    _fake_diskutil(monkeypatch, "Seagate", "UUID-1")

    with pytest.raises(G.WorldStorageError) as exc:
        G.preflight(cfg)
    assert "plain local DIRECTORY" in str(exc.value)
    # The message has to name the silent-empty-world hazard, or an operator
    # will read it as a generic path complaint.
    assert "empty world" in str(exc.value).lower()


def test_local_dir_allowed_when_layout_is_local(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    root = tmp_path / "acceptance_worlds"
    (root / "w1").mkdir(parents=True)
    cfg = G.WorldStorageConfig(
        enabled=True, layout=G.LAYOUT_LOCAL, root=root, symlink_sample=-1
    )
    report = G.preflight(cfg)
    assert report.ok
    assert any("local directory" in c for c in report.checks)


# ---------------------------------------------------------------------------
# drive-backed states
# ---------------------------------------------------------------------------
def _drive_cfg(tmp_path: Path, **kw) -> G.WorldStorageConfig:
    root = tmp_path / "acceptance_worlds"
    real = tmp_path / "vol" / "projects" / "atom" / "backend" / "data" / "acceptance_worlds"
    real.mkdir(parents=True)
    mount = tmp_path / "vol"
    defaults = dict(
        enabled=True,
        layout=G.LAYOUT_DRIVE_SYMLINK,
        root=root,
        link_target=real,
        volume_mount=mount,
        volume_name="Seagate Portable Drive",
        volume_uuid="0C0C11D3-8011-4F04-A213-E3EFE642C992",
        symlink_sample=-1,
    )
    defaults.update(kw)
    return G.WorldStorageConfig(**defaults)


def test_good_symlink_passes(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    cfg = _drive_cfg(tmp_path)
    os.symlink(cfg.link_target, cfg.root)
    _fake_diskutil(monkeypatch, cfg.volume_name, cfg.volume_uuid)
    report = G.preflight(cfg)
    assert report.ok
    assert any("resolving to" in c for c in report.checks)


def test_dangling_symlink_rejected(tmp_path, monkeypatch):
    """Drive unplugged: the link exists but resolves to nothing."""
    _isolate(monkeypatch, tmp_path)
    cfg = _drive_cfg(tmp_path)
    os.symlink(tmp_path / "vol" / "not_mounted", cfg.root)
    _fake_diskutil(monkeypatch, cfg.volume_name, cfg.volume_uuid)

    with pytest.raises(G.WorldStorageError) as exc:
        G.preflight(cfg)
    assert "DANGLING" in str(exc.value)


def test_symlink_to_wrong_target_rejected(tmp_path, monkeypatch):
    """A link that resolves, but somewhere other than the configured tree."""
    _isolate(monkeypatch, tmp_path)
    cfg = _drive_cfg(tmp_path)
    other = tmp_path / "vol" / "somewhere_else"
    other.mkdir(parents=True)
    os.symlink(other, cfg.root)
    _fake_diskutil(monkeypatch, cfg.volume_name, cfg.volume_uuid)

    with pytest.raises(G.WorldStorageError) as exc:
        G.preflight(cfg)
    assert "wrong place" in str(exc.value)


def test_missing_volume_rejected(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    cfg = _drive_cfg(tmp_path)
    cfg.volume_mount = tmp_path / "not-mounted-at-all"
    with pytest.raises(G.WorldStorageError) as exc:
        G.preflight(cfg)
    assert "NOT mounted" in str(exc.value)


def test_wrong_volume_uuid_rejected(tmp_path, monkeypatch):
    """A different drive that happens to be mounted at the right path.

    Name alone is not identity, so the UUID is the check that matters.
    """
    _isolate(monkeypatch, tmp_path)
    cfg = _drive_cfg(tmp_path)
    os.symlink(cfg.link_target, cfg.root)
    _fake_diskutil(monkeypatch, cfg.volume_name, "SOME-OTHER-UUID")
    with pytest.raises(G.WorldStorageError) as exc:
        G.preflight(cfg)
    assert "UUID mismatch" in str(exc.value)


def test_wrong_volume_name_rejected(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    cfg = _drive_cfg(tmp_path)
    os.symlink(cfg.link_target, cfg.root)
    _fake_diskutil(monkeypatch, "Backup Disk", cfg.volume_uuid)
    with pytest.raises(G.WorldStorageError) as exc:
        G.preflight(cfg)
    assert "name mismatch" in str(exc.value)


# ---------------------------------------------------------------------------
# maintenance interlock
# ---------------------------------------------------------------------------
def test_lock_blocks_preflight(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    root = tmp_path / "acceptance_worlds"
    root.mkdir()
    cfg = G.WorldStorageConfig(
        enabled=True, layout=G.LAYOUT_LOCAL, root=root, symlink_sample=-1
    )
    G.acquire_maintenance_lock("relocating worlds", operator="tester")
    with pytest.raises(G.WorldStorageError) as exc:
        G.preflight(cfg)
    msg = str(exc.value)
    assert "MAINTENANCE LOCK" in msg
    assert "relocating worlds" in msg
    assert "tester" in msg


def test_lock_roundtrip(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    assert G.lock_active() is False
    payload = G.acquire_maintenance_lock("window", operator="me")
    assert payload["active"] is True
    assert G.lock_active() is True
    G.release_maintenance_lock()
    assert G.lock_active() is False


def test_unreadable_lock_fails_closed(tmp_path, monkeypatch):
    """A lock we cannot parse must NOT be read as 'no lock'.

    Failing open here is the whole bug: the operator believes relocation is
    protected while launchers happily write into the tree being moved.
    """
    _isolate(monkeypatch, tmp_path)
    G.LOCK_PATH.write_text("{ this is not json")
    root = tmp_path / "acceptance_worlds"
    root.mkdir()
    cfg = G.WorldStorageConfig(
        enabled=True, layout=G.LAYOUT_LOCAL, root=root, symlink_sample=-1
    )
    assert G.lock_active() is True
    with pytest.raises(G.WorldStorageError) as exc:
        G.preflight(cfg)
    assert "MAINTENANCE LOCK" in str(exc.value)


def test_lock_checked_before_volume(tmp_path, monkeypatch):
    """The lock is the cheapest and most important check, so it goes first.

    During a window the drive may legitimately be unmounted; the operator
    must see the lock message, not a confusing 'volume NOT mounted'.
    """
    _isolate(monkeypatch, tmp_path)
    cfg = _drive_cfg(tmp_path)
    cfg.volume_mount = tmp_path / "gone"
    G.acquire_maintenance_lock("relocating")
    with pytest.raises(G.WorldStorageError) as exc:
        G.preflight(cfg)
    assert "MAINTENANCE LOCK" in str(exc.value)


# ---------------------------------------------------------------------------
# bypass
# ---------------------------------------------------------------------------
def test_bypass_env_short_circuits(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setenv(G.BYPASS_ENV, "1")
    cfg = _drive_cfg(tmp_path)
    cfg.volume_mount = tmp_path / "gone"  # would otherwise raise
    report = G.preflight(cfg)
    assert report.ok and report.bypassed


def test_bypass_respected_by_cheap_assert(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setenv(G.BYPASS_ENV, "1")
    cfg = _drive_cfg(tmp_path)
    cfg.volume_mount = tmp_path / "gone"
    G.assert_worlds_root_usable(cfg)  # must not raise


# ---------------------------------------------------------------------------
# cheap per-mkdir assertion
# ---------------------------------------------------------------------------
def test_cheap_assert_allows_local_layout(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    root = tmp_path / "acceptance_worlds"
    root.mkdir()
    G.assert_worlds_root_usable(
        G.WorldStorageConfig(enabled=True, layout=G.LAYOUT_LOCAL, root=root)
    )


def test_cheap_assert_rejects_plain_dir_in_drive_layout(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    root = tmp_path / "acceptance_worlds"
    root.mkdir()
    cfg = _drive_cfg(tmp_path, root=root)
    with pytest.raises(G.WorldStorageError) as exc:
        G.assert_worlds_root_usable(cfg, where="build_world(demo)")
    assert "build_world(demo)" in str(exc.value)


def test_cheap_assert_rejects_dangling(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    root = tmp_path / "acceptance_worlds"
    os.symlink(tmp_path / "missing", root)
    cfg = _drive_cfg(tmp_path, root=root)
    with pytest.raises(G.WorldStorageError) as exc:
        G.assert_worlds_root_usable(cfg)
    assert "DANGLING" in str(exc.value)


def test_cheap_assert_rejects_lock(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    root = tmp_path / "acceptance_worlds"
    root.mkdir()
    cfg = G.WorldStorageConfig(enabled=True, layout=G.LAYOUT_LOCAL, root=root)
    G.acquire_maintenance_lock("relocating")
    with pytest.raises(G.WorldStorageError):
        G.assert_worlds_root_usable(cfg)


def test_cheap_assert_rejects_absent_root(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    root = tmp_path / "nope"
    cfg = G.WorldStorageConfig(enabled=True, layout=G.LAYOUT_LOCAL, root=root)
    with pytest.raises(G.WorldStorageError) as exc:
        G.assert_worlds_root_usable(cfg)
    assert "does not exist" in str(exc.value)


# ---------------------------------------------------------------------------
# internal symlink audit — broken and mis-anchored, tested SEPARATELY
# ---------------------------------------------------------------------------
def test_audit_finds_broken_symlink(tmp_path):
    """A link whose target is gone. rsync -a copies this verbatim."""
    root = tmp_path / "worlds"
    (root / "w" / "code").mkdir(parents=True)
    (root / "w" / "backend_root").mkdir()
    os.symlink(root / "w" / "code" / "vanished.py", root / "w" / "backend_root" / "x.py")
    broken, misanchored = G.audit_internal_symlinks(root, 0)
    assert len(broken) == 1
    assert "vanished.py" in broken[0]
    assert misanchored == []


def test_audit_finds_misanchored_absolute_symlink(tmp_path):
    """Absolute link back into the canonical root.

    Resolves fine while the root is a symlink, and would silently point at
    the OLD tree if the root were ever a plain directory again. Reported
    separately from 'broken' because it is not broken — it is misdirected.
    """
    root = tmp_path / "worlds"
    (root / "w" / "code" / "backend").mkdir(parents=True)
    (root / "w" / "code" / "backend" / "mod.py").write_text("x = 1\n")
    (root / "w" / "backend_root").mkdir()
    os.symlink(
        str(root / "w" / "code" / "backend" / "mod.py"),
        root / "w" / "backend_root" / "mod.py",
    )
    broken, misanchored = G.audit_internal_symlinks(root, 0)
    assert broken == []
    assert len(misanchored) == 1
    assert str(root) in misanchored[0]


def test_audit_ignores_relative_symlinks(tmp_path):
    """Relative links stay correct after a move, so they are NOT misanchored."""
    root = tmp_path / "worlds"
    (root / "w" / "a").mkdir(parents=True)
    (root / "w" / "a" / "f.txt").write_text("hi")
    (root / "w" / "b").mkdir()
    os.symlink("../a/f.txt", root / "w" / "b" / "f.txt")
    broken, misanchored = G.audit_internal_symlinks(root, 0)
    assert broken == []
    assert misanchored == []


def test_audit_respects_sample_limit(tmp_path):
    root = tmp_path / "worlds"
    (root / "w").mkdir(parents=True)
    for i in range(10):
        os.symlink(f"missing{i}", root / "w" / f"l{i}")
    broken, _ = G.audit_internal_symlinks(root, sample=4)
    assert len(broken) == 4


def test_broken_symlinks_block_only_when_configured(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    root = tmp_path / "worlds"
    (root / "w").mkdir(parents=True)
    os.symlink(root / "w" / "gone", root / "w" / "l")

    tolerant = G.WorldStorageConfig(
        enabled=True, layout=G.LAYOUT_LOCAL, root=root,
        symlink_sample=-1, fail_on_broken_symlinks=False,
    )
    report = G.preflight(tolerant)
    assert report.ok
    assert len(report.broken_symlinks) == 1

    strict = G.WorldStorageConfig(
        enabled=True, layout=G.LAYOUT_LOCAL, root=root,
        symlink_sample=-1, fail_on_broken_symlinks=True,
    )
    with pytest.raises(G.WorldStorageError) as exc:
        G.preflight(strict)
    assert "broken internal symlink" in str(exc.value)


def test_audit_on_missing_root_is_empty_not_an_error(tmp_path):
    broken, misanchored = G.audit_internal_symlinks(tmp_path / "absent", 0)
    assert broken == [] and misanchored == []


# ---------------------------------------------------------------------------
# config handling
# ---------------------------------------------------------------------------
def test_relative_root_anchored_to_backend_not_cwd(tmp_path, monkeypatch):
    """AGENTS.md: never resolve storage paths CWD-relative."""
    _write_config(tmp_path, monkeypatch)
    cfg = G.load_config()
    assert cfg.root == G.BACKEND / "data" / "acceptance_worlds"
    assert cfg.root.is_absolute()


def test_absolute_root_used_as_is(tmp_path, monkeypatch):
    _write_config(
        tmp_path, monkeypatch, worlds={"root": "/Volumes/X/data/acceptance_worlds"}
    )
    cfg = G.load_config()
    assert cfg.root == Path("/Volumes/X/data/acceptance_worlds")


def test_corrupt_config_raises_instead_of_disabling(tmp_path, monkeypatch):
    """A broken config must not silently turn the guard off."""
    _isolate(monkeypatch, tmp_path)
    bad = tmp_path / "world_storage.json"
    bad.write_text("{not json")
    monkeypatch.setattr(G, "CONFIG_PATH", bad)
    with pytest.raises(G.WorldStorageError) as exc:
        G.load_config()
    assert "unreadable" in str(exc.value)


def test_unknown_layout_raises(tmp_path, monkeypatch):
    _write_config(tmp_path, monkeypatch, worlds={"root": "data/acceptance_worlds", "layout": "somewhere_else"})
    with pytest.raises(G.WorldStorageError) as exc:
        G.load_config()
    assert "unknown worlds layout" in str(exc.value)


def test_release_requires_yes_flag(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    G.acquire_maintenance_lock("window")
    assert G._main(["release"]) == 2
    assert G.lock_active() is True
    assert G._main(["release", "--yes"]) == 0
    assert G.lock_active() is False


def test_summary_is_bounded(tmp_path, monkeypatch):
    """A launcher printing 10k lines trains people to ignore the output."""
    _isolate(monkeypatch, tmp_path)
    root = tmp_path / "worlds"
    root.mkdir()
    report = G.PreflightReport(
        ok=True, broken_symlinks=[f"b{i}" for i in range(50)],
        misanchored_symlinks=[f"m{i}" for i in range(50)],
    )
    text = report.summary()
    assert "50" in text
    assert "and 47 more" in text
    assert len(text.splitlines()) < 20


# ---------------------------------------------------------------------------
# the shipped config must actually be the config that is honoured
# ---------------------------------------------------------------------------
def test_load_shipped_config_layout_is_honoured(tmp_path, monkeypatch):
    """Regression: the shipped file said `layout` at the top level while the
    loader read `worlds.layout`.

    The result was that flipping the config to `drive_symlink` — the exact
    step that makes the guard enforce the symlink during the window — was
    silently ignored. This asserts the real file's value reaches the loader,
    in either spelling, and that an unknown one still raises.
    """
    shipped = G.CONFIG_PATH
    assert shipped.is_file(), f"shipped config missing: {shipped}"

    raw = json.loads(shipped.read_text())
    declared = raw.get("layout") or (raw.get("worlds") or {}).get("layout")
    assert declared in (G.LAYOUT_LOCAL, G.LAYOUT_DRIVE_SYMLINK), declared

    # Read the real file with the real loader.
    cfg = G.load_config(shipped)
    assert cfg.layout == declared, "shipped layout is not the layout enforced"
    assert cfg.is_drive_layout == (declared == G.LAYOUT_DRIVE_SYMLINK)

    # An unknown layout must be rejected whichever way it is spelled.
    for spelling in ({"layout": "sideways"}, {"worlds": {"layout": "sideways"}}):
        bad = tmp_path / "bad.json"
        bad.write_text(json.dumps({"enabled": True, **spelling}))
        with pytest.raises(G.WorldStorageError):
            G.load_config(bad)


def test_drive_symlink_layout_actually_enforces(tmp_path, monkeypatch):
    """End-to-end: with the shipped schema set to drive_symlink and a plain
    local directory in place, the preflight MUST refuse.

    This is the guard doing its one real job, so it is asserted against the
    config file format rather than a hand-built dataclass.
    """
    root = tmp_path / "acceptance_worlds"
    root.mkdir()
    cfg_path = tmp_path / "world_storage.json"
    cfg_path.write_text(
        json.dumps(
            {
                "enabled": True,
                "layout": G.LAYOUT_DRIVE_SYMLINK,
                "worlds": {
                    "root": str(root),
                    "link_target": str(tmp_path / "elsewhere"),
                },
                "volume": {
                    "mount_point": str(tmp_path),
                    "name": "Vol",
                    "uuid": "U-1",
                },
                "symlink_sample": 0,
            }
        )
    )
    monkeypatch.setattr(G, "CONFIG_PATH", cfg_path)
    assert G.load_config().is_drive_layout is True
    _fake_diskutil(monkeypatch, "Vol", "U-1")
    with pytest.raises(G.WorldStorageError) as exc:
        G.preflight()
    assert "plain local DIRECTORY" in str(exc.value)
