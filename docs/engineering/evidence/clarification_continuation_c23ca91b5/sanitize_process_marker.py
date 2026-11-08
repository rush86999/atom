"""Create a labelled derivative; never change the retained raw log.

Only the UUID process-start liveness marker inside owner_process is masked.
This is not a general credential sanitizer. Other bytes/lines are retained.
"""
import hashlib
import json
from pathlib import Path
import re
import sys
import uuid

source, target = map(Path, sys.argv[1:3])
assert source.resolve() != target.resolve() and not target.exists()
raw = source.read_bytes()
pattern = rb"('owner_process':\s*\{[^{}\n]*?'token':\s*')([0-9a-f]{32})(')"
matches = list(re.finditer(pattern, raw))
assert len(matches) == 1
assert uuid.UUID(hex=matches[0].group(2).decode()).version == 4
clean = re.sub(pattern, lambda m: m.group(1) + b"[process-start-marker]" + m.group(3), raw)
assert len(raw.splitlines()) == len(clean.splitlines())
assert sum(a != b for a, b in zip(raw.splitlines(), clean.splitlines())) == 1
with target.open("xb") as out:
    out.write(clean)
print(json.dumps({
    "raw_sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
    "derivative_sha256": "sha256:" + hashlib.sha256(clean).hexdigest(),
    "redacted_marker_sha256": "sha256:" + hashlib.sha256(matches[0].group(2)).hexdigest(),
    "redacted_field": "owner_process.token", "redactions": 1,
    "line_count_unchanged": True, "other_line_bytes_unchanged": True,
}))
