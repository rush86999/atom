# Salesforce Integration Implementation Guide

## Overview

This guide provides comprehensive instructions for implementing and deploying the Salesforce integration for the ATOM Agent Memory System. The integration provides enterprise-grade Salesforce CRM capabilities with secure OAuth 2.0 authentication, advanced data management, and seamless integration with the broader ATOM ecosystem.

## Prerequisites

### System Requirements
- **Python**: 3.8+
- **PostgreSQL**: 12+ (or SQLite for development)
- **Flask**: 2.0+
- **Salesforce Account**: Developer or Enterprise edition

### Required Python Packages
```bash
pip install simple-salesforce==1.12.0
pip install flask==2.3.0
pip install asyncpg==0.28.0
pip install cryptography==41.0.0
```

## Implementation Steps

### Step 1: Salesforce Connected App Configuration

1. **Log in to Salesforce Setup**
   - Navigate to Setup → Platform Tools → Apps → App Manager
   - Click "New Connected App"

2. **Configure Connected App**
   - **Basic Information**:
     - Connected App Name: `ATOM Agent Memory System`
     - API Name: `ATOM_Agent_Memory_System`
     - Contact Email: Your email address
   - **API (Enable OAuth Settings)**:
     - Enable OAuth Settings: ✅ Check
     - Callback URL: `https://your-backend-domain.com/api/auth/salesforce/callback`
     - Selected OAuth Scopes:
       - Access and manage your data (api)
       - Perform requests on your behalf at any time (refresh_token, offline_access)
       - Provide access to your data via the Web (web)

3. **Save and Retrieve Credentials**
   - Note the **Consumer Key** and **Consumer Secret**
   - These will be used as `SALESFORCE_CLIENT_ID` and `SALESFORCE_CLIENT_SECRET`

### Step 2: Environment Configuration

Create or update your `.env` file with Salesforce configuration:

```bash
# Salesforce Configuration
SALESFORCE_CLIENT_ID="your-consumer-key-from-connected-app"
SALESFORCE_CLIENT_SECRET="your-consumer-secret-from-connected-app"
SALESFORCE_REDIRECT_URI="https://your-backend-domain.com/api/auth/salesforce/callback"
SALESFORCE_API_VERSION="57.0"

# Database Configuration
DATABASE_URL="postgresql://username:password@localhost/atom_db"
# or for SQLite development:
# DATABASE_URL="sqlite:///atom.db"
```

### Step 3: Database Setup

#### PostgreSQL Schema
```sql
-- Create Salesforce OAuth tokens table
CREATE TABLE salesforce_oauth_tokens (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL UNIQUE,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    expires_at TIMESTAMP WITH TIME ZONE,
    scope TEXT,
    organization_id VARCHAR(255),
    profile_id VARCHAR(255),
    instance_url TEXT,
    username VARCHAR(255),
    environment VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create index for performance
CREATE INDEX idx_salesforce_user_id ON salesforce_oauth_tokens(user_id);
CREATE INDEX idx_salesforce_expires_at ON salesforce_oauth_tokens(expires_at);
```

#### SQLite Schema (Development)
```sql
CREATE TABLE salesforce_oauth_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL UNIQUE,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    expires_at TEXT,
    scope TEXT,
    organization_id TEXT,
    profile_id TEXT,
    instance_url TEXT,
    username TEXT,
    environment TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### Step 4: Integration Files Implementation

#### 4.1 Core Service Layer (`salesforce_service.py`)
```python
import os
import logging
from typing import Optional, Tuple, List, Dict, Any
from simple_salesforce import Salesforce, SalesforceAuthenticationFailed
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

async def get_salesforce_client(user_id: str, db_conn_pool) -> Optional[Salesforce]:
    """
    Get authenticated Salesforce client using OAuth tokens from database
    """
    try:
        from db_oauth_salesforce import get_user_salesforce_tokens

        tokens = await get_user_salesforce_tokens(db_conn_pool, user_id)
        if not tokens:
            logger.warning(f"No Salesforce tokens found for user {user_id}")
            return None

        access_token = tokens.get("access_token")
        instance_url = tokens.get("instance_url")

        if not access_token or not instance_url:
            logger.error(f"Missing required Salesforce token data for user {user_id}")
            return None

        # Create Salesforce client with OAuth token
        sf = Salesforce(
            instance_url=instance_url,
            session_id=access_token,
            version="57.0",
        )

        # Test connection with a simple query
        test_result = sf.query("SELECT Id FROM User LIMIT 1")
        logger.info(f"Successfully connected to Salesforce for user {user_id}")
        return sf

    except Exception as e:
        logger.error(f"Error getting Salesforce client for user {user_id}: {e}")
        return None
```

#### 4.2 OAuth Handler (`auth_handler_salesforce.py`)
```python
import os
import logging
import secrets
import base64
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import requests
from flask import Blueprint, request, jsonify, redirect, current_app
import asyncio

logger = logging.getLogger(__name__)

