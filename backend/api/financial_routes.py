"""
Financial Data API Routes
Handles financial accounts and net worth tracking
"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.database import get_db
from core.models import FinancialAccount, NetWorthSnapshot, User

router = APIRouter(prefix="/api/financial", tags=["Financial"])


# Request/Response Models
class NetWorthSummaryResponse(BaseModel):
    """User's net worth summary"""
    user_id: str
    snapshot_date: date
    net_worth: Decimal
    assets: Decimal
    liabilities: Decimal


class FinancialAccountResponse(BaseModel):
    """Financial account information"""
    id: str
    account_type: str
    provider: Optional[str]
    name: Optional[str]
    balance: Decimal
    currency: str
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class CreateFinancialAccountRequest(BaseModel):
    """Request to create a financial account"""
    account_type: str = Field(..., description="Account type: checking, savings, investment, credit_card, etc.")
    provider: Optional[str] = Field(None, description="Financial institution name")
    name: Optional[str] = Field(None, description="Account nickname/name")
    balance: Decimal = Field(..., ge=0, description="Current balance")
    currency: str = Field(default="USD", description="Currency code (default: USD)")


class UpdateFinancialAccountRequest(BaseModel):
    """Request to update a financial account"""
    account_type: Optional[str] = Field(None, description="Account type")
    provider: Optional[str] = Field(None, description="Financial institution name")
    name: Optional[str] = Field(None, description="Account nickname/name")
    balance: Optional[Decimal] = Field(None, ge=0, description="Current balance")
    currency: Optional[str] = Field(None, description="Currency code")


class FinancialAccountDetailResponse(BaseModel):
    """Detailed financial account information"""
    id: str
    user_id: str
    account_type: str
    provider: Optional[str]
    name: Optional[str]
    balance: Decimal
    currency: str
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class DeleteFinancialAccountResponse(BaseModel):
    """Response after deleting account"""
    message: str


class CreateNetWorthSnapshotRequest(BaseModel):
    """Request to create net worth snapshot"""
    snapshot_date: Optional[date] = Field(None, description="Snapshot date (default: today)")
    net_worth: Decimal = Field(..., description="Net worth (assets - liabilities)")
    assets: Decimal = Field(..., ge=0, description="Total assets")
    liabilities: Decimal = Field(..., ge=0, description="Total liabilities")


# Endpoints
@router.get("/net-worth/summary", response_model=NetWorthSummaryResponse)
async def get_net_worth_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's net worth summary

    Returns the most recent net worth snapshot including assets,
    liabilities, and total net worth.
    """
    latest = db.query(NetWorthSnapshot).filter(
        NetWorthSnapshot.user_id == current_user.id
    ).order_by(NetWorthSnapshot.snapshot_date.desc()).first()

    if not latest:
        # Return empty summary if no snapshots exist
        return NetWorthSummaryResponse(
            user_id=current_user.id,
            snapshot_date=date.today(),
            net_worth=Decimal("0.00"),
            assets=Decimal("0.00"),
            liabilities=Decimal("0.00")
        )

    return NetWorthSummaryResponse(
        user_id=latest.user_id,
        snapshot_date=latest.snapshot_date.date() if isinstance(latest.snapshot_date, datetime) else latest.snapshot_date,
        net_worth=Decimal(str(latest.net_worth)),
        assets=Decimal(str(latest.assets)),
        liabilities=Decimal(str(latest.liabilities))
    )


@router.get("/accounts", response_model=List[FinancialAccountResponse])
async def list_financial_accounts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all financial accounts for the current user

    Returns banking, investment, and credit card accounts
    with current balances.
    """
    accounts = db.query(FinancialAccount).filter(
        FinancialAccount.user_id == current_user.id
    ).order_by(FinancialAccount.created_at.desc()).all()

    return [
        FinancialAccountResponse(
            id=account.id,
            account_type=account.account_type,
            provider=account.provider,
            name=account.name,
            balance=Decimal(str(account.balance)),
            currency=account.currency,
            created_at=account.created_at
        )
        for account in accounts
    ]


