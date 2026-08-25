import asyncio
import logging
import datetime
import os
from typing import Dict, Any, List

from core.database import SessionLocal
from core.models import HITLAction, HITLActionStatus
from core.agent_governance_service import AgentGovernanceService
from integrations.outlook_routes import outlook_service
from core.websockets import manager
from core.llm_service import get_llm_service

logger = logging.getLogger(__name__)

# Configurable CC email addresses
DEFAULT_CC_RECIPIENTS = ["chandrakant@brennan.ca", "support@brennan.ca"]

# Fallback reply used when the LLM is unavailable or the flag is off.
DEFAULT_REPLY_TEMPLATE = (
    "Hi,\n\nChandrakant here from Brennan Machinery. I have received a quote "
    "request from you.\n\nHow can I assist you today?\n\nThanks"
)

# LLM-drafted replies: off restores the fixed template above.
LLM_DRAFTS_FLAG = "ATOM_OUTLOOK_LLM_DRAFTS"
LLM_DRAFT_TIMEOUT_SECONDS = 10

# Set to track processed email message IDs during runtime to prevent double-drafting
PROCESSED_EMAIL_IDS = set()


def llm_drafts_enabled() -> bool:
    return os.getenv(LLM_DRAFTS_FLAG, "true").lower() in ("1", "true", "yes", "on")


def _build_draft_prompt(
    sender_name: str,
    sender_email: str,
    subject: str,
    body: str,
    preview: str,
) -> str:
    """Build the prompt for the reply-drafting LLM call (pure, testable)."""
    sender_name = (sender_name or "the customer").strip()
    email_body = (body or "").strip() or (preview or "").strip()
    subject = (subject or "(no subject)").strip()
    return (
        f"A customer sent a quote request to Brennan Machinery via the contact "
        f"page (https://brennan.ca/pages/contact).\n\n"
        f"Customer name: {sender_name}\n"
        f"Customer email: {sender_email}\n"
        f"Email subject: {subject}\n"
        f"Email body:\n{email_body[:2000]}\n\n"
        f"Write a professional, warm reply email. Do not invent prices, "
        f"lead times, or product specs that are not in the customer's message "
        f"— say that you will get them the details. Sign the email as "
        f"Chandrakant from Brennan Machinery. Keep it under 150 words."
    )


async def _draft_reply(
    sender_name: str,
    sender_email: str,
    subject: str,
    body: str,
    preview: str,
) -> str:
    """Draft a reply to a customer query email via the LLM. Never raises;
    returns "" on any failure/timeout so the caller falls back to the template."""
    try:
        llm = get_llm_service()
        draft = await asyncio.wait_for(
            llm.generate(
                prompt=_build_draft_prompt(sender_name, sender_email, subject, body, preview),
                system_instruction=(
                    "You are the email assistant for Brennan Machinery, a metal "
                    "fabrication company. Write concise, professional customer "
                    "replies. Never invent facts."
                ),
                temperature=0.7,
                max_tokens=400,
            ),
            timeout=LLM_DRAFT_TIMEOUT_SECONDS,
        )
        return (draft or "").strip()
    except Exception as e:
        logger.warning(f"[Outlook Automation] LLM reply draft failed, using template: {e}")
        return ""

