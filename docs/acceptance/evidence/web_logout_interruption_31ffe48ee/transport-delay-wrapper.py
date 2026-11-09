import json
from pathlib import Path
import main_api_app
import core.auth_endpoints as recovery
root=Path(__file__).parent
def capture(*args):
    with (root/'mail.private.jsonl').open('a') as out:
        out.write(json.dumps(args)+'\n')
    return True
recovery.send_smtp_email=capture
import asyncio,time
class DelayedLogout:
    async def __call__(self,scope,receive,send):
        delayed=scope.get('type')=='http' and scope.get('path')=='/api/auth/logout'
        if delayed:
            with (root/'delay-events.jsonl').open('a') as out:out.write(json.dumps({'event':'logout_started','at':time.time()})+'\n')
            await asyncio.sleep(30)
        await main_api_app.app(scope,receive,send)
        if delayed:
            with (root/'delay-events.jsonl').open('a') as out:out.write(json.dumps({'event':'logout_handler_completed','at':time.time()})+'\n')
app=DelayedLogout()
