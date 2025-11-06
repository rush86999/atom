# Shopify Integration Guide - ATOM Backend

Complete Shopify e-commerce integration for ATOM backend with Phase 1 features and beyond.

## 🛒 Integration Overview

This integration provides comprehensive Shopify e-commerce functionality including:
- **Real-time Webhooks**: Event notifications and triggers
- **Bulk API Integration**: Large-scale data operations
- **Custom App Extension**: Custom app support and extensions  
- **Advanced Analytics**: Enhanced reporting and insights
- **Full E-commerce**: Products, orders, customers, inventory

## 📁 File Structure

```
backend/python-api-service/
├── shopify_service.py                  # Core Shopify service
├── shopify_webhooks.py               # Real-time webhook handling
├── shopify_bulk_api.py               # Bulk operations API
├── shopify_custom_apps.py            # Custom app management
├── shopify_analytics.py              # Advanced analytics engine
├── shopify_routes.py                 # Flask API endpoints
├── shopify_integration_register.py    # Registration utilities
├── test_shopify_integration.py        # Comprehensive test suite
└── SHOPIFY_INTEGRATION_GUIDE.md     # This documentation
```

## 🚀 Quick Integration

### 1. Add to Main App

In `main_api_app.py`, add these imports:

```python
# Shopify integration imports
from shopify_integration_register import register_shopify_integration, get_shopify_service_info
```

### 2. Register Integration

Add this after your database pool setup:

```python
# Register Shopify integration
shopify_registered = register_shopify_integration(app, db_pool)
if shopify_registered:
    print("✅ Shopify integration registered successfully")
else:
    print("❌ Failed to register Shopify integration")
```

### 3. Add to Service Registry

Add to your service registration endpoint:

```python
from shopify_integration_register import get_shopify_service_info

# In your services endpoint
services.append({
    "name": "shopify",
    "info": get_shopify_service_info(),
    "status": "active" if shopify_registered else "inactive"
})
```

## 🔧 Environment Configuration

Add these variables to your `.env` file:

```bash
# Shopify API Configuration (for development)
SHOPIFY_ACCESS_TOKEN=shpat_your_development_token
SHOPIFY_SHOP_DOMAIN=test-shop.myshopify.com

# Shopify App Configuration (for custom apps)
SHOPIFY_APP_CLIENT_ID=your_app_client_id
SHOPIFY_APP_CLIENT_SECRET=your_app_client_secret
SHOPIFY_APP_SCOPES=read_products,write_products,read_orders,write_orders,read_customers,write_customers,read_inventory

# Shopify Webhook Configuration  
SHOPIFY_WEBHOOK_SECRET=your_webhook_secret
SHOPIFY_WEBHOOK_URL=https://your-domain.com/api/shopify/webhooks

# Shopify Analytics Configuration
SHOPIFY_ANALYTICS_CACHE_TTL=3600
SHOPIFY_ANALYTICS_FORECAST_DAYS=30
```

## 🌐 API Endpoints

### Core Shopify API
```
GET  /api/shopify/health                     # Health check
POST /api/shopify/connect                    # Connect to Shopify store
GET  /api/shopify/products                   # Get products
POST /api/shopify/products                   # Create product
GET  /api/shopify/orders                    # Get orders
POST /api/shopify/orders                    # Create order
GET  /api/shopify/customers                 # Get customers
POST /api/shopify/customers                 # Create customer
POST /api/shopify/search                     # Search Shopify data
GET  /api/shopify/shop                      # Get shop information
```

### Real-time Webhooks
```
POST /api/shopify/webhooks/setup            # Setup webhooks
POST /api/shopify/webhooks/<topic>          # Handle webhook events
GET  /api/shopify/webhooks/events           # Get event history
GET  /api/shopify/webhooks/topics           # List available topics
```

### Bulk Operations
```
POST /api/shopify/bulk/query                # Execute bulk GraphQL query
GET  /api/shopify/bulk/operations/<id>     # Get operation status
GET  /api/shopify/bulk/operations/<id>/wait # Wait for completion
GET  /api/shopify/bulk/products             # Bulk get products
GET  /api/shopify/bulk/orders              # Bulk get orders
POST /api/shopify/bulk/products/create     # Bulk create products
```

