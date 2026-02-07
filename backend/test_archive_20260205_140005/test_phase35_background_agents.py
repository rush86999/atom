import asyncio
import os
import sys
import unittest
from datetime import datetime

sys.path.append(os.getcwd())

from core.background_agent_runner import AgentStatus, BackgroundAgentRunner


class TestPhase35BackgroundAgents(unittest.IsolatedAsyncioTestCase):

    def test_register_agent(self):
        print("\n--- Phase 35: Register Agent Test ---")
        
        runner = BackgroundAgentRunner(log_dir="/tmp/test_agent_logs")
        runner.register_agent("test-agent", interval_seconds=60)
        
        status = runner.get_status("test-agent")
        
        self.assertEqual(status["agent_id"], "test-agent")
        self.assertEqual(status["status"], "stopped")
        print("✅ Agent registered successfully")

    def test_logging(self):
        print("\n--- Phase 35: Logging Test ---")
        
        runner = BackgroundAgentRunner(log_dir="/tmp/test_agent_logs")
        runner.register_agent("log-test-agent", interval_seconds=30)
        
        logs = runner.get_logs("log-test-agent")
        
        self.assertTrue(len(logs) > 0)
        self.assertEqual(logs[0]["event"], "registered")
        print(f"✅ Logged {len(logs)} events")

    async def test_start_stop(self):
        print("\n--- Phase 35: Start/Stop Test ---")
        
        runner = BackgroundAgentRunner(log_dir="/tmp/test_agent_logs")
        runner.register_agent("lifecycle-agent", interval_seconds=1)
        
        await runner.start_agent("lifecycle-agent")
        status = runner.get_status("lifecycle-agent")
        self.assertEqual(status["status"], "running")
        print("✅ Agent started")
        
        await asyncio.sleep(0.1)  # Brief pause
        
        await runner.stop_agent("lifecycle-agent")
        status = runner.get_status("lifecycle-agent")
        self.assertEqual(status["status"], "stopped")
        print("✅ Agent stopped")

if __name__ == "__main__":
    unittest.main()
