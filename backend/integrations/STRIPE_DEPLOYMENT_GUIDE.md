# Stripe Integration Deployment Guide

## Overview

This guide provides comprehensive instructions for deploying the Stripe payment processing integration in production environments. The Stripe integration enables businesses to manage payments, subscriptions, customers, and products directly through the ATOM platform.

## Prerequisites

### System Requirements
- Python 3.8+
- FastAPI application
- PostgreSQL database (for token storage)
- Redis (optional, for caching)

### Stripe Account Requirements
- Stripe Developer Account
- Valid Stripe API keys
- Webhook endpoint configured
- OAuth application registered

## Installation Steps

### 1. Install Dependencies

```bash
# Core dependencies
pip install stripe fastapi uvicorn sqlalchemy psycopg2-binary

# Optional dependencies for enhanced features
pip install redis python-multipart python-jose[cryptography] passlib[bcrypt]
```

### 2. Environment Configuration

Create a `.env` file with the following variables:

```bash
# Stripe Configuration
STRIPE_CLIENT_ID=your_stripe_client_id
STRIPE_CLIENT_SECRET=your_stripe_client_secret
STRIPE_REDIRECT_URI=https://yourdomain.com/auth/stripe/callback
STRIPE_WEBHOOK_SECRET=your_webhook_secret

# Database Configuration
DATABASE_URL=postgresql://user:password@localhost/atom_db

# Application Configuration
SECRET_KEY=your_secret_key
ENVIRONMENT=production
```

### 3. Database Setup

Create the required database tables for OAuth token storage:

```sql
-- OAuth token storage table
CREATE TABLE stripe_oauth_tokens (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    token_type VARCHAR(50),
    expires_at TIMESTAMP,
    stripe_user_id VARCHAR(255),
    stripe_publishable_key VARCHAR(255),
    scope TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for faster lookups
CREATE INDEX idx_stripe_user_id ON stripe_oauth_tokens(user_id);
CREATE INDEX idx_stripe_access_token ON stripe_oauth_tokens(access_token);
```

### 4. Integration Registration

#### Register Stripe Router

Add the Stripe routes to your FastAPI application:

```python
from integrations.stripe_routes import router as stripe_router

app = FastAPI(title="ATOM Platform")
app.include_router(stripe_router, prefix="/api/v1")
```

#### Add Health Check Endpoint

```python
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "stripe": "available"
        }
    }
```

## OAuth Configuration

### 1. Stripe Developer Portal Setup

