import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))


import asyncio
from ai.lux_model import get_lux_model

async def main():
    lux = await get_lux_model()
    result = await lux.execute_command("open calculator")
    print(result)

asyncio.run(main())
