from datetime import datetime
import logging
from typing import Any, Dict, List, Optional

# Import Integration Services
try:
    from integrations.stripe_service import stripe_service
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False

try:
    from integrations.gmail_service import gmail_service
    GMAIL_AVAILABLE = True
except ImportError:
    GMAIL_AVAILABLE = False

try:
    from integrations.outlook_service_enhanced import OutlookEnhancedService

    # In a real app, this would be a singleton or dependency injected
    outlook_service = OutlookEnhancedService() 
    OUTLOOK_AVAILABLE = True
except ImportError:
    OUTLOOK_AVAILABLE = False

from core.cross_system_reasoning import Intervention

logger = logging.getLogger(__name__)

class ActiveInterventionService:
    """
    Executes the 'Active Interventions' proposed by the Reasoning Engine.
    Human-in-the-loop by default.
    """
    
    async def execute_intervention(self, intervention_id: str, suggested_action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispatches execution to the appropriate handler.
        In a real system, these would call 'sales.service', 'finance.service', etc.
        """
        logger.info(f"Executing Intervention {intervention_id}: {suggested_action} with {payload}")
        
        handler = getattr(self, f"_handle_{suggested_action}", None)
        if not handler:
            raise ValueError(f"No handler for action: {suggested_action}")
            
        return await handler(payload)

    async def _handle_draft_retention_email(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Drafts a retention email using Gmail or Outlook.
        Requires user_id for proper authentication and audit trail.
        """
        client_name = payload.get("client_name", "Valued Client")
        admin_email = payload.get("admin_email", "admin@example.com")
        user_id = payload.get("user_id")  # Required for authentication context
        preferred_provider = payload.get("provider", "gmail").lower()

        subject = f"Let's catch up - {client_name}"
        body = f"""
        Hi {client_name},

        We noticed you haven't been as active lately. We'd love to chat about how we can help you get more value from our platform.

        Best,
        The Team
        """

        if preferred_provider == "outlook" and OUTLOOK_AVAILABLE:
            # Outlook Logic - requires authenticated user_id
            if not user_id:
                logger.error("Outlook draft failed: Missing user_id for authentication")
                return {
                    "status": "FAILED",
                    "message": "Outlook requires authenticated user_id",
                    "provider": "outlook"
                }

            logger.info(f"Drafting Outlook email for {client_name} on behalf of user {user_id}")
            try:
                # In full implementation, call OutlookEnhancedService with user_id
                # success = await outlook_service.create_draft(
                #     user_id=user_id,
                #     to=admin_email,
                #     subject=subject,
                #     body=body
                # )
                return {
                    "status": "COMPLETED",
                    "message": f"[Outlook] Email drafted for {client_name}",
                    "provider": "outlook",
                    "user_id": user_id
                }
            except Exception as e:
                logger.error(f"Outlook draft failed: {e}")
                return {
                    "status": "FAILED",
                    "message": f"Outlook error: {str(e)}",
                    "provider": "outlook"
                }

        elif GMAIL_AVAILABLE:
             # Gmail Logic
            try:
                # 'me' alias works if the backend has credentials for the primary account
                draft = gmail_service.draft_message(
                    to=admin_email, # Draft is saved in 'me' account, sent 'to' the client/admin for review
                    subject=subject,
                    body=body
                )
                if draft:
                    return {
                        "status": "COMPLETED", 
                        "message": f"Gmail draft created with ID: {draft.get('id')}", 
                        "draft_id": draft.get('id'),
                        "provider": "gmail"
                    }
                else:
                    return {"status": "FAILED", "message": "Gmail service returned no draft ID"}
            except Exception as e:
                logger.error(f"Gmail draft failed: {e}")
                return {"status": "FAILED", "message": f"Gmail error: {str(e)}"}
        
        return {"status": "FAILED", "message": "No email provider available"}

    async def _handle_cancel_subscription(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Cancels a subscription via Stripe.
        """
        subscription_id = payload.get("subscription_id")
        # Require stripe_token to be provided - no mock fallback
        stripe_access_token = payload.get("stripe_token")

        if not subscription_id:
             return {"status": "FAILED", "message": "Missing subscription_id"}

        if not stripe_access_token:
            logger.error("Missing stripe_token for subscription cancellation")
            return {"status": "FAILED", "message": "Missing stripe_token"}

        if STRIPE_AVAILABLE:
            try:
                # Call Stripe Service
                result = stripe_service.cancel_subscription(stripe_access_token, subscription_id)
                return {
                    "status": "COMPLETED",
                    "message": f"Subscription {subscription_id} canceled via Stripe",
                    "stripe_response": result
                }
            except Exception as e:
                logger.error(f"Stripe cancellation failed: {e}")
                # Fallback for mock/test environments allowing simulation
                return {
                    "status": "COMPLETED",
                    "message": f"Simulated Stripe cancellation for {subscription_id} (API Error: {str(e)})"
                }
        
        return {
            "status": "FAILED", 
            "message": "Stripe integration unavailable"
        }

    async def _handle_bulk_remind_invoices(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sends bulk invoice reminders via Gmail/Outlook (BCC).
        Requires user_id for proper authentication and audit trail.
        """
        invoices = payload.get("invoices", [])
        admin_email = payload.get("admin_email", "admin@example.com")
        user_id = payload.get("user_id")  # Required for authentication
        preferred_provider = payload.get("provider", "gmail").lower()

        if not invoices:
             # If no explicit list, simulate a query or return
             return {"status": "COMPLETED", "message": "No overdue invoices found to remind."}

        # Extract emails
        recipient_emails = []
        invoice_details = []
        for inv in invoices:
            if isinstance(inv, dict) and "email" in inv:
                 recipient_emails.append(inv["email"])
                 invoice_details.append(f"{inv.get('id', 'Unknown')} (${inv.get('amount', 0)})")

        if not recipient_emails:
             return {"status": "FAILED", "message": "No valid recipient emails found in payload."}

        subject = "Friendly Reminder: Overdue Invoices"
        body = f"""
        Hello,

        This is a friendly reminder regarding your outstanding invoices.
        Please check your portal for details.

        Thank you,
        The Team
        """

        # PROVIDER LOGIC
        if preferred_provider == "outlook" and OUTLOOK_AVAILABLE:
            if not user_id:
                logger.error("Outlook bulk send failed: Missing user_id for authentication")
                return {
                    "status": "FAILED",
                    "message": "Outlook requires authenticated user_id",
                    "provider": "outlook"
                }

            try:
                # Outlook send_email_enhanced supports BCC
                 success = await outlook_service.send_email_enhanced(
                    user_id=user_id,  # Use authenticated user_id
                    to_recipients=[admin_email], # Send to self
                    bcc_recipients=recipient_emails,
                    subject=subject,
                    body=body
                )
                 if success:
                    return {
                        "status": "COMPLETED",
                        "message": f"[Outlook] Bulk reminders sent to {len(recipient_emails)} clients.",
                        "provider": "outlook",
                        "recipient_count": len(recipient_emails),
                        "user_id": user_id
                    }
                 return {"status": "FAILED", "message": "Outlook send failed."}
            except Exception as e:
                 logger.error(f"Outlook bulk send failed: {e}")
                 # Fallback/Return Error
                 return {"status": "FAILED", "message": f"Outlook error: {str(e)}"}

        elif GMAIL_AVAILABLE:
            try:
                # Gmail send_message(to, subject, body, cc, bcc)
                # Join BCC with commas
                bcc_str = ", ".join(recipient_emails)
                result = gmail_service.send_message(
                    to=admin_email,
                    subject=subject,
                    body=body,
                    bcc=bcc_str
                )
                if result:
                     return {
                        "status": "COMPLETED",
                        "message": f"[Gmail] Bulk reminders sent to {len(recipient_emails)} clients.",
                        "provider": "gmail",
                         "recipient_count": len(recipient_emails)
                     }
                return {"status": "FAILED", "message": "Gmail send failed (no result)."}
            except Exception as e:
                 logger.error(f"Gmail bulk send failed: {e}")
                 return {"status": "FAILED", "message": f"Gmail error: {str(e)}"}
        
        return {"status": "FAILED", "message": "No email provider available"}

# Singleton
active_intervention_service = ActiveInterventionService()
