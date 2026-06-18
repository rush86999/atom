import os
import shutil
import logging
from typing import Any, Dict, List, Optional
import uuid
from accounting.ap_service import APService
from accounting.categorizer import AICategorizer
from accounting.dashboard_service import AccountingDashboardService
from accounting.export_service import AccountExporter
from accounting.fpa_service import FPAService
from accounting.models import (
    Account,
    Budget,
    CategorizationProposal,
    Document as FinancialDocument,
    Transaction,
)
from accounting.sync_manager import AccountingSyncManager
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from sqlalchemy.orm import Session
from werkzeug.utils import secure_filename

from core.auth_endpoints import get_current_user
from core.automation_settings import get_automation_settings
from core.database import get_db

router = APIRouter(prefix="/api/v1/accounting", tags=["Accounting"])
logger = logging.getLogger(__name__)

# ============================================================================
# File Upload Security Configuration
# ============================================================================

# Maximum file size: 10MB
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB in bytes

# Allowed file extensions - whitelist approach
ALLOWED_EXTENSIONS = {'.pdf', '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff'}

# File extension to MIME type mapping for validation
MIME_TYPES = {
    '.pdf': 'application/pdf',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.bmp': 'image/bmp',
    '.tiff': 'image/tiff'
}

# Magic byte signatures for file type validation
MAGIC_BYTES = {
    b'%PDF': '.pdf',
    b'\x89PNG\r\n\x1a\n': '.png',
    b'\xff\xd8\xff': '.jpg',  # JPEG
    b'GIF87a': '.gif',
    b'GIF89a': '.gif',
    b'BM': '.bmp',
    b'II*\x00': '.tiff',
    b'MM\x00*': '.tiff'
}


def check_accounting_enabled():
    if not get_automation_settings().is_accounting_enabled():
        raise HTTPException(status_code=403, detail="Accounting automations are disabled.")


def validate_file_extension(filename: str) -> str:
    """
    Validate and extract file extension from filename.

    Args:
        filename: User-provided filename

    Returns:
        Lowercase file extension with leading dot

    Raises:
        HTTPException: If extension is not in whitelist
    """
    if not filename:
        raise HTTPException(
            status_code=400,
            detail="No filename provided"
        )

    # Sanitize filename to prevent path traversal
    safe_filename = secure_filename(filename)
    if not safe_filename:
        raise HTTPException(
            status_code=400,
            detail="Invalid filename after sanitization"
        )

    # Extract extension
    _, ext = os.path.splitext(safe_filename.lower())

    # Validate against whitelist
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    return ext


def validate_file_type_with_magic_bytes(file_path: str, expected_ext: str) -> bool:
    """
    Validate actual file type using magic byte signatures.

    Args:
        file_path: Path to the uploaded file
        expected_ext: Expected file extension from whitelist

    Returns:
        True if magic bytes match expected type

    Raises:
        HTTPException: If magic bytes don't match expected type
    """
    try:
        with open(file_path, 'rb') as f:
            header = f.read(12)  # Read first 12 bytes for magic byte detection

        # Check magic bytes
        for magic_sig, file_ext in MAGIC_BYTES.items():
            if header.startswith(magic_sig):
                if file_ext == expected_ext:
                    return True
                else:
                    # Mismatch between claimed extension and actual content
                    os.remove(file_path)
                    raise HTTPException(
                        status_code=400,
                        detail=f"File content type ({file_ext}) doesn't match extension ({expected_ext})"
                    )

        # No matching magic bytes found
        os.remove(file_path)
        raise HTTPException(
            status_code=400,
            detail="Invalid file type - magic byte validation failed"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating file type: {e}")
        # Clean up file on error
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=500,
            detail="Error validating file type"
        )

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
    """
    Secure file upload endpoint for invoice documents.

    SECURITY FIXES:
    - File size limit validation (10MB max)
    - Extension whitelist validation (.pdf, .png, .jpg, etc.)
    - Filename sanitization with secure_filename()
    - Magic byte validation for file type verification
    - Path traversal protection
    """
    check_accounting_enabled()

    # SECURITY FIX #1: Validate filename and extension
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    # SECURITY FIX #2: Validate and sanitize file extension
    file_ext = validate_file_extension(file.filename)

    # SECURITY FIX #3: Create upload directory with safe path
    upload_dir = os.path.join(os.getcwd(), "data", "uploads", "invoices")
    os.makedirs(upload_dir, exist_ok=True)

    # SECURITY FIX #4: Generate safe file path
    file_id = str(uuid.uuid4())
    # Use UUID + sanitized extension instead of user-provided filename
    safe_filename = f"{file_id}{file_ext}"
    file_path = os.path.join(upload_dir, safe_filename)

    # SECURITY FIX #5: Validate file size before saving
    content = await file.read()

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB"
        )

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    # SECURITY FIX #6: Save file temporarily for validation
    with open(file_path, "wb") as buffer:
        buffer.write(content)

    try:
        # SECURITY FIX #7: Validate actual file type with magic bytes
        validate_file_type_with_magic_bytes(file_path, file_ext)

        # Track in Document table
        # SECURITY FIX #8: Store sanitized filename only
        doc = FinancialDocument(
            workspace_id=workspace_id,
            file_path=file_path,
            file_name=safe_filename,  # Use safe filename, not user input
            file_type="pdf" if file_ext == ".pdf" else "image"
        )
        db.add(doc)
        db.flush()

        # Process with AP Service
        ap_service = APService(db)
        result = await ap_service.process_invoice_document(
            document_id=doc.id,
            workspace_id=workspace_id,
            expense_account_code=expense_account_code
        )
        return result

    except HTTPException:
        # Clean up file on validation error
        if os.path.exists(file_path):
            os.remove(file_path)
        raise
    except Exception as e:
        logger.error(f"Error processing invoice: {e}")
        # Clean up file on processing error
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Invoice processing failed: {str(e)}")
