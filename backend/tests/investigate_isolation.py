
import os
import shutil
import sys
import unittest

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.lancedb_handler import get_lancedb_handler


class TestIsolation(unittest.TestCase):
    def setUp(self):
        # Clean up test data
        if os.path.exists("./data/atom_memory/test_ws_1"):
            shutil.rmtree("./data/atom_memory/test_ws_1")
        if os.path.exists("./data/atom_memory/test_ws_2"):
            shutil.rmtree("./data/atom_memory/test_ws_2")

    def test_physical_isolation(self):
        print("\n🧪 Testing Physical Isolation...")
        
        # Mock embedding function to return dummy vector
        # Size 384 for default local model
        dummy_vector = [0.1] * 384 
        
        # 1. Store data in Workspace 1
        h1 = get_lancedb_handler("test_ws_1")
        h1.embed_text = lambda x: dummy_vector # Mock embedding
        h1.add_document("docs", "Secret for WS1", metadata={"secret": True})
        
        # 2. Store data in Workspace 2
        h2 = get_lancedb_handler("test_ws_2")
        h2.embed_text = lambda x: dummy_vector # Mock embedding
        h2.add_document("docs", "Secret for WS2", metadata={"secret": True})
        
        # 3. Search in WS1
        # Need to fix the lambda to return numpy array if possible, or just list if handler accepts it
        # The handler converts to list if has tolist(), so list is fine provided Pydantic model accepts it
        # Actually Pydantic model expects list[float]
        
        # Wait, the search method calls embed_text which returns numpy array usually.
        # But `table.search()` accepts list or numpy.
        
        import numpy as np
        h1.embed_text = lambda x: np.array(dummy_vector)
        h2.embed_text = lambda x: np.array(dummy_vector)
        
        results1 = h1.search("docs", "Secret", limit=10)
        # Handle case where results might be empty if add failed silently (though logs would show)
        if not results1:
            print("⚠️ WS1 returned no results. Check insertion logic.")
        
        texts1 = [r['text'] for r in results1]
        print(f"WS1 Results: {texts1}")
        
        self.assertIn("Secret for WS1", texts1)
        self.assertNotIn("Secret for WS2", texts1)
        
        # 4. Search in WS2
        results2 = h2.search("docs", "Secret", limit=10)
        texts2 = [r['text'] for r in results2]
        print(f"WS2 Results: {texts2}")
        
        self.assertIn("Secret for WS2", texts2)
        self.assertNotIn("Secret for WS1", texts2)
        
        print("✅ Physical Isolation Verified (Separate DB Paths work)")

if __name__ == "__main__":
    unittest.main()