### Custom Apps
```
POST /api/shopify/apps                      # Create custom app
GET  /api/shopify/apps                      # Get custom apps
POST /api/shopify/apps/<id>/extensions      # Create app extension
POST /api/shopify/apps/<id>/install         # Install app
PUT  /api/shopify/apps/<id>/permissions     # Update permissions
GET  /api/shopify/installations             # Get installations
```

### Advanced Analytics
```
POST /api/shopify/analytics/sales           # Sales analytics
POST /api/shopify/analytics/customers       # Customer analytics
POST /api/shopify/analytics/products        # Product analytics
POST /api/shopify/analytics/inventory      # Inventory analytics
POST /api/shopify/analytics/report          # Comprehensive report
POST /api/shopify/analytics/forecast        # Sales forecasting
```

## 📊 Usage Examples

### Connect to Shopify Store

```python
import requests

response = requests.post("http://localhost:8000/api/shopify/connect", json={
    "user_id": "user_123",
    "shop_domain": "my-store.myshopify.com", 
    "access_token": "shpat_your_access_token"
})

if response.json()["ok"]:
    print("✅ Connected to Shopify!")
    shop_info = response.json()["shop"]
    print(f"Store: {shop_info['name']}")
```

### Get Products with Filtering

```python
response = requests.get("http://localhost:8000/api/shopify/products", params={
    "user_id": "user_123",
    "status": "active",
    "product_type": "electronics",
    "limit": 50
})

products = response.json()["products"]
print(f"Found {len(products)} products")
```

### Create Product

```python
product_data = {
    "title": "Wireless Headphones Pro",
    "handle": "wireless-headphones-pro",
    "description": "<p>Premium wireless headphones with noise cancellation</p>",
    "vendor": "AudioTech",
    "product_type": "Electronics", 
    "status": "active",
    "variants": [{
        "title": "Default Title",
        "price": "299.99",
        "sku": "HEADPHONES-PRO-001",
        "inventory_quantity": 100,
        "weight": 450
    }],
    "tags": "premium, wireless, headphones, noise-cancelling"
}

response = requests.post("http://localhost:8000/api/shopify/products", json={
    "user_id": "user_123",
    "product": product_data
})

product = response.json()["product"]
print(f"✅ Created product: {product['title']} (ID: {product['id']})")
```

### Setup Real-time Webhooks

```python
response = requests.post("http://localhost:8000/api/shopify/webhooks/setup", json={
    "user_id": "user_123",
    "webhook_secret": "your_webhook_secret",
    "webhook_url": "https://your-domain.com/api/shopify/webhooks"
})

webhooks = response.json()["webhooks"]
print(f"✅ Setup {len(webhooks)} webhooks")
for webhook in webhooks:
    print(f"   {webhook['topic']}: {webhook['address']}")
```

### Execute Bulk Operations

```python
# Bulk get products
response = requests.get("http://localhost:8000/api/shopify/bulk/products", params={
    "user_id": "user_123",
    "status": "active",
    "limit": 250
})

result = response.json()
products = result["products"]
print(f"✅ Bulk retrieved {len(products)} products")

# Bulk create products
products_to_create = [
    {
        "title": f"Product {i}",
        "variants": [{
            "title": "Default Title", 
            "price": f"{i + 10}.99",
            "sku": f"BULK-{i:03d}",
            "inventory_quantity": i + 5
        }]
    }
    for i in range(1, 6)
]

response = requests.post("http://localhost:8000/api/shopify/bulk/products/create", json={
    "user_id": "user_123",
    "products": products_to_create
})

result = response.json()
print(f"✅ Bulk created products (Operation: {result['operation_id']})")
```

### Get Sales Analytics

```python
analytics_data = {
    "user_id": "user_123",
    "start_date": "2024-01-01T00:00:00Z",
    "end_date": "2024-01-31T23:59:59Z", 
    "granularity": "daily",
    "include_forecast": True
}

response = requests.post("http://localhost:8000/api/shopify/analytics/sales", json=analytics_data)

analytics = response.json()["analytics"]
print(f"💰 Sales Analytics:")
print(f"   Total Revenue: ${analytics['total_revenue']:.2f}")
print(f"   Total Orders: {analytics['total_orders']}")
print(f"   Average Order Value: ${analytics['average_order_value']:.2f}")
print(f"   Conversion Rate: {analytics['conversion_rate']:.2f}%")
print(f"   Repeat Customer Rate: {analytics['repeat_customer_rate']:.2f}%")
```

