"""
Financial Data API Routes
Handles financial accounts and net worth tracking
"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from fastapi import Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from core.agent_context_resolver import AgentContextResolver
from core.agent_governance_service import AgentGovernanceService
from core.auth import get_current_user
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import FinancialAccount, FinancialAudit, NetWorthSnapshot, User

router = BaseAPIRouter(prefix="/api/financial", tags=["Financial"])


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

    model_config = ConfigDict(from_attributes=True)


class CreateFinancialAccountRequest(BaseModel):
    """Request to create a financial account"""
    account_type: str = Field(..., description="Account type: checking, savings, investment, credit_card, etc.")
    provider: Optional[str] = Field(None, description="Financial institution name")
    name: Optional[str] = Field(None, description="Account nickname/name")
    balance: Decimal = Field(..., ge=0, description="Current balance")
    currency: str = Field(default="USD", description="Currency code (default: USD)")
    agent_id: Optional[str] = Field(None, description="Agent ID requesting the creation")


class UpdateFinancialAccountRequest(BaseModel):
    """Request to update a financial account"""
    account_type: Optional[str] = Field(None, description="Account type")
    provider: Optional[str] = Field(None, description="Financial institution name")
    name: Optional[str] = Field(None, description="Account nickname/name")
    balance: Optional[Decimal] = Field(None, ge=0, description="Current balance")
    currency: Optional[str] = Field(None, description="Currency code")
    agent_id: Optional[str] = Field(None, description="Agent ID requesting the update")


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

    model_config = ConfigDict(from_attributes=True)


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
        raise router.not_found_error("Financial account", account_id)

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

    Governance:
    - SUPERVISED+ maturity required
    - All actions logged to FinancialAudit
    - Agent attribution tracked if agent_id provided
    """
    agent_id = None
    agent_execution_id = None
    agent_maturity = None
    governance_check_passed = True
    required_approval = False
    approval_granted = None

    # Resolve agent if provided
    if request.agent_id:
        resolver = AgentContextResolver(db)
        agent, context = await resolver.resolve_agent_for_request(
            user_id=str(current_user.id),
            requested_agent_id=request.agent_id,
            action_type="create_financial_account"
        )

        if agent:
            agent_id = str(agent.id)
            agent_maturity = agent.status

            # Check governance
            governance = AgentGovernanceService(db)
            governance_check = governance.can_perform_action(
                agent_id=agent_id,
                action_type="create_financial_account"
            )

            governance_check_passed = governance_check.get("allowed", False)
            required_approval = governance_check.get("requires_human_approval", False)

            if not governance_check_passed:
                # Create audit entry for failed governance check
                audit = FinancialAudit(
                    user_id=str(current_user.id),
                    agent_id=agent_id,
                    agent_execution_id=agent_execution_id,
                    account_id=None,  # Not created yet
                    action_type="create",
                    changes={"requested": request.dict()},
                    success=False,
                    error_message="Governance check failed",
                    agent_maturity=agent_maturity,
                    governance_check_passed=False,
                    required_approval=required_approval,
                    approval_granted=False
                )
                db.add(audit)
                db.commit()

                raise router.permission_denied_error("financial account", "create")

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

    # Create audit entry
    audit = FinancialAudit(
        user_id=str(current_user.id),
        agent_id=agent_id,
        agent_execution_id=agent_execution_id,
        account_id=account.id,
        action_type="create",
        changes={"created": request.dict()},
        new_values=request.dict(),
        success=True,
        agent_maturity=agent_maturity or "NONE",
        governance_check_passed=governance_check_passed,
        required_approval=required_approval,
        approval_granted=approval_granted
    )
    db.add(audit)
    db.commit()

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

    Governance:
    - SUPERVISED+ maturity required
    - All actions logged to FinancialAudit
    - Agent attribution tracked if agent_id provided
    """
    agent_id = None
    agent_execution_id = None
    agent_maturity = None
    governance_check_passed = True
    required_approval = False
    approval_granted = None

    # Resolve agent if provided
    if request.agent_id:
        resolver = AgentContextResolver(db)
        agent, context = await resolver.resolve_agent_for_request(
            user_id=str(current_user.id),
            requested_agent_id=request.agent_id,
            action_type="update_financial_account"
        )

        if agent:
            agent_id = str(agent.id)
            agent_maturity = agent.status

            # Check governance
            governance = AgentGovernanceService(db)
            governance_check = governance.can_perform_action(
                agent_id=agent_id,
                action_type="update_financial_account"
            )

            governance_check_passed = governance_check.get("allowed", False)
            required_approval = governance_check.get("requires_human_approval", False)

            if not governance_check_passed:
                # Create audit entry for failed governance check
                audit = FinancialAudit(
                    user_id=str(current_user.id),
                    agent_id=agent_id,
                    agent_execution_id=agent_execution_id,
                    account_id=account_id,
                    action_type="update",
                    changes={"requested": request.dict(exclude_none=True)},
                    success=False,
                    error_message="Governance check failed",
                    agent_maturity=agent_maturity,
                    governance_check_passed=False,
                    required_approval=required_approval,
                    approval_granted=False
                )
                db.add(audit)
                db.commit()

                raise router.permission_denied_error("financial account", "update")

    account = db.query(FinancialAccount).filter(
        FinancialAccount.id == account_id,
        FinancialAccount.user_id == current_user.id
    ).first()

    if not account:
        raise router.not_found_error("Financial account", account_id)

    # Track old values for audit
    old_values = {
        "account_type": account.account_type,
        "provider": account.provider,
        "name": account.name,
        "balance": str(account.balance),
        "currency": account.currency
    }

    # Update only provided fields
    changes = {}
    if request.account_type is not None:
        changes["account_type"] = {"old": account.account_type, "new": request.account_type}
        account.account_type = request.account_type
    if request.provider is not None:
        changes["provider"] = {"old": account.provider, "new": request.provider}
        account.provider = request.provider
    if request.name is not None:
        changes["name"] = {"old": account.name, "new": request.name}
        account.name = request.name
    if request.balance is not None:
        changes["balance"] = {"old": str(account.balance), "new": str(request.balance)}
        account.balance = float(request.balance)
    if request.currency is not None:
        changes["currency"] = {"old": account.currency, "new": request.currency}
        account.currency = request.currency

    db.commit()
    db.refresh(account)

    # Create audit entry
    audit = FinancialAudit(
        user_id=str(current_user.id),
        agent_id=agent_id,
        agent_execution_id=agent_execution_id,
        account_id=account_id,
        action_type="update",
        changes=changes,
        old_values=old_values,
        new_values=request.dict(exclude_none=True),
        success=True,
        agent_maturity=agent_maturity or "NONE",
        governance_check_passed=governance_check_passed,
        required_approval=required_approval,
        approval_granted=approval_granted
    )
    db.add(audit)
    db.commit()

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
    agent_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete financial account

    Permanently deletes a financial account and all associated data.
    Requires ownership of the account.

    Governance:
    - AUTONOMOUS maturity required for deletions
    - All actions logged to FinancialAudit
    - Agent attribution tracked if agent_id provided
    """
    agent_execution_id = None
    agent_maturity = None
    governance_check_passed = True
    required_approval = False
    approval_granted = None

    # Resolve agent if provided
    if agent_id:
        resolver = AgentContextResolver(db)
        agent, context = await resolver.resolve_agent_for_request(
            user_id=str(current_user.id),
            requested_agent_id=agent_id,
            action_type="delete_financial_account"
        )

        if agent:
            agent_id = str(agent.id)
            agent_maturity = agent.status

            # Check governance - AUTONOMOUS required for deletion
            governance = AgentGovernanceService(db)
            governance_check = governance.can_perform_action(
                agent_id=agent_id,
                action_type="delete_financial_account"
            )

            governance_check_passed = governance_check.get("allowed", False)
            required_approval = governance_check.get("requires_human_approval", False)

            if not governance_check_passed:
                # Create audit entry for failed governance check
                audit = FinancialAudit(
                    user_id=str(current_user.id),
                    agent_id=agent_id,
                    agent_execution_id=agent_execution_id,
                    account_id=account_id,
                    action_type="delete",
                    changes={},
                    success=False,
                    error_message="Governance check failed - AUTONOMOUS maturity required for deletion",
                    agent_maturity=agent_maturity,
                    governance_check_passed=False,
                    required_approval=required_approval,
                    approval_granted=False
                )
                db.add(audit)
                db.commit()

                raise router.permission_denied_error("financial account", "delete")

    account = db.query(FinancialAccount).filter(
        FinancialAccount.id == account_id,
        FinancialAccount.user_id == current_user.id
    ).first()

    if not account:
        raise router.not_found_error("Financial account", account_id)

    # Store account info for audit before deletion
    account_info = {
        "account_type": account.account_type,
        "provider": account.provider,
        "name": account.name,
        "balance": str(account.balance),
        "currency": account.currency
    }

    db.delete(account)
    db.commit()

    # Create audit entry
    audit = FinancialAudit(
        user_id=str(current_user.id),
        agent_id=agent_id,
        agent_execution_id=agent_execution_id,
        account_id=account_id,
        action_type="delete",
        changes={"deleted": account_info},
        old_values=account_info,
        success=True,
        agent_maturity=agent_maturity or "NONE",
        governance_check_passed=governance_check_passed,
        required_approval=required_approval,
        approval_granted=approval_granted
    )
    db.add(audit)
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
