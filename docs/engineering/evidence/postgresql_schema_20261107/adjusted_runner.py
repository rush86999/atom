import os,sys,json,subprocess,tempfile,time,signal,hashlib
from pathlib import Path
root=Path(tempfile.mkdtemp(prefix='root-pg-schema-',dir='/private/tmp'));os.chmod(root,0o700)
(root/'socket').mkdir(mode=0o700);(root/'home').mkdir(mode=0o700)
env={'PATH':'/usr/local/bin:/usr/bin:/bin','HOME':str(root/'home'),'LANG':'C','LC_ALL':'C','PYTHONDONTWRITEBYTECODE':'1','TESTING':'1','DATABASE_URL':'sqlite:///'+str(root/'safe-import.db'),'ATOM_DATA_DIR':str(root/'app-data'),'ATOM_OFFICE_DIR':str(root/'office'),'LANCEDB_URI':str(root/'lance'),'SECRET_KEY':'synthetic-scratch-pg-test-only'}
os.environ.clear();os.environ.update(env)
r={'scratch':str(root),'scope':'actual main-equivalent ORM metadata on installed PostgreSQL14 private unix-socket cluster; no TCP/live DB/provider','status':'started','postgres_version':subprocess.check_output(['/usr/local/bin/postgres','--version'],text=True).strip(),'crash_durability_qualified':False,'initdb_no_sync':True,'max_locks_per_transaction':512}
proc=None;engine=None;log=None
try:
 with (root/'initdb.log').open('w') as h:
  init=subprocess.run(['/usr/local/bin/initdb','-D',str(root/'data'),'-U','atom_scratch','--auth=trust','--no-locale','--encoding=UTF8','--no-sync'],env=env,stdout=h,stderr=subprocess.STDOUT)
 r['initdb_exit']=init.returncode
 if init.returncode:raise RuntimeError('private_initdb_failed')
 log=(root/'postgres.log').open('w');proc=subprocess.Popen(['/usr/local/bin/postgres','-D',str(root/'data'),'-h','','-k',str(root/'socket'),'-p','55439','-c','shared_buffers=16MB','-c','max_connections=10','-c','max_locks_per_transaction=512'],env=env,stdout=log,stderr=subprocess.STDOUT);r['pid']=proc.pid
 for _ in range(100):
  if proc.poll() is not None:raise RuntimeError('private_postgres_exited_before_ready')
  ready=subprocess.run(['/usr/local/bin/pg_isready','-h',str(root/'socket'),'-p','55439','-U','atom_scratch','-d','postgres'],env=env,capture_output=True)
  if ready.returncode==0:break
  time.sleep(.1)
 else:raise RuntimeError('private_postgres_not_ready')
 import sqlalchemy,psycopg2
 from sqlalchemy import create_engine,text
 from sqlalchemy.engine import URL
 url=URL.create('postgresql+psycopg2',username='atom_scratch',database='postgres',query={'host':str(root/'socket'),'port':'55439'})
 engine=create_engine(url)
 with engine.connect() as c:
  r['server_identity']=c.execute(text("SELECT current_user,current_database(),current_setting('data_directory'),inet_server_addr()::text,version()" )).one()._asdict() if False else list(c.execute(text("SELECT current_user,current_database(),current_setting('data_directory'),inet_server_addr()::text,version()" )).one())
 assert r['server_identity'][2]==str(root/'data') and r['server_identity'][3] is None
 w=Path('/private/tmp/atom-oracle-refresh-20261107');source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=w,text=True).strip();r['checkout_source']=source
 r['model_sha256']=hashlib.sha256((w/'backend/core/models.py').read_bytes()).hexdigest()
 expected=subprocess.check_output(['git','show','8ded00232:backend/core/models.py'],cwd=w);assert (w/'backend/core/models.py').read_bytes()==expected
 sys.path.insert(0,str(w/'backend'))
 import core.models
 from core.models_registration import Base
 r['metadata_table_count']=len(Base.metadata.tables)
 Base.metadata.create_all(engine)
 with engine.connect() as c:r['created_public_tables']=c.execute(text("SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'" )).scalar_one()
 r['status']='schema_created';r['whole_postgresql_qualified']=False
except Exception as e:
 r['status']='failed';r['error_class']=type(e).__name__;r['error_message_first_line']=str(e).splitlines()[0][:400];r['whole_postgresql_qualified']=False
finally:
 if engine:engine.dispose()
 if proc:
  if proc.poll() is None:proc.send_signal(signal.SIGTERM)
  try:r['process_exit']=proc.wait(timeout=20)
  except subprocess.TimeoutExpired:r['process_exit']='still_live_no_kill';r['status']='cleanup_incomplete'
 if log:log.close()
 r['finished']=time.time();(root/'result.json').write_text(json.dumps(r,indent=2)+'\n');Path('/private/tmp/root-pg-schema-lock512-result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
raise SystemExit(0 if r['status']=='schema_created' else 1)
