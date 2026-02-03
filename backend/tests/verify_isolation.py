import asyncio
import os
import shutil

from core.lancedb_handler import get_lancedb_handler


async def verify_isolation():
    print("Verifying Memory Isolation...")
    
    # 1. Workspace A
    ws_a = "business_apple"
    handler_a = get_lancedb_handler(ws_a)
    handler_a.add_document("documents", "Secret project for Apple: iCar 2026", source="confidential")
    
    # 2. Workspace B
    ws_b = "business_banana"
    handler_b = get_lancedb_handler(ws_b)
    handler_b.add_document("documents", "Banana smoothie recipes for Q3", source="internal")
    
    # 3. Verify Physical Separation
    path_a = f"./data/atom_memory/{ws_a}"
    path_b = f"./data/atom_memory/{ws_b}"
    
    print(f"Path A exists: {os.path.exists(path_a)}")
    print(f"Path B exists: {os.path.exists(path_b)}")
    
    # 4. Verify Search Isolation
    results_a = handler_a.search("documents", "recipes")
    results_b = handler_b.search("documents", "iCar")
    
    print(f"Results in A for 'recipes': {len(results_a)}")
    print(f"Results in B for 'iCar': {len(results_b)}")
    
    # Assertions
    assert len(results_a) == 0, "Business Apple should NOT see Banana recipes!"
    assert len(results_b) == 0, "Business Banana should NOT see Apple secrets!"
    
    print("Isolation Verification PASSED!")

if __name__ == "__main__":
    # Clean up old test data if exists
    if os.path.exists("./data/atom_memory/business_apple"):
        shutil.rmtree("./data/atom_memory/business_apple")
    if os.path.exists("./data/atom_memory/business_banana"):
        shutil.rmtree("./data/atom_memory/business_banana")
        
    asyncio.run(verify_isolation())
