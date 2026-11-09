"""Exercise the actual setup helper using temporary files, never installed settings."""
import importlib.util
from pathlib import Path
import stat
import unittest
import tempfile

spec=importlib.util.spec_from_file_location('web_setup',Path(__file__).resolve().parents[1]/'setup_web_auth.py')
setup=importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class WebAuthSetupTests(unittest.TestCase):
    def setUp(self):
        self.world=tempfile.TemporaryDirectory()
        self.addCleanup(self.world.cleanup)
        self.tmp_path=Path(self.world.name)

    def test_fresh_web_key_is_private_persistent_and_distinct(self):
        tmp_path=self.tmp_path
        a=tmp_path/'a'/'.env.local';b=tmp_path/'b'/'.env.local'
        assert setup.configure(a)
        first=a.read_bytes()
        assert b'NEXT_PUBLIC_API_URL=http://localhost:8001' in first
        assert b'NEXTAUTH_URL=http://localhost:3000' in first
        assert not setup.configure(a)
        assert a.read_bytes()==first
        assert stat.S_IMODE(a.stat().st_mode)==0o600
        assert setup.configure(b)
        assert b.read_bytes()!=first


    def test_existing_quoted_key_and_remote_backend_are_preserved(self):
        tmp_path=self.tmp_path
        p=tmp_path/'.env.local'
        original="NEXTAUTH_SECRET='existing-owned-private-key'\nAPI_BASE_URL=https://backend.example.invalid\nNEXTAUTH_URL=https://web.example.invalid\n# keep this\n"
        p.write_text(original)
        assert not setup.configure(p)
        assert p.read_text()==original


    def test_missing_key_adds_without_overwriting_other_configuration(self):
        tmp_path=self.tmp_path
        p=tmp_path/'.env.local';p.write_text('UNRELATED=value\nNEXT_PUBLIC_API_URL=http://127.0.0.1:18000\n')
        assert setup.configure(p)
        text=p.read_text()
        assert text.startswith('UNRELATED=value\nNEXT_PUBLIC_API_URL=http://127.0.0.1:18000\n')
        assert 'NEXTAUTH_SECRET=' in text
        assert 'localhost:8001' not in text


    def test_public_placeholder_is_replaced_once(self):
        tmp_path=self.tmp_path
        p=tmp_path/'.env.local';p.write_text('NEXTAUTH_SECRET=your-secret-key-change-in-production\n')
        assert setup.configure(p)
        assert not setup.configure(p)


    def test_symlink_configuration_is_refused_without_touching_target(self):
        tmp_path=self.tmp_path
        target=tmp_path/'target';target.write_text('keep')
        link=tmp_path/'.env.local';link.symlink_to(target)
        with self.assertRaises(ValueError):setup.configure(link)
        assert target.read_text()=='keep'

    def test_duplicate_keys_refuse_without_rotating_existing_material(self):
        for suffix in ['', 'your-secret-key-change-in-production']:
            p=self.tmp_path/('duplicate-'+str(len(suffix)))
            original='NEXTAUTH_SECRET=existing-private-material\nNEXTAUTH_SECRET='+suffix+'\n'
            p.write_text(original)
            with self.assertRaises(ValueError):setup.configure(p)
            assert p.read_text()==original

    def test_lock_symlink_is_refused_without_touching_target(self):
        p=self.tmp_path/'.env.local';target=self.tmp_path/'target';target.write_text('keep')
        (self.tmp_path/'.env.local.setup.lock').symlink_to(target)
        with self.assertRaises(OSError):setup.configure(p)
        assert target.read_text()=='keep'
        assert not p.exists()
