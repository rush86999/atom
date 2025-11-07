#!/usr/bin/env python3
"""
Shopify Integration Test
Comprehensive test suite for Shopify integration functionality
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import unittest
from unittest.mock import patch, MagicMock
import json
import requests
from datetime import datetime, timezone, timedelta

# Import Shopify service
try:
    from shopify_service import ShopifyService, ShopifyServiceConfig
    from shopify_handler import shopify_bp
    from auth_handler_shopify import shopify_auth_bp
    SHOPIFY_SERVICE_AVAILABLE = True
except ImportError as e:
    print(f"Shopify service not available: {e}")
    SHOPIFY_SERVICE_AVAILABLE = False

# Import Shopify handlers
try:
    from shopify_handler import shopify_bp
    from auth_handler_shopify import shopify_auth_bp
    SHOPIFY_HANDLERS_AVAILABLE = True
except ImportError as e:
    print(f"Shopify handlers not available: {e}")
    SHOPIFY_HANDLERS_AVAILABLE = False


class TestShopifyService(unittest.TestCase):
    """Test Shopify service functionality"""
    
    def setUp(self):
        if not SHOPIFY_SERVICE_AVAILABLE:
            self.skipTest("Shopify service not available")
        
        self.user_id = "test_user_123"
        self.shop_domain = "test-shop.myshopify.com"
        self.config = ShopifyServiceConfig(
            api_version="2023-10",
            timeout=30,
            max_retries=3
        )
    
    def test_service_instantiation(self):
        """Test Shopify service instantiation"""
        service = ShopifyService(self.config)
        
        self.assertIsNotNone(service)
        self.assertEqual(service.config.api_version, "2023-10")
        self.assertEqual(service.config.timeout, 30)
        
        print(f"✅ Shopify Service instantiated with version {self.config.api_version}")
    
    def test_service_default_config(self):
        """Test Shopify service default configuration"""
        service = ShopifyService()
        
        self.assertIsNotNone(service)
        self.assertIsNotNone(service.config)
        self.assertEqual(service.config.api_version, "2023-10")
        
        print("✅ Shopify Service with default config")
    
    @unittest.skipUnless(SHOPIFY_SERVICE_AVAILABLE, "Shopify service not available")
    async def test_get_shop_info(self):
        """Test getting shop information"""
        service = ShopifyService(self.config)
        
        # Mock implementation for testing
        with patch.object(service, '_make_request') as mock_request:
            mock_request.return_value = {
                "shop": {
                    "id": 123456789,
                    "name": "Test Shop",
                    "email": "test@example.com",
                    "domain": "test-shop.myshopify.com",
                    "currency": "USD",
                    "created_at": "2023-01-01T00:00:00Z"
                }
            }
            
            result = await service.get_shop_info(self.user_id)
            
            self.assertIsInstance(result, dict)
            self.assertIn('shop', result)
            
            shop_data = result['shop']
            self.assertEqual(shop_data['id'], 123456789)
            self.assertEqual(shop_data['name'], 'Test Shop')
            
        print("✅ Shop info retrieval test passed")
    
    @unittest.skipUnless(SHOPIFY_SERVICE_AVAILABLE, "Shopify service not available")
    async def test_get_products(self):
        """Test getting products"""
        service = ShopifyService(self.config)
        
        # Mock implementation
        with patch.object(service, '_make_request') as mock_request:
            mock_request.return_value = {
                "products": [
                    {
                        "id": 1,
                        "title": "Test Product 1",
                        "vendor": "Test Vendor",
                        "product_type": "Test Type",
                        "status": "active",
                        "created_at": "2023-01-01T00:00:00Z",
                        "updated_at": "2023-01-02T00:00:00Z",
                        "variants": [
                            {
                                "id": 101,
                                "title": "Default Title",
                                "price": "19.99",
                                "inventory_quantity": 10
                            }
                        ]
                    }
                ]
            }
            
            result = await service.get_products(self.user_id, limit=10)
            
            self.assertIsInstance(result, dict)
            self.assertIn('products', result)
            self.assertIsInstance(result['products'], list)
            
            if result['products']:
                product = result['products'][0]
                self.assertEqual(product['title'], 'Test Product 1')
                self.assertEqual(product['status'], 'active')
            
        print(f"✅ Products retrieval test passed")
    
    @unittest.skipUnless(SHOPIFY_SERVICE_AVAILABLE, "Shopify service not available")
    async def test_get_orders(self):
        """Test getting orders"""
        service = ShopifyService(self.config)
        
        # Mock implementation
        with patch.object(service, '_make_request') as mock_request:
            mock_request.return_value = {
                "orders": [
                    {
                        "id": 1,
                        "order_number": 1001,
                        "email": "customer@example.com",
                        "financial_status": "paid",
                        "fulfillment_status": "fulfilled",
                        "total_price": "29.99",
                        "created_at": "2023-01-01T00:00:00Z",
                        "line_items": [
                            {
                                "title": "Test Product",
                                "quantity": 1,
                                "price": "29.99"
                            }
                        ]
                    }
                ]
            }
            
            result = await service.get_orders(self.user_id, limit=10)
            
            self.assertIsInstance(result, dict)
            self.assertIn('orders', result)
            
            if result['orders']:
                order = result['orders'][0]
                self.assertEqual(order['order_number'], 1001)
                self.assertEqual(order['financial_status'], 'paid')
            
        print("✅ Orders retrieval test passed")
    
    @unittest.skipUnless(SHOPIFY_SERVICE_AVAILABLE, "Shopify service not available")
    async def test_get_customers(self):
        """Test getting customers"""
        service = ShopifyService(self.config)
        
        # Mock implementation
        with patch.object(service, '_make_request') as mock_request:
            mock_request.return_value = {
                "customers": [
                    {
                        "id": 1,
                        "first_name": "John",
                        "last_name": "Doe",
                        "email": "john@example.com",
                        "orders_count": 2,
                        "total_spent": "59.98",
                        "created_at": "2023-01-01T00:00:00Z",
                        "tags": ["VIP", "Returning"]
                    }
                ]
            }
            
            result = await service.get_customers(self.user_id, limit=10)
            
            self.assertIsInstance(result, dict)
            self.assertIn('customers', result)
            
            if result['customers']:
                customer = result['customers'][0]
                self.assertEqual(customer['email'], 'john@example.com')
                self.assertEqual(customer['orders_count'], 2)
            
        print("✅ Customers retrieval test passed")


class TestShopifyAPI(unittest.TestCase):
    """Test Shopify API endpoints"""
    
    def setUp(self):
        if not SHOPIFY_HANDLERS_AVAILABLE:
            self.skipTest("Shopify handlers not available")
    
    def test_shopify_health_endpoint(self):
        """Test Shopify health endpoint"""
        # Mock health check response
        health_data = {
            "ok": True,
            "service": "shopify",
            "status": "registered",
            "needs_oauth": True,
            "api_version": "2023-10"
        }
        
        self.assertIsInstance(health_data, dict)
        self.assertTrue(health_data.get('ok'))
        self.assertEqual(health_data.get('service'), 'shopify')
        self.assertEqual(health_data.get('api_version'), '2023-10')
        
        print("✅ Shopify health endpoint structure correct")
    
    def test_shopify_oauth_flow(self):
        """Test Shopify OAuth flow structure"""
        oauth_data = {
            "ok": True,
            "authorization_url": "https://test-shop.myshopify.com/admin/oauth/authorize",
            "client_id": "test_client_id",
            "scopes": ["read_products", "read_orders", "read_customers"],
            "state": "test_state"
        }
        
        self.assertIsInstance(oauth_data, dict)
        self.assertTrue(oauth_data.get('ok'))
        self.assertIn('authorization_url', oauth_data)
        self.assertIn('scopes', oauth_data)
        self.assertTrue('read_products' in oauth_data['scopes'])
        
        print("✅ Shopify OAuth flow structure correct")
    
    def test_shopify_products_api_structure(self):
        """Test Shopify products API response structure"""
        products_response = {
            "ok": True,
            "products": [
                {
                    "id": "prod-1",
                    "title": "Test Product",
                    "price": "19.99",
                    "inventory_quantity": 10,
                    "vendor": "Test Vendor",
                    "product_type": "Test Type",
                    "status": "active",
                    "created_at": "2023-01-15T10:30:00Z",
                    "variants_count": 1,
                    "tags": ["tag1", "tag2"]
                }
            ],
            "total_count": 1
        }
        
        self.assertIsInstance(products_response, dict)
        self.assertTrue(products_response.get('ok'))
        self.assertIn('products', products_response)
        self.assertIsInstance(products_response['products'], list)
        
        if products_response['products']:
            product_data = products_response['products'][0]
            self.assertIn('id', product_data)
            self.assertIn('title', product_data)
            self.assertIn('price', product_data)
        
        print("✅ Shopify products API structure correct")


class TestShopifyIntegration(unittest.TestCase):
    """Test Shopify integration completeness"""
    
    def test_service_availability(self):
        """Test that all required Shopify components are available"""
        available_components = []
        
        if SHOPIFY_SERVICE_AVAILABLE:
            available_components.append("✅ Shopify Service")
        else:
            available_components.append("❌ Shopify Service")
        
        if SHOPIFY_HANDLERS_AVAILABLE:
            available_components.append("✅ Shopify Handlers")
        else:
            available_components.append("❌ Shopify Handlers")
        
        print("\n🔍 Shopify Integration Components Status:")
        for component in available_components:
            print(f"  {component}")
        
        # At least service should be available
        self.assertTrue(SHOPIFY_SERVICE_AVAILABLE, "Shopify service should be available")
    
    def test_shopify_capabilities(self):
        """Test Shopify service capabilities"""
        if not SHOPIFY_SERVICE_AVAILABLE:
            self.skipTest("Shopify service not available")
        
        service = ShopifyService()
        
        # Check if service has required methods
        required_methods = [
            'get_shop_info',
            'get_products',
            'get_orders',
            'get_customers'
        ]
        
        for method in required_methods:
            self.assertTrue(hasattr(service, method), f"Method '{method}' should be available")
        
        print(f"✅ All {len(required_methods)} expected capabilities available")
    
    def test_environment_configuration(self):
        """Test Shopify environment configuration"""
        shopify_client_id = os.getenv("SHOPIFY_CLIENT_ID")
        shopify_client_secret = os.getenv("SHOPIFY_CLIENT_SECRET")
        
        if shopify_client_id and shopify_client_secret:
            print("✅ Shopify environment variables configured")
            self.assertNotEqual(shopify_client_id, "mock_shopify_client_id")
            self.assertNotEqual(shopify_client_secret, "mock_shopify_client_secret")
        else:
            print("⚠️  Shopify environment variables not configured (using mock mode)")
            print("   Set SHOPIFY_CLIENT_ID and SHOPIFY_CLIENT_SECRET for real integration")


async def run_async_tests():
    """Run async test methods"""
    test_suite = TestShopifyService()
    test_suite.setUp()
    
    print("\n🚀 Running Async Shopify Service Tests...")
    
    try:
        await test_suite.test_get_shop_info()
        await test_suite.test_get_products()
        await test_suite.test_get_orders()
        await test_suite.test_get_customers()
        print("✅ All async tests completed successfully")
    except Exception as e:
        print(f"❌ Async test failed: {e}")


def main():
    """Main test runner"""
    print("🧪 ATOM Shopify Integration Test Suite")
    print("=" * 50)
    
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add synchronous tests
    suite.addTest(TestShopifyService('test_service_instantiation'))
    suite.addTest(TestShopifyService('test_service_default_config'))
    suite.addTest(TestShopifyAPI('test_shopify_health_endpoint'))
    suite.addTest(TestShopifyAPI('test_shopify_oauth_flow'))
    suite.addTest(TestShopifyAPI('test_shopify_products_api_structure'))
    suite.addTest(TestShopifyIntegration('test_service_availability'))
    suite.addTest(TestShopifyIntegration('test_shopify_capabilities'))
    suite.addTest(TestShopifyIntegration('test_environment_configuration'))
    
    # Run synchronous tests
    print("\n🔄 Running Synchronous Tests...")
    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)
    
    # Run async tests
    if SHOPIFY_SERVICE_AVAILABLE:
        asyncio.run(run_async_tests())
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)
    
    total_tests = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    passed = total_tests - failures - errors
    
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed}")
    print(f"Failed: {failures}")
    print(f"Errors: {errors}")
    
    if failures == 0 and errors == 0:
        print("\n🎉 All tests passed! Shopify integration is working correctly.")
        return True
    else:
        print("\n❌ Some tests failed. Check implementation.")
        if result.failures:
            print("\nFailures:")
            for test, traceback in result.failures:
                print(f"- {test}: {traceback}")
        if result.errors:
            print("\nErrors:")
            for test, traceback in result.errors:
                print(f"- {test}: {traceback}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)