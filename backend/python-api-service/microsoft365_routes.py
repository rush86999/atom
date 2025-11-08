"""
Microsoft 365 API Routes
FastAPI routes for Microsoft 365 unified platform integration
"""

from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
import asyncio
import logging
from functools import wraps
from typing import Dict, Any, Optional
import datetime
import traceback

from microsoft365_unified_service import (
    Microsoft365UnifiedService,
    M365ServiceType,
    M365Team,
    M365Message,
    M365Document,
    M365Event,
    M365Channel,
    M365PowerAutomateFlow,
    M365SharePointSite,
    create_m365_service
)

from microsoft365_integration_register import Microsoft365IntegrationRegistry

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Global service instances
m365_service: Optional[Microsoft365UnifiedService] = None
m365_registry: Optional[Microsoft365IntegrationRegistry] = None

# Error handling decorator
def handle_errors(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {f.__name__}: {str(e)}\n{traceback.format_exc()}")
            return jsonify({
                "error": str(e),
                "timestamp": datetime.datetime.now().isoformat(),
                "endpoint": f.__name__
            }), 500
    return decorated_function

# Initialize M365 service
def initialize_m365_service():
    """Initialize Microsoft 365 service"""
    global m365_service, m365_registry
    
    if m365_service is None:
        # Configuration would come from environment variables or config
        config = {
            "tenant_id": request.headers.get('X-M365-Tenant-ID', 'default-tenant'),
            "client_id": request.headers.get('X-M365-Client-ID', 'default-client'),
            "client_secret": request.headers.get('X-M365-Client-Secret', 'default-secret'),
            "redirect_uri": request.headers.get('X-M365-Redirect-URI', 'http://localhost:3000/oauth/m365/callback'),
            "scopes": [
                "User.Read", "Mail.Read", "Mail.Send", "Files.Read", "Files.ReadWrite",
                "Team.ReadBasic.All", "Channel.ReadBasic.All", "Chat.Read",
                "Calendars.Read", "Calendars.ReadWrite", "Sites.Read.All"
            ]
        }
        
        # Create service instance
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        m365_service = loop.run_until_complete(create_m365_service(config))
        
        # Initialize registry
        m365_registry = Microsoft365IntegrationRegistry()
    
    return m365_service

def run_async(coro):
    """Run async function in Flask context"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

# ==============================
# CORE API ROUTES
# ==============================

@app.route('/api/m365/health', methods=['GET'])
@handle_errors
def health_check():
    """M365 service health check"""
    try:
        service = initialize_m365_service()
        health = run_async(service.get_service_health())
        
        return jsonify({
            "status": "healthy",
            "service": "Microsoft 365 Unified",
            "version": "1.0.0",
            "timestamp": datetime.datetime.now().isoformat(),
            "services": health
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat()
        }), 500

@app.route('/api/m365/auth/status', methods=['GET'])
@handle_errors
def auth_status():
    """Check authentication status"""
    try:
        service = initialize_m365_service()
        is_authenticated = run_async(service._ensure_authenticated())
        
        return jsonify({
            "authenticated": is_authenticated,
            "service": "Microsoft 365",
            "timestamp": datetime.datetime.now().isoformat(),
            "token_expires": service.token_expires_at.isoformat() if service.token_expires_at else None
        })
    except Exception as e:
        return jsonify({
            "authenticated": False,
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat()
        }), 500

# ==============================
# TEAMS API ROUTES
# ==============================

@app.route('/api/m365/teams', methods=['GET'])
@handle_errors
def get_teams():
    """Get all Microsoft Teams"""
    try:
        service = initialize_m365_service()
        teams = run_async(service.get_teams())
        
        return jsonify({
            "success": True,
            "teams": [team.dict() for team in teams],
            "count": len(teams),
            "timestamp": datetime.datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat()
        }), 500

@app.route('/api/m365/teams/<team_id>/channels', methods=['GET'])
@handle_errors
def get_team_channels(team_id):
    """Get channels for a specific team"""
    try:
        service = initialize_m365_service()
        channels = run_async(service.get_team_channels(team_id))
        
        return jsonify({
            "success": True,
            "team_id": team_id,
            "channels": [channel.dict() for channel in channels],
            "count": len(channels),
            "timestamp": datetime.datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "team_id": team_id,
            "timestamp": datetime.datetime.now().isoformat()
        }), 500

@app.route('/api/m365/teams/<team_id>/channels/<channel_id>/message', methods=['POST'])
@handle_errors
def send_teams_message(team_id, channel_id):
    """Send message to Teams channel"""
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({
                "success": False,
                "error": "Message content is required",
                "timestamp": datetime.datetime.now().isoformat()
            }), 400
        
        service = initialize_m365_service()
        success = run_async(service.send_teams_message(team_id, channel_id, data['message']))
        
        return jsonify({
            "success": success,
            "team_id": team_id,
            "channel_id": channel_id,
            "message": data['message'],
            "timestamp": datetime.datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat()
        }), 500

# ==============================
# OUTLOOK/EMAIL API ROUTES
# ==============================

@app.route('/api/m365/emails', methods=['GET'])
@handle_errors
def get_emails():
    """Get emails from Outlook"""
    try:
        folder = request.args.get('folder', 'inbox')
        limit = int(request.args.get('limit', 50))
        
        service = initialize_m365_service()
        emails = run_async(service.get_emails(folder=folder, limit=limit))
        
        return jsonify({
            "success": True,
            "folder": folder,
            "emails": [email.dict() for email in emails],
            "count": len(emails),
            "timestamp": datetime.datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat()
        }), 500

@app.route('/api/m365/emails/send', methods=['POST'])
@handle_errors
def send_email():
    """Send email via Outlook"""
    try:
        data = request.get_json()
        required_fields = ['to_addresses', 'subject', 'body']
        
        for field in required_fields:
            if field not in data:
                return jsonify({
                    "success": False,
                    "error": f"Missing required field: {field}",
                    "timestamp": datetime.datetime.now().isoformat()
                }), 400
        
        service = initialize_m365_service()
        success = run_async(service.send_email(
            to_addresses=data['to_addresses'],
            subject=data['subject'],
            body=data['body'],
            cc_addresses=data.get('cc_addresses', [])
        ))
        
        return jsonify({
            "success": success,
            "to_addresses": data['to_addresses'],
            "subject": data['subject'],
            "timestamp": datetime.datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat()
        }), 500

# ==============================
# FILE/DATABASE API ROUTES
# ==============================

@app.route('/api/m365/documents', methods=['GET'])
@handle_errors
def get_documents():
    """Get documents from OneDrive/SharePoint"""
    try:
        service_type = request.args.get('service_type', 'onedrive')
        limit = int(request.args.get('limit', 100))
        
        service_enum = M365ServiceType.ONEDRIVE if service_type == 'onedrive' else M365ServiceType.SHAREPOINT
        
        service = initialize_m365_service()
        documents = run_async(service.get_documents(service_type=service_enum, limit=limit))
        
        return jsonify({
            "success": True,
            "service_type": service_type,
            "documents": [doc.dict() for doc in documents],
            "count": len(documents),
            "timestamp": datetime.datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat()
        }), 500

@app.route('/api/m365/documents/upload', methods=['POST'])
@handle_errors
def upload_document():
    """Upload document to OneDrive/SharePoint"""
    try:
        if 'file' not in request.files:
            return jsonify({
                "success": False,
                "error": "No file provided",
                "timestamp": datetime.datetime.now().isoformat()
            }), 400
        
        file = request.files['file']
        service_type = request.form.get('service_type', 'onedrive')
        file_path = request.form.get('file_path', f'/{file.filename}')
        
        service_enum = M365ServiceType.ONEDRIVE if service_type == 'onedrive' else M365ServiceType.SHAREPOINT
        
        content = file.read()
        service = initialize_m365_service()
        document = run_async(service.upload_document(file_path, content, service_enum))
        
        return jsonify({
            "success": document is not None,
            "service_type": service_type,
            "file_path": file_path,
            "document": document.dict() if document else None,
            "timestamp": datetime.datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat()
        }), 500

# ==============================
# CALENDAR API ROUTES
# ==============================

@app.route('/api/m365/calendar/events', methods=['GET'])
@handle_errors
def get_calendar_events():
    """Get calendar events"""
    try:
        limit = int(request.args.get('limit', 50))
        
        start_date = None
        end_date = None
        if request.args.get('start_date'):
            start_date = datetime.datetime.fromisoformat(request.args.get('start_date'))
        if request.args.get('end_date'):
            end_date = datetime.datetime.fromisoformat(request.args.get('end_date'))
        
        service = initialize_m365_service()
        events = run_async(service.get_calendar_events(start_date=start_date, end_date=end_date, limit=limit))
        
        return jsonify({
            "success": True,
            "events": [event.dict() for event in events],
            "count": len(events),
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            "timestamp": datetime.datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat()
        }), 500

@app.route('/api/m365/calendar/events', methods=['POST'])
@handle_errors
def create_calendar_event():
    """Create calendar event"""
    try:
        data = request.get_json()
        required_fields = ['subject', 'start_time', 'end_time', 'attendees']
        
        for field in required_fields:
            if field not in data:
                return jsonify({
                    "success": False,
                    "error": f"Missing required field: {field}",
                    "timestamp": datetime.datetime.now().isoformat()
                }), 400
        
        # Parse dates
        start_time = datetime.datetime.fromisoformat(data['start_time'])
        end_time = datetime.datetime.fromisoformat(data['end_time'])
        
        event = M365Event(
            id="",  # Will be generated
            subject=data['subject'],
            start_time=start_time,
            end_time=end_time,
            attendees=data['attendees'],
            organizer=data.get('organizer', ''),
            description=data.get('description', ''),
            location=data.get('location', ''),
            event_type=data.get('event_type', 'meeting'),
            teams_meeting_url=data.get('teams_meeting_url'),
            is_online=data.get('is_online', False),
            status=data.get('status', 'scheduled')
        )
        
        service = initialize_m365_service()
        success = run_async(service.create_calendar_event(event))
        
        return jsonify({
            "success": success,
            "event": data,
            "timestamp": datetime.datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat()
        }), 500

# ==============================
# POWER AUTOMATE API ROUTES
# ==============================

@app.route('/api/m365/power-automate/flows', methods=['GET'])
@handle_errors
def get_power_automate_flows():
    """Get Power Automate flows"""
    try:
        environment_name = request.args.get('environment_name')
        
        service = initialize_m365_service()
        flows = run_async(service.get_power_automate_flows(environment_name))
        
        return jsonify({
            "success": True,
            "environment_name": environment_name,
            "flows": [flow.dict() for flow in flows],
            "count": len(flows),
            "timestamp": datetime.datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat()
        }), 500

# ==============================
# SHAREPOINT API ROUTES
# ==============================

@app.route('/api/m365/sharepoint/sites', methods=['GET'])
@handle_errors
def get_sharepoint_sites():
    """Get SharePoint sites"""
    try:
        service = initialize_m365_service()
        sites = run_async(service.get_sharepoint_sites())
        
        return jsonify({
            "success": True,
            "sites": [site.dict() for site in sites],
            "count": len(sites),
            "timestamp": datetime.datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat()
        }), 500

# ==============================
# CROSS-SERVICE WORKFLOW API ROUTES
# ==============================

@app.route('/api/m365/workflows/create', methods=['POST'])
@handle_errors
def create_cross_service_workflow():
    """Create cross-service workflow"""
    try:
        data = request.get_json()
        if not data or 'workflow_definition' not in data:
            return jsonify({
                "success": False,
                "error": "Workflow definition is required",
                "timestamp": datetime.datetime.now().isoformat()
            }), 400
        
        service = initialize_m365_service()
        workflow_id = run_async(service.create_cross_service_workflow(data['workflow_definition']))
        
        return jsonify({
            "success": workflow_id is not None,
            "workflow_id": workflow_id,
            "timestamp": datetime.datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat()
        }), 500

# ==============================
# ANALYTICS API ROUTES
# ==============================

@app.route('/api/m365/analytics/unified', methods=['GET'])
@handle_errors
def get_unified_analytics():
    """Get unified analytics across all M365 services"""
    try:
        start_date = None
        end_date = None
        if request.args.get('start_date'):
            start_date = datetime.datetime.fromisoformat(request.args.get('start_date'))
        if request.args.get('end_date'):
            end_date = datetime.datetime.fromisoformat(request.args.get('end_date'))
        
        if not start_date:
            start_date = datetime.datetime.now() - datetime.timedelta(days=30)
        if not end_date:
            end_date = datetime.datetime.now()
        
        service = initialize_m365_service()
        analytics = run_async(service.get_unified_analytics(start_date, end_date))
        
        return jsonify({
            "success": True,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "analytics": analytics,
            "timestamp": datetime.datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat()
        }), 500

# ==============================
# INTEGRATION REGISTRY API ROUTES
# ==============================

@app.route('/api/m365/integration/register', methods=['POST'])
@handle_errors
def register_integration():
    """Register M365 integration with ATOM platform"""
    try:
        data = request.get_json()
        config = data.get('config', {})
        
        global m365_registry
        if m365_registry is None:
            m365_registry = Microsoft365IntegrationRegistry()
        
        result = run_async(m365_registry.register_integration(config))
        
        return jsonify(result)
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat()
        }), 500

@app.route('/api/m365/integration/status', methods=['GET'])
@handle_errors
def get_integration_status():
    """Get M365 integration status"""
    try:
        global m365_registry
        if m365_registry is None:
            m365_registry = Microsoft365IntegrationRegistry()
        
        status = run_async(m365_registry.get_integration_status())
        
        return jsonify(status)
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat()
        }), 500

@app.route('/api/m365/integration/info', methods=['GET'])
@handle_errors
def get_integration_info():
    """Get M365 integration registration info"""
    try:
        global m365_registry
        if m365_registry is None:
            m365_registry = Microsoft365IntegrationRegistry()
        
        info = m365_registry.get_registration_info()
        
        return jsonify(info)
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat()
        }), 500

@app.route('/api/m365/integration/unregister', methods=['POST'])
@handle_errors
def unregister_integration():
    """Unregister M365 integration"""
    try:
        global m365_registry
        if m365_registry is None:
            m365_registry = Microsoft365IntegrationRegistry()
        
        result = run_async(m365_registry.unregister_integration())
        
        return jsonify(result)
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat()
        }), 500

# ==============================
# ERROR HANDLING AND UTILITIES
# ==============================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        "error": "Endpoint not found",
        "status": 404,
        "timestamp": datetime.datetime.now().isoformat()
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return jsonify({
        "error": "Internal server error",
        "status": 500,
        "timestamp": datetime.datetime.now().isoformat()
    }), 500

# ==============================
# ROOT ENDPOINT
# ==============================

@app.route('/', methods=['GET'])
def root():
    """Root endpoint with API information"""
    return jsonify({
        "service": "Microsoft 365 Unified API",
        "version": "1.0.0",
        "status": "active",
        "endpoints": {
            "health": "/api/m365/health",
            "auth": "/api/m365/auth/status",
            "teams": "/api/m365/teams",
            "emails": "/api/m365/emails",
            "documents": "/api/m365/documents",
            "calendar": "/api/m365/calendar/events",
            "power_automate": "/api/m365/power-automate/flows",
            "sharepoint": "/api/m365/sharepoint/sites",
            "analytics": "/api/m365/analytics/unified",
            "integration": {
                "register": "/api/m365/integration/register",
                "status": "/api/m365/integration/status",
                "info": "/api/m365/integration/info",
                "unregister": "/api/m365/integration/unregister"
            }
        },
        "services_supported": [
            "Microsoft Teams",
            "Microsoft Outlook",
            "Microsoft OneDrive",
            "Microsoft SharePoint",
            "Microsoft Power Automate",
            "Microsoft Calendar"
        ],
        "timestamp": datetime.datetime.now().isoformat()
    })

if __name__ == '__main__':
    # Run Flask app
    app.run(
        host='0.0.0.0',
        port=8001,  # Different port to avoid conflicts
        debug=True
    )