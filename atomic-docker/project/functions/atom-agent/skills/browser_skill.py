import asyncio
from browser_use import Agent
from browser_use.llm import ChatOpenAI
import os
import sys

async def main(task):
    agent = Agent(
        task=task,
        llm=ChatOpenAI(model="o4-mini", temperature=1.0, api_key=os.environ.get("OPENAI_API_KEY")),
    )
    await agent.run()

if __name__ == "__main__":
    task = " ".join(sys.argv[1:])
    asyncio.run(main(task))
