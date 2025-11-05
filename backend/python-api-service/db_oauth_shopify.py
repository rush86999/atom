"""
Shopify Enhanced Database Integration
Complete Shopify e-commerce database schema and operations
"""

import asyncpg
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logger = logging.getLogger('shopify_db')
logger.setLevel(logging.INFO)

# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://atom_user:atom_password@localhost:5432/atom_db')

# Shopify data models
@dataclass
class ShopifyToken:
    access_token: str
    token_type: str
    scope: str
    domain: str
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None
    created_at: Optional[str] = None
    user_info: Optional[Dict[str, Any]] = None

@dataclass
class ShopifyProduct:
    id: int
    title: str
    body_html: str
    vendor: str
    product_type: str
    created_at: str
    handle: str
    updated_at: str
    published_at: Optional[str]
    template_suffix: Optional[str]
    status: str
    published_scope: str
    tags: str
    admin_graphql_api_id: str
    options: List[Dict[str, Any]]
    images: List[Dict[str, Any]]
    image: Optional[Dict[str, Any]]
    variants: List[Dict[str, Any]]
    metafields: List[Dict[str, Any]]
    user_id: str
    sync_at: datetime
    shop_domain: str

@dataclass
class ShopifyOrder:
    id: int
    admin_graphql_api_id: str
    app_id: Optional[int]
    browser_ip: str
    buyer_accepts_marketing: bool
    cancel_reason: Optional[str]
    cancelled_at: Optional[str]
    cart_token: Optional[str]
    checkout_id: Optional[int]
    checkout_token: str
    client_details: Dict[str, Any]
    closed_at: Optional[str]
    confirmed: bool
    contact_email: str
    created_at: str
    currency: str
    current_subtotal_price: str
    current_total_price: str
    current_total_tax: str
    customer_locale: str
    device_id: Optional[int]
    discount_codes: List[Dict[str, Any]]
    email: str
    estimated_taxes: bool
    financial_status: str
    fulfillment_status: Optional[str]
    gateway: str
    landing_site: str
    name: str
    note: Optional[str]
    note_attributes: List[Dict[str, Any]]
    number: int
    order_number: int
    order_status_url: str
    payment_gateway_names: List[str]
    phone: str
    presentment_currency: str
    processed_at: Optional[str]
    processing_method: str
    reference: Optional[str]
    referring_site: str
    source_identifier: Optional[str]
    source_name: str
    source_url: Optional[str]
    subtotal_price: str
    tags: str
    tax_lines: List[Dict[str, Any]]
    taxes_included: bool
    test: bool
    token: str
    total_discounts: str
    total_line_items_price: str
    total_outstanding: str
    total_price: str
    total_tax: str
    total_tip_received: str
    total_weight: int
    updated_at: str
    user_id: Optional[int]
    billing_address: Optional[Dict[str, Any]]
    customer: Optional[Dict[str, Any]]
    discount_applications: List[Dict[str, Any]]
    fulfillments: List[Dict[str, Any]]
    line_items: List[Dict[str, Any]]
    payment_details: Optional[Dict[str, Any]]
    refunds: List[Dict[str, Any]]
    shipping_address: Optional[Dict[str, Any]]
    shipping_lines: List[Dict[str, Any]]
    shop_domain: str
    sync_at: datetime

@dataclass
class ShopifyCustomer:
    id: int
    email: str
    created_at: str
    updated_at: str
    first_name: str
    last_name: str
    state: str
    note: Optional[str]
    verified_email: bool
    multipass_identifier: Optional[str]
    tax_exempt: bool
    tags: str
    last_order_id: Optional[int]
    last_order_name: Optional[str]
    currency: str
    total_spent: str
    phone: Optional[str]
    addresses: List[Dict[str, Any]]
    accepts_marketing: bool
    accepts_marketing_updated_at: str
    marketing_opt_in_level: str
    tax_exemptions: List[Dict[str, Any]]
    sms_marketing_consent: Optional[Dict[str, Any]]
    admin_graphql_api_id: str
    user_id: str
    sync_at: datetime
    shop_domain: str

