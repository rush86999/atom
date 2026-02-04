import os
import shutil
import uuid
from typing import Any, Dict, List, Optional
from accounting.ap_service import APService
from accounting.categorizer import AICategorizer
from accounting.dashboard_service import AccountingDashboardService
from accounting.export_service import AccountExporter
from accounting.fpa_service import FPAService
from accounting.models import Account, Budget, CategorizationProposal
from accounting.models import Document as FinancialDocument
from accounting.models import Transaction
from accounting.sync_manager import AccountingSyncManager
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from sqlalchemy.orm import Session

from core.auth_endpoints import get_current_user
from core.automation_settings import get_automation_settings
from core.database import get_db

router = APIRouter(prefix="/api/v1/accounting", tags=["Accounting"])

def check_accounting_enabled():
    if not get_automation_settings().is_accounting_enabled():
        raise HTTPException(status_code=403, detail="Accounting automations are disabled.")

@router.get("/accounts")
async def get_accounts(
    workspace_id: str,
    db: Session = Depends(get_db),
    _user = Depends(get_current_user)
):
    check_accounting_enabled()
    accounts = db.query(Account).filter(Account.workspace_id == workspace_id).all()
    return accounts

@router.patch("/accounts/{account_id}/mapping")
async def update_account_mapping(
    account_id: str,
    mapping: Dict[str, str],
    db: Session = Depends(get_db),
    _user = Depends(get_current_user)
):
    check_accounting_enabled()
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    account.standards_mapping = mapping
    db.commit()
    return {"status": "success", "mapping": account.standards_mapping}

@router.get("/proposals")
async def get_pending_proposals(
    workspace_id: str,
    db: Session = Depends(get_db),
    _user = Depends(get_current_user)
):
    check_accounting_enabled()
    proposals = db.query(CategorizationProposal).join(Transaction).filter(
        Transaction.workspace_id == workspace_id,
        CategorizationProposal.is_accepted == False
    ).all()
    return proposals

@router.post("/proposals/{proposal_id}/approve")
async def approve_proposal(
    proposal_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    check_accounting_enabled()
    categorizer = AICategorizer(db)
    success = categorizer.accept_proposal(proposal_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return {"status": "success"}

@router.get("/forecast")
async def get_cash_forecast(
    workspace_id: str,
    db: Session = Depends(get_db),
    _user = Depends(get_current_user)
):
    check_accounting_enabled()
    fpa = FPAService(db)
    forecast = fpa.generate_13_week_forecast(workspace_id)
    return forecast

@router.post("/scenario")
async def run_scenario(
    workspace_id: str,
    scenario_description: str,
    db: Session = Depends(get_db),
    _user = Depends(get_current_user)
):
    check_accounting_enabled()
    fpa = FPAService(db)
    # Note: Description parsing is simple in backend, usually LLM handles this in chat.
    # We'll pass it through to the simple parser in FPAService.
    result = fpa.model_scenario(workspace_id, scenario_description)
    return result

@router.get("/export/gl")
async def export_gl(
    workspace_id: str,
    db: Session = Depends(get_db),
    _user = Depends(get_current_user)
):
    check_accounting_enabled()
    exporter = AccountExporter(db)
    csv_content = exporter.export_general_ledger_csv(workspace_id)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=gl_export_{workspace_id}.csv"}
    )

@router.get("/export/trial-balance")
async def export_trial_balance(
    workspace_id: str,
    db: Session = Depends(get_db),
    _user = Depends(get_current_user)
):
    check_accounting_enabled()
    exporter = AccountExporter(db)
    return exporter.export_trial_balance_json(workspace_id)

@router.post("/sync")
async def trigger_external_sync(
    workspace_id: str,
    platform: str,
    credentials: Dict[str, Any],
    db: Session = Depends(get_db),
    _user = Depends(get_current_user)
):
    check_accounting_enabled()
    sync_manager = AccountingSyncManager(db)
    result = await sync_manager.sync_external_transactions(workspace_id, platform, credentials)
    return result

@router.get("/dashboard/summary")
async def get_accounting_summary(
    workspace_id: str,
    db: Session = Depends(get_db),
    _user = Depends(get_current_user)
):
    check_accounting_enabled()
    service = AccountingDashboardService(db)
    return service.get_financial_summary(workspace_id)

@router.post("/bills/upload")
async def upload_invoice(
    workspace_id: str = Form(...),
    file: UploadFile = File(...),
    expense_account_code: str = Form("5100"),
    db: Session = Depends(get_db),
    _user = Depends(get_current_user)
):
    check_accounting_enabled()
    
    # 1. Save file locally (Simulating cloud storage)
    upload_dir = "/home/developer/projects/atom/backend/data/uploads/invoices"
    os.makedirs(upload_dir, exist_ok=True)
    
    file_id = str(uuid.uuid4())
    file_ext = os.path.splitext(file.filename)[1]
    file_path = os.path.join(upload_dir, f"{file_id}{file_ext}")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # 2. Track in Document table
    doc = FinancialDocument(
        workspace_id=workspace_id,
        file_path=file_path,
        file_name=file.filename,
        file_type="pdf" if file_ext.lower() == ".pdf" else "image"
    )
    db.add(doc)
    db.flush()
    
    # 3. Process with AP Service
    ap_service = APService(db)
    try:
        result = await ap_service.process_invoice_document(
            document_id=doc.id, 
            workspace_id=workspace_id,
            expense_account_code=expense_account_code
        )
        return result
    except Exception as e:
        logger.error(f"Error processing invoice: {e}")
        raise HTTPException(status_code=500, detail=f"Invoice processing failed: {str(e)}")
