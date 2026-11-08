import ast,asyncio,hashlib,json,logging,threading,types
from pathlib import Path
ROOT=Path('/private/tmp/atom-alignment-loop-responsive-20261108')
CASES=[('backend/core/llm/stage_router_automation.py','stage_router_automation_loop'),('backend/core/fleet_orchestration/fleet_router_automation.py','fleet_router_automation_loop')]
async def check(relative,name):
    p=ROOT/relative;source=p.read_bytes();tree=ast.parse(source);node=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name==name)
    loop=asyncio.get_running_loop();heartbeat=threading.Event();seen=[];ticks=0;real_sleep=asyncio.sleep
    async def tick(seconds):
        nonlocal ticks
        ticks+=1
        if ticks>1:raise asyncio.CancelledError()
        await real_sleep(0)
    def controlled_pass():
        loop.call_soon_threadsafe(heartbeat.set);seen.append(heartbeat.wait(0.3))
    ns={'asyncio':types.SimpleNamespace(sleep=tick,CancelledError=asyncio.CancelledError),'logger':logging.getLogger(name),'_INTERVAL_MIN':0.5,'_interval_min':0.5,'run_auto_certification':controlled_pass}
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(p),'exec'),ns)
    try:await ns[name]()
    except asyncio.CancelledError:pass
    return {'path':relative,'source_sha256':hashlib.sha256(source).hexdigest(),'function':name,'heartbeat_during_pass':seen,'scope':'exact production loop AST executed with bounded pass/timer doubles; not full module startup'}
async def main():
    result=[await check(*case) for case in CASES];print(json.dumps(result));assert all(r['heartbeat_during_pass']==[True] for r in result),'router loops blocked their event loop'
asyncio.run(main())
