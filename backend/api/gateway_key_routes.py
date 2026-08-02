"""Gateway API-key management routes.

Only the SHA-256 ``key_hash`` + a ``key_prefix`` are ever stored; the plaintext
``atom_sk_*`` value is returned exactly once at creation time.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.database import get_db
from core.llm.gateway.auth import hash_api_key, generate_key_prefix
from core.models import GatewayApiKey, User

router = APIRouter(prefix="/api/gateway/keys", tags=["LLM Gateway Keys"])


class CreateKeyRequest(BaseModel):
    name: str = Field(default="default", max_length=255)
    rate_limit_per_minute: int = Field(default=60, ge=1, le=10000)
    expires_at: Optional[datetime] = None


class CreateKeyResponse(BaseModel):
    id: str
    key: str  # plaintext, shown once
    key_prefix: str


def _get_owned_key(db: Session, key_id: str, user_id: str) -> GatewayApiKey:
    row = db.query(GatewayApiKey).filter(
        GatewayApiKey.id == key_id, GatewayApiKey.user_id == user_id
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="API key not found")
    return row


@router.post("", response_model=CreateKeyResponse, status_code=201)
def create_key(
    body: CreateKeyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    plaintext = f"atom_sk_{uuid.uuid4().hex}"
    row = GatewayApiKey(
        key_hash=hash_api_key(plaintext),
        key_prefix=generate_key_prefix(plaintext),
        name=body.name,
        user_id=current_user.id,
        tenant_id=getattr(current_user, "tenant_id", None),
        rate_limit_per_minute=body.rate_limit_per_minute,
        expires_at=body.expires_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return CreateKeyResponse(id=row.id, key=plaintext, key_prefix=row.key_prefix)


@router.get("")
def list_keys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(GatewayApiKey)
        .filter(GatewayApiKey.user_id == current_user.id)
        .order_by(GatewayApiKey.created_at.desc())
        .all()
    )
    return {
        "success": True,
        "data": [
            {
                "id": r.id,
                "name": r.name,
                "key_prefix": r.key_prefix,
                "is_active": r.is_active,
                "rate_limit_per_minute": r.rate_limit_per_minute,
                "expires_at": r.expires_at.isoformat() if r.expires_at else None,
                "last_used": r.last_used.isoformat() if r.last_used else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.delete("/{key_id}")
def revoke_key(
    key_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = _get_owned_key(db, key_id, current_user.id)
    row.is_active = False
    row.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return {"success": True, "message": "API key revoked"}


@router.post("/{key_id}/rotate", response_model=CreateKeyResponse)
def rotate_key(
    key_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = _get_owned_key(db, key_id, current_user.id)
    row.is_active = False
    row.revoked_at = datetime.now(timezone.utc)
    row.last_rotated = datetime.now(timezone.utc)

    plaintext = f"atom_sk_{uuid.uuid4().hex}"
    new_row = GatewayApiKey(
        key_hash=hash_api_key(plaintext),
        key_prefix=generate_key_prefix(plaintext),
        name=row.name,
        user_id=row.user_id,
        tenant_id=row.tenant_id,
        workspace_id=row.workspace_id,
        rate_limit_per_minute=row.rate_limit_per_minute,
        expires_at=row.expires_at,
    )
    db.add(new_row)
    db.commit()
    db.refresh(new_row)
    return CreateKeyResponse(id=new_row.id, key=plaintext, key_prefix=new_row.key_prefix)
