import hashlib, io, json, os, tarfile, tempfile
from pathlib import Path
from core.runtime_identity import capture_runtime_identity
world=Path(tempfile.mkdtemp(prefix='root-export-identity-drift-',dir='/private/tmp'))
code=world/'code'; backend=code/'backend'; backend.mkdir(parents=True)
app=backend/'app.py'; app.write_text('VALUE = 1\n')
farm=world/'backend_root'; farm.mkdir(); (farm/'app.py').symlink_to(app)
manifest={'backend/app.py':hashlib.sha256(app.read_bytes()).hexdigest()}
(world/'code_manifest.json').write_text(json.dumps(manifest))
b=io.BytesIO()
with tarfile.open(fileobj=b,mode='w') as t:t.add(app,arcname='backend/app.py')
(world/'MANIFEST.json').write_text(json.dumps({'code_archive_sha256':hashlib.sha256(b.getvalue()).hexdigest()}))
first=capture_runtime_identity(cwd=str(farm))
app.write_text('VALUE = 2\n')
second=capture_runtime_identity(cwd=str(farm))
r={'scope':'working draft runtime identity; actual code changes with retained original manifest','first':{'kind':first.identity_kind,'source_id':first.source_id,'error':first.error},'after_drift':{'kind':second.identity_kind,'source_id':second.source_id,'error':second.error},'same_id_after_changed_bytes':first.source_id==second.source_id,'accepted_changed_export':second.identity_kind=='export' and second.error is None}
Path('/private/tmp/brennan-brief/EXPORTED_IDENTITY_DRIFT_ROOT_PROBE.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r))
assert not r['accepted_changed_export'] or not r['same_id_after_changed_bytes'], 'Changed exported code must not retain verified clean export identity'
