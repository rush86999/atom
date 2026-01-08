import sys
import os
import unittest
from datetime import datetime, timedelta

sys.path.append(os.getcwd())

from core.workflow_metrics import WorkflowMetrics, ExecutionRecord

class TestPhase34Analytics(unittest.TestCase):

    def test_record_execution(self):
        print("\n--- Phase 34: Record Execution Test ---")
        
        metrics = WorkflowMetrics()
        
        now = datetime.now()
        metrics.record_execution(
            execution_id="exec-001",
            workflow_id="wf-test",
            status="completed",
            started_at=now - timedelta(seconds=5),
            completed_at=now,
            steps_executed=3,
            template_id="template-abc"
        )
        
        summary = metrics.get_summary(days=1)
        
        self.assertEqual(summary["total_executions"], 1)
        self.assertEqual(summary["success_rate"], 100.0)
        print(f"✅ Recorded 1 execution. Success rate: {summary['success_rate']}%")

    def test_summary_aggregation(self):
        print("\n--- Phase 34: Summary Aggregation Test ---")
        
        metrics = WorkflowMetrics()
        now = datetime.now()
        
        # Record multiple executions
        for i in range(10):
            status = "completed" if i < 8 else "failed"
            metrics.record_execution(
                execution_id=f"exec-{i}",
                workflow_id="wf-bulk",
                status=status,
                started_at=now - timedelta(seconds=10),
                completed_at=now,
                steps_executed=5,
                template_id="sales-pipeline",
                retries_used=1 if i % 3 == 0 else 0
            )
        
        summary = metrics.get_summary(days=1)
        
        self.assertEqual(summary["total_executions"], 10)
        self.assertEqual(summary["success_rate"], 80.0)  # 8/10
        print(f"✅ Summary: {summary['total_executions']} executions, {summary['success_rate']}% success")

    def test_workflow_stats(self):
        print("\n--- Phase 34: Workflow Stats Test ---")
        
        metrics = WorkflowMetrics()
        now = datetime.now()
        
        metrics.record_execution(
            execution_id="exec-a",
            workflow_id="special-workflow",
            status="completed",
            started_at=now - timedelta(seconds=2),
            completed_at=now,
            steps_executed=2
        )
        
        stats = metrics.get_workflow_stats("special-workflow")
        
        self.assertEqual(stats["workflow_id"], "special-workflow")
        self.assertEqual(stats["executions"], 1)
        print(f"✅ Workflow stats: {stats}")

if __name__ == "__main__":
    unittest.main()
