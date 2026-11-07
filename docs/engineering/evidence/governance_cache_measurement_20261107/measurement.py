import os,sys,json,time,statistics,platform,hashlib,subprocess,math
from pathlib import Path
w=Path('/private/tmp/atom-oracle-refresh-20261107');source='8ded00232c30961a990e675e06ec672ef6a43910'
p=w/'backend/core/governance_cache.py';expected=subprocess.check_output(['git','show',source+':backend/core/governance_cache.py'],cwd=w);assert p.read_bytes()==expected
sys.path.insert(0,str(w/'backend'))
from core.governance_cache import GovernanceCache
cache=GovernanceCache(max_size=1000,ttl_seconds=3600)
for i in range(100):assert cache.set(f'fixture-{i}','read',{'allowed':bool(i%2),'fixture':i})
for i in range(10000):assert cache.get(f'fixture-{i%100}','read')['fixture']==i%100
clock=[];latency=[];miss=[]
for _ in range(50000):
 t=time.perf_counter_ns();clock.append(time.perf_counter_ns()-t)
for i in range(50000):
 t=time.perf_counter_ns();v=cache.get(f'fixture-{i%100}','read');latency.append(time.perf_counter_ns()-t);assert v['fixture']==i%100
for i in range(10000):
 t=time.perf_counter_ns();v=cache.get(f'absent-{i}','read');miss.append(time.perf_counter_ns()-t);assert v is None
rates=[]
for batch in range(5):
 t=time.perf_counter_ns()
 for i in range(200000):
  v=cache.get(f'fixture-{i%100}','read')
  if v is None or v['fixture']!=i%100:raise AssertionError('wrong cached result')
 elapsed=(time.perf_counter_ns()-t)/1e9;rates.append({'batch':batch,'operations':200000,'elapsed_seconds':elapsed,'ops_per_second':200000/elapsed})
def percentiles(xs):
 a=sorted(xs);return {'n':len(a),'p50_ns':a[math.ceil(.5*len(a))-1],'p95_ns':a[math.ceil(.95*len(a))-1],'p99_ns':a[math.ceil(.99*len(a))-1],'max_ns':a[-1]}
r={'source':source,'actual_checkout_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=w,text=True).strip(),'source_file':'backend/core/governance_cache.py','source_sha256':hashlib.sha256(expected).hexdigest(),'scope':'sync GovernanceCache get only,100 seeded in-memory fixture keys, no DB/API/full governance/model work','method':'perf_counter_ns nearest-rank percentiles; raw clock overhead reported not subtracted;10000warmup;5 independent timed batches200000each include key formatting and result identity check','environment':{'python':sys.version,'platform':platform.platform(),'machine':platform.machine(),'logical_cpus':os.cpu_count(),'clock':time.get_clock_info('perf_counter')._asdict() if hasattr(time.get_clock_info('perf_counter'),'_asdict') else str(time.get_clock_info('perf_counter'))},'clock_overhead':percentiles(clock),'warm_cache_hit':percentiles(latency),'uncached_key_miss':percentiles(miss),'throughput_batches':rates,'median_ops_per_second':statistics.median(x['ops_per_second'] for x in rates),'cache_correctness_stats':cache.get_stats(),'full_governance_p99_qualified':False,'historical_scores_changed':False}
Path('/private/tmp/root-governance-cache-measurement.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
