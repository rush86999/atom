# Integration Health Monitoring Guide

**Last Updated**: February 4, 2026

This guide explains the integration health monitoring system in Atom, which provides real-time status checks for all third-party service integrations.

---

## Overview

The integration health monitoring system provides:

- **Real-time health checks** for 10+ integration services
- **Configuration validation** (missing environment variables)
- **Service availability** verification
- **Consistent API response format** across all services
- **Audit logging** for all health check operations

---

## Supported Services

### Integrations with Health Checks

| Service | Health Check | Configuration Required |
|---------|--------------|------------------------|
| **Zoom** | ✅ | `ZOOM_API_KEY`, `ZOOM_API_SECRET` |
| **Notion** | ✅ | `NOTION_CLIENT_ID`, `NOTION_CLIENT_SECRET` |
| **Trello** | ✅ | `TRELLO_API_KEY`, `TRELLO_API_SECRET` |
| **Stripe** | ✅ | `STRIPE_API_KEY`, `STRIPE_WEBHOOK_SECRET` |
| **QuickBooks** | ✅ | `QUICKBOOKS_CLIENT_ID`, `QUICKBOOKS_CLIENT_SECRET` |
| **GitHub** | ✅ | `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `GITHUB_TOKEN` |
| **Salesforce** | ✅ | `SALESFORCE_CLIENT_ID`, `SALESFORCE_CLIENT_SECRET` |
| **Google Drive** | ✅ | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` |
| **Dropbox** | ✅ | `DROPBOX_APP_KEY`, `DROPBOX_APP_SECRET` |
| **Slack** | ✅ | `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`, `SLACK_SIGNING_SECRET` |

---

## API Endpoints

### 1. Check Service Health

**Endpoint**: `GET /api/{service}/health`

**Description**: Check the health and configuration status of a specific integration.

**Services**: `zoom`, `notion`, `trello`, `stripe`, `quickbooks`, `github`, `salesforce`, `googledrive`, `dropbox`, `slack`

**Example Request**:
```bash
curl "http://localhost:8000/api/zoom/health"
```

**Example Response** (Healthy & Configured):
```json
{
  "ok": true,
  "status": "healthy",
  "service": "zoom",
  "timestamp": "2026-02-04T12:00:00Z",
  "is_mock": false,
  "configured": true,
  "message": "Zoom integration is operational",
  "checks": {
    "configuration": {
      "status": "pass",
      "required_env_vars": ["ZOOM_API_KEY", "ZOOM_API_SECRET"],
      "present_env_vars": ["ZOOM_API_KEY", "ZOOM_API_SECRET"],
      "missing_env_vars": []
    },
    "api_access": {
      "status": "pass",
      "message": "Successfully connected to Zoom API"
    }
  }
}
```

**Example Response** (Not Configured):
```json
{
  "ok": true,
  "status": "unhealthy",
  "service": "zoom",
  "timestamp": "2026-02-04T12:00:00Z",
  "is_mock": false,
  "configured": false,
  "message": "Zoom integration is not properly configured",
  "checks": {
    "configuration": {
      "status": "fail",
      "required_env_vars": ["ZOOM_API_KEY", "ZOOM_API_SECRET"],
      "present_env_vars": [],
      "missing_env_vars": ["ZOOM_API_KEY", "ZOOM_API_SECRET"]
    },
    "api_access": {
      "status": "skip",
      "message": "API access check skipped due to missing configuration"
    }
  }
}
```

---

### 2. All Services Health Overview

**Endpoint**: `GET /api/integrations/health`

**Description**: Get an overview of all integration services' health status.

**Example Request**:
```bash
curl "http://localhost:8000/api/integrations/health"
```

**Example Response**:
```json
{
  "ok": true,
  "timestamp": "2026-02-04T12:00:00Z",
  "summary": {
    "total_services": 10,
    "healthy_services": 7,
    "unhealthy_services": 3,
    "overall_status": "degraded"
  },
  "services": {
    "zoom": {
      "status": "healthy",
      "configured": true,
      "message": "Zoom integration is operational"
    },
    "notion": {
      "status": "healthy",
      "configured": true,
      "message": "Notion integration is operational"
    },
    "slack": {
      "status": "unhealthy",
      "configured": false,
      "message": "Slack integration is not properly configured",
      "missing_env_vars": ["SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET", "SLACK_SIGNING_SECRET"]
    }
  }
}
```

---

### 3. Service Configuration Status

**Endpoint**: `GET /api/integrations/config`

**Description**: Get detailed configuration status for all integrations without performing API health checks.

**Example Request**:
```bash
curl "http://localhost:8000/api/integrations/config"
```