1. Log in to your [Stripe Dashboard](https://dashboard.stripe.com)
2. Navigate to **Developers** → **OAuth**
3. Click **Add Platform**
4. Configure the following settings:

```
Platform Name: ATOM Platform
Website URL: https://yourdomain.com
Redirect URI: https://yourdomain.com/auth/stripe/callback
```

### 2. OAuth Scopes

The integration requires the following OAuth scopes:

```python
STRIPE_SCOPES = [
    "read_only",  # Basic read access
    "write",      # Write access for creating resources
    "payments",   # Payment processing
    "customers",  # Customer management
    "subscriptions",  # Subscription management
    "products"    # Product catalog management
]
```

## Webhook Configuration

### 1. Webhook Endpoint Setup

Configure webhooks in the Stripe Dashboard:

1. Go to **Developers** → **Webhooks**
2. Click **Add endpoint**
3. Set the endpoint URL: `https://yourdomain.com/api/v1/stripe/webhooks`
4. Select events to listen for:

```
- payment_intent.succeeded
- payment_intent.payment_failed
- customer.subscription.created
- customer.subscription.updated
- customer.subscription.deleted
- invoice.payment_succeeded
- invoice.payment_failed
```

### 2. Webhook Handler Implementation

Add webhook handling to your routes:

```python
@router.post("/webhooks")
async def handle_stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None)
):
    payload = await request.body()
    
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
        )
        
        # Handle different event types
        if event['type'] == 'payment_intent.succeeded':
            await handle_payment_success(event['data']['object'])
        elif event['type'] == 'payment_intent.payment_failed':
            await handle_payment_failure(event['data']['object'])
        # Add more event handlers as needed
        
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
```

## Security Configuration

### 1. Rate Limiting

Implement rate limiting to prevent abuse:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/payments")
@limiter.limit("10/minute")
async def create_payment(request: Request, ...):
    # Payment creation logic
    pass
```

### 2. Input Validation

Ensure all inputs are properly validated:

```python
from pydantic import BaseModel, validator

class CreatePaymentRequest(BaseModel):
    amount: int
    currency: str = "usd"
    customer: Optional[str]
    description: Optional[str]
    
    @validator('amount')
    def validate_amount(cls, v):
        if v < 50:  # Minimum amount in cents
            raise ValueError('Amount must be at least 50 cents')
        return v
```

### 3. Token Security

Implement secure token storage and rotation:

```python
import secrets
from datetime import datetime, timedelta

def generate_secure_token():
    return secrets.token_urlsafe(32)

def is_token_expired(expires_at):
    return datetime.utcnow() > expires_at
```

## Monitoring & Logging

### 1. Health Monitoring

Implement comprehensive health checks:

```python
@router.get("/health/detailed")
async def detailed_health_check():
    health_status = {
        "stripe": await check_stripe_health(),
        "database": await check_database_health(),
        "redis": await check_redis_health(),
        "timestamp": datetime.utcnow().isoformat()
    }
    return health_status

async def check_stripe_health():
    try:
        # Test Stripe connectivity
        balance = stripe_service.get_balance("test_token")
        return {"status": "healthy", "response_time": "fast"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
```

### 2. Logging Configuration

Configure structured logging:

```python
import logging
from loguru import logger

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Log Stripe API calls
logger.add(
    "logs/stripe_integration.log",
    rotation="10 MB",
    retention="30 days",
    level="INFO"
)
```

## Performance Optimization

### 1. Caching Strategy

Implement caching for frequently accessed data:

```python
import redis
from functools import wraps

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def cache_stripe_data(ttl=300):  # 5 minutes TTL
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"stripe:{func.__name__}:{str(args)}:{str(kwargs)}"
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
            
            result = await func(*args, **kwargs)
            redis_client.setex(cache_key, ttl, json.dumps(result))
            return result
        return wrapper
    return decorator

@router.get("/customers")
@cache_stripe_data(ttl=600)  # 10 minutes cache
async def get_customers(...):
    # Customer retrieval logic
    pass
```

### 2. Connection Pooling

Configure database connection pooling:

```python
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=3600
)
```

## Deployment Strategies

### 1. Docker Deployment

Create a Dockerfile for the integration:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 2. Kubernetes Deployment

Create Kubernetes manifests:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: atom-stripe-integration
spec:
  replicas: 3
  selector:
    matchLabels:
      app: atom-stripe
  template:
    metadata:
      labels:
        app: atom-stripe
    spec:
      containers:
      - name: atom-stripe
        image: your-registry/atom-stripe:latest
        ports:
        - containerPort: 8000
        env:
        - name: STRIPE_CLIENT_ID
          valueFrom:
            secretKeyRef:
              name: stripe-secrets
              key: client-id
        - name: STRIPE_CLIENT_SECRET
          valueFrom:
            secretKeyRef:
              name: stripe-secrets
              key: client-secret
```

## Testing in Production

### 1. Smoke Tests

Run smoke tests after deployment:

```python
import requests

def run_smoke_tests(base_url):
    tests = [
        ("/api/v1/stripe/health", "GET"),
        ("/api/v1/stripe/customers?limit=1", "GET"),
    ]
    
    for endpoint, method in tests:
        try:
            response = requests.request(method, f"{base_url}{endpoint}")
            assert response.status_code == 200
            print(f"✅ {endpoint} - PASS")
        except Exception as e:
            print(f"❌ {endpoint} - FAIL: {e}")
```

### 2. Load Testing

Perform load testing with tools like Locust:

```python
from locust import HttpUser, task, between

class StripeIntegrationUser(HttpUser):
    wait_time = between(1, 5)
    
    @task
    def get_customers(self):
        self.client.get("/api/v1/stripe/customers")
    
    @task(3)
    def create_payment(self):
        self.client.post("/api/v1/stripe/payments", json={
            "amount": 2000,
            "currency": "usd"
        })
```

## Troubleshooting

### Common Issues

#### 1. OAuth Authentication Failures

**Symptoms**: 401 errors, token validation failures
**Solutions**:
- Verify Stripe client ID and secret
- Check redirect URI configuration
- Ensure proper scopes are requested
- Validate token storage implementation

#### 2. Webhook Delivery Failures

**Symptoms**: Missing webhook events, 400 errors
**Solutions**:
- Verify webhook secret configuration
- Check endpoint URL accessibility
- Monitor Stripe dashboard for webhook failures
- Implement webhook retry logic

#### 3. Rate Limiting Issues

**Symptoms**: 429 errors, slow response times
**Solutions**:
- Implement exponential backoff for retries
- Monitor API usage in Stripe dashboard
- Consider implementing request queuing
- Cache frequently accessed data

### Monitoring Metrics

Set up monitoring for key metrics:

- API response times (< 2 seconds)
- Error rates (< 1%)
- Webhook delivery success rate (> 99%)
- Payment success rate (> 98%)
- Token refresh success rate (> 99%)

## Backup and Recovery

### 1. Database Backups

```bash
# Daily backup script
pg_dump -h localhost -U user atom_db > /backups/atom_stripe_$(date +%Y%m%d).sql
```

### 2. Token Recovery

Implement token recovery mechanisms:

```python
async def recover_expired_tokens():
    expired_tokens = await get_expired_tokens()
    for token in expired_tokens:
        try:
            new_token = await refresh_token(token.refresh_token)
            await update_token_in_database(token.user_id, new_token)
        except Exception as e:
            logger.error(f"Failed to refresh token for user {token.user_id}: {e}")
```

## Scaling Considerations

### 1. Horizontal Scaling

- Use load balancers for multiple instances
- Implement sticky sessions if needed
- Configure database connection pooling
- Use distributed caching (Redis Cluster)

### 2. Vertical Scaling

- Monitor resource usage (CPU, memory, disk I/O)
- Scale database resources as needed
- Optimize database queries and indexes
- Implement connection pooling

## Security Audit Checklist

- [ ] All API endpoints use HTTPS
- [ ] OAuth tokens are securely stored and encrypted
- [ ] Input validation is implemented for all endpoints
- [ ] Rate limiting is configured
- [ ] Webhook signatures are verified
- [ ] Error messages don't expose sensitive information
- [ ] Database connections use SSL
- [ ] Regular security updates are applied

## Support and Maintenance

### 1. Regular Maintenance Tasks

- Monitor Stripe API version updates
- Update dependencies regularly
- Review and rotate API keys
- Monitor security advisories
- Perform regular backups

### 2. Support Channels

- Stripe API Documentation: https://stripe.com/docs/api
- ATOM Platform Documentation
- Development team support
- Stripe Support for API issues

## Version History

### v1.1.0 (Current)
- Enhanced testing with mock data
- Comprehensive deployment guide
- Improved error handling
- Webhook support

### v1.0.0
- Initial Stripe integration release
- Basic payment processing
- Customer and subscription management
- OAuth authentication

---

**Next Steps**: After deployment, monitor the integration for 24-48 hours and perform comprehensive testing before enabling for all users.