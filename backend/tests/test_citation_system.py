
import asyncio
import os
import shutil
from core.agent_world_model import WorldModelService, BusinessFact
from integrations.mcp_service import mcp_service

async def test_citation_system():
    print("Starting Citation System Test...")
    
    # 1. Setup Dummy Policy File
    test_file_path = "/tmp/test_policy.txt"
    with open(test_file_path, "w") as f:
        f.write("POLICY: All refunds over $500 must be approved by the VP of Finance.")
    
    print(f"Created test policy file at {test_file_path}")
    
    # 2. Test 'save_business_fact' Tool
    print("\nTesting 'save_business_fact' tool...")
    args = {
        "fact": "Refunds > $500 require VP approval",
        "citations": [test_file_path],
        "reason": "Compliance",
        "source": "Initial Audit"
    }
    # Mock context
    context = {"workspace_id": "test_ws", "agent_id": "tester_1"}
    
    # We call via MCP generic call_tool to test routing
    result = await mcp_service.call_tool("save_business_fact", args, context)
    print(f"Save Result: {result}")
    assert "saved" in str(result).lower()
    
    # 3. Test 'verify_citation' Tool
    print("\nTesting 'verify_citation' tool...")
    ver_args = {"path": test_file_path}
    ver_result = await mcp_service.call_tool("verify_citation", ver_args, context)
    print(f"Verify Result: {ver_result}")
    assert "Verified" in str(ver_result)
    assert "POLICY" in str(ver_result)
    
    # 4. Test Knowledge Retrieval (World Model)
    print("\nTesting Retrieval from World Model...")
    wm = WorldModelService("test_ws")
    facts = await wm.get_relevant_business_facts("refund approval")
    
    print(f"Retrieved {len(facts)} facts.")
    for f in facts:
        print(f"- Fact: {f.fact}")
        print(f"  Citations: {f.citations}")
        print(f"  Status: {f.verification_status}")
        
    assert len(facts) > 0
    assert facts[0].fact == args["fact"]
    assert facts[0].citations == args["citations"]
    
    # Cleanup
    if os.path.exists(test_file_path):
        os.remove(test_file_path)
    print("\nTest Complete: SUCCESS")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(test_citation_system())