### Generate Comprehensive Report

```python
report_data = {
    "user_id": "user_123",
    "start_date": "2024-01-01T00:00:00Z",
    "end_date": "2024-01-31T23:59:59Z",
    "include_forecast": True
}

response = requests.post("http://localhost:8000/api/shopify/analytics/report", json=report_data)

report = response.json()["report"]
print(f"📊 Comprehensive Report Generated:")
print(f"   Period: {report['report_period']['start_date']} to {report['report_period']['end_date']}")
print(f"   Generated At: {report['generated_at']}")

# Key insights
if report.get("key_insights"):
    print(f"   Key Insights:")
    for insight in report["key_insights"]:
        print(f"   - {insight['title']}: {insight['description']}")
```

## 🧪 Testing

Run comprehensive tests:

```bash
# Run the Shopify integration test suite
python test_shopify_integration.py

# Or with pytest for specific tests
pytest test_shopify_integration.py::TestShopifyIntegration::test_shopify_health_check -v
```

### Test Coverage

- ✅ Health checks and connection
- ✅ Core API operations (products, orders, customers)
- ✅ Real-time webhooks setup and handling
- ✅ Bulk operations and status tracking
- ✅ Custom app creation and management
- ✅ Advanced analytics and reporting
- ✅ Sales forecasting
- ✅ End-to-end workflows

## 🔧 Advanced Features

### Real-time Webhooks

The integration supports all Shopify webhook topics:

- **Order Events**: orders/create, orders/paid, orders/cancelled, orders/fulfilled
- **Product Events**: products/create, products/update, products/delete
- **Customer Events**: customers/create, customers/update, customers/delete
- **Inventory Events**: inventory_levels/update, inventory_items/create
- **Shop Events**: shop/update, app/uninstalled

### Bulk Operations

Efficiently handle large-scale data:

- **GraphQL Bulk Queries**: Process thousands of records
- **Bulk Product Operations**: Create/update products in bulk
- **Bulk Order Management**: Process orders at scale
- **Status Tracking**: Monitor operation progress
- **Result Parsing**: Automatic JSONL result processing

### Custom Apps

Build and manage custom Shopify apps:

- **App Creation**: Generate apps with custom permissions
- **App Extensions**: Create theme, checkout, and post-purchase extensions
- **Installation Management**: Handle app installation lifecycle
- **Permission Control**: Granular scope management
- **OAuth Support**: Complete OAuth flow implementation

### Advanced Analytics

Comprehensive business intelligence:

- **Sales Analytics**: Revenue, AOV, conversion, churn analysis
- **Customer Analytics**: LTV, segmentation, cohort analysis
- **Product Analytics**: Performance, inventory turns, category analysis
- **Inventory Analytics**: Optimization, dead stock, overstock analysis
- **Forecasting**: Sales prediction with trend and seasonal analysis
- **Insights Generation**: Automated business insights and recommendations

## 🚨 Error Handling

The integration provides comprehensive error handling:

### HTTP Response Format

```json
{
  "ok": true,
  "data": { ... }
}
```

```json
{
  "ok": false,
  "error": "Error description",
  "details": { ... }
}
```

### Common Error Codes

- `400`: Bad Request - Invalid parameters
- `401`: Unauthorized - Missing or invalid authentication
- `403`: Forbidden - Insufficient permissions
- `404`: Not Found - Resource not found
- `429`: Too Many Requests - Rate limit exceeded
- `500`: Internal Server Error - Server-side error

### Rate Limiting

Shopify API rate limits are automatically handled:

- **Leaky Bucket Algorithm**: Standard Shopify rate limiting
- **Retry Logic**: Automatic retry with exponential backoff
- **Queue Management**: Bulk operations use Shopify's bulk queue
- **Usage Monitoring**: Track API usage and limits

## 🔒 Security Features

### Authentication

- **OAuth 2.0**: Secure token-based authentication
- **Token Management**: Secure token storage and refresh
- **Scope-based Access**: Granular permission control
- **Shop-level Isolation**: User and shop data isolation