**Example Response**:
```json
{
  "ok": true,
  "timestamp": "2026-02-04T12:00:00Z",
  "integrations": {
    "zoom": {
      "configured": true,
      "required_env_vars": ["ZOOM_API_KEY", "ZOOM_API_SECRET"],
      "present_env_vars": ["ZOOM_API_KEY", "ZOOM_API_SECRET"],
      "missing_env_vars": [],
      "configuration_percentage": 100
    },
    "slack": {
      "configured": false,
      "required_env_vars": ["SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET", "SLACK_SIGNING_SECRET"],
      "present_env_vars": ["SLACK_SIGNING_SECRET"],
      "missing_env_vars": ["SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET"],
      "configuration_percentage": 33
    }
  },
  "summary": {
    "total_integrations": 10,
    "fully_configured": 7,
    "partially_configured": 2,
    "not_configured": 1
  }
}
```

---

## Health Check Implementation

### Health Check Function

The core health check function is defined in `api/integration_health_stubs.py`:

```python
def check_integration_health(
    integration: str,
    check_api: bool = True
) -> Dict[str, Any]:
    """
    Check the health of an integration service.

    Args:
        integration: Integration service name (e.g., "zoom", "notion")
        check_api: Whether to perform actual API connectivity check

    Returns:
        Health check result with configuration and API status
    """
    config = INTEGRATION_CONFIG.get(integration)

    if not config:
        return {
            "ok": False,
            "service": integration,
            "status": "unknown",
            "message": f"Unknown integration: {integration}"
        }

    # Check configuration
    missing_vars = [
        env_var for env_var in config["env_vars"]
        if not os.getenv(env_var)
    ]
    is_configured = len(missing_vars) == 0

    # Prepare response
    result = {
        "ok": True,
        "service": integration,
        "timestamp": datetime.utcnow().isoformat(),
        "is_mock": False,
        "configured": is_configured,
        "checks": {
            "configuration": {
                "status": "pass" if is_configured else "fail",
                "required_env_vars": config["env_vars"],
                "present_env_vars": [
                    var for var in config["env_vars"]
                    if os.getenv(var)
                ],
                "missing_env_vars": missing_vars
            }
        }
    }

    # Check API access if configured
    if is_configured and check_api:
        api_status = check_api_connectivity(integration)
        result["checks"]["api_access"] = api_status
        result["status"] = "healthy" if api_status["status"] == "pass" else "degraded"
        result["message"] = api_status.get("message", f"{integration.capitalize()} integration is operational")
    else:
        result["checks"]["api_access"] = {
            "status": "skip",
            "message": "API access check skipped due to missing configuration"
        }
        result["status"] = "unhealthy"
        result["message"] = f"{integration.capitalize()} integration is not properly configured"

    return result
```

---

## Configuration

### Integration Configuration Structure

Each integration is configured in `INTEGRATION_CONFIG`:

```python
INTEGRATION_CONFIG = {
    "zoom": {
        "env_vars": [
            "ZOOM_API_KEY",
            "ZOOM_API_SECRET"
        ],
        "service_name": "Zoom",
        "health_check_endpoint": "https://api.zoom.us/v2/users/me"
    },
    "notion": {
        "env_vars": [
            "NOTION_CLIENT_ID",
            "NOTION_CLIENT_SECRET"
        ],
        "service_name": "Notion",
        "health_check_endpoint": "https://api.notion.com/v1/users/me"
    },
    # ... more integrations
}
```

---

## Using Health Checks

### Frontend Integration

```typescript
import React, { useEffect, useState } from 'react';

interface IntegrationHealth {
  service: string;
  status: 'healthy' | 'unhealthy' | 'degraded';
  configured: boolean;
  message: string;
}

function IntegrationsList() {
  const [health, setHealth] = useState<IntegrationHealth[]>([]);

  useEffect(() => {
    const fetchHealth = async () => {
      const response = await fetch('/api/integrations/health');
      const data = await response.json();
      setHealth(data.services);
    };

    fetchHealth();
    const interval = setInterval(fetchHealth, 60000); // Check every minute

    return () => clearInterval(interval);
  }, []);

  return (
    <div>
      <h2>Integration Status</h2>
      {health.map((integration) => (
        <div key={integration.service}>
          <span>
            {integration.service}: {integration.status}
          </span>
          {!integration.configured && (
            <span> - {integration.message}</span>
          )}
        </div>
      ))}
    </div>
  );
}
```

### Backend Integration

```python
from fastapi import Depends, HTTPException
from core.database import SessionLocal
from sqlalchemy.orm import Session

def verify_integration_health(service: str):
    """Dependency to verify integration is healthy before proceeding"""

    def check_health():
        from api.integration_health_stubs import check_integration_health

        health = check_integration_health(service, check_api=True)

        if not health.get("configured"):
            raise HTTPException(
                status_code=503,
                detail=f"{service.capitalize()} integration is not configured"
            )

        if health.get("status") != "healthy":
            raise HTTPException(
                status_code=503,
                detail=f"{service.capitalize()} integration is currently unavailable"
            )

        return health

    return check_health

# Usage in routes
@router.post("/api/zoom/create-meeting")
async def create_zoom_meeting(
    meeting_data: dict,
    health: dict = Depends(verify_integration_health("zoom"))
):
    # Health check passed, proceed with Zoom API call
    pass
```

---

## Testing

### Test Health Endpoints

