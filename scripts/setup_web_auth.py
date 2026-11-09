"""Quickstart-owned persistent web configuration. Never prints credential material."""
import argparse
import fcntl
import os
from pathlib import Path
import re
import secrets
import stat
import tempfile


def configure(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError('web configuration must be a regular owned file')
    lock_path = path.parent / (path.name + '.setup.lock')
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    if not stat.S_ISREG(os.fstat(lock_fd).st_mode) or os.fstat(lock_fd).st_uid != os.getuid():
        os.close(lock_fd)
        raise ValueError('web setup lock is not an owned regular file')
    with os.fdopen(lock_fd, 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        text = ''
        if path.exists() or path.is_symlink():
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd) as source:
                info = os.fstat(source.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
                    raise ValueError('web configuration is not an owned regular file')
                text = source.read()
        values = {}
        managed = {'NEXTAUTH_SECRET', 'NEXTAUTH_URL', 'NEXT_PUBLIC_API_URL', 'API_BASE_URL', 'PYTHON_BACKEND_URL'}
        for line in text.splitlines():
            match = re.match(r'^\s*(?:export\s+)?([A-Z_]+)\s*=\s*(.*?)\s*$', line)
            if match:
                if match.group(1) in managed and match.group(1) in values:
                    raise ValueError('duplicate web configuration key; resolve explicitly without rotating credentials')
                value = match.group(2)
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                values[match.group(1)] = value
        additions = []
        if not values.get('NEXTAUTH_SECRET', '').strip() or values['NEXTAUTH_SECRET'] == 'your-secret-key-change-in-production':
            text = re.sub(r'^\s*(?:export\s+)?NEXTAUTH_SECRET\s*=.*(?:\n|$)', '', text, flags=re.MULTILINE)
            additions.append('NEXTAUTH_SECRET=' + secrets.token_urlsafe(48))
        if not any(values.get(key, '').strip() for key in ['NEXT_PUBLIC_API_URL', 'API_BASE_URL', 'PYTHON_BACKEND_URL']):
            additions.append('NEXT_PUBLIC_API_URL=http://localhost:8001')
        if not values.get('NEXTAUTH_URL', '').strip():
            additions.append('NEXTAUTH_URL=http://localhost:3000')
        if not additions:
            return False
        result = text + ('\n' if text and not text.endswith('\n') else '') + '\n'.join(additions) + '\n'
        fd, temporary = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
        try:
            with os.fdopen(fd, 'w') as out:
                out.write(result)
                out.flush()
                os.fsync(out.fileno())
            os.replace(temporary, path)
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, required=True)
    args = parser.parse_args()
    changed = configure(args.env_file)
    print('Web authentication configuration ready' + (' (updated)' if changed else ' (preserved)'))
