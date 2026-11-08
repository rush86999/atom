import asyncio,contextvars,importlib.util,json,hashlib
from pathlib import Path
p=Path('/private/tmp/root-public-shared-automation-worker-author-20261108/backend/core/asyncio_compat.py')
spec=importlib.util.spec_from_file_location('candidate_worker_compat',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
async def main():
    marker=contextvars.ContextVar('synthetic_probe',default='missing');marker.set('caller');origin=m.notification_loop_var('synthetic_origin');loop=asyncio.get_running_loop();saved=asyncio.to_thread
    asyncio.to_thread=None
    try:result=await asyncio.wait_for(m.run_sync_in_worker(lambda:(marker.get(),origin.get()),origin),2)
    finally:asyncio.to_thread=saved
    report={'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'caller_context_preserved':result[0]=='caller','origin_loop_preserved':result[1] is loop,'scope':'actual generic executor fallback, no app DB/model'};print(json.dumps(report));assert report['caller_context_preserved'] and report['origin_loop_preserved'], 'executor fallback lost caller context'
asyncio.run(main())
