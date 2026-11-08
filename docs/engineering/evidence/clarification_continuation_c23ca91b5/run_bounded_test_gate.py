#!/usr/bin/env python3
"""Local development test serialization; never changes product policy or test results."""
import argparse,fcntl,json,os,shutil,subprocess,sys,time,signal
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--cwd',required=True);p.add_argument('--profile',choices=['heavy','bounded'],default='heavy');p.add_argument('command',nargs=argparse.REMAINDER);a=p.parse_args()
cmd=a.command
if cmd and cmd[0]=='--':cmd=cmd[1:]
if not cmd:p.error('test command required after --')
root=Path('/private/tmp/atom-agent-cli');root.mkdir(exist_ok=True)
with (root/'heavy-test-gate.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 free=shutil.disk_usage(a.cwd).free
 minimum=(4 if a.profile=='heavy' else 2)*1024**3
 if free<minimum:
  print(json.dumps({'status':'not_dispatched_disk_headroom','free_bytes':free,'minimum_bytes':minimum,'profile':a.profile}),flush=True);sys.exit(75)
 record={'owner_pid':os.getpid(),'cwd':a.cwd,'started':time.time(),'status':'running','free_before':free,'profile':a.profile,'minimum_bytes':minimum}
 state=root/'heavy-test-gate.json';state.write_text(json.dumps(record)+'\n')
 try:
  child=subprocess.Popen(cmd,cwd=a.cwd,pass_fds=(lock.fileno(),))
  def forward(signum,frame):
   if child.poll() is None:child.send_signal(signum)
  signal.signal(signal.SIGINT,forward);signal.signal(signal.SIGTERM,forward)
  child.wait()
  result=child
  record.update(status='completed',actual_exit=result.returncode,finished=time.time(),free_after=shutil.disk_usage(a.cwd).free);state.write_text(json.dumps(record)+'\n')
  sys.exit(result.returncode)
 except BaseException as exc:
  if isinstance(exc,SystemExit):raise
  record.update(status='interrupted_or_launch_error',error_class=type(exc).__name__,finished=time.time());state.write_text(json.dumps(record)+'\n');raise
