import asyncio
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

async def test_phase8():
    print("--- Phase 8 Verification: MCP Service Extension ---")
    
    from integrations.mcp_service import mcp_service
    
    # 1. Verify new tools are registered
    print("\n1. Verifying new platform tools are registered...")
    tools = await mcp_service.get_server_tools("local-tools")
    
    tool_names = [t["name"] for t in tools]
    expected_tools = ["send_telegram_message", "send_whatsapp_message", "create_zoom_meeting", "get_zoom_meetings"]
    
    for tool in expected_tools:
        if tool in tool_names:
            print(f"✓ {tool} registered in MCP")
        else:
            print(f"✗ {tool} NOT found in MCP")
    
    # 2. Test tool calling infrastructure (without real execution)
    print("\n2. Testing tool call infrastructure...")
    
    # Test that call_tool routes correctly to new tools
    tools_from_all = await mcp_service.get_all_tools()
    all_names = [t["name"] for t in tools_from_all]
    
    for tool in expected_tools:
        if tool in all_names:
            print(f"✓ {tool} available via get_all_tools()")
        else:
            print(f"✗ {tool} NOT in get_all_tools()")
    
    # 3. Test agent access via MCPCapableMixin
    print("\n3. Verifying agent access via MCPCapableMixin...")
    from core.base_agent_mixin import MCPCapableMixin
    
    class TestAgent(MCPCapableMixin):
        pass
    
    agent = TestAgent()
    agent_tools = await agent.mcp.get_server_tools("local-tools")
    agent_tool_names = [t["name"] for t in agent_tools]
    
    if "send_telegram_message" in agent_tool_names:
        print("✓ Agent can access Telegram tools via mcp property")
    else:
        print("✗ Agent cannot access new tools")
    
    print("\n--- Phase 8 Verification Complete ---")

if __name__ == "__main__":
    asyncio.run(test_phase8())
