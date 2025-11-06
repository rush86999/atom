# Stripe Integration Documentation

## Overview

The Stripe integration provides comprehensive payment processing and financial management capabilities for the ATOM platform. This integration enables businesses to manage payments, subscriptions, customers, and products directly through the ATOM interface.

## Features

### Core Payment Processing
- **Payment Management**: Create, retrieve, and manage payments
- **Customer Management**: Handle customer records and billing information
- **Subscription Management**: Create and manage recurring subscriptions
- **Product Catalog**: Manage products and pricing
- **Account Management**: Access account information and balance

### Advanced Features
- **Search Functionality**: Search across all Stripe resources
- **Health Monitoring**: Real-time integration health checks
- **Error Handling**: Comprehensive error reporting and recovery
- **Response Formatting**: Consistent API response structure

## API Endpoints

### Health & Status
- `GET /stripe/health` - Check integration health status
- `GET /stripe/` - Integration information and available endpoints

### Payments
- `GET /stripe/payments` - List payments with filtering options
- `GET /stripe/payments/{payment_id}` - Get specific payment details
- `POST /stripe/payments` - Create a new payment

### Customers
- `GET /stripe/customers` - List customers with filtering options
- `GET /stripe/customers/{customer_id}` - Get specific customer details
- `POST /stripe/customers` - Create a new customer

### Subscriptions
- `GET /stripe/subscriptions` - List subscriptions with filtering options
- `GET /stripe/subscriptions/{subscription_id}` - Get specific subscription details
- `POST /stripe/subscriptions` - Create a new subscription
- `DELETE /stripe/subscriptions/{subscription_id}` - Cancel a subscription

### Products
- `GET /stripe/products` - List products with filtering options
- `GET /stripe/products/{product_id}` - Get specific product details
- `POST /stripe/products` - Create a new product

### Search & Analytics
- `GET /stripe/search` - Search across Stripe resources
- `GET /stripe/profile` - Get account profile information
- `GET /stripe/balance` - Get account balance
- `GET /stripe/account` - Get account information

## Authentication

The Stripe integration uses OAuth 2.0 for authentication:

1. **OAuth Flow**: Standard OAuth 2.0 authorization code flow
2. **Scopes**: Full read/write access to Stripe account
3. **Token Management**: Automatic token refresh and management

### Required Environment Variables
```bash
STRIPE_CLIENT_ID=your_stripe_client_id
STRIPE_CLIENT_SECRET=your_stripe_client_secret
STRIPE_REDIRECT_URI=http://localhost:3000/auth/stripe/callback
```

## Installation & Setup

### Prerequisites
- Python 3.8+
- FastAPI application
- Stripe developer account

### Installation Steps
1. Install required dependencies:
```bash
pip install stripe fastapi uvicorn
```

2. Configure environment variables with your Stripe credentials

3. Import and register the Stripe router in your FastAPI app:
```python
from integrations.stripe_routes import router as stripe_router
app.include_router(stripe_router)
```

## Usage Examples

### Creating a Payment
```python
import requests

# Create a payment
response = requests.post(
    "http://localhost:8000/stripe/payments",
    json={
        "amount": 2000,  # $20.00 in cents
        "currency": "usd",
        "customer": "cus_123456789",
        "description": "Monthly subscription payment"
    },
    headers={"Authorization": "Bearer your_access_token"}
)
```

### Managing Customers
```python
# Create a customer
response = requests.post(
    "http://localhost:8000/stripe/customers",
    json={
        "email": "customer@example.com",
        "name": "John Doe",
        "description": "Premium customer"
    },
    headers={"Authorization": "Bearer your_access_token"}
)

# List customers with filtering
response = requests.get(
    "http://localhost:8000/stripe/customers?limit=10&email=customer@example.com",
    headers={"Authorization": "Bearer your_access_token"}
)
```

### Subscription Management
```python
# Create a subscription
response = requests.post(
    "http://localhost:8000/stripe/subscriptions",
    json={
        "customer": "cus_123456789",
        "items": [
            {
                "price": "price_123456789",
                "quantity": 1
            }
        ]
    },
    headers={"Authorization": "Bearer your_access_token"}
)
```

## Error Handling

The integration provides consistent error responses:

### Success Response Format
```json
{
    "ok": true,
    "data": {...},
    "service": "stripe",
    "timestamp": "2024-01-15T10:30:00Z"
}
```

### Error Response Format
```json
{
    "ok": false,
    "error": {
        "code": "API_ERROR",
        "message": "Detailed error message",
        "service": "stripe"
    },
    "timestamp": "2024-01-15T10:30:00Z"
}
```

### Common Error Codes
- `AUTH_INIT_FAILED`: OAuth initialization failed
- `OAUTH_ERROR`: OAuth callback error
- `USER_INFO_FAILED`: Failed to get user information
- `CALLBACK_ERROR`: OAuth callback processing error
- `API_ERROR`: Stripe API request failed

## Testing

### Running Tests
```bash
cd atom/backend/integrations
python test_stripe_integration.py
```

### Test Coverage
- Health check functionality
- Payment management
- Customer operations
- Subscription handling
- Product catalog management
- Search functionality
- Response formatting
- Error handling

## Security Considerations

1. **Token Security**: Access tokens are securely stored and managed
2. **API Rate Limiting**: Built-in rate limiting to prevent abuse
3. **Input Validation**: All inputs are validated before processing
4. **Error Logging**: Comprehensive error logging without exposing sensitive data

## Monitoring & Logging

### Health Monitoring
The integration provides real-time health monitoring:
- API connectivity checks
- Token validity verification
- Response time monitoring

### Logging
- OAuth flow events
- API request/response logging
- Error and exception tracking
- Performance metrics

## Troubleshooting

### Common Issues

1. **Authentication Errors**
   - Verify Stripe credentials
   - Check OAuth redirect URI configuration
   - Ensure proper scopes are requested

2. **API Connection Issues**
   - Verify network connectivity
   - Check Stripe API status
   - Validate API version compatibility

3. **Rate Limiting**
   - Implement proper retry logic
   - Monitor API usage
   - Consider implementing caching

### Support Resources
- Stripe API Documentation: https://stripe.com/docs/api
- ATOM Integration Support: Contact development team
- Error Logs: Check application logs for detailed error information

## Version History

### v1.0.0 (Current)
- Initial Stripe integration release
- Complete payment processing functionality
- Customer and subscription management
- Comprehensive API coverage

## Contributing

To contribute to the Stripe integration:

1. Follow the existing code style and patterns
2. Add comprehensive tests for new features
3. Update documentation accordingly
4. Submit pull requests for review

## License

This integration is part of the ATOM platform and follows the same licensing terms.