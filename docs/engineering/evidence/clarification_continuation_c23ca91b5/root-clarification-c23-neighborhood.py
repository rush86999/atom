import os,json,subprocess,tempfile,time,hashlib
from pathlib import Path
w=Path('/private/tmp/atom-clarification-continuation-20261108');source='c23ca91b51aa92f737ad62a845e24e477c5844e8';assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=w,text=True).strip()==source
root=Path(tempfile.mkdtemp(prefix='root-feedback-sqlite-',dir='/private/tmp'));out=Path('/private/tmp/root-clarification-c23-neighborhood');files=['tests/test_root_clarification_continuation.py','tests/test_assignment_external_reply_identity.py','tests/test_assignment_gap_reply_identity.py','tests/test_root_gap_operation_settlement_guard.py']
env=os.environ.copy();env['PYTHONPATH']='/private/tmp/root-py311-plugins';env.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_DATASETS_OFFLINE='1');
for key in list(env):
 if key.endswith(('_API_KEY','_ACCESS_TOKEN')) or key.startswith('AWS_'): env.pop(key,None)
env.update(ATOM_BPE_DATA_DIR=str(root/'bpe'),TESTING='1',DATABASE_URL='sqlite:///'+str(root/'atom.db'),ATOM_DATA_DIR=str(root/'data'),ATOM_OFFICE_DIR=str(root/'office'),LANCEDB_URI=str(root/'lance'),ATOM_OUTPUT_DIR=str(root/'output'),SECRET_KEY='synthetic-feedback-dialect-tests-only',PYTHONDONTWRITEBYTECODE='1')
cmd=['/private/tmp/atom-agent-cli/run_bounded_test_gate.py','--cwd',str(w/'backend'),'--profile','bounded','--','/Users/rushiparikh/projects/atom/backend/venv314/bin/python','-m','pytest',*files,'-q','--tb=short','-p','no:cacheprovider','-p','root_no_network','-p','no:randomly','-p','no:rerunfailures','--timeout=120','--timeout-method=thread','--basetemp='+str(root/'pytest')]
out.with_suffix('.spec.json').write_text(json.dumps({'source':source,'root':str(root),'command':cmd},indent=2))
with out.with_suffix('.log').open('w') as log:r=subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT)
out.with_suffix('.exit.json').write_text(json.dumps({'source':source,'exit':r.returncode,'finished':time.time(),'head_after':subprocess.check_output(['git','rev-parse','HEAD'],cwd=w,text=True).strip()},indent=2));print('Actual SQLite feedback gate exit:',r.returncode);raise SystemExit(r.returncode)
