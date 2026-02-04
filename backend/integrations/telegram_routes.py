"""
Telegram Routes for ATOM Platform
Exposes AtomTelegramIntegration via FastAPI

Enhanced with interactive keyboards, callback queries, inline mode, and chat actions.
"""

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from integrations.atom_telegram_integration import atom_telegram_integration
from integrations.universal_webhook_bridge import universal_webhook_bridge

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/telegram", tags=["Telegram"])

# ============================================================================
# Webhook & Core Endpoints
# ============================================================================

@router.post("/webhook")
async def telegram_webhook(update: Dict[str, Any]):
    """
    Telegram webhook endpoint for incoming updates.

    Handles:
    - Messages
    - Callback queries (inline keyboard button presses)
    - Inline queries
    - Chat actions
    """
    logger.info(f"Received Telegram webhook update: {update.get('update_id')}")

    # Check for callback query (button press)
    callback_query = update.get("callback_query")
    if callback_query:
        # Route to callback handler
        import asyncio
        asyncio.create_task(atom_telegram_integration.handle_callback_query(callback_query))
        return {"status": "ok", "callback_query_id": callback_query.get("id")}

    # Check for inline query
    inline_query = update.get("inline_query")
    if inline_query:
        # Route to inline handler
        import asyncio
        asyncio.create_task(atom_telegram_integration.handle_inline_query(inline_query))
        return {"status": "ok", "inline_query_id": inline_query.get("id")}

    # Check if it's a message
    message = update.get("message")
    if message:
        # Route to Universal Webhook Bridge
        import asyncio
        asyncio.create_task(universal_webhook_bridge.process_incoming_message("telegram", message))

    return {"status": "ok"}

