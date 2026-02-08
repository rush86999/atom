from datetime import datetime
import json
import logging
from typing import Any, Dict, List, Optional
from accounting.models import Account, CategorizationProposal, CategorizationRule, Transaction
from sqlalchemy.orm import Session

from core.models import AuditLog
from integrations.ai_enhanced_service import (
    AIModelType,
    AIRequest,
    AIServiceType,
    AITaskType,
    ai_enhanced_service,
)

logger = logging.getLogger(__name__)

class AICategorizer:
    """
    Service for suggesting Chart of Accounts (CoA) categories for transactions.
    """

    def __init__(self, db: Session):
        self.db = db

    async def propose_categorization(
        self,
        transaction: Transaction,
        workspace_id: str,
        confidence_threshold: float = 0.8
    ) -> Optional[CategorizationProposal]:
        """
        Analyze transaction metadata and propose a CoA category.
        """
        # 0. Check for existing rules (Learning Layer)
        rule = self.db.query(CategorizationRule).filter(
            CategorizationRule.workspace_id == workspace_id,
            CategorizationRule.is_active == True,
            Transaction.description.ilike("%" + CategorizationRule.merchant_pattern + "%")
        ).first()

        if rule:
            logger.info(f"Using existing rule for {transaction.description}: {rule.merchant_pattern}")
            proposal = CategorizationProposal(
                transaction_id=transaction.id,
                suggested_account_id=rule.target_account_id,
                confidence=0.95, # Rule match is high confidence
                reasoning=f"Matched learned rule for '{rule.merchant_pattern}'"
            )
            self.db.add(proposal)
            self.db.commit()
            return proposal

        # 1. Get available accounts for this workspace
        accounts = self.db.query(Account).filter(Account.workspace_id == workspace_id).all()
        coa_context = [
            {"id": acc.id, "name": acc.name, "description": acc.description, "type": acc.type.value}
            for acc in accounts
        ]

        # 2. Prepare AI Request
        prompt_data = {
            "transaction": {
                "description": transaction.description,
                "amount": sum(je.amount for je in transaction.journal_entries if je.type == "debit"), # Simplified total
                "date": transaction.transaction_date.isoformat(),
                "metadata": transaction.metadata_json
            },
            "chart_of_accounts": coa_context
        }

        ai_request = AIRequest(
            request_id=f"categorize_{transaction.id}",
            task_type=AITaskType.NATURAL_LANGUAGE_COMMANDS,
            model_type=AIModelType.GPT_4,
            service_type=AIServiceType.OPENAI,
            input_data={
                "text": json.dumps(prompt_data),
                "instruction": (
                    "Based on the transaction description and metadata, pick the most appropriate "
                    "account from the provided Chart of Accounts. Return JSON with 'account_id', "
                    "'confidence' (0-1), and 'reasoning'."
                )
            },
            platform="accounting"
        )

        try:
            ai_response = await ai_enhanced_service.process_ai_request(ai_request)
            if ai_response.confidence <= 0:
                logger.error(f"AI Categorization failed or had 0 confidence")
                return None

            # 3. Parse AI output (assuming it returns a dict in output_data)
            # In a real scenario, we might need to parse JSON from a string if the AI returns text.
            result = ai_response.output_data
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except (json.JSONDecodeError, ValueError, TypeError):
                    logger.error("Failed to parse AI response as JSON")
                    return None

            suggested_account_id = result.get("account_id")
            confidence = result.get("confidence", 0.0)
            reasoning = result.get("reasoning", "")

            if not suggested_account_id:
                return None

            # 4. Save Proposal
            proposal = CategorizationProposal(
                transaction_id=transaction.id,
                suggested_account_id=suggested_account_id,
                confidence=confidence,
                reasoning=reasoning
            )
            self.db.add(proposal)
            self.db.commit()

            logger.info(f"Created categorization proposal for {transaction.id} with confidence {confidence}")
            return proposal

        except Exception as e:
            logger.error(f"Error in AICategorizer: {e}")
            return None

    def accept_proposal(self, proposal_id: str, user_id: str) -> bool:
        """User manual approval of a categorization proposal"""
        proposal = self.db.query(CategorizationProposal).filter(CategorizationProposal.id == proposal_id).first()
        if not proposal:
            return False

        proposal.is_accepted = True
        proposal.reviewed_by = user_id
        proposal.reviewed_at = datetime.utcnow()
        
        # LEARNING LAYER: Create or update a rule
        # Extract a simplified merchant name from description
        merchant = proposal.transaction.description.split()[0] # Very simple heuristic
        
        existing_rule = self.db.query(CategorizationRule).filter(
            CategorizationRule.workspace_id == proposal.transaction.workspace_id,
            CategorizationRule.merchant_pattern == merchant
        ).first()
        
        if existing_rule:
            if existing_rule.target_account_id == proposal.suggested_account_id:
                existing_rule.confidence_weight += 0.1 # Reinforce
            else:
                # Disagreement - lower confidence or update if weight is low
                existing_rule.confidence_weight -= 0.2
        else:
            new_rule = CategorizationRule(
                workspace_id=proposal.transaction.workspace_id,
                merchant_pattern=merchant,
                target_account_id=proposal.suggested_account_id,
                confidence_weight=1.1
            )
            self.db.add(new_rule)

        # AUDIT TRAIL: Record the approval
        audit = AuditLog(
            event_type="FINANCIAL_APPROVAL",
            security_level="medium",
            threat_level="none",
            user_id=user_id,
            workspace_id=proposal.transaction.workspace_id,
            resource=f"Transaction:{proposal.transaction_id}",
            action="ACCEPT_CATEGORIZATION",
            description=f"User approved categorization rule for '{merchant}' to account '{proposal.suggested_account_id}'",
            success=True
        )
        self.db.add(audit)

        self.db.commit()
        return True
