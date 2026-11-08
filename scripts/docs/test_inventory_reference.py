"""Boundary tests: inventory is immutable-source metadata, not certification."""
import json
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
