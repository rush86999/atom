import sys, pathlib, tempfile, shutil, subprocess, os, json, hashlib
script=pathlib.Path(sys.argv[1]);repo=pathlib.Path(sys.argv[2]);exe='/usr/local/opt/python@3.11/bin/python3.11'
root=pathlib.Path(tempfile.mkdtemp(prefix='root-cache-source-probe-',dir='/private/tmp'));core=root/'backend/core';core.mkdir(parents=True)
for name in ['governance_cache.py','asyncio_compat.py']:shutil.copyfile(repo/'backend/core'/name,core/name)
p=core/'governance_cache.py';p.write_text(p.read_text()+"\nSOURCE_ATTESTATION_PROBE = 'old'\n")
subprocess.run([exe,'-c','import py_compile,sys;py_compile.compile(sys.argv[1],doraise=True,invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP)',str(p)],check=True)
st=p.stat();p.write_text(p.read_text().replace("SOURCE_ATTESTATION_PROBE = 'old'","SOURCE_ATTESTATION_PROBE = 'new'"));os.utime(p,ns=(st.st_atime_ns,st.st_mtime_ns))
code="""import importlib.util,sys,json,hashlib
from pathlib import Path
spec=importlib.util.spec_from_file_location('benchmark_probe',sys.argv[1]);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
mod,p,_=m._load_repo_modules(Path(sys.argv[2]));result={'executed_marker':mod.SOURCE_ATTESTATION_PROBE,'expected_marker':'new','reported_disk_sha256':m._file_identity(p)['sha256'],'loaded_sha256':getattr(mod,'__benchmark_loaded_source_sha256__',None),'script_sha256':hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest(),'scope':'actual cache copy plus appended marker; loader integrity only, no performance result'};print(json.dumps(result));assert mod.SOURCE_ATTESTATION_PROBE=='new','stale bytecode was executed'
"""
r=subprocess.run([exe,'-c',code,str(script),str(root)],capture_output=True,text=True,timeout=10);sys.stdout.write(r.stdout);sys.stderr.write(r.stderr);raise SystemExit(r.returncode)
