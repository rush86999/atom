"""
Gmail Email Workflow API Endpoints
Complete Gmail email workflow automation with LanceDB integration
"""

import os
import logging
import json
import asyncio
import tempfile
import shutil
from datetime import datetime, timezone
from flask import request, jsonify, Blueprint, send_file
from typing import Dict, Any, Optional, List
from werkzeug.utils import secure_filename

# Import Gmail LanceDB service
try:
    from gmail_lancedb_ingestion_service import (
        gmail_lancedb_service,
        GmailMemorySettings
    )
    GMAIL_LANCEDB_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Gmail LanceDB service not available: {e}")
    GMAIL_LANCEDB_AVAILABLE = False
    gmail_lancedb_service = None

# Import enhanced Gmail service
try:
    from gmail_enhanced_service import gmail_enhanced_service
    GMAIL_SERVICE_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Gmail service not available: {e}")
    GMAIL_SERVICE_AVAILABLE = False

# Configure logging
logger = logging.getLogger(__name__)

# Create Flask blueprint
gmail_email_workflow_bp = Blueprint("gmail_email_workflow_bp", __name__)

# Error handling decorator
def handle_gmail_email_workflow_errors(func):
    """Decorator to handle Gmail email workflow API errors"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Gmail email workflow API error: {e}")
            return jsonify({
                "ok": False,
                "error": str(e),
                "error_type": "api_error"
            }), 500
    return wrapper

# Authentication decorator
def require_user_auth(func):
    """Decorator to require user authentication"""
    def wrapper(*args, **kwargs):
        data = request.get_json() if request.is_json else {}
        user_id = data.get('user_id') or request.headers.get('X-User-ID')
        access_token = data.get('access_token') or request.headers.get('X-Access-Token')
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "User ID is required"
            }), 400
        
        if not access_token:
            return jsonify({
                "ok": False,
                "error": "Access token is required"
            }), 400
        
        return func(*args, **kwargs)
    return wrapper

# File upload validation
ALLOWED_ATTACHMENT_TYPES = {
    'txt', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
    'jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp',
    'zip', 'rar', '7z', 'tar', 'gz',
    'csv', 'json', 'xml', 'yaml', 'yml'
}

MAX_ATTACHMENT_SIZE = 25 * 1024 * 1024  # 25MB

def allowed_attachment(filename: str) -> bool:
    """Check if attachment type is allowed"""
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    return ext in ALLOWED_ATTACHMENT_TYPES

@gmail_email_workflow_bp.route("/api/gmail/email-workflow/health", methods=["GET"])
@handle_gmail_email_workflow_errors
def health():
    """Health check for Gmail email workflow service"""
    try:
        service_info = {
            "service": "gmail-email-workflow-api",
            "status": "healthy",
            "version": "1.0.0",
            "features": {
                "lancedb_available": GMAIL_LANCEDB_AVAILABLE,
                "gmail_service_available": GMAIL_SERVICE_AVAILABLE,
                "message_operations": True,
                "thread_management": True,
                "label_management": True,
                "attachment_handling": True,
                "email_search": True,
                "memory_ingestion": True,
                "user_controls": True,
                "automation_features": True
            }
        }
        
        return jsonify({
            "ok": True,
            **service_info
        })
        
    except Exception as e:
        logger.error(f"Gmail email workflow health check error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Message Operations
@gmail_email_workflow_bp.route("/api/gmail/email-workflow/messages/list", methods=["POST"])
@handle_gmail_email_workflow_errors
@require_user_auth
def list_messages():
    """List Gmail messages"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        access_token = data.get('access_token')
        max_results = data.get('max_results', 50)
        query = data.get('query', '')
        label_ids = data.get('label_ids', [])
        include_spam_trash = data.get('include_spam_trash', False)
        page_token = data.get('page_token')
        
        if not GMAIL_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Gmail service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            gmail_enhanced_service.list_messages(
                access_token=access_token,
                max_results=max_results,
                query=query,
                label_ids=label_ids,
                include_spam_trash=include_spam_trash,
                page_token=page_token
            )
        )
        loop.close()
        
        if result.get('error'):
            return jsonify({
                "ok": False,
                "error": result.get('error'),
                "error_type": result.get('error_type', 'list_error')
            }), 500
        
        return jsonify({
            "ok": True,
            "messages": result.get('messages', []),
            "next_page_token": result.get('next_page_token'),
            "result_size_estimate": result.get('result_size_estimate', 0),
            "total_results": result.get('total_results', 0),
            "filters": {
                "max_results": max_results,
                "query": query,
                "label_ids": label_ids,
                "include_spam_trash": include_spam_trash,
                "page_token": page_token
            }
        })
        
    except Exception as e:
        logger.error(f"Error listing Gmail messages: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@gmail_email_workflow_bp.route("/api/gmail/email-workflow/messages/get", methods=["POST"])
@handle_gmail_email_workflow_errors
@require_user_auth
def get_message():
    """Get Gmail message"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        access_token = data.get('access_token')
        message_id = data.get('message_id')
        format = data.get('format', 'full')
        include_attachments = data.get('include_attachments', True)
        
        if not GMAIL_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Gmail service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        message = loop.run_until_complete(
            gmail_enhanced_service.get_message(
                message_id=message_id,
                access_token=access_token,
                format=format,
                include_attachments=include_attachments
            )
        )
        loop.close()
        
        if message:
            return jsonify({
                "ok": True,
                "message": message.to_dict()
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Message not found",
                "error_type": "not_found"
            }), 404
        
    except Exception as e:
        logger.error(f"Error getting Gmail message: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@gmail_email_workflow_bp.route("/api/gmail/email-workflow/messages/send", methods=["POST"])
@handle_gmail_email_workflow_errors
@require_user_auth
def send_message():
    """Send Gmail message"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        access_token = data.get('access_token')
        to = data.get('to')
        subject = data.get('subject')
        body = data.get('body', '')
        cc = data.get('cc', '')
        bcc = data.get('bcc', '')
        from_email = data.get('from_email', '')
        reply_to_message_id = data.get('reply_to_message_id')
        is_html = data.get('is_html', False)
        attachments = data.get('attachments', [])
        
        if not GMAIL_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Gmail service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            gmail_enhanced_service.send_message(
                access_token=access_token,
                to=to,
                subject=subject,
                body=body,
                cc=cc,
                bcc=bcc,
                from_email=from_email,
                reply_to_message_id=reply_to_message_id,
                attachments=attachments,
                is_html=is_html
            )
        )
        loop.close()
        
        if result.get('success'):
            return jsonify({
                "ok": True,
                "message": {
                    "id": result.get('message_id'),
                    "thread_id": result.get('thread_id'),
                    "label_ids": result.get('label_ids')
                },
                "message_sent": "Message sent successfully"
            })
        else:
            return jsonify({
                "ok": False,
                "error": result.get('error', 'Unknown send error'),
                "error_type": result.get('error_type', 'send_error')
            }), 500
        
    except Exception as e:
        logger.error(f"Error sending Gmail message: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@gmail_email_workflow_bp.route("/api/gmail/email-workflow/messages/search", methods=["POST"])
@handle_gmail_email_workflow_errors
@require_user_auth
def search_messages():
    """Search Gmail messages"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        access_token = data.get('access_token')
        query = data.get('query', '')
        max_results = data.get('max_results', 50)
        page_token = data.get('page_token')
        
        if not GMAIL_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Gmail service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            gmail_enhanced_service.search_messages(
                access_token=access_token,
                query=query,
                max_results=max_results,
                page_token=page_token
            )
        )
        loop.close()
        
        if result.get('error'):
            return jsonify({
                "ok": False,
                "error": result.get('error'),
                "error_type": result.get('error_type', 'search_error')
            }), 500
        
        return jsonify({
            "ok": True,
            "messages": result.get('messages', []),
            "next_page_token": result.get('next_page_token'),
            "result_size_estimate": result.get('result_size_estimate', 0),
            "total_results": result.get('total_results', 0),
            "search_filters": {
                "query": query,
                "max_results": max_results,
                "page_token": page_token
            }
        })
        
    except Exception as e:
        logger.error(f"Error searching Gmail messages: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@gmail_email_workflow_bp.route("/api/gmail/email-workflow/messages/trash", methods=["POST"])
@handle_gmail_email_workflow_errors
@require_user_auth
def trash_message():
    """Trash Gmail message"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        access_token = data.get('access_token')
        message_id = data.get('message_id')
        
        if not GMAIL_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Gmail service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(
            gmail_enhanced_service.trash_message(
                access_token=access_token,
                message_id=message_id
            )
        )
        loop.close()
        
        if success:
            return jsonify({
                "ok": True,
                "message": "Message moved to trash successfully"
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Failed to trash message",
                "error_type": "trash_error"
            }), 500
        
    except Exception as e:
        logger.error(f"Error trashing Gmail message: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@gmail_email_workflow_bp.route("/api/gmail/email-workflow/messages/delete", methods=["POST"])
@handle_gmail_email_workflow_errors
@require_user_auth
def delete_message():
    """Delete Gmail message permanently"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        access_token = data.get('access_token')
        message_id = data.get('message_id')
        confirm = data.get('confirm', False)
        
        if not confirm:
            return jsonify({
                "ok": False,
                "error": "Confirmation required to permanently delete message",
                "error_type": "confirmation_required"
            }), 400
        
        if not GMAIL_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Gmail service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(
            gmail_enhanced_service.delete_message(
                access_token=access_token,
                message_id=message_id
            )
        )
        loop.close()
        
        if success:
            return jsonify({
                "ok": True,
                "message": "Message deleted permanently"
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Failed to delete message",
                "error_type": "delete_error"
            }), 500
        
    except Exception as e:
        logger.error(f"Error deleting Gmail message: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Thread Management
@gmail_email_workflow_bp.route("/api/gmail/email-workflow/threads/list", methods=["POST"])
@handle_gmail_email_workflow_errors
@require_user_auth
def list_threads():
    """List Gmail threads"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        access_token = data.get('access_token')
        max_results = data.get('max_results', 50)
        query = data.get('query', '')
        label_ids = data.get('label_ids', [])
        include_spam_trash = data.get('include_spam_trash', False)
        page_token = data.get('page_token')
        
        if not GMAIL_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Gmail service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            gmail_enhanced_service.list_threads(
                access_token=access_token,
                max_results=max_results,
                query=query,
                label_ids=label_ids,
                include_spam_trash=include_spam_trash,
                page_token=page_token
            )
        )
        loop.close()
        
        if result.get('error'):
            return jsonify({
                "ok": False,
                "error": result.get('error'),
                "error_type": result.get('error_type', 'list_error')
            }), 500
        
        return jsonify({
            "ok": True,
            "threads": result.get('threads', []),
            "next_page_token": result.get('next_page_token'),
            "result_size_estimate": result.get('result_size_estimate', 0),
            "total_results": result.get('total_results', 0),
            "filters": {
                "max_results": max_results,
                "query": query,
                "label_ids": label_ids,
                "include_spam_trash": include_spam_trash,
                "page_token": page_token
            }
        })
        
    except Exception as e:
        logger.error(f"Error listing Gmail threads: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@gmail_email_workflow_bp.route("/api/gmail/email-workflow/threads/get", methods=["POST"])
@handle_gmail_email_workflow_errors
@require_user_auth
def get_thread():
    """Get Gmail thread"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        access_token = data.get('access_token')
        thread_id = data.get('thread_id')
        
        if not GMAIL_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Gmail service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        thread = loop.run_until_complete(
            gmail_enhanced_service.get_thread(
                thread_id=thread_id,
                access_token=access_token
            )
        )
        loop.close()
        
        if thread:
            return jsonify({
                "ok": True,
                "thread": thread.to_dict()
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Thread not found",
                "error_type": "not_found"
            }), 404
        
    except Exception as e:
        logger.error(f"Error getting Gmail thread: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Label Management
@gmail_email_workflow_bp.route("/api/gmail/email-workflow/labels/list", methods=["POST"])
@handle_gmail_email_workflow_errors
@require_user_auth
def list_labels():
    """List Gmail labels"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        access_token = data.get('access_token')
        
        if not GMAIL_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Gmail service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        labels = loop.run_until_complete(
            gmail_enhanced_service.get_labels(access_token)
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "labels": [label.to_dict() for label in labels],
            "total_labels": len(labels)
        })
        
    except Exception as e:
        logger.error(f"Error listing Gmail labels: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@gmail_email_workflow_bp.route("/api/gmail/email-workflow/labels/create", methods=["POST"])
@handle_gmail_email_workflow_errors
@require_user_auth
def create_label():
    """Create Gmail label"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        access_token = data.get('access_token')
        name = data.get('name')
        label_list_visibility = data.get('label_list_visibility', 'labelShow')
        message_list_visibility = data.get('message_list_visibility', 'show')
        color = data.get('color', {})
        
        if not GMAIL_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Gmail service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        label = loop.run_until_complete(
            gmail_enhanced_service.create_label(
                access_token=access_token,
                name=name,
                label_list_visibility=label_list_visibility,
                message_list_visibility=message_list_visibility,
                color=color
            )
        )
        loop.close()
        
        if label:
            return jsonify({
                "ok": True,
                "label": label.to_dict(),
                "message": "Label created successfully"
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Failed to create label",
                "error_type": "create_error"
            }), 500
        
    except Exception as e:
        logger.error(f"Error creating Gmail label: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@gmail_email_workflow_bp.route("/api/gmail/email-workflow/messages/modify-labels", methods=["POST"])
@handle_gmail_email_workflow_errors
@require_user_auth
def modify_message_labels():
    """Modify Gmail message labels"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        access_token = data.get('access_token')
        message_id = data.get('message_id')
        add_labels = data.get('add_labels', [])
        remove_labels = data.get('remove_labels', [])
        
        if not GMAIL_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Gmail service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(
            gmail_enhanced_service.modify_message_labels(
                access_token=access_token,
                message_id=message_id,
                add_labels=add_labels,
                remove_labels=remove_labels
            )
        )
        loop.close()
        
        if success:
            return jsonify({
                "ok": True,
                "message": "Message labels modified successfully",
                "changes": {
                    "added_labels": add_labels,
                    "removed_labels": remove_labels
                }
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Failed to modify message labels",
                "error_type": "modify_error"
            }), 500
        
    except Exception as e:
        logger.error(f"Error modifying Gmail message labels: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Attachments
@gmail_email_workflow_bp.route("/api/gmail/email-workflow/attachments/get", methods=["POST"])
@handle_gmail_email_workflow_errors
@require_user_auth
def get_attachment():
    """Get Gmail attachment"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        access_token = data.get('access_token')
        message_id = data.get('message_id')
        attachment_id = data.get('attachment_id')
        download = data.get('download', False)
        
        if not GMAIL_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Gmail service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        attachment = loop.run_until_complete(
            gmail_enhanced_service.get_attachment(
                access_token=access_token,
                message_id=message_id,
                attachment_id=attachment_id
            )
        )
        loop.close()
        
        if attachment:
            if download:
                # Create temporary file
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=attachment.filename)
                try:
                    # Decode base64 data
                    import base64
                    data = base64.b64decode(attachment.data)
                    temp_file.write(data)
                    temp_file.close()
                    
                    return send_file(
                        temp_file.name,
                        as_attachment=True,
                        download_name=attachment.filename,
                        mimetype=attachment.mime_type
                    )
                finally:
                    # Clean up temp file
                    if os.path.exists(temp_file.name):
                        os.unlink(temp_file.name)
            else:
                return jsonify({
                    "ok": True,
                    "attachment": attachment.to_dict()
                })
        else:
            return jsonify({
                "ok": False,
                "error": "Attachment not found",
                "error_type": "not_found"
            }), 404
        
    except Exception as e:
        logger.error(f"Error getting Gmail attachment: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@gmail_email_workflow_bp.route("/api/gmail/email-workflow/attachments/upload", methods=["POST"])
@handle_gmail_email_workflow_errors
@require_user_auth
def upload_attachment():
    """Upload attachment for Gmail message"""
    try:
        user_id = request.form.get('user_id')
        access_token = request.form.get('access_token')
        to = request.form.get('to')
        subject = request.form.get('subject')
        body = request.form.get('body', '')
        is_html = request.form.get('is_html', 'false').lower() == 'true'
        
        if not user_id or not access_token:
            return jsonify({
                "ok": False,
                "error": "User ID and access token are required"
            }), 400
        
        # Get attachments
        attachments = []
        if 'files' in request.files:
            files = request.files.getlist('files')
            for file in files:
                if file and file.filename and allowed_attachment(file.filename):
                    # Check file size
                    file.seek(0, os.SEEK_END)
                    file_size = file.tell()
                    file.seek(0)
                    
                    if file_size > MAX_ATTACHMENT_SIZE:
                        return jsonify({
                            "ok": False,
                            "error": f"File {file.filename} exceeds maximum size of 25MB",
                            "error_type": "file_too_large"
                        }), 400
                    
                    # Save to temporary file
                    temp_path = os.path.join(tempfile.gettempdir(), secure_filename(file.filename))
                    file.save(temp_path)
                    
                    attachments.append({
                        'path': temp_path,
                        'name': file.filename
                    })
        
        if not attachments:
            return jsonify({
                "ok": False,
                "error": "No valid attachments provided",
                "error_type": "no_attachments"
            }), 400
        
        if not GMAIL_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Gmail service not available"
            }), 503
        
        # Send message with attachments
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            gmail_enhanced_service.send_message(
                access_token=access_token,
                to=to,
                subject=subject,
                body=body,
                attachments=attachments,
                is_html=is_html
            )
        )
        loop.close()
        
        # Clean up temporary files
        for attachment in attachments:
            if os.path.exists(attachment['path']):
                os.unlink(attachment['path'])
        
        if result.get('success'):
            return jsonify({
                "ok": True,
                "message": {
                    "id": result.get('message_id'),
                    "thread_id": result.get('thread_id'),
                    "label_ids": result.get('label_ids')
                },
                "message_sent": "Message with attachments sent successfully"
            })
        else:
            return jsonify({
                "ok": False,
                "error": result.get('error', 'Unknown send error'),
                "error_type": result.get('error_type', 'send_error')
            }), 500
        
    except Exception as e:
        logger.error(f"Error uploading Gmail attachment: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Drafts
@gmail_email_workflow_bp.route("/api/gmail/email-workflow/drafts/list", methods=["POST"])
@handle_gmail_email_workflow_errors
@require_user_auth
def list_drafts():
    """List Gmail drafts"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        access_token = data.get('access_token')
        
        if not GMAIL_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Gmail service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        drafts = loop.run_until_complete(
            gmail_enhanced_service.get_drafts(access_token)
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "drafts": [draft.to_dict() for draft in drafts],
            "total_drafts": len(drafts)
        })
        
    except Exception as e:
        logger.error(f"Error listing Gmail drafts: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@gmail_email_workflow_bp.route("/api/gmail/email-workflow/drafts/create", methods=["POST"])
@handle_gmail_email_workflow_errors
@require_user_auth
def create_draft():
    """Create Gmail draft"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        access_token = data.get('access_token')
        to = data.get('to')
        subject = data.get('subject')
        body = data.get('body', '')
        cc = data.get('cc', '')
        bcc = data.get('bcc', '')
        from_email = data.get('from_email', '')
        attachments = data.get('attachments', [])
        is_html = data.get('is_html', False)
        
        if not GMAIL_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Gmail service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        draft = loop.run_until_complete(
            gmail_enhanced_service.create_draft(
                access_token=access_token,
                to=to,
                subject=subject,
                body=body,
                cc=cc,
                bcc=bcc,
                from_email=from_email,
                attachments=attachments,
                is_html=is_html
            )
        )
        loop.close()
        
        if draft:
            return jsonify({
                "ok": True,
                "draft": draft.to_dict(),
                "message": "Draft created successfully"
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Failed to create draft",
                "error_type": "create_error"
            }), 500
        
    except Exception as e:
        logger.error(f"Error creating Gmail draft: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Memory Management
@gmail_email_workflow_bp.route("/api/gmail/email-workflow/memory/settings", methods=["POST"])
@handle_gmail_email_workflow_errors
@require_user_auth
def get_memory_settings():
    """Get Gmail memory settings for user"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not GMAIL_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Gmail LanceDB service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        settings = loop.run_until_complete(
            gmail_lancedb_service.get_user_settings(user_id)
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "settings": {
                "user_id": settings.user_id,
                "ingestion_enabled": settings.ingestion_enabled,
                "sync_frequency": settings.sync_frequency,
                "data_retention_days": settings.data_retention_days,
                "include_labels": settings.include_labels or [],
                "exclude_labels": settings.exclude_labels or [],
                "include_threads": settings.include_threads,
                "include_drafts": settings.include_drafts,
                "include_sent": settings.include_sent,
                "include_received": settings.include_received,
                "max_messages_per_sync": settings.max_messages_per_sync,
                "max_attachment_size_mb": settings.max_attachment_size_mb,
                "include_attachments": settings.include_attachments,
                "index_attachments": settings.index_attachments,
                "search_enabled": settings.search_enabled,
                "semantic_search_enabled": settings.semantic_search_enabled,
                "metadata_extraction_enabled": settings.metadata_extraction_enabled,
                "thread_tracking_enabled": settings.thread_tracking_enabled,
                "contact_analysis_enabled": settings.contact_analysis_enabled,
                "last_sync_timestamp": settings.last_sync_timestamp,
                "next_sync_timestamp": settings.next_sync_timestamp,
                "sync_in_progress": settings.sync_in_progress,
                "error_message": settings.error_message,
                "created_at": settings.created_at,
                "updated_at": settings.updated_at
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting Gmail memory settings: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@gmail_email_workflow_bp.route("/api/gmail/email-workflow/memory/settings", methods=["PUT"])
@handle_gmail_email_workflow_errors
@require_user_auth
def save_memory_settings():
    """Save Gmail memory settings for user"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not GMAIL_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Gmail LanceDB service not available"
            }), 503
        
        # Validate settings
        valid_frequencies = ["real-time", "hourly", "daily", "weekly", "manual"]
        sync_frequency = data.get('sync_frequency', 'hourly')
        if sync_frequency not in valid_frequencies:
            return jsonify({
                "ok": False,
                "error": f"Invalid sync frequency. Must be one of: {valid_frequencies}",
                "error_type": "validation_error"
            }), 400
        
        # Create settings object
        settings = GmailMemorySettings(
            user_id=user_id,
            ingestion_enabled=data.get('ingestion_enabled', True),
            sync_frequency=sync_frequency,
            data_retention_days=data.get('data_retention_days', 365),
            include_labels=data.get('include_labels', []),
            exclude_labels=data.get('exclude_labels', []),
            include_threads=data.get('include_threads', True),
            include_drafts=data.get('include_drafts', False),
            include_sent=data.get('include_sent', True),
            include_received=data.get('include_received', True),
            max_messages_per_sync=data.get('max_messages_per_sync', 1000),
            max_attachment_size_mb=data.get('max_attachment_size_mb', 25),
            include_attachments=data.get('include_attachments', True),
            index_attachments=data.get('index_attachments', False),
            search_enabled=data.get('search_enabled', True),
            semantic_search_enabled=data.get('semantic_search_enabled', True),
            metadata_extraction_enabled=data.get('metadata_extraction_enabled', True),
            thread_tracking_enabled=data.get('thread_tracking_enabled', True),
            contact_analysis_enabled=data.get('contact_analysis_enabled', True)
        )
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(
            gmail_lancedb_service.save_user_settings(settings)
        )
        loop.close()
        
        if success:
            return jsonify({
                "ok": True,
                "message": "Gmail memory settings saved successfully",
                "settings": {
                    "user_id": settings.user_id,
                    "ingestion_enabled": settings.ingestion_enabled,
                    "sync_frequency": settings.sync_frequency,
                    "updated_at": settings.updated_at
                }
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Failed to save Gmail memory settings",
                "error_type": "save_error"
            }), 500
        
    except Exception as e:
        logger.error(f"Error saving Gmail memory settings: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@gmail_email_workflow_bp.route("/api/gmail/email-workflow/memory/ingest", methods=["POST"])
@handle_gmail_email_workflow_errors
@require_user_auth
def start_ingestion():
    """Start Gmail message ingestion"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        access_token = data.get('access_token')
        query = data.get('query', '')
        max_messages = data.get('max_messages')
        force_sync = data.get('force_sync', False)
        
        if not GMAIL_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Gmail LanceDB service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            gmail_lancedb_service.ingest_gmail_messages(
                user_id=user_id,
                access_token=access_token,
                query=query,
                max_messages=max_messages,
                force_sync=force_sync
            )
        )
        loop.close()
        
        if result.get('success'):
            return jsonify({
                "ok": True,
                "ingestion_result": {
                    "messages_ingested": result.get('messages_ingested', 0),
                    "threads_ingested": result.get('threads_ingested', 0),
                    "attachments_ingested": result.get('attachments_ingested', 0),
                    "total_size_mb": result.get('total_size_mb', 0),
                    "batch_id": result.get('batch_id'),
                    "next_sync": result.get('next_sync'),
                    "sync_frequency": result.get('sync_frequency')
                },
                "message": "Gmail message ingestion completed successfully"
            })
        else:
            return jsonify({
                "ok": False,
                "error": result.get('error', 'Unknown ingestion error'),
                "error_type": result.get('error_type', 'ingestion_error')
            }), 500
        
    except Exception as e:
        logger.error(f"Error starting Gmail ingestion: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@gmail_email_workflow_bp.route("/api/gmail/email-workflow/memory/status", methods=["POST"])
@handle_gmail_email_workflow_errors
@require_user_auth
def get_memory_status():
    """Get Gmail memory synchronization status"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not GMAIL_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Gmail LanceDB service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        status = loop.run_until_complete(
            gmail_lancedb_service.get_sync_status(user_id)
        )
        loop.close()
        
        if status.get('error'):
            return jsonify({
                "ok": False,
                "error": status.get('error'),
                "error_type": status.get('error_type', 'status_error')
            }), 500
        
        return jsonify({
            "ok": True,
            "memory_status": status
        })
        
    except Exception as e:
        logger.error(f"Error getting Gmail memory status: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@gmail_email_workflow_bp.route("/api/gmail/email-workflow/memory/search", methods=["POST"])
@handle_gmail_email_workflow_errors
@require_user_auth
def search_memory():
    """Search Gmail messages in memory"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        query = data.get('query', '')
        label_filter = data.get('label_filter')
        date_from = data.get('date_from')
        date_to = data.get('date_to')
        limit = data.get('limit', 50)
        
        if not GMAIL_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Gmail LanceDB service not available"
            }), 503
        
        # Validate limit
        limit = min(limit, 200)  # Max 200 results
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        messages = loop.run_until_complete(
            gmail_lancedb_service.search_gmail_messages(
                user_id=user_id,
                query=query,
                label_filter=label_filter,
                date_from=date_from,
                date_to=date_to,
                limit=limit
            )
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "messages": messages,
            "count": len(messages),
            "search_filters": {
                "query": query,
                "label_filter": label_filter,
                "date_from": date_from,
                "date_to": date_to,
                "limit": limit
            }
        })
        
    except Exception as e:
        logger.error(f"Error searching Gmail memory: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@gmail_email_workflow_bp.route("/api/gmail/email-workflow/memory/threads-search", methods=["POST"])
@handle_gmail_email_workflow_errors
@require_user_auth
def search_memory_threads():
    """Search Gmail threads in memory"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        query = data.get('query', '')
        label_filter = data.get('label_filter')
        limit = data.get('limit', 50)
        
        if not GMAIL_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Gmail LanceDB service not available"
            }), 503
        
        # Validate limit
        limit = min(limit, 200)  # Max 200 results
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        threads = loop.run_until_complete(
            gmail_lancedb_service.search_gmail_threads(
                user_id=user_id,
                query=query,
                label_filter=label_filter,
                limit=limit
            )
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "threads": threads,
            "count": len(threads),
            "search_filters": {
                "query": query,
                "label_filter": label_filter,
                "limit": limit
            }
        })
        
    except Exception as e:
        logger.error(f"Error searching Gmail memory threads: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@gmail_email_workflow_bp.route("/api/gmail/email-workflow/memory/contacts-search", methods=["POST"])
@handle_gmail_email_workflow_errors
@require_user_auth
def search_memory_contacts():
    """Search Gmail contacts in memory"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        query = data.get('query', '')
        limit = data.get('limit', 50)
        
        if not GMAIL_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Gmail LanceDB service not available"
            }), 503
        
        # Validate limit
        limit = min(limit, 200)  # Max 200 results
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        contacts = loop.run_until_complete(
            gmail_lancedb_service.search_gmail_contacts(
                user_id=user_id,
                query=query,
                limit=limit
            )
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "contacts": contacts,
            "count": len(contacts),
            "search_filters": {
                "query": query,
                "limit": limit
            }
        })
        
    except Exception as e:
        logger.error(f"Error searching Gmail memory contacts: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@gmail_email_workflow_bp.route("/api/gmail/email-workflow/memory/ingestion-stats", methods=["POST"])
@handle_gmail_email_workflow_errors
@require_user_auth
def get_ingestion_stats():
    """Get Gmail ingestion statistics"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not GMAIL_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Gmail LanceDB service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        stats = loop.run_until_complete(
            gmail_lancedb_service.get_ingestion_stats(user_id)
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "ingestion_stats": {
                "user_id": stats.user_id,
                "total_messages_ingested": stats.total_messages_ingested,
                "total_threads_ingested": stats.total_threads_ingested,
                "total_attachments_ingested": stats.total_attachments_ingested,
                "total_contacts_processed": stats.total_contacts_processed,
                "last_ingestion_timestamp": stats.last_ingestion_timestamp,
                "total_size_mb": stats.total_size_mb,
                "failed_ingestions": stats.failed_ingestions,
                "last_error_message": stats.last_error_message,
                "avg_messages_per_sync": stats.avg_messages_per_sync,
                "avg_processing_time_ms": stats.avg_processing_time_ms,
                "created_at": stats.created_at,
                "updated_at": stats.updated_at
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting Gmail ingestion stats: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@gmail_email_workflow_bp.route("/api/gmail/email-workflow/memory/delete", methods=["POST"])
@handle_gmail_email_workflow_errors
@require_user_auth
def delete_user_data():
    """Delete all Gmail data for user"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        confirm = data.get('confirm', False)
        
        if not GMAIL_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Gmail LanceDB service not available"
            }), 503
        
        if not confirm:
            return jsonify({
                "ok": False,
                "error": "Confirmation required to delete Gmail data",
                "error_type": "confirmation_required"
            }), 400
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(
            gmail_lancedb_service.delete_user_data(user_id)
        )
        loop.close()
        
        if success:
            return jsonify({
                "ok": True,
                "message": "All Gmail data deleted successfully",
                "deleted_at": datetime.utcnow().isoformat()
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Failed to delete Gmail data",
                "error_type": "delete_error"
            }), 500
        
    except Exception as e:
        logger.error(f"Error deleting Gmail user data: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Utility Endpoints
@gmail_email_workflow_bp.route("/api/gmail/email-workflow/service-info", methods=["GET"])
@handle_gmail_email_workflow_errors
def get_service_info():
    """Get service information"""
    try:
        if GMAIL_SERVICE_AVAILABLE:
            service_info = gmail_enhanced_service.get_service_info()
        else:
            service_info = {
                "name": "Enhanced Gmail Service",
                "version": "1.0.0",
                "error": "Gmail service not available"
            }
        
        return jsonify({
            "ok": True,
            "service_info": service_info,
            "lancedb_available": GMAIL_LANCEDB_AVAILABLE,
            "gmail_service_available": GMAIL_SERVICE_AVAILABLE
        })
        
    except Exception as e:
        logger.error(f"Error getting Gmail service info: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Export components
__all__ = [
    'gmail_email_workflow_bp'
]