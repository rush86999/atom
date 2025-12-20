import logging
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from accounting.models import Account, AccountType, EntryType
from accounting.ledger import EventSourcedLedger
from integrations.ai_enhanced_service import ai_enhanced_service, AIRequest, AITaskType, AIModelType, AIServiceType

logger = logging.getLogger(__name__)

class AccountingAssistant:
    """
    Assistant for natural language accounting queries and commands.
    """

    def __init__(self, db: Session):
        self.db = db
        self.ledger = EventSourcedLedger(db)

    async def process_query(self, workspace_id: str, query: str) -> Dict[str, Any]:
        """Process a natural language accounting query"""
        
        # 1. Use AI to understand intent and extract parameters
        ai_request = AIRequest(
            request_id=f"finance_query_{int(datetime.utcnow().timestamp())}",
            task_type=AITaskType.NATURAL_LANGUAGE_COMMANDS,
            model_type=AIModelType.GPT_4,
            service_type=AIServiceType.OPENAI,
            input_data={
                "text": query,
                "instruction": (
                    "Interpret the accounting query. Is the user asking for a balance, runway, burn rate, "
                    "or wanting to record a transaction? Return JSON with 'intent', 'params' (dict), and 'reasoning'."
                )
            }
        )
        
        try:
            ai_response = await ai_enhanced_service.process_ai_request(ai_request)
            # For brevity in MVP, we handle some intents directly or via AI result
            result = ai_response.output_data
            if isinstance(result, str):
                try: result = json.loads(result)
                except: pass
            
            intent = result.get("intent", "unknown")
            params = result.get("params", {})

            if intent == "get_balance":
                return self._handle_get_balance(workspace_id, params)
            elif intent == "get_runway":
                return self._handle_get_runway(workspace_id)
            elif intent == "check_overdue":
                return {"intent": "check_overdue"} # Handled by orchestrator
            elif intent == "get_aging":
                return {"intent": "get_aging"} # Handled by orchestrator
            elif intent == "check_close_readiness":
                return {"intent": "check_close_readiness", "params": params}
            elif intent == "get_tax_estimate":
                return {"intent": "get_tax_estimate"}
            elif intent == "get_cash_forecast":
                return {"intent": "get_cash_forecast"}
            elif intent == "run_scenario":
                return {"intent": "run_scenario", "params": params}
            elif intent == "get_intercompany_report":
                return {"intent": "get_intercompany_report"}
            elif intent == "record_transaction":
                return await self._handle_record_transaction(workspace_id, query, params)
            
            return {
                "answer": "I'm not sure how to help with that financial query yet. I can check balances, runway, or record simple transactions.",
                "intent": intent
            }

        except Exception as e:
            logger.error(f"Accounting assistant error: {e}")
            return {"answer": f"Sorry, I encountered an error: {str(e)}"}

    def _handle_get_balance(self, workspace_id: str, params: Dict) -> Dict[str, Any]:
        account_name = params.get("account_name", "Cash")
        account = self.db.query(Account).filter(
            Account.workspace_id == workspace_id,
            Account.name.ilike(f"%{account_name}%")
        ).first()
        
        if not account:
            return {"answer": f"I couldn't find an account named '{account_name}'."}
        
        balance = self.ledger.get_account_balance(account.id)
        return {
            "answer": f"The current balance of {account.name} is ${balance:,.2f}.",
            "data": {"account": account.name, "balance": balance}
        }

    def _handle_get_runway(self, workspace_id: str) -> Dict[str, Any]:
        # Simple runway calculation: Cash / Avg monthly burn
        cash_account = self.db.query(Account).filter(
            Account.workspace_id == workspace_id,
            Account.code == "1000"
        ).first()
        
        if not cash_account:
            return {"answer": "I need a cash account to calculate runway."}
        
        cash_balance = self.ledger.get_account_balance(cash_account.id)
        
        # Calculate monthly burn (simplified: total expenses in last 30 days)
        # In a real app, this would use trend analysis
        monthly_burn = 5000.0 # Placeholder
        
        if monthly_burn <= 0:
            return {"answer": "Your burn rate is 0 or positive cash flow, so your runway is infinite!"}
        
        runway_months = cash_balance / monthly_burn
        return {
            "answer": f"Based on your current cash balance of ${cash_balance:,.2f} and a burn rate of ${monthly_burn:,.2f}/mo, your runway is approximately {runway_months:.1f} months.",
            "data": {"cash": cash_balance, "burn": monthly_burn, "runway": runway_months}
        }

    async def _handle_record_transaction(self, workspace_id: str, query: str, params: Dict) -> Dict[str, Any]:
        # This would use the TransactionIngestor or DoubleEntryEngine directly
        # For MVP, we'll just acknowledge the intent
        return {
            "answer": "I've understood you want to record a transaction. (Integration with ledger coming in Phase 2!)",
            "intent": "record_transaction",
            "extracted_params": params
        }