class ShopifyDBManager:
    """Enhanced Shopify Database Manager"""
    
    def __init__(self, connection_string: str = DATABASE_URL):
        self.connection_string = connection_string
        self._pool = None
    
    @asynccontextmanager
    async def get_connection(self):
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                self.connection_string,
                min_size=5,
                max_size=20,
                command_timeout=60
            )
        
        async with self._pool.acquire() as connection:
            yield connection
    
    async def create_tables(self) -> None:
        """Create Shopify database tables"""
        
        # Shopify tokens table
        tokens_sql = """
        CREATE TABLE IF NOT EXISTS shopify_tokens (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(255) NOT NULL,
            access_token TEXT NOT NULL,
            token_type VARCHAR(50) DEFAULT 'Bearer',
            scope TEXT NOT NULL,
            domain VARCHAR(255) NOT NULL,
            refresh_token TEXT,
            expires_in INTEGER,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            user_info JSONB,
            UNIQUE(user_id, domain)
        );
        """
        
        # Shopify products table
        products_sql = """
        CREATE TABLE IF NOT EXISTS shopify_products (
            id BIGINT PRIMARY KEY,
            title TEXT NOT NULL,
            body_html TEXT,
            vendor TEXT,
            product_type TEXT,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL,
            handle TEXT NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
            published_at TIMESTAMP WITH TIME ZONE,
            template_suffix TEXT,
            status VARCHAR(50) DEFAULT 'active',
            published_scope VARCHAR(50) DEFAULT 'global',
            tags TEXT,
            admin_graphql_api_id TEXT UNIQUE,
            options JSONB NOT NULL DEFAULT '[]',
            images JSONB NOT NULL DEFAULT '[]',
            image JSONB,
            variants JSONB NOT NULL DEFAULT '[]',
            metafields JSONB NOT NULL DEFAULT '[]',
            user_id VARCHAR(255) NOT NULL,
            shop_domain VARCHAR(255) NOT NULL,
            sync_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            INDEX(user_id),
            INDEX(shop_domain),
            INDEX(status),
            INDEX(product_type),
            INDEX(vendor),
            INDEX(created_at),
            INDEX(updated_at)
        );
        """
        
        # Shopify orders table
        orders_sql = """
        CREATE TABLE IF NOT EXISTS shopify_orders (
            id BIGINT PRIMARY KEY,
            admin_graphql_api_id TEXT UNIQUE,
            app_id INTEGER,
            browser_ip TEXT,
            buyer_accepts_marketing BOOLEAN DEFAULT FALSE,
            cancel_reason TEXT,
            cancelled_at TIMESTAMP WITH TIME ZONE,
            cart_token TEXT,
            checkout_id INTEGER,
            checkout_token TEXT,
            client_details JSONB NOT NULL DEFAULT '{}',
            closed_at TIMESTAMP WITH TIME ZONE,
            confirmed BOOLEAN DEFAULT FALSE,
            contact_email TEXT,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL,
            currency VARCHAR(10) NOT NULL,
            current_subtotal_price DECIMAL(10,2) DEFAULT 0,
            current_total_price DECIMAL(10,2) DEFAULT 0,
            current_total_tax DECIMAL(10,2) DEFAULT 0,
            customer_locale TEXT,
            device_id INTEGER,
            discount_codes JSONB NOT NULL DEFAULT '[]',
            email TEXT,
            estimated_taxes BOOLEAN DEFAULT FALSE,
            financial_status VARCHAR(50) DEFAULT 'pending',
            fulfillment_status VARCHAR(50),
            gateway TEXT,
            landing_site TEXT,
            name TEXT NOT NULL,
            note TEXT,
            note_attributes JSONB NOT NULL DEFAULT '[]',
            number INTEGER,
            order_number INTEGER NOT NULL,
            order_status_url TEXT,
            payment_gateway_names JSONB NOT NULL DEFAULT '[]',
            phone TEXT,
            presentment_currency VARCHAR(10),
            processed_at TIMESTAMP WITH TIME ZONE,
            processing_method VARCHAR(50),
            reference TEXT,
            referring_site TEXT,
            source_identifier TEXT,
            source_name TEXT,
            source_url TEXT,
            subtotal_price DECIMAL(10,2) DEFAULT 0,
            tags TEXT,
            tax_lines JSONB NOT NULL DEFAULT '[]',
            taxes_included BOOLEAN DEFAULT FALSE,
            test BOOLEAN DEFAULT FALSE,
            token TEXT,
            total_discounts DECIMAL(10,2) DEFAULT 0,
            total_line_items_price DECIMAL(10,2) DEFAULT 0,
            total_outstanding DECIMAL(10,2) DEFAULT 0,
            total_price DECIMAL(10,2) DEFAULT 0,
            total_tax DECIMAL(10,2) DEFAULT 0,
            total_tip_received DECIMAL(10,2) DEFAULT 0,
            total_weight INTEGER,
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
            user_id INTEGER,
            billing_address JSONB,
            customer JSONB,
            discount_applications JSONB NOT NULL DEFAULT '[]',
            fulfillments JSONB NOT NULL DEFAULT '[]',
            line_items JSONB NOT NULL DEFAULT '[]',
            payment_details JSONB,
            refunds JSONB NOT NULL DEFAULT '[]',
            shipping_address JSONB,
            shipping_lines JSONB NOT NULL DEFAULT '[]',
            shop_domain VARCHAR(255) NOT NULL,
            sync_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            INDEX(user_id),
            INDEX(shop_domain),
            INDEX(financial_status),
            INDEX(fulfillment_status),
            INDEX(email),
            INDEX(created_at),
            INDEX(updated_at),
            INDEX(order_number)
        );
        """
        
        # Shopify customers table
        customers_sql = """
        CREATE TABLE IF NOT EXISTS shopify_customers (
            id BIGINT PRIMARY KEY,
            email TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
            first_name TEXT,
            last_name TEXT,
            state VARCHAR(50) DEFAULT 'enabled',
            note TEXT,
            verified_email BOOLEAN DEFAULT TRUE,
            multipass_identifier TEXT,
            tax_exempt BOOLEAN DEFAULT FALSE,
            tags TEXT,
            last_order_id INTEGER,
            last_order_name TEXT,
            currency VARCHAR(10) DEFAULT 'USD',
            total_spent DECIMAL(10,2) DEFAULT 0,
            phone TEXT,
            addresses JSONB NOT NULL DEFAULT '[]',
            accepts_marketing BOOLEAN DEFAULT FALSE,
            accepts_marketing_updated_at TIMESTAMP WITH TIME ZONE,
            marketing_opt_in_level VARCHAR(50) DEFAULT 'single_opt_in',
            tax_exemptions JSONB NOT NULL DEFAULT '[]',
            sms_marketing_consent JSONB,
            admin_graphql_api_id TEXT UNIQUE,
            user_id VARCHAR(255) NOT NULL,
            shop_domain VARCHAR(255) NOT NULL,
            sync_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            INDEX(user_id),
            INDEX(shop_domain),
            INDEX(email),
            INDEX(state),
            INDEX(accepts_marketing),
            INDEX(created_at),
            INDEX(updated_at)
        );
        """
        
        # Create indexes
        indexes_sql = [
            "CREATE INDEX IF NOT EXISTS idx_shopify_tokens_user_id ON shopify_tokens(user_id);",
            "CREATE INDEX IF NOT EXISTS idx_shopify_products_user_domain ON shopify_products(user_id, shop_domain);",
            "CREATE INDEX IF NOT EXISTS idx_shopify_orders_user_domain ON shopify_orders(user_id, shop_domain);",
            "CREATE INDEX IF NOT EXISTS idx_shopify_customers_user_domain ON shopify_customers(user_id, shop_domain);",
            "CREATE INDEX IF NOT EXISTS idx_shopify_products_status_type ON shopify_products(status, product_type);",
            "CREATE INDEX IF NOT EXISTS idx_shopify_orders_status_email ON shopify_orders(financial_status, email);",
            "CREATE INDEX IF NOT EXISTS idx_shopify_customers_state_email ON shopify_customers(state, email);"
        ]
        
        try:
            async with self.get_connection() as conn:
                await conn.execute(tokens_sql)
                await conn.execute(products_sql)
                await conn.execute(orders_sql)
                await conn.execute(customers_sql)
                
                for index_sql in indexes_sql:
                    await conn.execute(index_sql)
                
                logger.info("Shopify database tables created successfully")
        except Exception as e:
            logger.error(f"Error creating Shopify tables: {e}")
            raise
    
    async def save_tokens(self, user_id: str, tokens: ShopifyToken) -> None:
        """Save or update Shopify tokens"""
        sql = """
        INSERT INTO shopify_tokens (user_id, access_token, token_type, scope, domain, refresh_token, expires_in, user_info)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (user_id, domain)
        DO UPDATE SET
            access_token = EXCLUDED.access_token,
            token_type = EXCLUDED.token_type,
            scope = EXCLUDED.scope,
            refresh_token = EXCLUDED.refresh_token,
            expires_in = EXCLUDED.expires_in,
            updated_at = NOW(),
            user_info = EXCLUDED.user_info;
        """
        
        try:
            async with self.get_connection() as conn:
                await conn.execute(
                    sql,
                    user_id,
                    tokens.access_token,
                    tokens.token_type,
                    tokens.scope,
                    tokens.domain,
                    tokens.refresh_token,
                    tokens.expires_in,
                    json.dumps(tokens.user_info) if tokens.user_info else None
                )
                logger.info(f"Shopify tokens saved for user: {user_id}")
        except Exception as e:
            logger.error(f"Error saving Shopify tokens: {e}")
            raise
    
    async def get_tokens(self, user_id: str, domain: Optional[str] = None) -> Optional[ShopifyToken]:
        """Get Shopify tokens for user"""
        if domain:
            sql = """
            SELECT access_token, token_type, scope, domain, refresh_token, expires_in, created_at, updated_at, user_info
            FROM shopify_tokens
            WHERE user_id = $1 AND domain = $2;
            """
            params = [user_id, domain]
        else:
            sql = """
            SELECT access_token, token_type, scope, domain, refresh_token, expires_in, created_at, updated_at, user_info
            FROM shopify_tokens
            WHERE user_id = $1
            ORDER BY updated_at DESC
            LIMIT 1;
            """
            params = [user_id]
        
        try:
            async with self.get_connection() as conn:
                row = await conn.fetchrow(sql, *params)
                
                if row:
                    return ShopifyToken(
                        access_token=row['access_token'],
                        token_type=row['token_type'],
                        scope=row['scope'],
                        domain=row['domain'],
                        refresh_token=row['refresh_token'],
                        expires_in=row['expires_in'],
                        created_at=row['created_at'].isoformat() if row['created_at'] else None,
                        user_info=row['user_info']
                    )
                return None
        except Exception as e:
            logger.error(f"Error getting Shopify tokens: {e}")
            return None
    
    async def delete_tokens(self, user_id: str, domain: Optional[str] = None) -> None:
        """Delete Shopify tokens for user"""
        if domain:
            sql = "DELETE FROM shopify_tokens WHERE user_id = $1 AND domain = $2;"
            params = [user_id, domain]
        else:
            sql = "DELETE FROM shopify_tokens WHERE user_id = $1;"
            params = [user_id]
        
        try:
            async with self.get_connection() as conn:
                await conn.execute(sql, *params)
                logger.info(f"Shopify tokens deleted for user: {user_id}")
        except Exception as e:
            logger.error(f"Error deleting Shopify tokens: {e}")
            raise
    
    async def save_products(self, products: List[ShopifyProduct]) -> None:
        """Save or update Shopify products"""
        sql = """
        INSERT INTO shopify_products (
            id, title, body_html, vendor, product_type, created_at, handle, updated_at,
            published_at, template_suffix, status, published_scope, tags, admin_graphql_api_id,
            options, images, image, variants, metafields, user_id, shop_domain
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21
        )
        ON CONFLICT (id)
        DO UPDATE SET
            title = EXCLUDED.title,
            body_html = EXCLUDED.body_html,
            vendor = EXCLUDED.vendor,
            product_type = EXCLUDED.product_type,
            handle = EXCLUDED.handle,
            updated_at = EXCLUDED.updated_at,
            published_at = EXCLUDED.published_at,
            template_suffix = EXCLUDED.template_suffix,
            status = EXCLUDED.status,
            published_scope = EXCLUDED.published_scope,
            tags = EXCLUDED.tags,
            options = EXCLUDED.options,
            images = EXCLUDED.images,
            image = EXCLUDED.image,
            variants = EXCLUDED.variants,
            metafields = EXCLUDED.metafields,
            sync_at = NOW();
        """
        
        try:
            async with self.get_connection() as conn:
                for product in products:
                    await conn.execute(
                        sql,
                        product.id,
                        product.title,
                        product.body_html,
                        product.vendor,
                        product.product_type,
                        product.created_at,
                        product.handle,
                        product.updated_at,
                        product.published_at,
                        product.template_suffix,
                        product.status,
                        product.published_scope,
                        product.tags,
                        product.admin_graphql_api_id,
                        json.dumps(product.options),
                        json.dumps(product.images),
                        json.dumps(product.image) if product.image else None,
                        json.dumps(product.variants),
                        json.dumps(product.metafields),
                        product.user_id,
                        product.shop_domain
                    )
                logger.info(f"Saved {len(products)} Shopify products")
        except Exception as e:
            logger.error(f"Error saving Shopify products: {e}")
            raise
    
    async def get_products(self, user_id: str, shop_domain: str, 
                          status: Optional[str] = None,
                          product_type: Optional[str] = None,
                          vendor: Optional[str] = None,
                          limit: int = 100) -> List[Dict[str, Any]]:
        """Get Shopify products with filters"""
        
        base_conditions = ["user_id = $1", "shop_domain = $2"]
        params = [user_id, shop_domain]
        param_count = 2
        
        if status:
            param_count += 1
            base_conditions.append(f"status = ${param_count}")
            params.append(status)
        
        if product_type:
            param_count += 1
            base_conditions.append(f"product_type = ${param_count}")
            params.append(product_type)
        
        if vendor:
            param_count += 1
            base_conditions.append(f"vendor = ${param_count}")
            params.append(vendor)
        
        sql = f"""
        SELECT *
        FROM shopify_products
        WHERE {' AND '.join(base_conditions)}
        ORDER BY updated_at DESC
        LIMIT ${param_count + 1};
        """
        params.append(limit)
        
        try:
            async with self.get_connection() as conn:
                rows = await conn.fetch(sql, *params)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting Shopify products: {e}")
            return []
    
    async def save_orders(self, orders: List[ShopifyOrder]) -> None:
        """Save or update Shopify orders"""
        sql = """
        INSERT INTO shopify_orders (
            id, admin_graphql_api_id, app_id, browser_ip, buyer_accepts_marketing, cancel_reason,
            cancelled_at, cart_token, checkout_id, checkout_token, client_details, closed_at,
            confirmed, contact_email, created_at, currency, current_subtotal_price, current_total_price,
            current_total_tax, customer_locale, device_id, discount_codes, email, estimated_taxes,
            financial_status, fulfillment_status, gateway, landing_site, name, note, note_attributes,
            number, order_number, order_status_url, payment_gateway_names, phone, presentment_currency,
            processed_at, processing_method, reference, referring_site, source_identifier, source_name,
            source_url, subtotal_price, tags, tax_lines, taxes_included, test, token, total_discounts,
            total_line_items_price, total_outstanding, total_price, total_tax, total_tip_received,
            total_weight, updated_at, user_id, billing_address, customer, discount_applications,
            fulfillments, line_items, payment_details, refunds, shipping_address, shipping_lines, shop_domain
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19,
            $20, $21, $22, $23, $24, $25, $26, $27, $28, $29, $30, $31, $32, $33, $34, $35, $36, $37,
            $38, $39, $40, $41, $42, $43, $44, $45, $46, $47, $48, $49, $50, $51, $52, $53, $54, $55,
            $56, $57, $58, $59, $60, $61, $62, $63, $64, $65, $66, $67, $68, $69, $70, $71
        )
        ON CONFLICT (id)
        DO UPDATE SET
            admin_graphql_api_id = EXCLUDED.admin_graphql_api_id,
            browser_ip = EXCLUDED.browser_ip,
            buyer_accepts_marketing = EXCLUDED.buyer_accepts_marketing,
            cancel_reason = EXCLUDED.cancel_reason,
            cancelled_at = EXCLUDED.cancelled_at,
            cart_token = EXCLUDED.cart_token,
            checkout_id = EXCLUDED.checkout_id,
            checkout_token = EXCLUDED.checkout_token,
            client_details = EXCLUDED.client_details,
            closed_at = EXCLUDED.closed_at,
            confirmed = EXCLUDED.confirmed,
            contact_email = EXCLUDED.contact_email,
            updated_at = EXCLUDED.updated_at,
            current_subtotal_price = EXCLUDED.current_subtotal_price,
            current_total_price = EXCLUDED.current_total_price,
            current_total_tax = EXCLUDED.current_total_tax,
            customer_locale = EXCLUDED.customer_locale,
            device_id = EXCLUDED.device_id,
            discount_codes = EXCLUDED.discount_codes,
            email = EXCLUDED.email,
            estimated_taxes = EXCLUDED.estimated_taxes,
            financial_status = EXCLUDED.financial_status,
            fulfillment_status = EXCLUDED.fulfillment_status,
            gateway = EXCLUDED.gateway,
            landing_site = EXCLUDED.landing_site,
            name = EXCLUDED.name,
            note = EXCLUDED.note,
            note_attributes = EXCLUDED.note_attributes,
            number = EXCLUDED.number,
            order_number = EXCLUDED.order_number,
            order_status_url = EXCLUDED.order_status_url,
            payment_gateway_names = EXCLUDED.payment_gateway_names,
            phone = EXCLUDED.phone,
            presentment_currency = EXCLUDED.presentment_currency,
            processed_at = EXCLUDED.processed_at,
            processing_method = EXCLUDED.processing_method,
            reference = EXCLUDED.reference,
            referring_site = EXCLUDED.referring_site,
            source_identifier = EXCLUDED.source_identifier,
            source_name = EXCLUDED.source_name,
            source_url = EXCLUDED.source_url,
            subtotal_price = EXCLUDED.subtotal_price,
            tags = EXCLUDED.tags,
            tax_lines = EXCLUDED.tax_lines,
            taxes_included = EXCLUDED.taxes_included,
            test = EXCLUDED.test,
            token = EXCLUDED.token,
            total_discounts = EXCLUDED.total_discounts,
            total_line_items_price = EXCLUDED.total_line_items_price,
            total_outstanding = EXCLUDED.total_outstanding,
            total_price = EXCLUDED.total_price,
            total_tax = EXCLUDED.total_tax,
            total_tip_received = EXCLUDED.total_tip_received,
            total_weight = EXCLUDED.total_weight,
            billing_address = EXCLUDED.billing_address,
            customer = EXCLUDED.customer,
            discount_applications = EXCLUDED.discount_applications,
            fulfillments = EXCLUDED.fulfillments,
            line_items = EXCLUDED.line_items,
            payment_details = EXCLUDED.payment_details,
            refunds = EXCLUDED.refunds,
            shipping_address = EXCLUDED.shipping_address,
            shipping_lines = EXCLUDED.shipping_lines,
            sync_at = NOW();
        """
        
        try:
            async with self.get_connection() as conn:
                for order in orders:
                    await conn.execute(
                        sql,
                        order.id, order.admin_graphql_api_id, order.app_id, order.browser_ip,
                        order.buyer_accepts_marketing, order.cancel_reason, order.cancelled_at,
                        order.cart_token, order.checkout_id, order.checkout_token,
                        json.dumps(order.client_details), order.closed_at, order.confirmed,
                        order.contact_email, order.created_at, order.currency,
                        float(order.current_subtotal_price), float(order.current_total_price),
                        float(order.current_total_tax), order.customer_locale, order.device_id,
                        json.dumps(order.discount_codes), order.email, order.estimated_taxes,
                        order.financial_status, order.fulfillment_status, order.gateway,
                        order.landing_site, order.name, order.note, json.dumps(order.note_attributes),
                        order.number, order.order_number, order.order_status_url,
                        json.dumps(order.payment_gateway_names), order.phone, order.presentment_currency,
                        order.processed_at, order.processing_method, order.reference, order.referring_site,
                        order.source_identifier, order.source_name, order.source_url,
                        float(order.subtotal_price), order.tags, json.dumps(order.tax_lines),
                        order.taxes_included, order.test, order.token, float(order.total_discounts),
                        float(order.total_line_items_price), float(order.total_outstanding),
                        float(order.total_price), float(order.total_tax), float(order.total_tip_received),
                        order.total_weight, order.updated_at, order.user_id,
                        json.dumps(order.billing_address) if order.billing_address else None,
                        json.dumps(order.customer) if order.customer else None,
                        json.dumps(order.discount_applications), json.dumps(order.fulfillments),
                        json.dumps(order.line_items), json.dumps(order.payment_details) if order.payment_details else None,
                        json.dumps(order.refunds), json.dumps(order.shipping_address) if order.shipping_address else None,
                        json.dumps(order.shipping_lines), order.shop_domain
                    )
                logger.info(f"Saved {len(orders)} Shopify orders")
        except Exception as e:
            logger.error(f"Error saving Shopify orders: {e}")
            raise
    
    async def get_orders(self, user_id: str, shop_domain: str,
                        status: Optional[str] = None,
                        fulfillment_status: Optional[str] = None,
                        limit: int = 100) -> List[Dict[str, Any]]:
        """Get Shopify orders with filters"""
        
        base_conditions = ["user_id = $1", "shop_domain = $2"]
        params = [user_id, shop_domain]
        param_count = 2
        
        if status and status != 'any':
            param_count += 1
            base_conditions.append(f"financial_status = ${param_count}")
            params.append(status)
        
        if fulfillment_status:
            param_count += 1
            base_conditions.append(f"fulfillment_status = ${param_count}")
            params.append(fulfillment_status)
        
        sql = f"""
        SELECT *
        FROM shopify_orders
        WHERE {' AND '.join(base_conditions)}
        ORDER BY created_at DESC
        LIMIT ${param_count + 1};
        """
        params.append(limit)
        
        try:
            async with self.get_connection() as conn:
                rows = await conn.fetch(sql, *params)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting Shopify orders: {e}")
            return []
    
    async def save_customers(self, customers: List[ShopifyCustomer]) -> None:
        """Save or update Shopify customers"""
        sql = """
        INSERT INTO shopify_customers (
            id, email, created_at, updated_at, first_name, last_name, state, note,
            verified_email, multipass_identifier, tax_exempt, tags, last_order_id,
            last_order_name, currency, total_spent, phone, addresses, accepts_marketing,
            accepts_marketing_updated_at, marketing_opt_in_level, tax_exemptions,
            sms_marketing_consent, admin_graphql_api_id, user_id, shop_domain
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17,
            $18, $19, $20, $21, $22, $23, $24, $25, $26
        )
        ON CONFLICT (id)
        DO UPDATE SET
            email = EXCLUDED.email,
            updated_at = EXCLUDED.updated_at,
            first_name = EXCLUDED.first_name,
            last_name = EXCLUDED.last_name,
            state = EXCLUDED.state,
            note = EXCLUDED.note,
            verified_email = EXCLUDED.verified_email,
            multipass_identifier = EXCLUDED.multipass_identifier,
            tax_exempt = EXCLUDED.tax_exempt,
            tags = EXCLUDED.tags,
            last_order_id = EXCLUDED.last_order_id,
            last_order_name = EXCLUDED.last_order_name,
            currency = EXCLUDED.currency,
            total_spent = EXCLUDED.total_spent,
            phone = EXCLUDED.phone,
            addresses = EXCLUDED.addresses,
            accepts_marketing = EXCLUDED.accepts_marketing,
            accepts_marketing_updated_at = EXCLUDED.accepts_marketing_updated_at,
            marketing_opt_in_level = EXCLUDED.marketing_opt_in_level,
            tax_exemptions = EXCLUDED.tax_exemptions,
            sms_marketing_consent = EXCLUDED.sms_marketing_consent,
            sync_at = NOW();
        """
        
        try:
            async with self.get_connection() as conn:
                for customer in customers:
                    await conn.execute(
                        sql,
                        customer.id, customer.email, customer.created_at, customer.updated_at,
                        customer.first_name, customer.last_name, customer.state, customer.note,
                        customer.verified_email, customer.multipass_identifier, customer.tax_exempt,
                        customer.tags, customer.last_order_id, customer.last_order_name,
                        customer.currency, float(customer.total_spent), customer.phone,
                        json.dumps(customer.addresses), customer.accepts_marketing,
                        customer.accepts_marketing_updated_at, customer.marketing_opt_in_level,
                        json.dumps(customer.tax_exemptions),
                        json.dumps(customer.sms_marketing_consent) if customer.sms_marketing_consent else None,
                        customer.admin_graphql_api_id, customer.user_id, customer.shop_domain
                    )
                logger.info(f"Saved {len(customers)} Shopify customers")
        except Exception as e:
            logger.error(f"Error saving Shopify customers: {e}")
            raise
    
    async def get_customers(self, user_id: str, shop_domain: str,
                          email: Optional[str] = None,
                          limit: int = 100) -> List[Dict[str, Any]]:
        """Get Shopify customers with filters"""
        
        base_conditions = ["user_id = $1", "shop_domain = $2"]
        params = [user_id, shop_domain]
        param_count = 2
        
        if email:
            param_count += 1
            base_conditions.append(f"email ILIKE ${param_count}")
            params.append(f"%{email}%")
        
        sql = f"""
        SELECT *
        FROM shopify_customers
        WHERE {' AND '.join(base_conditions)}
        ORDER BY updated_at DESC
        LIMIT ${param_count + 1};
        """
        params.append(limit)
        
        try:
            async with self.get_connection() as conn:
                rows = await conn.fetch(sql, *params)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting Shopify customers: {e}")
            return []
    
    async def search_shopify(self, user_id: str, shop_domain: str, query: str,
                            search_type: str = 'all', limit: int = 20) -> Dict[str, List[Dict[str, Any]]]:
        """Search across Shopify data"""
        results = {
            'products': [],
            'orders': [],
            'customers': []
        }
        
        try:
            async with self.get_connection() as conn:
                # Search products
                if search_type in ['products', 'all']:
                    products_sql = """
                    SELECT id, title, handle, vendor, product_type, status, created_at, updated_at,
                           tags, admin_graphql_api_id, sync_at
                    FROM shopify_products
                    WHERE user_id = $1 AND shop_domain = $2 AND (
                        title ILIKE $3 OR handle ILIKE $3 OR vendor ILIKE $3 OR tags ILIKE $3
                    )
                    ORDER BY updated_at DESC
                    LIMIT $4;
                    """
                    product_rows = await conn.fetch(products_sql, user_id, shop_domain, f"%{query}%", limit)
                    results['products'] = [dict(row) for row in product_rows]
                
                # Search orders
                if search_type in ['orders', 'all']:
                    orders_sql = """
                    SELECT id, name, email, financial_status, fulfillment_status, created_at,
                           updated_at, total_price, tags, sync_at
                    FROM shopify_orders
                    WHERE user_id = $1 AND shop_domain = $2 AND (
                        name ILIKE $3 OR email ILIKE $3 OR tags ILIKE $3
                    )
                    ORDER BY created_at DESC
                    LIMIT $4;
                    """
                    order_rows = await conn.fetch(orders_sql, user_id, shop_domain, f"%{query}%", limit)
                    results['orders'] = [dict(row) for row in order_rows]
                
                # Search customers
                if search_type in ['customers', 'all']:
                    customers_sql = """
                    SELECT id, email, first_name, last_name, state, created_at, updated_at,
                           total_spent, tags, sync_at
                    FROM shopify_customers
                    WHERE user_id = $1 AND shop_domain = $2 AND (
                        email ILIKE $3 OR first_name ILIKE $3 OR last_name ILIKE $3 OR tags ILIKE $3
                    )
                    ORDER BY updated_at DESC
                    LIMIT $4;
                    """
                    customer_rows = await conn.fetch(customers_sql, user_id, shop_domain, f"%{query}%", limit)
                    results['customers'] = [dict(row) for row in customer_rows]
        
        except Exception as e:
            logger.error(f"Error searching Shopify data: {e}")
        
        return results
    
    async def get_user_shopify_data(self, user_id: str) -> Dict[str, Any]:
        """Get all Shopify data for a user"""
        try:
            async with self.get_connection() as conn:
                # Get tokens
                tokens_row = await conn.fetchrow("""
                    SELECT * FROM shopify_tokens WHERE user_id = $1 ORDER BY updated_at DESC LIMIT 1;
                """, user_id)
                
                if not tokens_row:
                    return {}
                
                # Get aggregated stats
                stats_sql = """
                SELECT 
                    COUNT(DISTINCT sp.id) as total_products,
                    COUNT(DISTINCT so.id) as total_orders,
                    COUNT(DISTINCT sc.id) as total_customers,
                    SUM(CAST(sp.variants->>0->'inventory_quantity' AS INTEGER)) as total_inventory,
                    SUM(CAST(so.total_price AS DECIMAL(10,2))) as total_revenue,
                    SUM(CAST(sc.total_spent AS DECIMAL(10,2))) as total_customer_spent
                FROM shopify_tokens st
                LEFT JOIN shopify_products sp ON sp.user_id = st.user_id AND sp.shop_domain = st.domain
                LEFT JOIN shopify_orders so ON so.user_id = st.user_id AND so.shop_domain = st.domain
                LEFT JOIN shopify_customers sc ON sc.user_id = st.user_id AND sc.shop_domain = st.domain
                WHERE st.user_id = $1;
                """
                
                stats_row = await conn.fetchrow(stats_sql, user_id)
                
                return {
                    'tokens': dict(tokens_row),
                    'stats': dict(stats_row) if stats_row else {}
                }
        
        except Exception as e:
            logger.error(f"Error getting user Shopify data: {e}")
            return {}
    
    async def cleanup_old_data(self, days: int = 30) -> None:
        """Clean up old Shopify sync data"""
        try:
            async with self.get_connection() as conn:
                cutoff_date = datetime.utcnow() - timedelta(days=days)
                
                # Delete old product data
                await conn.execute("""
                    DELETE FROM shopify_products 
                    WHERE sync_at < $1 AND id NOT IN (
                        SELECT id FROM shopify_products 
                        WHERE sync_at >= $1 OR updated_at >= $1
                    );
                """, cutoff_date)
                
                # Delete old order data
                await conn.execute("""
                    DELETE FROM shopify_orders 
                    WHERE sync_at < $1 AND id NOT IN (
                        SELECT id FROM shopify_orders 
                        WHERE sync_at >= $1 OR updated_at >= $1
                    );
                """, cutoff_date)
                
                # Delete old customer data
                await conn.execute("""
                    DELETE FROM shopify_customers 
                    WHERE sync_at < $1 AND id NOT IN (
                        SELECT id FROM shopify_customers 
                        WHERE sync_at >= $1 OR updated_at >= $1
                    );
                """, cutoff_date)
                
                logger.info(f"Cleaned up Shopify data older than {days} days")
        
        except Exception as e:
            logger.error(f"Error cleaning up old Shopify data: {e}")

