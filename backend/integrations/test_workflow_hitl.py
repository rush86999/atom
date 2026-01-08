import asyncio
import logging
import sys
import os
import json
from unittest.mock import MagicMock, AsyncMock

# Add the current directory to sys.path
sys.path.append(os.getcwd())

# 1. PRE-MOCK PDFOCRService to avoid heavy imports
mock_ocr_instance = MagicMock()
mock_ocr_instance.process_pdf = AsyncMock(return_value={
    "extracted_content": {"text": "Short ext"}, # Short text to trigger low confidence (60%)
    "success": True
})
mock_pdf_ocr_mod = MagicMock()
mock_pdf_ocr_mod.PDFOCRService.return_value = mock_ocr_instance
sys.modules['integrations.pdf_processing.pdf_ocr_service'] = mock_pdf_ocr_mod
sys.modules['integrations.pdf_processing'] = MagicMock()

from core.database import SessionLocal, engine
from core.models import Workspace, WorkflowExecution, User
from accounting.models import Account, Bill, Transaction
from accounting.seeds import seed_default_accounts
from advanced_workflow_orchestrator import AdvancedWorkflowOrchestrator, WorkflowDefinition, WorkflowStep, WorkflowStepType, WorkflowStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_hitl_flow():
    db = SessionLocal()
    workspace_id = "hitl-test-ws"
    
    try:
        # 1. Setup
        print("--- Phase 1: Setup ---")
        ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()
        if not ws:
            ws = Workspace(id=workspace_id, name="HITL Test")
            db.add(ws)
            db.commit()

        # Clean old data
        db.query(Bill).filter(Bill.workspace_id == workspace_id).delete()
        db.query(Transaction).filter(Transaction.workspace_id == workspace_id).delete()
        db.query(Account).filter(Account.workspace_id == workspace_id).delete()
        from accounting.models import Document as FinancialDocument
        db.query(FinancialDocument).filter(FinancialDocument.workspace_id == workspace_id).delete()
        db.query(WorkflowExecution).filter(WorkflowExecution.workflow_id == "hitl_workflow").delete()
        db.commit()

        seed_default_accounts(db, workspace_id)
        
        # Ensure a test user exists for auth
        user = db.query(User).filter(User.email == "test@example.com").first()
        if not user:
            user = User(email="test@example.com", workspace_id=workspace_id)
            db.add(user)
            db.commit()

        orchestrator = AdvancedWorkflowOrchestrator()
        
        # Create a workflow with high threshold (0.9) but we will return 0.6
        step_id = "process_invoice_hitl"
        wf_def = WorkflowDefinition(
            workflow_id="hitl_workflow",
            name="HITL Verification Workflow",
            description="Test HITL",
            start_step=step_id,
            steps=[
                WorkflowStep(
                    step_id=step_id,
                    step_type=WorkflowStepType.INVOICE_PROCESSING,
                    description="Process with HITL",
                    parameters={"document_id": "doc_123", "workspace_id": workspace_id},
                    confidence_threshold=0.9 # High threshold to trigger HITL
                )
            ]
        )
        orchestrator.workflows[wf_def.workflow_id] = wf_def

        # Create doc record
        from accounting.models import Document
        doc = Document(id="doc_123", workspace_id=workspace_id, file_path="/tmp/fake.pdf", file_name="fake.pdf")
        db.add(doc)
        db.commit()

        # 2. Trigger Workflow
        print("\n--- Phase 2: Triggering Workflow ---")
        input_data = {"document_id": "doc_123", "workspace_id": workspace_id}
        orchestrator.active_contexts = {} # Reset
        
        context = await orchestrator.execute_workflow("hitl_workflow", input_data)
        
        print(f"Workflow Status: {context.status}")
        if context.status == WorkflowStatus.WAITING_APPROVAL:
            print("✅ Workflow correctly paused for approval!")
        else:
            print(f"❌ Workflow failed to pause. Status: {context.status}")
            return

        # 3. Verify Database Persistence
        print("\n--- Phase 3: Verifying Persistence ---")
        execution = db.query(WorkflowExecution).filter(
            WorkflowExecution.execution_id == context.workflow_id
        ).first()
        
        if execution and execution.status == "waiting_approval":
            print(f"✅ Execution persisted in DB with status: {execution.status}")
        else:
            print(f"❌ Execution not found or wrong status in DB: {execution.status if execution else 'None'}")
            return

        # 4. Respond to Approval
        print("\n--- Phase 4: Approving Action ---")
        resumed_context = await orchestrator.resume_workflow(context.workflow_id, step_id)
        
        print(f"Resumed Status: {resumed_context.status}")
        
        if resumed_context.status == WorkflowStatus.COMPLETED:
            print("✅ Workflow resumed and completed successfully!")
        else:
            print(f"❌ Workflow failed to complete. Status: {resumed_context.status}")

        # 5. Verify Ledger
        print("\n--- Phase 5: Ledger Verification ---")
        bill = db.query(Bill).filter(Bill.workspace_id == workspace_id).first()
        if bill:
            print(f"✅ Bill recorded after approval. Amount: {bill.amount}")
        else:
            print("❌ Bill not found after approval!")

        print("\nHITL Flow Verified!")

    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_hitl_flow())
