"""Pin storage paths to absolute (repo-root) locations in the .env files.

DATABASE_URL/LANCEDB_URI/LANCEDB_PATH/BYOK_ENC_KEY_FILE are CWD-relative, which
caused the app to silently create two SQLite DBs + two LanceDB stores + two
encryption keys depending on where uvicorn was launched. This rewrites those
keys (in-place, preserving every other line incl. secrets) so the server uses
one canonical storage location regardless of the launch directory.

Only touches the four keys above; never prints or logs secret values.
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(ROOT, "atom_dev.db").replace("\\", "/")
LANCEDB = os.path.join(ROOT, "data", "atom_memory").replace("\\", "/")
KEYFILE = os.path.join(ROOT, "data", "byok_encryption_key").replace("\\", "/")

TARGETS = {
    "DATABASE_URL": f"sqlite:///{DB_PATH}",
    "LANCEDB_URI": LANCEDB,
    "LANCEDB_PATH": LANCEDB,
    "BYOK_ENC_KEY_FILE": KEYFILE,
}

FILES = [os.path.join(ROOT, "backend", ".env"), os.path.join(ROOT, ".env")]


def rewrite(path: str) -> bool:
    if not os.path.exists(path):
        print(f"skip {path} (missing)")
        return False
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    changed = False
    out = []
    present = {k: False for k in TARGETS}
    for line in lines:
        matched = False
        for key, value in TARGETS.items():
            if re.match(rf"^{re.escape(key)}\s*=", line):
                out.append(f"{key}={value}\n")
                present[key] = True
                changed = True
                matched = True
                break
        if not matched:
            out.append(line)
    for key, value in TARGETS.items():
        if not present[key]:
            out.append(f"\n# Pinned to canonical repo-root storage (CWD-independent)\n{key}={value}\n")
            changed = True

    if changed:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.writelines(out)
    print(f"{'updated' if changed else 'unchanged'} {path}")
    return True


def main() -> int:
    for p in FILES:
        rewrite(p)
    # Print only the four keys we touched (values are paths, not secrets).
    for p in FILES:
        if not os.path.exists(p):
            continue
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                key = line.split("=", 1)[0].strip()
                if key in TARGETS:
                    print(f"{os.path.relpath(p, ROOT)}: {line.strip()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
