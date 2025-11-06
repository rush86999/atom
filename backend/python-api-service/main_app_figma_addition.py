"""
Add Figma Integration to Main App
This code should be added to main_api_app.py around line 645 after other OAuth registrations
"""

# Add this to the imports section at the top of main_api_app.py:
from figma_integration_register import register_figma_integration, register_figma_service, register_figma_desktop_integration

# Add this to the create_app() function after line 645 (after Figma OAuth handler registration):

# Register complete Figma integration
figma_integration_status = register_figma_integration(app, db_pool)
logging.info(f"Figma integration registered: {figma_integration_status}")

# Register Figma service globally
figma_service_status = register_figma_service()
logging.info(f"Figma service status: {figma_service_status}")

# Register Figma desktop integration
figma_desktop_status = register_figma_desktop_integration()
logging.info(f"Figma desktop integration status: {figma_desktop_status}")

# Add this to the routes listing in list_routes() function around line 1750:
{
    "method": "GET",
    "path": "/api/oauth/figma/url",
    "description": "Figma OAuth"
},
{
    "method": "POST", 
    "path": "/api/oauth/figma/callback",
    "description": "Figma OAuth Callback"
},
{
    "method": "GET",
    "path": "/api/figma/health",
    "description": "Figma Health Check"
},
{
    "method": "GET",
    "path": "/api/figma/health/detailed",
    "description": "Figma Detailed Health Check"
},
{
    "method": "POST",
    "path": "/api/figma/search",
    "description": "Figma Search"
},

# Add this to the root endpoint response around line 1764 to update counts:
"blueprints_loaded": 26,  # Updated from 25
"services_connected": 9,   # Updated from 8