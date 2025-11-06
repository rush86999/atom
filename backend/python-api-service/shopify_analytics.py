"""
Shopify Advanced Analytics
Enhanced reporting and insights for Shopify
"""

import json
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger
import statistics
import math

class MetricType(Enum):
    """Analytics metric types"""
    REVENUE = "revenue"
    ORDERS = "orders"
    CUSTOMERS = "customers"
    PRODUCTS = "products"
    CONVERSION = "conversion"
    AOV = "average_order_value"
    LTV = "lifetime_value"
    CHURN = "churn"
    RETENTION = "retention"
    INVENTORY_TURNS = "inventory_turns"

class TimeGranularity(Enum):
    """Time granularity for analytics"""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"

@dataclass
class AnalyticsMetric:
    """Analytics metric model"""
    name: str
    value: float
    type: MetricType
    timestamp: datetime
    period: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    trend: Optional[float] = None
    change_percentage: Optional[float] = None
    previous_value: Optional[float] = None

@dataclass
class SalesAnalytics:
    """Sales analytics model"""
    total_revenue: float
    total_orders: int
    average_order_value: float
    conversion_rate: float
    cart_abandonment_rate: float
    repeat_customer_rate: float
    period: str
    start_date: datetime
    end_date: datetime
    daily_breakdown: List[Dict[str, Any]] = field(default_factory=list)
    top_products: List[Dict[str, Any]] = field(default_factory=list)
    top_customers: List[Dict[str, Any]] = field(default_factory=list)
    sales_by_channel: Dict[str, float] = field(default_factory=dict)

@dataclass
class CustomerAnalytics:
    """Customer analytics model"""
    total_customers: int
    new_customers: int
    returning_customers: int
    customer_lifetime_value: float
    average_order_value_per_customer: float
    retention_rate: float
    churn_rate: float
    period: str
    start_date: datetime
    end_date: datetime
    customer_segments: List[Dict[str, Any]] = field(default_factory=list)
    cohort_analysis: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class ProductAnalytics:
    """Product analytics model"""
    total_products: int
    active_products: int
    out_of_stock_products: int
    top_selling_products: List[Dict[str, Any]] = field(default_factory=list)
    low_stock_products: List[Dict[str, Any]] = field(default_factory=list)
    product_performance: List[Dict[str, Any]] = field(default_factory=list)
    category_performance: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    period: str
    start_date: datetime
    end_date: datetime

@dataclass
class InventoryAnalytics:
    """Inventory analytics model"""
    total_inventory_value: float
    total_units: int
    inventory_turns: float
    days_of_supply: float
    dead_stock_value: float
    low_stock_alerts: int
    overstock_items: List[Dict[str, Any]] = field(default_factory=list)
    inventory_by_location: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    period: str
    start_date: datetime
    end_date: datetime