# Global database manager instance
shopify_db_manager = ShopifyDBManager()

# Database helper functions for backward compatibility
async def get_tokens(user_id: str, domain: Optional[str] = None) -> Optional[ShopifyToken]:
    """Get Shopify tokens for user"""
    return await shopify_db_manager.get_tokens(user_id, domain)

async def save_tokens(user_id: str, tokens: ShopifyToken) -> None:
    """Save Shopify tokens for user"""
    await shopify_db_manager.save_tokens(user_id, tokens)

async def delete_tokens(user_id: str, domain: Optional[str] = None) -> None:
    """Delete Shopify tokens for user"""
    await shopify_db_manager.delete_tokens(user_id, domain)

async def get_user_shopify_data(user_id: str) -> Dict[str, Any]:
    """Get all Shopify data for a user"""
    return await shopify_db_manager.get_user_shopify_data(user_id)

async def save_shopify_data(user_id: str, shop_domain: str, 
                           products: Optional[List[ShopifyProduct]] = None,
                           orders: Optional[List[ShopifyOrder]] = None,
                           customers: Optional[List[ShopifyCustomer]] = None) -> None:
    """Save Shopify data for user"""
    try:
        if products:
            await shopify_db_manager.save_products(products)
        if orders:
            await shopify_db_manager.save_orders(orders)
        if customers:
            await shopify_db_manager.save_customers(customers)
        
        logger.info(f"Saved Shopify data for user: {user_id}, shop: {shop_domain}")
    except Exception as e:
        logger.error(f"Error saving Shopify data: {e}")
        raise

# Initialize database
async def init_shopify_db():
    """Initialize Shopify database tables"""
    await shopify_db_manager.create_tables()
    logger.info("Shopify database initialized")

# Export database manager and functions
__all__ = [
    'ShopifyDBManager',
    'shopify_db_manager',
    'ShopifyToken',
    'ShopifyProduct',
    'ShopifyOrder',
    'ShopifyCustomer',
    'get_tokens',
    'save_tokens',
    'delete_tokens',
    'get_user_shopify_data',
    'save_shopify_data',
    'init_shopify_db'
]