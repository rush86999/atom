"""
Business Facts Admin Routes

REST API for managing business facts with JIT citations.
Supports document upload, fact extraction, and CRUD operations.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional, Any, Dict
from pydantic import BaseModel
from datetime import datetime
import uuid
import os
import tempfile
import logging

from core.database import get_db
from core.models import UserRole
from core.auth import get_current_user
from core.security.rbac import require_role
from core.agent_world_model import WorldModelService, BusinessFact
from core.policy_fact_extractor import get_policy_fact_extractor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/governance/facts", tags=["Business Facts"])


class FactResponse(BaseModel):
    id: str
    fact: str
    citations: List[str]
    reason: str
    domain: str
    verification_status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class FactCreateRequest(BaseModel):
    fact: str
    citations: List[str] = []
    reason: str = ""
    domain: str = "general"


class FactUpdateRequest(BaseModel):
    fact: Optional[str] = None
    citations: Optional[List[str]] = None
    reason: Optional[str] = None
    domain: Optional[str] = None
    verification_status: Optional[str] = None


class ExtractionResponse(BaseModel):
    success: bool
    facts_extracted: int
    facts: List[FactResponse]
    source_document: str
    extraction_time: float


@router.get("", response_model=List[FactResponse])
async def list_facts(
    status: Optional[str] = None,
    domain: Optional[str] = None,
    limit: int = 100,
    current_user = Depends(get_current_user),
    _ = Depends(require_role(UserRole.ADMIN))
):
    """
    List all business facts with optional filters.
    """
    # Get workspace from user context
    workspace_id = getattr(current_user, 'workspace_id', None) or "default"
    
    wm = WorldModelService(workspace_id)
    facts = await wm.list_all_facts(status=status, domain=domain, limit=limit)
    
    return [
        FactResponse(
            id=f.id,
            fact=f.fact,
            citations=f.citations,
            reason=f.reason,
            domain=f.metadata.get("domain", "general") if f.metadata else "general",
            verification_status=f.verification_status,
            created_at=f.created_at
        )
        for f in facts
        if f.verification_status != "deleted"  # Filter out deleted facts
    ]


@router.get("/{fact_id}", response_model=FactResponse)
async def get_fact(
    fact_id: str,
    current_user = Depends(get_current_user),
    _ = Depends(require_role(UserRole.ADMIN))
):
    """
    Get a specific fact by ID.
    """
    workspace_id = getattr(current_user, 'workspace_id', None) or "default"
    wm = WorldModelService(workspace_id)
    
    fact = await wm.get_fact_by_id(fact_id)
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found")
    
    return FactResponse(
        id=fact.id,
        fact=fact.fact,
        citations=fact.citations,
        reason=fact.reason,
        domain=fact.metadata.get("domain", "general") if fact.metadata else "general",
        verification_status=fact.verification_status,
        created_at=fact.created_at
    )


@router.post("", response_model=FactResponse)
async def create_fact(
    request: FactCreateRequest,
    current_user = Depends(get_current_user),
    _ = Depends(require_role(UserRole.ADMIN))
):
    """
    Manually create a new business fact.
    """
    workspace_id = getattr(current_user, 'workspace_id', None) or "default"
    wm = WorldModelService(workspace_id)
    
    fact = BusinessFact(
        id=str(uuid.uuid4()),
        fact=request.fact,
        citations=request.citations,
        reason=request.reason,
        source_agent_id=f"user:{current_user.id}",
        created_at=datetime.now(),
        last_verified=datetime.now(),
        verification_status="verified",
        metadata={"domain": request.domain}
    )
    
    success = await wm.record_business_fact(fact)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to create fact")
    
    return FactResponse(
        id=fact.id,
        fact=fact.fact,
        citations=fact.citations,
        reason=fact.reason,
        domain=request.domain,
        verification_status=fact.verification_status,
        created_at=fact.created_at
    )


@router.put("/{fact_id}", response_model=FactResponse)
async def update_fact(
    fact_id: str,
    request: FactUpdateRequest,
    current_user = Depends(get_current_user),
    _ = Depends(require_role(UserRole.ADMIN))
):
    """
    Update an existing fact.
    """
    workspace_id = getattr(current_user, 'workspace_id', None) or "default"
    wm = WorldModelService(workspace_id)
    
    existing = await wm.get_fact_by_id(fact_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Fact not found")
    
    # Update verification status if provided
    if request.verification_status:
        await wm.update_fact_verification(fact_id, request.verification_status)
    
    # For other updates, we need to re-record the fact (LanceDB is append-only)
    if request.fact or request.citations or request.reason or request.domain:
        updated_fact = BusinessFact(
            id=fact_id,
            fact=request.fact or existing.fact,
            citations=request.citations if request.citations is not None else existing.citations,
            reason=request.reason or existing.reason,
            source_agent_id=existing.source_agent_id,
            created_at=existing.created_at,
            last_verified=datetime.now(),
            verification_status=request.verification_status or existing.verification_status,
            metadata={"domain": request.domain or existing.metadata.get("domain", "general")}
        )
        await wm.record_business_fact(updated_fact)
    
    # Return updated fact
    return FactResponse(
        id=fact_id,
        fact=request.fact or existing.fact,
        citations=request.citations if request.citations is not None else existing.citations,
        reason=request.reason or existing.reason,
        domain=request.domain or existing.metadata.get("domain", "general"),
        verification_status=request.verification_status or existing.verification_status,
        created_at=existing.created_at
    )


@router.delete("/{fact_id}")
async def delete_fact(
    fact_id: str,
    current_user = Depends(get_current_user),
    _ = Depends(require_role(UserRole.ADMIN))
):
    """
    Soft delete a fact.
    """
    workspace_id = getattr(current_user, 'workspace_id', None) or "default"
    wm = WorldModelService(workspace_id)
    
    success = await wm.delete_fact(fact_id)
    if not success:
        raise HTTPException(status_code=404, detail="Fact not found or already deleted")
    
    return {"status": "deleted", "id": fact_id}


@router.post("/upload", response_model=ExtractionResponse)
async def upload_and_extract(
    file: UploadFile = File(...),
    domain: str = Form(default="general"),
    current_user = Depends(get_current_user),
    _ = Depends(require_role(UserRole.ADMIN))
):
    """
    Upload a policy document to R2 and extract business facts.
    """
    workspace_id = getattr(current_user, 'workspace_id', None) or "default"
    
    # Validate file type
    allowed_extensions = ['.pdf', '.docx', '.doc', '.txt', '.png', '.tiff', '.tif', '.jpeg', '.jpg']
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file type: {ext}. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # Save to temp file for extraction
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, file.filename)
    
    try:
        content = await file.read()
        with open(temp_path, 'wb') as f:
            f.write(content)
        
        # 1. Upload to R2 (Persistent Storage)
        from core.storage import get_storage_service
        storage = get_storage_service()
        file_key = f"business_facts/{workspace_id}/{uuid.uuid4()}/{file.filename}"
        
        # Reset file pointer for upload if needed, or just upload bytes
        # Since we have 'content' in memory, we can wrap it
        import io
        s3_uri = storage.upload_file(io.BytesIO(content), file_key, content_type=file.content_type)
        
        # 2. Extract facts using local temp file
        extractor = get_policy_fact_extractor(workspace_id)
        result = await extractor.extract_facts_from_document(
            document_path=temp_path,
            user_id=str(current_user.id)
        )
        
        # 3. Store Facts with R2 Citation
        wm = WorldModelService(workspace_id)
        business_facts = []
        
        for extracted in result.facts:
            # Citation format: s3://bucket/key
            citation = s3_uri  
            
            fact = BusinessFact(
                id=str(uuid.uuid4()),
                fact=extracted.fact,
                citations=[citation],
                reason=f"Extracted from {file.filename}",
                source_agent_id=f"user:{current_user.id}",
                created_at=datetime.now(),
                last_verified=datetime.now(),
                verification_status="verified", # Initial upload is considered valid
                metadata={"domain": extracted.domain or domain}
            )
            business_facts.append(fact)
        
        # Bulk store
        stored_count = await wm.bulk_record_facts(business_facts)
        
        logger.info(f"Extracted and stored {stored_count} facts from {file.filename} (Archived to {s3_uri})")
        
        return ExtractionResponse(
            success=True,
            facts_extracted=stored_count,
            facts=[
                FactResponse(
                    id=f.id,
                    fact=f.fact,
                    citations=f.citations,
                    reason=f.reason,
                    domain=f.metadata.get("domain", "general"),
                    verification_status=f.verification_status,
                    created_at=f.created_at
                )
                for f in business_facts
            ],
            source_document=file.filename,
            extraction_time=result.extraction_time
        )
        
    except Exception as e:
        logger.error(f"Failed to extract facts from {file.filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        # Cleanup temp file
        try:
            os.unlink(temp_path)
            os.rmdir(temp_dir)
        except Exception as e:
            pass


@router.post("/{fact_id}/verify-citation")
async def verify_citation(
    fact_id: str,
    current_user = Depends(get_current_user),
    _ = Depends(require_role(UserRole.ADMIN))
):
    """
    Re-verify that a fact's citation sources still exist in R2/S3.
    """
    workspace_id = getattr(current_user, 'workspace_id', None) or "default"
    wm = WorldModelService(workspace_id)
    
    fact = await wm.get_fact_by_id(fact_id)
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found")
    
    from core.storage import get_storage_service
    storage = get_storage_service()
    
    verification_results = []
    all_valid = True
    
    for citation in fact.citations:
        exists = False
        
        # Check S3/R2
        if citation.startswith("s3://"):
            try:
                # s3://bucket/key -> extract key
                # We assume bucket matches, or we parse it. 
                # Our storage service uses env bucket.
                bucket_name = storage.bucket
                if f"s3://{bucket_name}/" in citation:
                    key = citation.replace(f"s3://{bucket_name}/", "")
                    exists = storage.check_exists(key)
                else:
                    # Cross-bucket or legacy? Assume false or try generic check if we supported it
                    # Just generic parse for robustness
                    parts = citation.replace("s3://", "").split("/", 1)
                    if len(parts) == 2 and parts[0] == bucket_name:
                        exists = storage.check_exists(parts[1])
            except Exception as e:
                logger.warning(f"Failed to check S3 citation {citation}: {e}")
        
        # Fallback: Check Local (Legacy)
        else:
            filename = citation.split(":")[0]
            for base_path in ["/app/uploads", "/tmp", os.getcwd()]:
                full_path = os.path.join(base_path, filename)
                if os.path.exists(full_path):
                    exists = True
                    break
        
        verification_results.append({
            "citation": citation,
            "exists": exists,
            "source": "R2" if citation.startswith("s3://") else "Local"
        })
        
        if not exists:
            all_valid = False
            logger.warning(f"Verification failed for citation: {citation}")
    
    # Update verification status
    new_status = "verified" if all_valid else "outdated"
    await wm.update_fact_verification(fact_id, new_status)
    
    return {
        "fact_id": fact_id,
        "new_status": new_status,
        "citations": verification_results
    }