class SalesforceOAuthHandler:
    def __init__(self, db_conn_pool=None):
        self.db_conn_pool = db_conn_pool
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, str]:
        """Load Salesforce OAuth configuration from environment"""
        config = {
            'client_id': os.getenv('SALESFORCE_CLIENT_ID'),
            'client_secret': os.getenv('SALESFORCE_CLIENT_SECRET'),
            'redirect_uri': os.getenv('SALESFORCE_REDIRECT_URI'),
            'api_version': os.getenv('SALESFORCE_API_VERSION', '57.0')
        }
        
        if not all([config['client_id'], config['client_secret'], config['redirect_uri']]):
            raise ValueError("Missing required Salesforce OAuth configuration")
            
        return config

    def get_oauth_url(self, user_id: str) -> Dict[str, Any]:
        """Generate Salesforce OAuth authorization URL"""
        try:
            state = secrets.token_urlsafe(32)
            
            auth_url = (
                f"https://login.salesforce.com/services/oauth2/authorize"
                f"?response_type=code"
                f"&client_id={self.config['client_id']}"
                f"&redirect_uri={self.config['redirect_uri']}"
                f"&state={state}"
                f"&scope=api refresh_token offline_access"
            )
            
            return {
                "ok": True,
                "data": {
                    "authorization_url": auth_url,
                    "state": state
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating Salesforce OAuth URL: {e}")
            return {
                "ok": False,
                "error": {
                    "code": "OAUTH_URL_GENERATION_FAILED",
                    "message": f"Failed to generate OAuth URL: {str(e)}"
                }
            }
```

#### 4.3 Database Handler (`db_oauth_salesforce.py`)
```python
import os
import logging
import asyncpg
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

class SalesforceOAuthDatabase:
    def __init__(self):
        # Generate or load encryption key
        self.encryption_key = os.getenv('ENCRYPTION_KEY')
        if not self.encryption_key:
            # Generate a new key for development
            self.encryption_key = Fernet.generate_key().decode()
        self.fernet = Fernet(self.encryption_key.encode())

    def _encrypt_token(self, token: str) -> str:
        """Encrypt OAuth token for secure storage"""
        return self.fernet.encrypt(token.encode()).decode()

    def _decrypt_token(self, encrypted_token: str) -> str:
        """Decrypt OAuth token for use"""
        return self.fernet.decrypt(encrypted_token.encode()).decode()

async def init_salesforce_oauth_table(db_conn_pool) -> bool:
    """Initialize Salesforce OAuth table in database"""
    try:
        async with db_conn_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS salesforce_oauth_tokens (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL UNIQUE,
                    access_token TEXT NOT NULL,
                    refresh_token TEXT,
                    expires_at TIMESTAMP WITH TIME ZONE,
                    scope TEXT,
                    organization_id VARCHAR(255),
                    profile_id VARCHAR(255),
                    instance_url TEXT,
                    username VARCHAR(255),
                    environment VARCHAR(50),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)
        logger.info("Salesforce OAuth table initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize Salesforce OAuth table: {e}")
        return False
```

### Step 5: API Endpoints Implementation

#### 5.1 Main API Handler (`salesforce_handler.py`)
```python
import logging
from flask import Blueprint, request, jsonify, current_app
import salesforce_service

logger = logging.getLogger(__name__)

salesforce_bp = Blueprint('salesforce_bp', __name__)

@salesforce_bp.route('/api/salesforce/contacts', methods=['GET', 'POST'])
async def handle_contacts():
    user_id = request.args.get('user_id') if request.method == 'GET' else request.get_json().get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        sf = await salesforce_service.get_salesforce_client(user_id, db_conn_pool)
        if not sf:
            return jsonify({"ok": False, "error": {"code": "AUTH_ERROR", "message": "Could not get authenticated Salesforce client. Please connect your Salesforce account."}}), 401

        if request.method == 'GET':
            contacts = await salesforce_service.list_contacts(sf)
            return jsonify({"ok": True, "data": {"contacts": contacts}})
        else: # POST
            data = request.get_json()
            last_name = data.get('LastName')
            if not last_name:
                return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "LastName is required to create a contact."}}), 400

            first_name = data.get('FirstName')
            email = data.get('Email')
            contact = await salesforce_service.create_contact(sf, last_name, first_name, email)
            return jsonify({"ok": True, "data": contact})
    except Exception as e:
        logger.error(f"Error handling Salesforce contacts for user {user_id}: {e}")
        return jsonify({"ok": False, "error": {"code": "CONTACTS_HANDLING_FAILED", "message": str(e)}}), 500
```

#### 5.2 Health Monitoring (`salesforce_health_handler.py`)
```python
import logging
from flask import Blueprint, jsonify, request, current_app
from datetime import datetime, timezone
import asyncio

logger = logging.getLogger(__name__)

salesforce_health_bp = Blueprint("salesforce_health_bp", __name__)