async def process_outlook_automation():
    """
    Background worker loop that:
    1. Reads unread emails from Outlook (simulated or real).
    2. Scans for 'https://brennan.ca/pages/contact'.
    3. Requests approval (HITLAction) to reply.
    4. Detects decided/approved HITLActions and sends the reply email.
    """
    db = SessionLocal()
    try:
        user_id = "default_user"  # Default user in development
        
        # Step 1: Fetch unread emails
        emails = await outlook_service.get_unread_emails(user_id=user_id, max_results=10)
        
        # Fallback/Mock behavior in local development when no real unread emails are fetched:
        # We simulate receiving a quote request if there's no active real Microsoft token.
        # This makes the automation 100% testable out-of-the-box!
        has_real_emails = len(emails) > 0
        if not has_real_emails:
            # Let's check if we already have a mock action in database to avoid looping infinitely
            mock_action_exists = db.query(HITLAction).filter(
                HITLAction.action_type == "outlook_automation_send_email"
            ).first()
            
            # If no action exists yet, simulate one incoming email to show the flow!
            if not mock_action_exists:
                logger.info("[Outlook Automation] Simulating incoming mock email for Brennan Machinery quote request...")
                emails = [{
                    "id": "mock_email_brennan_12345",
                    "subject": "Quote Request - Brennan Machinery Contact",
                    "body_preview": "Hi, I visited your page at https://brennan.ca/pages/contact. Please send me a quote.",
                    "body": {"contentType": "text", "content": "Hi, I visited your page at https://brennan.ca/pages/contact. Please send me a quote for the machinery parts."},
                    "from_field": {
                        "emailAddress": {
                            "name": "Customer John",
                            "address": "john.customer@example.com"
                        }
                    }
                }]
        
        # Process each unread email
        for email in emails:
            email_id = email.get("id")
            if not email_id or email_id in PROCESSED_EMAIL_IDS:
                continue
                
            body_content = ""
            if isinstance(email.get("body"), dict):
                body_content = email.get("body", {}).get("content", "")
            else:
                body_content = str(email.get("body") or "")
            body_preview = email.get("body_preview", "")
            
            full_text = (body_content + " " + body_preview).lower()
            
            # Check for target URL
            if "https://brennan.ca/pages/contact" in full_text:
                # Extract sender email address
                from_field = email.get("from_field") or {}
                sender_email = from_field.get("emailAddress", {}).get("address")
                if not sender_email:
                    # try fallback sender field
                    sender_email = (email.get("sender") or {}).get("emailAddress", {}).get("address")
                
                if not sender_email:
                    logger.warning(f"[Outlook Automation] Email {email_id} matched URL but no sender email found")
                    continue
                
                # Check if we already created a HITL action for this specific email
                existing_hitl = db.query(HITLAction).filter(
                    HITLAction.action_type == "outlook_automation_send_email",
                    HITLAction.reason.like(f"%{email_id}%")
                ).first()
                
                if existing_hitl:
                    continue
                
                # Create HITL Action (Human approval required before sending email)
                logger.info(f"[Outlook Automation] Match found in email {email_id} from {sender_email}. Requesting HITL approval...")

                # LLM-drafted reply (personalized) with the template as a
                # safe fallback — the approval UI shows whichever body lands here.
                draft_body = DEFAULT_REPLY_TEMPLATE
                draft_subject = "Brennan Machinery"
                if llm_drafts_enabled():
                    sender_name = str(
                        (from_field.get("emailAddress") or {}).get("name")
                        or (email.get("sender") or {}).get("name")
                        or ""
                    )
                    drafted = await _draft_reply(
                        sender_name=sender_name,
                        sender_email=str(sender_email),
                        subject=str(email.get("subject") or ""),
                        body=str(body_content or ""),
                        preview=str(body_preview or ""),
                    )
                    if drafted:
                        draft_body = drafted
                        original_subject = str(email.get("subject") or "").strip()
                        if original_subject:
                            draft_subject = f"Re: {original_subject}"[:120]

                gov_service = AgentGovernanceService(db)
                params = {
                    "user_id": user_id,
                    "to_recipients": [sender_email],
                    "cc_recipients": DEFAULT_CC_RECIPIENTS,
                    "subject": draft_subject,
                    "body": draft_body,
                    "email_id": email_id
                }
                
                hitl_id = gov_service.request_approval(
                    agent_id="outlook_automation_agent",
                    action_type="outlook_automation_send_email",
                    params=params,
                    reason=f"Email from {sender_email} contains Brennan contact page. Requesting approval to reply. Original Email ID: {email_id}"
                )
                
                # Broadcast via WebSockets so the UI/Chat gets updated live!
                try:
                    asyncio.create_task(manager.broadcast_event(
                        "chat",
                        "hitl_paused",
                        {
                            "id": hitl_id,
                            "type": "hitl_paused",
                            "action_type": "outlook_automation_send_email",
                            "agent_id": "outlook_automation_agent",
                            "reason": f"Approval required to reply to Brennan Machinery quote request from {sender_email}.",
                            "params": params
                        }
                    ))
                except Exception as ws_err:
                    logger.debug(f"WS broadcast failed: {ws_err}")
                
                PROCESSED_EMAIL_IDS.add(email_id)

        # Step 2: Scan for newly APPROVED actions in database
        approved_actions = db.query(HITLAction).filter(
            HITLAction.action_type == "outlook_automation_send_email",
            HITLAction.status == HITLActionStatus.APPROVED.value
        ).all()
        
        for action in approved_actions:
            params = action.params or {}
            to_recipients = params.get("to_recipients", [])
            cc_recipients = params.get("cc_recipients", [])
            subject = params.get("subject", "Brennan Machinery")
            body = params.get("body", "")
            
            logger.info(f"[Outlook Automation] Sending approved reply email to {to_recipients} (CC: {cc_recipients})...")
            
            # Send email via Outlook service
            send_result = await outlook_service.send_email(
                user_id=user_id,
                to_recipients=to_recipients,
                subject=subject,
                body=body,
                cc_recipients=cc_recipients
            )
            
            # Update action status to completed
            action.status = "completed"
            action.reviewed_at = datetime.datetime.now()
            db.commit()
            
            logger.info(f"[Outlook Automation] Reply email successfully sent for HITL action {action.id}!")
            
            # Broadcast final decision update to WebSockets
            try:
                asyncio.create_task(manager.broadcast_event(
                    "chat",
                    "hitl_decision",
                    {
                        "id": action.id,
                        "type": "hitl_decision",
                        "status": "approved",
                        "action_type": "outlook_automation_send_email"
                    }
                ))
            except Exception as ws_err:
                logger.debug(f"WS decision broadcast failed: {ws_err}")

        # Clean up rejected/denied actions
        rejected_actions = db.query(HITLAction).filter(
            HITLAction.action_type == "outlook_automation_send_email",
            HITLAction.status == HITLActionStatus.REJECTED.value
        ).all()
        
        for action in rejected_actions:
            action.status = "cancelled"
            db.commit()
            logger.info(f"[Outlook Automation] HITL action {action.id} rejected by user. Reply email cancelled.")

    except Exception as e:
        logger.error(f"[Outlook Automation] Error in processing loop: {e}", exc_info=True)
    finally:
        db.close()

async def start_outlook_automation_loop():
    """Start background task loop"""
    logger.info("[Outlook Automation] Starting background automation daemon...")
    while True:
        await process_outlook_automation()
        await asyncio.sleep(15)  # Scan every 15 seconds
