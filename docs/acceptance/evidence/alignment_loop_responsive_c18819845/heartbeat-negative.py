import asyncio, importlib.util, json, threading, types
from pathlib import Path
path=Path('/private/tmp/atom-governance-cache-reproducer-20261108/backend/core/org_politics_automation.py')
import sys
sys.path.insert(0,str(path.parents[1]))
spec=importlib.util.spec_from_file_location('probe_org_automation',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
async def main():
    loop=asyncio.get_running_loop();heartbeat=threading.Event();observed=[];ticks=0
    real_sleep=asyncio.sleep
    async def controlled_tick(seconds):
        nonlocal ticks
        ticks+=1
        if ticks>1:raise asyncio.CancelledError()
        await real_sleep(0)
    def bounded_pass():
        loop.call_soon_threadsafe(heartbeat.set)
        observed.append(heartbeat.wait(0.3))
    m.asyncio=types.SimpleNamespace(sleep=controlled_tick,CancelledError=asyncio.CancelledError)
    m.automation_interval_min=lambda:0.5
    m.run_auto_certification=bounded_pass
    await m.org_politics_automation_loop()
    await real_sleep(0)
    result={'source':'d9a45f559033e4f6ae9a2e50725ade3cddfb2b4b','heartbeat_during_pass':observed,'scope':'real loop; bounded pass double; no DB/model/provider'}
    print(json.dumps(result))
    assert observed==[True], 'synchronous certification pass blocked the application event loop'
asyncio.run(main())