@salesforce_health_bp.route("/api/salesforce/health", methods=["GET"])
async def salesforce_health():
    """Health check endpoint for Salesforce integration"""
    try:
        health_status = {
            "service": "salesforce",
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {},
        }

        # Check database connectivity
        db_conn_pool = current_app.config.get("DB_CONNECTION_POOL")
        if not db_conn_pool:
            health_status["status"] = "degraded"
            health_status["checks"]["database"] = {
                "status": "unavailable",
                "message": "Database connection pool not configured",
            }
        else:
            health_status["checks"]["database"] = {
                "status": "healthy",
                "message": "Database connection successful",
            }

        return jsonify(health_status)

    except Exception as e:
        logger.error(f"Salesforce health check failed: {e}")
        return jsonify(
            {
                "service": "salesforce",
                "status": "unhealthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": f"Health check failed: {str(e)}",
            }
        ), 500
```

### Step 6: Desktop App Integration

#### 6.1 TypeScript Skills (`salesforceSkills.ts`)
```typescript
import axios, { AxiosError } from 'axios';
import { SkillResponse } from '../types';
import { PYTHON_API_SERVICE_BASE_URL } from '../constants';

export async function listSalesforceContacts(
  userId: string
): Promise<SkillResponse<{ contacts: any[] }>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: 'CONFIG_ERROR',
        message: 'Python API service URL is not configured.',
      },
    };
  }
  
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/salesforce/contacts?user_id=${userId}`;

  try {
    const response = await axios.get(endpoint);
    if (response.data && response.data.ok && response.data.data) {
      return { ok: true, data: response.data.data };
    }
    return {
      ok: false,
      error: {
        code: response.data?.error?.code || 'API_ERROR',
        message: response.data?.error?.message || 'Failed to list Salesforce contacts.',
      },
    };
  } catch (error) {
    return {
      ok: false,
      error: {
        code: 'NETWORK_ERROR',
        message: `Failed to list Salesforce contacts: ${error}`,
      },
    };
  }
}
```

### Step 7: Application Registration

#### 7.1 Main Application Integration (`main_api_app.py`)
```python
# Import Salesforce handlers
try:
    from auth_handler_salesforce import (
        init_salesforce_oauth_handler,
        salesforce_auth_bp,
    )
    SALESFORCE_OAUTH_AVAILABLE = True
except ImportError as e:
    SALESFORCE_OAUTH_AVAILABLE = False
    logging.warning(f"Salesforce OAuth handler not available: {e}")

try:
    from salesforce_handler import salesforce_bp
    SALESFORCE_HANDLER_AVAILABLE = True
except ImportError as e:
    SALESFORCE_HANDLER_AVAILABLE = False
    logging.warning(f"Salesforce handler not available: {e}")

try:
    from salesforce_health_handler import salesforce_health_bp
    SALESFORCE_HEALTH_AVAILABLE = True
except ImportError as e:
    SALESFORCE_HEALTH_AVAILABLE = False
    logging.warning(f"Salesforce health handler not available: {e}")

# Register blueprints in create_app function
if SALESFORCE_OAUTH_AVAILABLE:
    app.register_blueprint(
        salesforce_auth_bp, url_prefix="/api/auth", name="salesforce_auth"
    )
    logging.info("Salesforce OAuth handler registered successfully")

if SALESFORCE_HANDLER_AVAILABLE:
    app.register_blueprint(
        salesforce_bp, url_prefix="/api", name="salesforce_handler"
    )
    logging.info("Salesforce handler registered successfully")

if SALESFORCE_HEALTH_AVAILABLE:
    app.register_blueprint(
        salesforce_health_bp, url_prefix="/api", name="salesforce_health"
    )
    logging.info("Salesforce health handler registered successfully")

# Initialize database tables
if SALESFORCE_OAUTH_AVAILABLE and db_pool:
    from db_oauth_salesforce import init_salesforce_oauth_table
    asyncio.run(init_salesforce_oauth_table(db_pool))
    logging.info("Salesforce OAuth table initialized successfully")
```

### Step 8: Service Registry Integration

#### 8.1 Service Registration (`service_registry_routes.py`)
```python
# Import Salesforce services if available
try:
    from salesforce_service import (
        get_salesforce_client,
        list_contacts,
        list_accounts,
        list_opportunities,
        create_contact,
        create_account,
        create_opportunity,
        update_opportunity,
        get_opportunity,
        create_lead,
    )
    SALESFORCE_SERVICE_AVAILABLE = True
except ImportError:
    SALESFORCE_SERVICE_AVAILABLE = False

# Add to services dictionary
services = {
    "salesforce_service": {
        "name": "Salesforce",
        "status": "available",
        "type": "integration",
        "description": "Salesforce CRM integration service",
        "capabilities": [
            "get_salesforce_client",
            "list_contacts",
            "list_accounts",
            "list_opportunities",
            "create_contact",
            "create_account",
            "create_opportunity",
            "update_opportunity",
            "get_opportunity",
            "create_lead",
        ],
        "health": "healthy",
        "workflow_triggers": ["manual_trigger", "scheduled_trigger"],
        "workflow_actions": ["execute_service", "process_data"],
        "chat_commands": [
            "use salesforce",
            "access salesforce",
            "get salesforce contacts",
            "create salesforce account",
        ],
        "last_checked": datetime.now(timezone.utc).isoformat(),
    }