@router.get("/health")
async def telegram_health():
    """Telegram health check"""
    try:
        status = await atom_telegram_integration.get_service_status()
        if status.get("status") == "active":
            return {"status": "healthy", "service": "Telegram"}
        return {"status": "inactive", "service": "Telegram"}
    except Exception as e:
        logger.error(f"Telegram health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}

@router.get("/status")
async def telegram_status():
    """Get detailed Telegram status"""
    return await atom_telegram_integration.get_service_status()

@router.get("/workspaces/{user_id}")
async def get_telegram_workspaces(user_id: int):
    """Get Telegram workspaces for user"""
    return await atom_telegram_integration.get_intelligent_workspaces(user_id)

# ============================================================================
# Interactive Keyboard Endpoints
# ============================================================================

class SendKeyboardRequest(BaseModel):
    """Request to send message with inline keyboard"""
    chat_id: int = Field(..., description="Telegram chat ID")
    text: str = Field(..., description="Message text")
    keyboard: List[List[Dict[str, Any]]] = Field(..., description="Inline keyboard buttons")
    parse_mode: Optional[str] = Field(None, description="Markdown or HTML")
    disable_web_page_preview: Optional[bool] = Field(None)
    disable_notification: Optional[bool] = Field(None)
    reply_to_message_id: Optional[int] = Field(None)

class KeyboardButton(BaseModel):
    """Individual keyboard button"""
    text: str = Field(..., description="Button label")
    callback_data: Optional[str] = Field(None, description="Data for callback query")
    url: Optional[str] = Field(None, description="URL to open")
    switch_inline_query: Optional[str] = Field(None, description="Switch to inline query")
    switch_inline_query_current_chat: Optional[str] = Field(None, description="Switch to inline in current chat")

@router.post("/send-keyboard")
async def send_keyboard_message(request: SendKeyboardRequest):
    """
    Send a message with interactive inline keyboard.

    Keyboard buttons can trigger:
    - Callback queries (for bot processing)
    - URLs (opens in browser)
    - Inline query switching
    """
    result = await atom_telegram_integration.send_message_with_keyboard(
        chat_id=request.chat_id,
        text=request.text,
        keyboard=request.keyboard,
        parse_mode=request.parse_mode,
        disable_web_page_preview=request.disable_web_page_preview,
        disable_notification=request.disable_notification,
        reply_to_message_id=request.reply_to_message_id,
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
    return result

@router.post("/edit-keyboard")
async def edit_message_keyboard(
    chat_id: int,
    message_id: int,
    keyboard: List[List[Dict[str, Any]]],
):
    """
    Edit keyboard of an existing message.

    Allows updating buttons after message is sent.
    """
    result = await atom_telegram_integration.edit_message_keyboard(
        chat_id=chat_id,
        message_id=message_id,
        keyboard=keyboard,
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
    return result

@router.post("/answer-callback")
async def answer_callback_query(
    callback_query_id: str,
    text: Optional[str] = None,
    show_alert: Optional[bool] = False,
    url: Optional[str] = None,
    cache_time: Optional[int] = None,
):
    """
    Answer a callback query from an inline keyboard button.

    Response options:
    - text: Show notification text
    - show_alert: Show alert instead of notification
    - url: Open URL
    - cache_time: Cache button response (in seconds)
    """
    result = await atom_telegram_integration.answer_callback_query(
        callback_query_id=callback_query_id,
        text=text,
        show_alert=show_alert,
        url=url,
        cache_time=cache_time,
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
    return result

# ============================================================================
# Inline Mode Endpoints
# ============================================================================

class InlineQueryRequest(BaseModel):
    """Request to answer inline query"""
    inline_query_id: str = Field(..., description="Inline query ID")
    results: List[Dict[str, Any]] = Field(..., description="Inline query results")
    cache_time: Optional[int] = Field(300, description="Cache time in seconds")
    personal: Optional[bool] = Field(None, description="Cache only for user")
    next_offset: Optional[str] = Field(None, description="Next offset for pagination")

@router.post("/answer-inline")
async def answer_inline_query(request: InlineQueryRequest):
    """
    Answer an inline query.

    Used for:
    - Inline bot suggestions
    - Inline mode results
    - Search results in chat
    """
    result = await atom_telegram_integration.answer_inline_query(
        inline_query_id=request.inline_query_id,
        results=request.results,
        cache_time=request.cache_time,
        personal=request.personal,
        next_offset=request.next_offset,
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
    return result

# ============================================================================
# Chat Action Endpoints
# ============================================================================

class ChatActionRequest(BaseModel):
    """Request to send chat action"""
    chat_id: int = Field(..., description="Telegram chat ID")
    action: str = Field(..., description="Action: typing, upload_photo, record_video, etc.")
    progress: Optional[int] = Field(None, description="Progress percentage (0-100)")

@router.post("/send-chat-action")
async def send_chat_action(request: ChatActionRequest):
    """
    Send a chat action indicator.

    Supported actions:
    - typing: "typing..." indicator
    - upload_photo: "uploading photo..." indicator
    - record_video: "recording video..." indicator
    - upload_video: "uploading video..." indicator
    - record_audio: "recording audio..." indicator
    - upload_audio: "uploading audio..." indicator
    - upload_document: "uploading document..." indicator
    - choose_sticker: "choosing a sticker..." indicator
    - find_location: "looking for location..." indicator
    - record_video_note: "recording video note..." indicator
    - upload_video_note: "uploading video note..." indicator
    """
    result = await atom_telegram_integration.send_chat_action(
        chat_id=request.chat_id,
        action=request.action,
        progress=request.progress,
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
    return result

# ============================================================================
# Message Endpoints (Enhanced)
# ============================================================================

class TelegramMessageRequest(BaseModel):
    channel_id: int
    message: str
    metadata: Optional[Dict[str, Any]] = None
    parse_mode: Optional[str] = None
    disable_web_page_preview: Optional[bool] = None
    disable_notification: Optional[bool] = None
    reply_to_message_id: Optional[int] = None

@router.post("/send")
async def send_telegram_message(request: TelegramMessageRequest):
    """
    Send a telegram message with enhanced options.

    Enhanced with:
    - Parse mode (Markdown, HTML)
    - Web page preview control
    - Notification control
    - Reply to message
    """
    result = await atom_telegram_integration.send_intelligent_message(
        channel_id=request.channel_id,
        message=request.message,
        metadata=request.metadata,
        parse_mode=request.parse_mode,
        disable_web_page_preview=request.disable_web_page_preview,
        disable_notification=request.disable_notification,
        reply_to_message_id=request.reply_to_message_id,
    )
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
    return result

class SendPhotoRequest(BaseModel):
    chat_id: int
    photo: str = Field(..., description="Photo URL or file_id")
    caption: Optional[str] = None
    parse_mode: Optional[str] = None

@router.post("/send-photo")
async def send_telegram_photo(request: SendPhotoRequest):
    """Send a photo to Telegram chat"""
    result = await atom_telegram_integration.send_photo(
        chat_id=request.chat_id,
        photo=request.photo,
        caption=request.caption,
        parse_mode=request.parse_mode,
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
    return result

class SendPollRequest(BaseModel):
    chat_id: int
    question: str
    options: List[str]
    is_anonymous: Optional[bool] = False
    allows_multiple_answers: Optional[bool] = False
    explanation: Optional[str] = None

@router.post("/send-poll")
async def send_telegram_poll(request: SendPollRequest):
    """Send a poll to Telegram chat"""
    result = await atom_telegram_integration.send_poll(
        chat_id=request.chat_id,
        question=request.question,
        options=request.options,
        is_anonymous=request.is_anonymous,
        allows_multiple_answers=request.allows_multiple_answers,
        explanation=request.explanation,
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
    return result

# ============================================================================
# Utility Endpoints
# ============================================================================

@router.post("/get-chat-info/{chat_id}")
async def get_chat_info(chat_id: int):
    """Get information about a Telegram chat"""
    result = await atom_telegram_integration.get_chat_info(chat_id)

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
    return result

@router.get("/capabilities")
async def telegram_capabilities():
    """Get Telegram integration capabilities"""
    return {
        "platform": "Telegram",
        "features": {
            "messaging": True,
            "interactive_keyboards": True,
            "callback_queries": True,
            "inline_mode": True,
            "chat_actions": True,
            "photos": True,
            "polls": True,
            "documents": True,
            "stickers": True,
            "videos": True,
            "voice_messages": True,
            "video_notes": True,
            "locations": True,
            "contacts": True,
            "web_pages": True,
        },
        "governance": {
            "student": {"blocked": True},
            "intern": {"requires_approval": True},
            "supervised": {"auto_approved": True, "monitored": True},
            "autonomous": {"full_access": True},
        },
        "interactive_components": {
            "inline_keyboards": True,
            "reply_keyboards": True,
            "custom_keyboards": True,
            "button_callback_data": True,
            "button_urls": True,
            "inline_query_results": True,
        },
    }