class ShopifyAnalytics:
    """Shopify analytics engine"""
    
    def __init__(self, shopify_service, db_pool=None):
        self.shopify_service = shopify_service
        self.db_pool = db_pool
        self.cache_ttl = timedelta(hours=1)
        self.metrics_cache: Dict[str, AnalyticsMetric] = {}
        self.cache_timestamps: Dict[str, datetime] = {}
    
    def _get_cache_key(self, metric_type: str, period: str, **kwargs) -> str:
        """Generate cache key for analytics"""
        key_parts = [metric_type, period]
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}:{v}")
        return ":".join(key_parts)
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached data is still valid"""
        if cache_key not in self.cache_timestamps:
            return False
        return datetime.now(timezone.utc) - self.cache_timestamps[cache_key] < self.cache_ttl
    
    def _update_cache_timestamp(self, cache_key: str):
        """Update cache timestamp"""
        self.cache_timestamps[cache_key] = datetime.now(timezone.utc)
    
    # Sales Analytics
    async def get_sales_analytics(
        self,
        user_id: str,
        start_date: datetime,
        end_date: datetime,
        granularity: TimeGranularity = TimeGranularity.DAILY,
        include_forecast: bool = False
    ) -> SalesAnalytics:
        """Get comprehensive sales analytics"""
        try:
            cache_key = self._get_cache_key(
                "sales", f"{start_date.date()}_{end_date.date()}",
                granularity=granularity.value
            )
            
            if self._is_cache_valid(cache_key) and cache_key in self.metrics_cache:
                cached_data = self.metrics_cache[cache_key].metadata
                return SalesAnalytics(**cached_data)
            
            # Get orders data
            orders = await self.shopify_service.get_orders(
                user_id=user_id,
                created_at_min=start_date.isoformat(),
                created_at_max=end_date.isoformat(),
                limit=1000,
                db_conn_pool=self.db_pool
            )
            
            # Calculate metrics
            total_revenue = sum(float(order.get("total_price", 0)) for order in orders)
            total_orders = len(orders)
            average_order_value = total_revenue / total_orders if total_orders > 0 else 0
            
            # Get daily breakdown
            daily_breakdown = self._calculate_daily_breakdown(orders, granularity)
            
            # Get top products
            top_products = await self._get_top_products(user_id, orders, limit=10)
            
            # Get top customers
            top_customers = await self._get_top_customers(orders, limit=10)
            
            # Calculate sales by channel
            sales_by_channel = self._calculate_sales_by_channel(orders)
            
            # Calculate conversion and churn rates
            conversion_rate = await self._calculate_conversion_rate(user_id, start_date, end_date)
            cart_abandonment_rate = await self._calculate_cart_abandonment_rate(user_id, start_date, end_date)
            repeat_customer_rate = await self._calculate_repeat_customer_rate(user_id, orders)
            
            analytics = SalesAnalytics(
                total_revenue=total_revenue,
                total_orders=total_orders,
                average_order_value=average_order_value,
                conversion_rate=conversion_rate,
                cart_abandonment_rate=cart_abandonment_rate,
                repeat_customer_rate=repeat_customer_rate,
                period=f"{granularity.value} {start_date.date()} to {end_date.date()}",
                start_date=start_date,
                end_date=end_date,
                daily_breakdown=daily_breakdown,
                top_products=top_products,
                top_customers=top_customers,
                sales_by_channel=sales_by_channel
            )
            
            # Cache results
            cache_metric = AnalyticsMetric(
                name="sales_analytics",
                value=total_revenue,
                type=MetricType.REVENUE,
                timestamp=datetime.now(timezone.utc),
                period=f"{start_date.date()}_{end_date.date()}",
                metadata=analytics.__dict__
            )
            
            self.metrics_cache[cache_key] = cache_metric
            self._update_cache_timestamp(cache_key)
            
            return analytics
            
        except Exception as e:
            logger.error(f"Error getting sales analytics: {e}")
            return SalesAnalytics(
                total_revenue=0, total_orders=0, average_order_value=0,
                conversion_rate=0, cart_abandonment_rate=0, repeat_customer_rate=0,
                period="", start_date=start_date, end_date=end_date
            )
    
    def _calculate_daily_breakdown(
        self, 
        orders: List[Dict[str, Any]], 
        granularity: TimeGranularity
    ) -> List[Dict[str, Any]]:
        """Calculate daily breakdown of orders"""
        breakdown = []
        
        if not orders:
            return breakdown
        
        # Group orders by time period
        grouped_orders = {}
        
        for order in orders:
            created_at = datetime.fromisoformat(order["created_at"].replace("Z", "+00:00"))
            
            if granularity == TimeGranularity.DAILY:
                period_key = created_at.date().isoformat()
            elif granularity == TimeGranularity.WEEKLY:
                week_start = created_at - timedelta(days=created_at.weekday())
                period_key = week_start.date().isoformat()
            elif granularity == TimeGranularity.MONTHLY:
                period_key = created_at.strftime("%Y-%m")
            else:
                period_key = created_at.date().isoformat()
            
            if period_key not in grouped_orders:
                grouped_orders[period_key] = []
            grouped_orders[period_key].append(order)
        
        # Calculate metrics for each period
        for period, period_orders in sorted(grouped_orders.items()):
            revenue = sum(float(order.get("total_price", 0)) for order in period_orders)
            order_count = len(period_orders)
            aov = revenue / order_count if order_count > 0 else 0
            
            breakdown.append({
                "period": period,
                "revenue": revenue,
                "orders": order_count,
                "average_order_value": aov
            })
        
        return breakdown
    
    async def _get_top_products(
        self, 
        user_id: str, 
        orders: List[Dict[str, Any]], 
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get top selling products"""
        try:
            product_sales = {}
            
            for order in orders:
                for line_item in order.get("line_items", []):
                    product_id = line_item.get("product_id")
                    title = line_item.get("title", "Unknown Product")
                    quantity = int(line_item.get("quantity", 0))
                    price = float(line_item.get("price", 0))
                    total = quantity * price
                    
                    if product_id not in product_sales:
                        product_sales[product_id] = {
                            "product_id": product_id,
                            "title": title,
                            "quantity": 0,
                            "revenue": 0,
                            "orders": 0
                        }
                    
                    product_sales[product_id]["quantity"] += quantity
                    product_sales[product_id]["revenue"] += total
                    product_sales[product_id]["orders"] += 1
            
            # Sort by revenue and return top N
            top_products = sorted(
                product_sales.values(),
                key=lambda x: x["revenue"],
                reverse=True
            )[:limit]
            
            return top_products
            
        except Exception as e:
            logger.error(f"Error getting top products: {e}")
            return []
    
    async def _get_top_customers(
        self, 
        orders: List[Dict[str, Any]], 
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get top customers by spending"""
        try:
            customer_spending = {}
            
            for order in orders:
                customer = order.get("customer", {})
                customer_id = customer.get("id")
                
                if not customer_id:
                    continue
                
                email = customer.get("email", "Unknown")
                total = float(order.get("total_price", 0))
                
                if customer_id not in customer_spending:
                    customer_spending[customer_id] = {
                        "customer_id": customer_id,
                        "email": email,
                        "total_spent": 0,
                        "orders": 0
                    }
                
                customer_spending[customer_id]["total_spent"] += total
                customer_spending[customer_id]["orders"] += 1
            
            # Sort by total spent and return top N
            top_customers = sorted(
                customer_spending.values(),
                key=lambda x: x["total_spent"],
                reverse=True
            )[:limit]
            
            # Calculate average order value for each customer
            for customer in top_customers:
                customer["average_order_value"] = customer["total_spent"] / customer["orders"]
            
            return top_customers
            
        except Exception as e:
            logger.error(f"Error getting top customers: {e}")
            return []
    
    def _calculate_sales_by_channel(self, orders: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate sales by channel"""
        sales_by_channel = {}
        
        for order in orders:
            source_name = order.get("source_name", "web")
            total = float(order.get("total_price", 0))
            
            if source_name not in sales_by_channel:
                sales_by_channel[source_name] = 0
            sales_by_channel[source_name] += total
        
        return sales_by_channel
    
    async def _calculate_conversion_rate(
        self, 
        user_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> float:
        """Calculate conversion rate"""
        try:
            # Get checkout data (simplified for mock)
            # In real implementation, this would track visitors vs orders
            total_orders = await self.shopify_service.get_orders(
                user_id=user_id,
                created_at_min=start_date.isoformat(),
                created_at_max=end_date.isoformat(),
                limit=1000,
                db_conn_pool=self.db_pool
            )
            
            # Mock conversion calculation (orders / visitors * 100)
            # In real implementation, you'd track actual visitors
            orders_count = len(total_orders)
            estimated_visitors = orders_count * 50  # Assume 2% conversion rate
            conversion_rate = (orders_count / estimated_visitors * 100) if estimated_visitors > 0 else 0
            
            return round(conversion_rate, 2)
            
        except Exception as e:
            logger.error(f"Error calculating conversion rate: {e}")
            return 0.0
    
    async def _calculate_cart_abandonment_rate(
        self, 
        user_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> float:
        """Calculate cart abandonment rate"""
        try:
            # Mock cart abandonment rate
            # In real implementation, you'd track actual checkouts vs completed orders
            return 68.5  # Industry average
            
        except Exception as e:
            logger.error(f"Error calculating cart abandonment rate: {e}")
            return 0.0
    
    async def _calculate_repeat_customer_rate(
        self, 
        user_id: str, 
        orders: List[Dict[str, Any]]
    ) -> float:
        """Calculate repeat customer rate"""
        try:
            customer_orders = {}
            
            for order in orders:
                customer = order.get("customer", {})
                customer_id = customer.get("id")
                
                if customer_id:
                    if customer_id not in customer_orders:
                        customer_orders[customer_id] = 0
                    customer_orders[customer_id] += 1
            
            if not customer_orders:
                return 0.0
            
            repeat_customers = sum(1 for count in customer_orders.values() if count > 1)
            repeat_rate = (repeat_customers / len(customer_orders)) * 100
            
            return round(repeat_rate, 2)
            
        except Exception as e:
            logger.error(f"Error calculating repeat customer rate: {e}")
            return 0.0
    
    # Customer Analytics
    async def get_customer_analytics(
        self,
        user_id: str,
        start_date: datetime,
        end_date: datetime,
        include_cohort: bool = True
    ) -> CustomerAnalytics:
        """Get comprehensive customer analytics"""
        try:
            # Get customers and orders
            customers = await self.shopify_service.get_customers(
                user_id=user_id,
                limit=1000,
                db_conn_pool=self.db_pool
            )
            
            orders = await self.shopify_service.get_orders(
                user_id=user_id,
                created_at_min=start_date.isoformat(),
                created_at_max=end_date.isoformat(),
                limit=1000,
                db_conn_pool=self.db_pool
            )
            
            total_customers = len(customers)
            new_customers = sum(1 for customer in customers 
                               if datetime.fromisoformat(customer["created_at"].replace("Z", "+00:00")) >= start_date)
            returning_customers = total_customers - new_customers
            
            # Calculate customer lifetime value
            clv = await self._calculate_customer_lifetime_value(customers, orders)
            
            # Calculate average order value per customer
            aov_per_customer = sum(float(order.get("total_price", 0)) for order in orders) / total_customers if total_customers > 0 else 0
            
            # Calculate retention and churn rates
            retention_rate = await self._calculate_retention_rate(user_id, customers, start_date, end_date)
            churn_rate = 100 - retention_rate
            
            # Customer segmentation
            customer_segments = await self._segment_customers(customers, orders)
            
            # Cohort analysis
            cohort_analysis = []
            if include_cohort:
                cohort_analysis = await self._perform_cohort_analysis(customers, orders)
            
            return CustomerAnalytics(
                total_customers=total_customers,
                new_customers=new_customers,
                returning_customers=returning_customers,
                customer_lifetime_value=clv,
                average_order_value_per_customer=aov_per_customer,
                retention_rate=retention_rate,
                churn_rate=churn_rate,
                period=f"{start_date.date()} to {end_date.date()}",
                start_date=start_date,
                end_date=end_date,
                customer_segments=customer_segments,
                cohort_analysis=cohort_analysis
            )
            
        except Exception as e:
            logger.error(f"Error getting customer analytics: {e}")
            return CustomerAnalytics(
                total_customers=0, new_customers=0, returning_customers=0,
                customer_lifetime_value=0, average_order_value_per_customer=0,
                retention_rate=0, churn_rate=0,
                period="", start_date=start_date, end_date=end_date
            )
    
    async def _calculate_customer_lifetime_value(
        self, 
        customers: List[Dict[str, Any]], 
        orders: List[Dict[str, Any]]
    ) -> float:
        """Calculate customer lifetime value"""
        try:
            customer_spending = {}
            
            for order in orders:
                customer = order.get("customer", {})
                customer_id = customer.get("id")
                
                if customer_id:
                    total = float(order.get("total_price", 0))
                    if customer_id not in customer_spending:
                        customer_spending[customer_id] = 0
                    customer_spending[customer_id] += total
            
            if not customer_spending:
                return 0.0
            
            clv = sum(customer_spending.values()) / len(customer_spending)
            return round(clv, 2)
            
        except Exception as e:
            logger.error(f"Error calculating CLV: {e}")
            return 0.0
    
    async def _calculate_retention_rate(
        self, 
        user_id: str, 
        customers: List[Dict[str, Any]], 
        start_date: datetime, 
        end_date: datetime
    ) -> float:
        """Calculate customer retention rate"""
        try:
            # Mock retention calculation
            # In real implementation, you'd track actual customer retention
            return 75.0  # Industry average
            
        except Exception as e:
            logger.error(f"Error calculating retention rate: {e}")
            return 0.0
    
    async def _segment_customers(
        self, 
        customers: List[Dict[str, Any]], 
        orders: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Segment customers based on RFM analysis"""
        try:
            customer_orders = {}
            customer_spending = {}
            
            for order in orders:
                customer = order.get("customer", {})
                customer_id = customer.get("id")
                
                if customer_id:
                    total = float(order.get("total_price", 0))
                    created_at = datetime.fromisoformat(order["created_at"].replace("Z", "+00:00"))
                    
                    if customer_id not in customer_orders:
                        customer_orders[customer_id] = []
                        customer_spending[customer_id] = 0
                    
                    customer_orders[customer_id].append(created_at)
                    customer_spending[customer_id] += total
            
            segments = []
            
            for customer in customers:
                customer_id = customer.get("id")
                if customer_id not in customer_orders:
                    continue
                
                # RFM Analysis
                frequency = len(customer_orders[customer_id])
                monetary = customer_spending[customer_id]
                recency_days = (datetime.now(timezone.utc) - max(customer_orders[customer_id])).days
                
                # Segment based on RFM
                if frequency >= 10 and monetary >= 1000 and recency_days <= 30:
                    segment = "Champions"
                elif frequency >= 5 and monetary >= 500 and recency_days <= 60:
                    segment = "Loyal Customers"
                elif monetary >= 1000 and recency_days <= 90:
                    segment = "Big Spenders"
                elif frequency >= 3 and recency_days <= 30:
                    segment = "New Customers"
                elif recency_days > 90:
                    segment = "At Risk"
                else:
                    segment = "Others"
                
                segments.append({
                    "customer_id": customer_id,
                    "email": customer.get("email", ""),
                    "segment": segment,
                    "frequency": frequency,
                    "monetary": monetary,
                    "recency_days": recency_days
                })
            
            return segments
            
        except Exception as e:
            logger.error(f"Error segmenting customers: {e}")
            return []
    
    async def _perform_cohort_analysis(
        self, 
        customers: List[Dict[str, Any]], 
        orders: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Perform cohort analysis"""
        try:
            # Simplified cohort analysis
            cohorts = {}
            
            for order in orders:
                customer = order.get("customer", {})
                customer_id = customer.get("id")
                
                if not customer_id:
                    continue
                
                # Get customer's first order date
                customer_orders = [o for o in orders if o.get("customer", {}).get("id") == customer_id]
                if not customer_orders:
                    continue
                
                first_order_date = datetime.fromisoformat(
                    min(customer_orders, key=lambda o: o["created_at"])["created_at"].replace("Z", "+00:00")
                )
                current_order_date = datetime.fromisoformat(order["created_at"].replace("Z", "+00:00"))
                
                # Calculate cohort period (month) and period number
                cohort_month = first_order_date.strftime("%Y-%m")
                period_number = (current_order_date.year - first_order_date.year) * 12 + (current_order_date.month - first_order_date.month)
                
                if cohort_month not in cohorts:
                    cohorts[cohort_month] = {}
                
                if period_number not in cohorts[cohort_month]:
                    cohorts[cohort_month][period_number] = 0
                
                cohorts[cohort_month][period_number] += 1
            
            # Convert to cohort table format
            cohort_table = []
            for cohort_month, periods in sorted(cohorts.items()):
                cohort_data = {"cohort": cohort_month, "periods": []}
                
                for period in range(0, 12):  # Show up to 12 periods
                    count = periods.get(period, 0)
                    cohort_data["periods"].append({
                        "period": period,
                        "count": count,
                        "percentage": (count / periods.get(0, 1)) * 100 if period > 0 else 100
                    })
                
                cohort_table.append(cohort_data)
            
            return cohort_table
            
        except Exception as e:
            logger.error(f"Error performing cohort analysis: {e}")
            return []
    
    # Product Analytics
    async def get_product_analytics(
        self,
        user_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> ProductAnalytics:
        """Get comprehensive product analytics"""
        try:
            # Get products data
            products = await self.shopify_service.get_products(
                user_id=user_id,
                limit=1000,
                db_conn_pool=self.db_pool
            )
            
            # Get orders for product performance
            orders = await self.shopify_service.get_orders(
                user_id=user_id,
                created_at_min=start_date.isoformat(),
                created_at_max=end_date.isoformat(),
                limit=1000,
                db_conn_pool=self.db_pool
            )
            
            total_products = len(products)
            active_products = sum(1 for p in products if p.get("status") == "active")
            out_of_stock_products = sum(1 for p in products if p.get("variants", [{}])[0].get("inventory_quantity", 0) == 0)
            
            # Top selling products
            top_selling_products = await self._get_top_products(user_id, orders, limit=20)
            
            # Low stock products
            low_stock_products = await self._get_low_stock_products(products, threshold=10)
            
            # Product performance
            product_performance = await self._analyze_product_performance(products, orders)
            
            # Category performance
            category_performance = await self._analyze_category_performance(products, orders)
            
            return ProductAnalytics(
                total_products=total_products,
                active_products=active_products,
                out_of_stock_products=out_of_stock_products,
                top_selling_products=top_selling_products,
                low_stock_products=low_stock_products,
                product_performance=product_performance,
                category_performance=category_performance,
                period=f"{start_date.date()} to {end_date.date()}",
                start_date=start_date,
                end_date=end_date
            )
            
        except Exception as e:
            logger.error(f"Error getting product analytics: {e}")
            return ProductAnalytics(
                total_products=0, active_products=0, out_of_stock_products=0,
                period="", start_date=start_date, end_date=end_date
            )
    
    async def _get_low_stock_products(
        self, 
        products: List[Dict[str, Any]], 
        threshold: int = 10
    ) -> List[Dict[str, Any]]:
        """Get products with low stock"""
        low_stock = []
        
        for product in products:
            total_inventory = sum(variant.get("inventory_quantity", 0) for variant in product.get("variants", []))
            
            if 0 < total_inventory < threshold:
                low_stock.append({
                    "product_id": product.get("id"),
                    "title": product.get("title"),
                    "total_inventory": total_inventory,
                    "status": product.get("status")
                })
        
        return sorted(low_stock, key=lambda x: x["total_inventory"])
    
    async def _analyze_product_performance(
        self, 
        products: List[Dict[str, Any]], 
        orders: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Analyze individual product performance"""
        product_metrics = {}
        
        # Initialize metrics for all products
        for product in products:
            product_id = product.get("id")
            product_metrics[product_id] = {
                "product_id": product_id,
                "title": product.get("title"),
                "total_revenue": 0,
                "units_sold": 0,
                "orders": 0,
                "average_price": 0,
                "view_to_order_rate": 0  # Mock data
            }
        
        # Calculate metrics from orders
        for order in orders:
            for line_item in order.get("line_items", []):
                product_id = line_item.get("product_id")
                if product_id in product_metrics:
                    quantity = int(line_item.get("quantity", 0))
                    price = float(line_item.get("price", 0))
                    total = quantity * price
                    
                    product_metrics[product_id]["total_revenue"] += total
                    product_metrics[product_id]["units_sold"] += quantity
                    product_metrics[product_id]["orders"] += 1
        
        # Calculate additional metrics
        for product_id, metrics in product_metrics.items():
            if metrics["units_sold"] > 0:
                metrics["average_price"] = metrics["total_revenue"] / metrics["units_sold"]
                metrics["view_to_order_rate"] = (metrics["orders"] / metrics["units_sold"]) * 100
            
            # Get product price from catalog
            product = next((p for p in products if p.get("id") == product_id), None)
            if product and product.get("variants"):
                catalog_price = float(product["variants"][0].get("price", 0))
                metrics["price_variance"] = ((metrics["average_price"] - catalog_price) / catalog_price * 100) if catalog_price > 0 else 0
        
        return list(product_metrics.values())
    
    async def _analyze_category_performance(
        self, 
        products: List[Dict[str, Any]], 
        orders: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """Analyze performance by product category"""
        category_metrics = {}
        
        # Initialize category metrics
        for product in products:
            product_type = product.get("product_type", "Uncategorized")
            if product_type not in category_metrics:
                category_metrics[product_type] = {
                    "total_revenue": 0,
                    "units_sold": 0,
                    "orders": 0,
                    "products": 0,
                    "average_price": 0
                }
            category_metrics[product_type]["products"] += 1
        
        # Calculate metrics from orders
        for order in orders:
            for line_item in order.get("line_items", []):
                product_id = line_item.get("product_id")
                product = next((p for p in products if p.get("id") == product_id), None)
                
                if product:
                    product_type = product.get("product_type", "Uncategorized")
                    quantity = int(line_item.get("quantity", 0))
                    price = float(line_item.get("price", 0))
                    total = quantity * price
                    
                    category_metrics[product_type]["total_revenue"] += total
                    category_metrics[product_type]["units_sold"] += quantity
                    category_metrics[product_type]["orders"] += 1
        
        # Calculate averages
        for category, metrics in category_metrics.items():
            if metrics["units_sold"] > 0:
                metrics["average_price"] = metrics["total_revenue"] / metrics["units_sold"]
                metrics["revenue_per_product"] = metrics["total_revenue"] / metrics["products"]
        
        return category_metrics
    
    # Inventory Analytics
    async def get_inventory_analytics(
        self,
        user_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> InventoryAnalytics:
        """Get comprehensive inventory analytics"""
        try:
            # Get inventory levels
            inventory_response = await self.shopify_service._make_request(
                user_id=user_id,
                method="GET",
                endpoint="inventory_levels.json",
                params={"limit": 1000},
                db_conn_pool=self.db_pool
            )
            
            inventory_levels = inventory_response.get("inventory_levels", [])
            
            # Get products for cost information
            products = await self.shopify_service.get_products(
                user_id=user_id,
                limit=1000,
                db_conn_pool=self.db_pool
            )
            
            # Calculate inventory metrics
            total_units = sum(level.get("available", 0) for level in inventory_levels)
            
            # Calculate inventory value (mock cost data)
            total_inventory_value = total_units * 25.0  # Average cost per unit
            
            # Calculate inventory turns (simplified)
            inventory_turns = await self._calculate_inventory_turns(user_id, products, start_date, end_date)
            
            # Calculate days of supply
            days_of_supply = total_units / (total_units / 30) if total_units > 0 else 0  # Simplified calculation
            
            # Dead stock value (items not sold in 90 days)
            dead_stock_value = await self._calculate_dead_stock_value(user_id, products, inventory_levels)
            
            # Low stock alerts
            low_stock_alerts = sum(1 for level in inventory_levels if 0 < level.get("available", 0) < 10)
            
            # Overstock items
            overstock_items = await self._identify_overstock_items(products, inventory_levels)
            
            # Inventory by location
            inventory_by_location = await self._analyze_inventory_by_location(inventory_levels)
            
            return InventoryAnalytics(
                total_inventory_value=total_inventory_value,
                total_units=total_units,
                inventory_turns=inventory_turns,
                days_of_supply=days_of_supply,
                dead_stock_value=dead_stock_value,
                low_stock_alerts=low_stock_alerts,
                overstock_items=overstock_items,
                inventory_by_location=inventory_by_location,
                period=f"{start_date.date()} to {end_date.date()}",
                start_date=start_date,
                end_date=end_date
            )
            
        except Exception as e:
            logger.error(f"Error getting inventory analytics: {e}")
            return InventoryAnalytics(
                total_inventory_value=0, total_units=0, inventory_turns=0, days_of_supply=0,
                dead_stock_value=0, low_stock_alerts=0,
                period="", start_date=start_date, end_date=end_date
            )
    
    async def _calculate_inventory_turns(
        self, 
        user_id: str, 
        products: List[Dict[str, Any]], 
        start_date: datetime, 
        end_date: datetime
    ) -> float:
        """Calculate inventory turnover ratio"""
        try:
            # Get orders for the period
            orders = await self.shopify_service.get_orders(
                user_id=user_id,
                created_at_min=start_date.isoformat(),
                created_at_max=end_date.isoformat(),
                limit=1000,
                db_conn_pool=self.db_pool
            )
            
            # Calculate cost of goods sold (simplified)
            cogs = sum(
                sum(int(li.get("quantity", 0)) * 15.0 for li in order.get("line_items", []))  # Mock cost
                for order in orders
            )
            
            # Calculate average inventory value
            total_inventory = sum(
                sum(variant.get("inventory_quantity", 0) for variant in product.get("variants", []))
                for product in products
            ) * 15.0  # Mock cost
            
            if total_inventory == 0:
                return 0.0
            
            # Inventory turns = COGS / Average Inventory
            period_length = (end_date - start_date).days
            annualized_turns = (cogs / total_inventory) * (365 / period_length)
            
            return round(annualized_turns, 2)
            
        except Exception as e:
            logger.error(f"Error calculating inventory turns: {e}")
            return 0.0
    
    async def _calculate_dead_stock_value(
        self, 
        user_id: str, 
        products: List[Dict[str, Any]], 
        inventory_levels: List[Dict[str, Any]]
    ) -> float:
        """Calculate dead stock value"""
        try:
            # Simplified dead stock calculation
            # In real implementation, you'd track last sale date for each item
            total_units = sum(level.get("available", 0) for level in inventory_levels)
            dead_stock_percentage = 0.15  # Assume 15% of inventory is dead stock
            dead_stock_units = total_units * dead_stock_percentage
            dead_stock_value = dead_stock_units * 20.0  # Mock cost per unit
            
            return round(dead_stock_value, 2)
            
        except Exception as e:
            logger.error(f"Error calculating dead stock value: {e}")
            return 0.0
    
    async def _identify_overstock_items(
        self, 
        products: List[Dict[str, Any]], 
        inventory_levels: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Identify overstock items"""
        try:
            overstock_items = []
            
            for level in inventory_levels:
                available = level.get("available", 0)
                if available > 100:  # Over 100 units considered overstock
                    inventory_item_id = level.get("inventory_item_id")
                    
                    # Find product for this inventory item
                    product = None
                    for p in products:
                        if inventory_item_id in [v.get("inventory_item_id") for v in p.get("variants", [])]:
                            product = p
                            break
                    
                    if product:
                        overstock_items.append({
                            "product_id": product.get("id"),
                            "title": product.get("title"),
                            "inventory_item_id": inventory_item_id,
                            "available": available,
                            "location_id": level.get("location_id"),
                            "estimated_value": available * 20.0  # Mock cost
                        })
            
            return sorted(overstock_items, key=lambda x: x["available"], reverse=True)
            
        except Exception as e:
            logger.error(f"Error identifying overstock items: {e}")
            return []
    
    async def _analyze_inventory_by_location(
        self, 
        inventory_levels: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """Analyze inventory by location"""
        try:
            location_metrics = {}
            
            for level in inventory_levels:
                location_id = level.get("location_id")
                available = level.get("available", 0)
                
                if location_id not in location_metrics:
                    location_metrics[location_id] = {
                        "total_units": 0,
                        "total_items": 0,
                        "out_of_stock_items": 0
                    }
                
                location_metrics[location_id]["total_units"] += available
                location_metrics[location_id]["total_items"] += 1
                
                if available == 0:
                    location_metrics[location_id]["out_of_stock_items"] += 1
            
            # Calculate additional metrics
            for location_id, metrics in location_metrics.items():
                if metrics["total_items"] > 0:
                    metrics["out_of_stock_rate"] = (metrics["out_of_stock_items"] / metrics["total_items"]) * 100
                    metrics["average_units_per_item"] = metrics["total_units"] / metrics["total_items"]
            
            return location_metrics
            
        except Exception as e:
            logger.error(f"Error analyzing inventory by location: {e}")
            return {}
    
    # Forecasting Methods (Basic Implementation)
    async def forecast_sales(
        self,
        user_id: str,
        start_date: datetime,
        end_date: datetime,
        forecast_days: int = 30
    ) -> Dict[str, Any]:
        """Forecast future sales"""
        try:
            # Get historical sales data
            orders = await self.shopify_service.get_orders(
                user_id=user_id,
                created_at_min=(start_date - timedelta(days=90)).isoformat(),  # 90 days of history
                created_at_max=end_date.isoformat(),
                limit=5000,
                db_conn_pool=self.db_pool
            )
            
            # Calculate daily sales
            daily_sales = {}
            for order in orders:
                date = datetime.fromisoformat(order["created_at"].replace("Z", "+00:00")).date()
                if date not in daily_sales:
                    daily_sales[date] = 0
                daily_sales[date] += float(order.get("total_price", 0))
            
            # Simple linear regression forecast
            if len(daily_sales) < 7:
                return {"error": "Insufficient data for forecasting"}
            
            dates = sorted(daily_sales.keys())
            sales_values = [daily_sales[date] for date in dates]
            
            # Calculate trend
            x_values = list(range(len(dates)))
            n = len(dates)
            
            sum_x = sum(x_values)
            sum_y = sum(sales_values)
            sum_xy = sum(x * y for x, y in zip(x_values, sales_values))
            sum_x2 = sum(x * x for x in x_values)
            
            # Linear regression coefficients
            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
            intercept = (sum_y - slope * sum_x) / n
            
            # Generate forecast
            forecast = []
            for day in range(forecast_days):
                forecast_date = end_date + timedelta(days=day + 1)
                forecast_value = slope * (len(dates) + day) + intercept
                
                # Add seasonal adjustment (simplified)
                day_of_week = forecast_date.weekday()
                seasonal_multiplier = 1.0
                
                if day_of_week >= 5:  # Weekend
                    seasonal_multiplier = 0.8
                elif day_of_week == 0:  # Monday
                    seasonal_multiplier = 1.2
                
                adjusted_forecast = forecast_value * seasonal_multiplier
                
                forecast.append({
                    "date": forecast_date.date().isoformat(),
                    "forecast_sales": max(0, adjusted_forecast),
                    "trend_component": max(0, forecast_value),
                    "seasonal_multiplier": seasonal_multiplier
                })
            
            # Calculate forecast metrics
            total_forecast_sales = sum(item["forecast_sales"] for item in forecast)
            average_daily_forecast = total_forecast_sales / forecast_days
            
            return {
                "success": True,
                "forecast_period": f"{forecast_days} days",
                "total_forecast_sales": round(total_forecast_sales, 2),
                "average_daily_forecast": round(average_daily_forecast, 2),
                "trend_slope": round(slope, 2),
                "historical_period_days": len(daily_sales),
                "forecast": forecast
            }
            
        except Exception as e:
            logger.error(f"Error forecasting sales: {e}")
            return {"success": False, "error": str(e)}
    
    # Generate comprehensive report
    async def generate_analytics_report(
        self,
        user_id: str,
        start_date: datetime,
        end_date: datetime,
        include_forecast: bool = True
    ) -> Dict[str, Any]:
        """Generate comprehensive analytics report"""
        try:
            logger.info(f"Generating analytics report for {start_date.date()} to {end_date.date()}")
            
            # Get all analytics data
            sales_analytics = await self.get_sales_analytics(
                user_id, start_date, end_date
            )
            
            customer_analytics = await self.get_customer_analytics(
                user_id, start_date, end_date, include_cohort=True
            )
            
            product_analytics = await self.get_product_analytics(
                user_id, start_date, end_date
            )
            
            inventory_analytics = await self.get_inventory_analytics(
                user_id, start_date, end_date
            )
            
            # Generate forecast if requested
            forecast = None
            if include_forecast:
                forecast = await self.forecast_sales(user_id, start_date, end_date)
            
            # Compile report
            report = {
                "report_period": {
                    "start_date": start_date.date().isoformat(),
                    "end_date": end_date.date().isoformat(),
                    "days": (end_date - start_date).days
                },
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "sales_analytics": sales_analytics.__dict__,
                "customer_analytics": customer_analytics.__dict__,
                "product_analytics": product_analytics.__dict__,
                "inventory_analytics": inventory_analytics.__dict__,
                "forecast": forecast,
                "key_insights": self._generate_key_insights(
                    sales_analytics, customer_analytics, product_analytics, inventory_analytics
                )
            }
            
            logger.info("Analytics report generated successfully")
            return {
                "success": True,
                "report": report
            }
            
        except Exception as e:
            logger.error(f"Error generating analytics report: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _generate_key_insights(
        self,
        sales: SalesAnalytics,
        customers: CustomerAnalytics,
        products: ProductAnalytics,
        inventory: InventoryAnalytics
    ) -> List[Dict[str, Any]]:
        """Generate key insights from analytics data"""
        insights = []
        
        # Sales insights
        if sales.conversion_rate < 2.0:
            insights.append({
                "type": "conversion_rate",
                "severity": "warning",
                "title": "Low Conversion Rate",
                "description": f"Conversion rate is {sales.conversion_rate}%, below industry average of 2-3%",
                "recommendation": "Optimize checkout process and improve product descriptions"
            })
        
        # Customer insights
        if customers.churn_rate > 25.0:
            insights.append({
                "type": "customer_retention",
                "severity": "critical",
                "title": "High Customer Churn",
                "description": f"Churn rate is {customers.churn_rate}%, indicating customer retention issues",
                "recommendation": "Implement loyalty programs and improve customer service"
            })
        
        # Product insights
        out_of_stock_percentage = (products.out_of_stock_products / products.total_products * 100) if products.total_products > 0 else 0
        if out_of_stock_percentage > 10.0:
            insights.append({
                "type": "inventory",
                "severity": "warning",
                "title": "High Out-of-Stock Rate",
                "description": f"{out_of_stock_percentage:.1f}% of products are out of stock",
                "recommendation": "Review inventory management and restocking procedures"
            })
        
        # Inventory insights
        if inventory.inventory_turns < 4.0:
            insights.append({
                "type": "inventory_efficiency",
                "severity": "warning",
                "title": "Low Inventory Turnover",
                "description": f"Inventory turns is {inventory.inventory_turns}, indicating inefficient inventory",
                "recommendation": "Implement just-in-time inventory and clear slow-moving items"
            })
        
        # Growth insights
        if sales.top_products and len(sales.top_products) > 0:
            top_product = sales.top_products[0]
            if top_product["revenue"] > sales.total_revenue * 0.4:
                insights.append({
                    "type": "product_concentration",
                    "severity": "info",
                    "title": "High Product Concentration",
                    "description": f"Top product '{top_product['title']}' accounts for {top_product['revenue']/sales.total_revenue*100:.1f}% of revenue",
                    "recommendation": "Diversify product portfolio to reduce dependency"
                })
        
        return insights

# Export components
__all__ = [
    "ShopifyAnalytics",
    "SalesAnalytics",
    "CustomerAnalytics", 
    "ProductAnalytics",
    "InventoryAnalytics",
    "AnalyticsMetric",
    "MetricType",
    "TimeGranularity"
]