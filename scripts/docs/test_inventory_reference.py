"""Boundary tests: inventory is immutable-source metadata, not certification."""
import json
import contextlib
import io
from unittest import mock
import inventory_reference
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from inventory_reference import build_inventory, embedded


class ReferenceInventoryBoundaryTests(unittest.TestCase):
    def repo(self, root):
        repo = root / 'repo'
        repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(repo)], check=True)
        return repo

    def commit(self, repo):
        subprocess.run(['git', '-C', str(repo), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(repo), '-c', 'user.name=Inventory fixture',
                        '-c', 'user.email=inventory@example.invalid',
                        '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null',
                        'commit', '-qm', 'source snapshot'], check=True)
        return subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()

    def test_reads_declared_git_source_not_changed_disk(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = self.repo(Path(folder))
            (repo / 'README.md').write_text('# Reference\n\n```mermaid\nflowchart TD\nA-->B\n```\n')
            (repo / 'diagram.svg').write_bytes(b'not a rendered or validated figure')
            source = self.commit(repo)
            (repo / 'README.md').write_text('changed disk without a diagram')
            (repo / 'diagram.svg').unlink()
            result = build_inventory(repo, source)
            self.assertEqual(result['source_ref'], source)
            self.assertEqual(result['summary']['diagram_candidates'], 1)
            self.assertEqual(result['summary']['figure_candidates'], 1)
            self.assertFalse(result['accuracy_complete'])
            self.assertFalse(result['diagram_candidates'][0]['rendered'])
            self.assertEqual(result['diagram_candidates'][0]['semantic_status'], 'not_reviewed')

    def test_literal_nested_example_is_not_counted_as_rendered_diagram(self):
        data = b'````markdown\n```mermaid\nA-->B\n```\n````\n~~~mermaid\nA-->C\n~~~\n'
        found = embedded('guide.md', data)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]['start_line'], 6)
        self.assertFalse(found[0]['rendered'])

    def test_unclosed_diagram_remains_unresolved(self):
        found = embedded('guide.md', b'```mermaid\nA-->B\n')
        self.assertIsNone(found[0]['end_line'])
        self.assertEqual(found[0]['semantic_status'], 'unclosed_fence_needs_review')

    def test_symlink_reference_does_not_read_outside_git(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            repo = self.repo(root)
            private = root / 'private.md'
            private.write_text('outside-marker\n```mermaid\nsecret-->value\n```\n')
            (repo / 'README.md').symlink_to(private)
            source = self.commit(repo)
            result = build_inventory(repo, source)
            self.assertEqual(result['summary']['references'], 1)
            self.assertEqual(result['summary']['diagram_candidates'], 0)
            self.assertNotIn('outside-marker', json.dumps(result))

    def test_cli_refuses_dangling_output_symlink(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            repo = self.repo(root)
            (repo / 'README.md').write_text('# Fixture')
            self.commit(repo)
            target = root / 'must-not-be-created.json'
            output = root / 'inventory.json'
            output.symlink_to(target)
            with mock.patch.object(sys, 'argv', ['inventory', '--repo', str(repo), '--output', str(output)]):
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as result:
                        inventory_reference.main()
            self.assertEqual(result.exception.code, 2)
            self.assertFalse(target.exists())

    def test_late_peer_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            repo = self.repo(root)
            (repo / 'README.md').write_text('# Fixture')
            self.commit(repo)
            output = root / 'inventory.json'
            original = inventory_reference.build_inventory
            def peer_writes_after_preflight(*args):
                result = original(*args)
                output.write_bytes(b'peer retained snapshot')
                return result
            with mock.patch.object(sys, 'argv', ['inventory', '--repo', str(repo), '--output', str(output)]):
                with mock.patch.object(inventory_reference, 'build_inventory', side_effect=peer_writes_after_preflight):
                    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                        with self.assertRaises(SystemExit) as result:
                            inventory_reference.main()
            self.assertEqual(result.exception.code, 2)
            self.assertEqual(output.read_bytes(), b'peer retained snapshot')

    def test_missing_output_parent_is_not_created(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            repo = self.repo(root)
            (repo / 'README.md').write_text('# Fixture')
            self.commit(repo)
            output = root / 'unrequested-tree' / 'inventory.json'
            with mock.patch.object(sys, 'argv', ['inventory', '--repo', str(repo), '--output', str(output)]):
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as result:
                        inventory_reference.main()
            self.assertEqual(result.exception.code, 2)
            self.assertFalse(output.parent.exists())

    def test_valid_new_output_is_written_and_source_bound(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            repo = self.repo(root)
            (repo / 'README.md').write_text('# Fixture')
            source = self.commit(repo)
            output = root / 'inventory.json'
            with mock.patch.object(sys, 'argv', ['inventory', '--repo', str(repo), '--output', str(output)]):
                with contextlib.redirect_stdout(io.StringIO()):
                    inventory_reference.main()
            self.assertEqual(json.loads(output.read_text())['source_ref'], source)

    def test_cli_refuses_overwriting_retained_inventory(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'inventory.json'
            path.write_bytes(b'retained snapshot')
            result = subprocess.run([sys.executable, str(Path(__file__).with_name('inventory_reference.py')),
                                     '--output', str(path)], capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(path.read_bytes(), b'retained snapshot')


if __name__ == '__main__':
    unittest.main()