### Webhook Security

- **Signature Verification**: HMAC SHA-256 verification
- **Replay Protection**: Timestamp validation
- **Secure Callbacks**: HTTPS webhook URLs only
- **Content Validation**: JSON schema validation

### Data Protection

- **Input Validation**: Comprehensive parameter validation
- **Output Sanitization**: Safe data serialization
- **Error Sanitization**: No sensitive data in errors
- **Audit Logging**: Complete request/response logging

## 📈 Performance Features

### Caching

- **Response Caching**: API response caching
- **Analytics Caching**: Computed analytics caching
- **Token Caching**: OAuth token caching
- **Configuration Caching**: App and webhook caching

### Optimization

- **Connection Pooling**: HTTP connection reuse
- **Parallel Processing**: Async operation handling
- **Bulk Operations**: Efficient data processing
- **Lazy Loading**: On-demand data loading

### Monitoring

- **Health Checks**: Service health monitoring
- **Performance Metrics**: Response time tracking
- **Error Tracking**: Comprehensive error logging
- **Usage Analytics**: API usage statistics

## 🔮 Phase 2 & 3 Roadmap

### Phase 2 (Q2 2025) - Advanced Features

- **AI-Powered Insights**: Product recommendations and sales forecasting
- **Automated Inventory**: Inventory optimization and restocking  
- **Multi-channel Sales**: Integration with other sales channels
- **Advanced Customer Segmentation**: AI-driven customer analytics

### Phase 3 (H2 2025) - Platform Evolution

- **Predictive Analytics**: Advanced sales and inventory forecasting
- **Automated Marketing**: Integrated marketing campaign management
- **Supply Chain Optimization**: End-to-end supply chain integration
- **International Expansion**: Multi-currency and multi-language support

## 🛠️ Troubleshooting

### Common Issues

1. **Shopify Connection Failed**
   ```bash
   # Check credentials and permissions
   # Verify access token has required scopes
   # Test with a simple GET request first
   ```

2. **Webhook Not Receiving Events**
   ```bash
   # Check webhook URL accessibility
   # Verify webhook secret matches
   # Check webhook topic registration
   ```

3. **Bulk Operations Taking Too Long**
   ```bash
   # Check operation queue status
   # Reduce query complexity
   # Use pagination for large datasets
   ```

4. **Analytics Data Missing**
   ```bash
   # Check date range coverage
   # Verify user permissions
   # Check data sync status
   ```

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Or use loguru
from loguru import logger
logger.remove()
logger.add(sys.stderr, level="DEBUG")
```

### Health Monitoring

Check integration health:

```bash
curl "http://localhost:8000/api/shopify/health"
```

Detailed health check:

```bash
curl "http://localhost:8000/api/shopify/health?detailed=true&user_id=your_user_id"
```

## 📞 Support

### Documentation

- **API Reference**: Complete endpoint documentation
- **Integration Guides**: Step-by-step integration tutorials
- **Troubleshooting Guide**: Common issues and solutions
- **Best Practices**: Performance and security recommendations

### Community

- **Issue Reporting**: GitHub issue tracker
- **Feature Requests**: Enhancement requests
- **Community Forum**: Discussion and support
- **Knowledge Base**: FAQs and solutions

---

## 🎉 Summary

The Shopify integration provides a complete, production-ready e-commerce solution for the ATOM ecosystem. With comprehensive API coverage, real-time webhooks, bulk operations, custom app support, and advanced analytics, it enables full-featured e-commerce functionality.

**Key Features:**
- ✅ Complete Shopify API coverage (REST + GraphQL)
- ✅ Real-time webhook handling with security
- ✅ Efficient bulk operations at scale
- ✅ Custom app development and management
- ✅ Advanced analytics and forecasting
- ✅ Comprehensive error handling
- ✅ Performance optimization
- ✅ Security best practices
- ✅ Complete test coverage
- ✅ Production-ready deployment

This integration is ready for enterprise deployment and can handle large-scale e-commerce operations with reliability and performance.

**Phase 1 Status: ✅ COMPLETE**
- Real-time Webhooks ✅
- Bulk API Integration ✅  
- Custom App Extension ✅
- Advanced Analytics ✅

Ready for Phase 2 advanced features in Q2 2025! 🚀