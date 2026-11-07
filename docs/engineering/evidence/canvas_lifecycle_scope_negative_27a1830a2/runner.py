import os,json,subprocess,tempfile,time,hashlib
from pathlib import Path
w=Path("/private/tmp/atom-oracle-refresh-20261107");root=Path(tempfile.mkdtemp(prefix="root-wait-source-final-review-",dir="/private/tmp"));out=Path("/private/tmp/root-canvas-lifecycle-portable-baseline")
source=subprocess.check_output(["git","rev-parse","HEAD"],cwd=w,text=True).strip();assert subprocess.check_output(["git","rev-parse",source+":backend"],cwd=w,text=True)==subprocess.check_output(["git","rev-parse","8ded00232:backend"],cwd=w,text=True)
proof_files=["backend/api/canvas_routes.py","backend/tools/canvas_crud_tool.py","backend/core/models.py"]
before_bytes={f:hashlib.sha256((w/f).read_bytes()).hexdigest() for f in proof_files}
files=["/private/tmp/atom-current-claim-audit-20261107/docs/engineering/probes/canvas_lifecycle_scope_root_2026_11_07.py"]
env=os.environ.copy();env.update(TESTING="1",DATABASE_URL="sqlite:///"+str(root/"atom.db"),ATOM_DATA_DIR=str(root/"data"),ATOM_OFFICE_DIR=str(root/"office"),LANCEDB_URI=str(root/"lancedb"),SECRET_KEY="synthetic-root-focused-test-key",ATOM_TEST_PYTHON="/Users/rushiparikh/projects/atom/backend/venv314/bin/python")
cmd=["/private/tmp/atom-agent-cli/run_bounded_test_gate.py","--cwd",str(w/"backend"),"--profile","bounded","--","/Users/rushiparikh/projects/atom/backend/venv314/bin/python","-m","pytest",*files,"-q","--tb=short","-p","no:cacheprovider","--basetemp="+str(root/"pytest")]
out.with_suffix(".spec.json").write_text(json.dumps({"source":source,"scratch":str(root),"command":cmd},indent=2))
with out.with_suffix(".log").open("w") as log:r=subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT)
after=subprocess.check_output(["git","rev-parse","HEAD"],cwd=w,text=True).strip();dirty=subprocess.check_output(["git","diff","--name-only",source,"--","backend/core","backend/api",*['backend/'+f for f in files]],cwd=w,text=True).splitlines()
d={"external_diagnostic_probe":True,"source_bytes_before":before_bytes,"source_bytes_after":{f:hashlib.sha256((w/f).read_bytes()).hexdigest() for f in proof_files},"source":source,"head_after":after,"runtime_or_test_diff":dirty,"actual_exit":r.returncode,"scratch":str(root),"finished":time.time()};out.with_suffix(".exit.json").write_text(json.dumps(d,indent=2));print(json.dumps(d));raise SystemExit(r.returncode)
