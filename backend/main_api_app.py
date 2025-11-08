import uvicorn

# Import our modules
from api_routes import router
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

# Import Asana integration
try:
    from integrations.asana_routes import router as asana_router

    ASANA_AVAILABLE = True
except ImportError as e:
    print(f"Asana integration not available: {e}")
    ASANA_AVAILABLE = False
    asana_router = None

# Import Notion integration
try:
    from integrations.notion_routes import router as notion_router

    NOTION_AVAILABLE = True
except ImportError as e:
    print(f"Notion integration not available: {e}")
    NOTION_AVAILABLE = False
    notion_router = None

# Import Linear integration
try:
    from integrations.linear_routes import router as linear_router

    LINEAR_AVAILABLE = True
except ImportError as e:
    print(f"Linear integration not available: {e}")
    LINEAR_AVAILABLE = False
    linear_router = None

# Import Outlook integration
try:
    from integrations.outlook_routes import router as outlook_router

    OUTLOOK_AVAILABLE = True
except ImportError as e:
    print(f"Outlook integration not available: {e}")
    OUTLOOK_AVAILABLE = False
    outlook_router = None

# Import Dropbox integration
try:
    from integrations.dropbox_routes import router as dropbox_router

    DROPBOX_AVAILABLE = True
except ImportError as e:
    print(f"Dropbox integration not available: {e}")
    DROPBOX_AVAILABLE = False
    dropbox_router = None

# Import Stripe integration
try:
    from integrations.stripe_routes import router as stripe_router

    STRIPE_AVAILABLE = True
except ImportError as e:
    print(f"Stripe integration not available: {e}")
    STRIPE_AVAILABLE = False
    stripe_router = None

# Import Salesforce integration
try:
    from integrations.salesforce_routes import router as salesforce_router

    SALESFORCE_AVAILABLE = True
except ImportError as e:
    print(f"Salesforce integration not available: {e}")
    SALESFORCE_AVAILABLE = False
    salesforce_router = None

# Import Zoom integration
try:
    from integrations.zoom_routes import router as zoom_router

    ZOOM_AVAILABLE = True
except ImportError as e:
    print(f"Zoom integration not available: {e}")
    ZOOM_AVAILABLE = False
    zoom_router = None

# Initialize FastAPI app
app = FastAPI(
    title="ATOM API",
    description="Advanced Task Orchestration & Management API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api/v1")

# Include Asana integration routes if available
if ASANA_AVAILABLE and asana_router:
    app.include_router(asana_router)
    print("✅ Asana integration routes loaded")
else:
    print("⚠️  Asana integration routes not available")

# Include Notion integration routes if available
if NOTION_AVAILABLE and notion_router:
    app.include_router(notion_router)
    print("✅ Notion integration routes loaded")
else:
    print("⚠️  Notion integration routes not available")

# Include Linear integration routes if available
if LINEAR_AVAILABLE and linear_router:
    app.include_router(linear_router)
    print("✅ Linear integration routes loaded")
else:
    print("⚠️  Linear integration routes not available")

# Include Outlook integration routes if available
if OUTLOOK_AVAILABLE and outlook_router:
    app.include_router(outlook_router)
    print("✅ Outlook integration routes loaded")
else:
    print("⚠️  Outlook integration routes not available")

# Include Dropbox integration routes if available
if DROPBOX_AVAILABLE and dropbox_router:
    app.include_router(dropbox_router)
    print("✅ Dropbox integration routes loaded")
else:
    print("⚠️  Dropbox integration routes not available")

# Include Stripe integration routes if available
if STRIPE_AVAILABLE and stripe_router:
    app.include_router(stripe_router)
    print("✅ Stripe integration routes loaded")
else:
    print("⚠️  Stripe integration routes not available")

# Include Salesforce integration routes if available
if SALESFORCE_AVAILABLE and salesforce_router:
    app.include_router(salesforce_router)
    print("✅ Salesforce integration routes loaded")
else:
    print("⚠️  Salesforce integration routes not available")

# Include GitHub integration routes if available
try:
    from integrations.github_routes import router as github_router

    GITHUB_AVAILABLE = True
except ImportError as e:
    print(f"GitHub integration not available: {e}")
    GITHUB_AVAILABLE = False
    github_router = None

if GITHUB_AVAILABLE and github_router:
    app.include_router(github_router)
    print("✅ GitHub integration routes loaded")
else:
    print("⚠️  GitHub integration routes not available")

# Include Zoom integration routes if available
if ZOOM_AVAILABLE and zoom_router:
    app.include_router(zoom_router)
    print("✅ Zoom integration routes loaded")
else:
    print("⚠️  Zoom integration routes not available")

# Include Tableau integration routes if available
try:
    from integrations.tableau_routes import router as tableau_router

    TABLEAU_AVAILABLE = True
except ImportError as e:
    print(f"Tableau integration not available: {e}")
    TABLEAU_AVAILABLE = False
    tableau_router = None

if TABLEAU_AVAILABLE and tableau_router:
    app.include_router(tableau_router)
    print("✅ Tableau integration routes loaded")
else:
    print("⚠️  Tableau integration routes not available")

# Include Box integration routes if available
try:
    from integrations.box_routes import router as box_router

    BOX_AVAILABLE = True
except ImportError as e:
    print(f"Box integration not available: {e}")
    BOX_AVAILABLE = False
    box_router = None

if BOX_AVAILABLE and box_router:
    app.include_router(box_router)
    print("✅ Box integration routes loaded")
else:
    print("⚠️  Box integration routes not available")


@app.get("/")
async def root():
    return {"message": "ATOM API is running", "status": "operational"}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}


if __name__ == "__main__":
    uvicorn.run(
        "main_api_app:app", host="0.0.0.0", port=8000, reload=True, log_level="info"
    )