```bash
# Test individual service health
curl http://localhost:8000/api/zoom/health
curl http://localhost:8000/api/notion/health
curl http://localhost:8000/api/slack/health

# Test all integrations health
curl http://localhost:8000/api/integrations/health

# Test configuration status
curl http://localhost:8000/api/integrations/config
```

### Run Health Check Tests

```bash
# Run all health check tests
pytest backend/tests/test_integration_health.py -v

# Test specific service
pytest backend/tests/test_integration_health.py::test_zoom_health -v

# Test with coverage
pytest backend/tests/test_integration_health.py --cov=api.integration_health_stubs --cov-report=html
```

---

## Adding New Integration Health Checks

To add a health check for a new integration:

1. **Add Configuration** to `INTEGRATION_CONFIG`:
   ```python
   NEWSERVICE_CONFIG = {
       "env_vars": [
           "NEWSERVICE_API_KEY",
           "NEWSERVICE_API_SECRET"
       ],
       "service_name": "NewService",
       "health_check_endpoint": "https://api.newservice.com/v1/health"
   }
   ```

2. **Add Health Check Endpoint** to `api/integration_health_stubs.py`:
   ```python
   @router.get("/newservice/health")
   async def newservice_health():
       """Check NewService integration health"""
       health = check_integration_health("newservice", check_api=True)
       return health
   ```

3. **Add Tests** to `tests/test_integration_health.py`:
   ```python
   def test_newservice_health():
       """Test NewService health check endpoint"""
       response = client.get("/api/newservice/health")
       assert response.status_code == 200

       data = response.json()
       assert "service" in data
       assert data["service"] == "newservice"
       assert "status" in data
       assert "configured" in data
   ```

---

## Monitoring and Alerts

### Logging

All health check operations are logged:

```python
logger.info(f"Health check for {integration}: {health['status']}")
logger.warning(f"Integration {integration} is not configured: {missing_vars}")
logger.error(f"Integration {integration} API check failed: {error}")
```

### Recommended Monitoring Setup

1. **Health Check Dashboard**:
   - Display all integration statuses
   - Update every 30-60 seconds
   - Show historical uptime

2. **Alert Rules**:
   - Alert when 3+ integrations are unhealthy
   - Alert when a critical integration (e.g., Slack, Zoom) goes down
   - Alert when configuration is missing

3. **Metrics to Track**:
   - Uptime percentage per integration
   - Mean time to recovery (MTTR)
   - Configuration change events
   - API response times

---

## Troubleshooting

### Common Issues

#### 1. "Integration not configured"

**Problem**: Health check returns `configured: false`

**Solution**:
- Check environment variables are set
- Verify variable names match exactly
- Restart application after setting variables

```bash
# Check environment variables
echo $ZOOM_API_KEY
echo $ZOOM_API_SECRET

# Set missing variables
export ZOOM_API_KEY="your_api_key"
export ZOOM_API_SECRET="your_api_secret"
```

#### 2. "API access check failed"

**Problem**: Configuration is correct but API check fails

**Solution**:
- Verify API credentials are valid
- Check API credentials have required permissions
- Verify network connectivity to API endpoint
- Check for rate limiting or IP restrictions

#### 3. "Unknown integration"

**Problem**: Health check returns unknown integration error

**Solution**:
- Verify integration name is correct
- Check integration is in `INTEGRATION_CONFIG`
- Ensure health check endpoint exists

---

## Best Practices

1. **Check Before Use**: Always verify integration health before making API calls
2. **Graceful Degradation**: Handle unhealthy integrations gracefully in your code
3. **Cache Results**: Cache health check results for 30-60 seconds to avoid excessive API calls
4. **Alert on Critical Failures**: Set up alerts for critical integrations
5. **Document Dependencies**: Document which integrations each feature depends on
6. **Provide Helpful Error Messages**: Show users what's missing when configuration is incomplete

---

## Security Considerations

1. **Don't Expose Credentials**: Health check responses should never include actual API keys or secrets
2. **Rate Limiting**: Implement rate limiting on health check endpoints
3. **Access Control**: Consider authentication for health check endpoints in production
4. **Audit Logging**: Log all health check operations for security auditing

---

## Performance

**Health Check Performance Targets**:

| Metric | Target | Notes |
|--------|--------|-------|
| Configuration check | <10ms | No API call |
| Full health check | <500ms | Includes API call |
| Batch health check | <2s | All integrations |

**Optimization Tips**:
- Cache health check results for 30-60 seconds
- Use async HTTP clients for API checks
- Implement parallel health checks for multiple services
- Use connection pooling for HTTP requests

---

## Summary

| Feature | Status |
|---------|--------|
| Health Check Endpoints | ✅ Complete (10+ services) |
| Configuration Validation | ✅ Complete |
| API Connectivity Checks | ✅ Complete |
| Consistent Response Format | ✅ Complete |
| Tests | ✅ Complete |
| Documentation | ✅ Complete |

---

*For questions or issues, please refer to the main documentation or open an issue.*
