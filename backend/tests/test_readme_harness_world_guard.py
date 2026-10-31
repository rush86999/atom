"""The README harness must never delete an unowned or protected directory."""
from pathlib import Path

import pytest

from scripts.readme_acceptance import common


def _world(root: Path, name: str = "world") -> Path:
    return root / name


def test_marked_world_can_be_replaced(tmp_path):
    root = tmp_path / "root"
    world = _world(root)
    world.mkdir(parents=True)
    (world / "old.txt").write_text("old")
    (world / common.HARNESS_MARKER).write_text("owned")

    returned = common.reset_world(world, allowed_root=root)

    assert returned == world.resolve()
    assert not (world / "old.txt").exists()
    assert (world / common.HARNESS_MARKER).is_file()


def test_unmarked_existing_directory_is_refused_and_preserved(tmp_path):
    root = tmp_path / "root"
    world = _world(root)
    world.mkdir(parents=True)
    precious = world / "keep.txt"
    precious.write_text("do not delete")

    with pytest.raises(common.UnsafeWorldError, match="ownership marker"):
        common.reset_world(world, allowed_root=root)

    assert precious.read_text() == "do not delete"


def test_symlinked_world_is_refused_and_target_preserved(tmp_path):
    root = tmp_path / "root"
    target = tmp_path / "target"
    target.mkdir(parents=True)
    (target / common.HARNESS_MARKER).write_text("owned")
    league = root / "world"
    root.mkdir(parents=True)
    league.symlink_to(target)

    with pytest.raises(common.UnsafeWorldError, match="symlink"):
        common.reset_world(league, allowed_root=root)

    assert (target / common.HARNESS_MARKER).is_file()


def test_parent_symlink_is_refused(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep")
    (root / "link").symlink_to(outside)

    with pytest.raises(common.UnsafeWorldError):
        common.reset_world(root / "link" / "world", allowed_root=root)

    assert (outside / "keep.txt").read_text() == "keep"


def test_world_outside_allowed_root_is_refused(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep")

    with pytest.raises(common.UnsafeWorldError, match="outside the allowed root"):
        common.reset_world(outside, allowed_root=root)

    assert (outside / "keep.txt").read_text() == "keep"


def test_allowed_root_itself_is_refused(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "keep.txt").write_text("keep")

    with pytest.raises(common.UnsafeWorldError, match="root itself"):
        common.reset_world(root, allowed_root=root)

    assert (root / "keep.txt").read_text() == "keep"


@pytest.mark.parametrize("protected", [Path("/"), Path.home(), common.REPO])
def test_protected_paths_are_refused(protected, tmp_path):
    with pytest.raises(common.UnsafeWorldError):
        common.reset_world(protected, reset=False, allowed_root=tmp_path)


def test_broad_allowed_root_is_refused(tmp_path):
    with pytest.raises(common.UnsafeWorldError, match="protected allowed world root"):
        common.reset_world(Path("/tmp/anything"), reset=False, allowed_root=Path("/"))
