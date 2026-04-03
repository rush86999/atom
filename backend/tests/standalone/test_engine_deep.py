import asyncio
import logging
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

# Configure logging
logging.basicConfig(level=logging.INFO)

async def main():
    try:
        from ai.automation_engine import AutomationEngine, PlatformType
        print("Successfully imported AutomationEngine")
        
        engine = AutomationEngine()
        print("Successfully initialized AutomationEngine")
        
        # Test connector initialization
        print(f"Platform connectors keys: {len(engine.platform_connectors)}")
        
        # Try to access a connector
        connector = engine.platform_connectors.get(PlatformType.SLACK)
        print(f"Slack connector: {connector}")
        
        # Try to execute a mock action
        result = await engine._mock_platform_connector("test", "entity", {})
        print(f"Mock result: {result}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