@router.get("/accounts/{account_id}", response_model=FinancialAccountDetailResponse)
async def get_financial_account(
    account_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get specific financial account by ID

    Returns detailed account information including creation date.
    Requires ownership of the account.
    """
    account = db.query(FinancialAccount).filter(
        FinancialAccount.id == account_id,
        FinancialAccount.user_id == current_user.id
    ).first()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Financial account not found"
        )

    return FinancialAccountDetailResponse(
        id=account.id,
        user_id=account.user_id,
        account_type=account.account_type,
        provider=account.provider,
        name=account.name,
        balance=Decimal(str(account.balance)),
        currency=account.currency,
        created_at=account.created_at
    )


@router.post("/accounts", response_model=FinancialAccountDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_financial_account(
    request: CreateFinancialAccountRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new financial account

    Creates a new financial account for tracking assets, liabilities,
    or investment accounts.
    """
    account = FinancialAccount(
        user_id=current_user.id,
        account_type=request.account_type,
        provider=request.provider,
        name=request.name,
        balance=float(request.balance),
        currency=request.currency
    )

    db.add(account)
    db.commit()
    db.refresh(account)

    return FinancialAccountDetailResponse(
        id=account.id,
        user_id=account.user_id,
        account_type=account.account_type,
        provider=account.provider,
        name=account.name,
        balance=Decimal(str(account.balance)),
        currency=account.currency,
        created_at=account.created_at
    )


@router.patch("/accounts/{account_id}", response_model=FinancialAccountDetailResponse)
async def update_financial_account(
    account_id: str,
    request: UpdateFinancialAccountRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update financial account

    Updates account information. Only provided fields are updated.
    Requires ownership of the account.
    """
    account = db.query(FinancialAccount).filter(
        FinancialAccount.id == account_id,
        FinancialAccount.user_id == current_user.id
    ).first()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Financial account not found"
        )

    # Update only provided fields
    if request.account_type is not None:
        account.account_type = request.account_type
    if request.provider is not None:
        account.provider = request.provider
    if request.name is not None:
        account.name = request.name
    if request.balance is not None:
        account.balance = float(request.balance)
    if request.currency is not None:
        account.currency = request.currency

    db.commit()
    db.refresh(account)

    return FinancialAccountDetailResponse(
        id=account.id,
        user_id=account.user_id,
        account_type=account.account_type,
        provider=account.provider,
        name=account.name,
        balance=Decimal(str(account.balance)),
        currency=account.currency,
        created_at=account.created_at
    )


@router.delete("/accounts/{account_id}", response_model=DeleteFinancialAccountResponse)
async def delete_financial_account(
    account_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete financial account

    Permanently deletes a financial account and all associated data.
    Requires ownership of the account.
    """
    account = db.query(FinancialAccount).filter(
        FinancialAccount.id == account_id,
        FinancialAccount.user_id == current_user.id
    ).first()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Financial account not found"
        )

    db.delete(account)
    db.commit()

    return DeleteFinancialAccountResponse(message="Financial account deleted successfully")


@router.post("/net-worth/snapshot", response_model=NetWorthSummaryResponse, status_code=status.HTTP_201_CREATED)
async def create_net_worth_snapshot(
    request: CreateNetWorthSnapshotRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create net worth snapshot

    Creates a snapshot of net worth at a specific point in time.
    Useful for tracking financial progress over time.
    """
    snapshot = NetWorthSnapshot(
        user_id=current_user.id,
        snapshot_date=request.snapshot_date or date.today(),
        net_worth=float(request.net_worth),
        assets=float(request.assets),
        liabilities=float(request.liabilities)
    )

    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)

    return NetWorthSummaryResponse(
        user_id=snapshot.user_id,
        snapshot_date=snapshot.snapshot_date.date() if isinstance(snapshot.snapshot_date, datetime) else snapshot.snapshot_date,
        net_worth=Decimal(str(snapshot.net_worth)),
        assets=Decimal(str(snapshot.assets)),
        liabilities=Decimal(str(snapshot.liabilities))
    )
