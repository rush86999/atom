import os,json,subprocess,tempfile,time,hashlib
from pathlib import Path
w=Path('/private/tmp/atom-feedback-postgres-20261107');source='bdd48960b34c48b45756ae30f288a62cb94953c9';assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=w,text=True).strip()==source
root=Path(tempfile.mkdtemp(prefix='root-feedback-sqlite-',dir='/private/tmp'));out=Path('/private/tmp/root-feedback-sqlite-bdd');files=['tests/test_employee_business_feedback.py','tests/test_employee_feedback_interleaving.py','tests/test_feedback_cas_dialect_contract.py']
env=os.environ.copy();env.update(TESTING='1',DATABASE_URL='sqlite:///'+str(root/'atom.db'),ATOM_DATA_DIR=str(root/'data'),ATOM_OFFICE_DIR=str(root/'office'),LANCEDB_URI=str(root/'lance'),ATOM_OUTPUT_DIR=str(root/'output'),SECRET_KEY='synthetic-feedback-dialect-tests-only',PYTHONDONTWRITEBYTECODE='1')
cmd=['/private/tmp/atom-agent-cli/run_bounded_test_gate.py','--cwd',str(w/'backend'),'--profile','bounded','--','/Users/rushiparikh/projects/atom/backend/venv314/bin/python','-m','pytest',*files,'-q','--tb=short','-p','no:cacheprovider','--basetemp='+str(root/'pytest')]
out.with_suffix('.spec.json').write_text(json.dumps({'source':source,'root':str(root),'command':cmd},indent=2))
with out.with_suffix('.log').open('w') as log:r=subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT)
out.with_suffix('.exit.json').write_text(json.dumps({'source':source,'exit':r.returncode,'finished':time.time(),'head_after':subprocess.check_output(['git','rev-parse','HEAD'],cwd=w,text=True).strip()},indent=2));print('Actual SQLite feedback gate exit:',r.returncode);raise SystemExit(r.returncode)
