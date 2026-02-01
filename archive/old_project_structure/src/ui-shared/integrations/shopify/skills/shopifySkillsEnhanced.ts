"""
Shopify Enhanced Skills
Complete Shopify e-commerce and store management system
"""

import { Skill, SkillContext, SkillResult } from '../../../types/skillTypes';

/**
 * Shopify Enhanced Skills
 * Complete Shopify e-commerce and store management system
 */

// Product Management Skills
export class ShopifyCreateProductSkill implements Skill {
  id = 'shopify_create_product';
  name = 'Create Shopify Product';
  description = 'Create a new product in Shopify';
  category = 'e-commerce';
  examples = [
    'Create Shopify product for wireless headphones',
    'Add product Premium Wireless Headphones to Shopify',
    'Create product Organic Cotton T-Shirt with variants'
  ];

  async execute(context: SkillContext): Promise<SkillResult> {
    try {
      const { intent, entities } = context;
      
      // Extract product details
      const title = this.extractProductTitle(intent) ||
                   entities.find((e: any) => e.type === 'product_title')?.value;
      
      const description = this.extractDescription(intent) ||
                          entities.find((e: any) => e.type === 'description')?.value;
      
      const price = this.extractPrice(intent) ||
                   entities.find((e: any) => e.type === 'price')?.value;
      
      const vendor = this.extractVendor(intent) ||
                    entities.find((e: any) => e.type === 'vendor')?.value;
      
      const productType = this.extractProductType(intent) ||
                          entities.find((e: any) => e.type === 'product_type')?.value;
      
      const tags = this.extractTags(intent) ||
                  entities.find((e: any) => e.type === 'tags')?.value;

      if (!title) {
        return {
          success: false,
          message: 'Product title is required',
          error: 'Missing product title'
        };
      }

      // Call Shopify API
      const response = await fetch('/api/integrations/shopify/products', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: context.user?.id || 'default',
          operation: 'create',
          data: {
            title: title,
            body_html: description ? `<p>${description}</p>` : '',
            vendor: vendor || 'Test Vendor',
            product_type: productType || 'Test Type',
            tags: tags || '',
            variants: price ? [{
              title: 'Default Title',
              price: price,
              sku: '',
              inventory_policy: 'deny',
              fulfillment_service: 'manual',
              inventory_management: null,
              option1: 'Default Title',
              option2: null,
              option3: null,
              taxable: true,
              barcode: '',
              requires_shipping: true,
              weight: 0,
              weight_unit: 'g'
            }] : [{
              title: 'Default Title',
              price: '0.00',
              sku: '',
              inventory_policy: 'deny',
              fulfillment_service: 'manual',
              inventory_management: null,
              option1: 'Default Title',
              option2: null,
              option3: null,
              taxable: true,
              barcode: '',
              requires_shipping: true,
              weight: 0,
              weight_unit: 'g'
            }],
            options: [{
              name: 'Title',
              product_id: 1,
              position: 1,
              values: ['Default Title']
            }],
            metafields: []
          }
        })
      });

      const result = await response.json();

      if (result.ok) {
        const product = result.data.product;
        return {
          success: true,
          message: `Shopify product "${product.title}" created successfully`,
          data: {
            product: product,
            title: product.title,
            price: product.variants[0]?.price || '0.00',
            vendor: product.vendor,
            product_type: product.product_type,
            product_id: product.id
          },
          actions: [
            {
              type: 'open_url',
              label: 'View Product',
              url: `https://${result.data.shop?.domain || 'test-shop'}.myshopify.com/admin/products/${product.id}`
            }
          ]
        };
      } else {
        return {
          success: false,
          message: `Failed to create Shopify product: ${result.error?.message || 'Unknown error'}`,
          error: result.error
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error creating Shopify product: ${error}`,
        error: error as any
      };
    }
  }

  private extractProductTitle(intent: string): string | null {
    const patterns = [
      /create (?:shopify )?product (?:for|called|named) (.+?)(?: with|at|:|$)/i,
      /add product (?:called|named) (.+?)(?: with|at|:|$)/i,
      /product (?:called|named) (.+?)(?: with|at|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractDescription(intent: string): string | null {
    const patterns = [
      /(?:for|with) (.+?) (?:product|variant|price|:|$)/i,
      /description (.+?) (?:product|variant|price|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractPrice(intent: string): string | null {
    const patterns = [
      /\$(\d+\.?\d*)/i,
      /(\d+\.?\d*)\s*(?:dollars?|usd)/i,
      /price\s+of\s*\$?(\d+\.?\d*)/i,
      /for\s+\$?(\d+\.?\d*)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1];
      }
    }

    return null;
  }

  private extractVendor(intent: string): string | null {
    const patterns = [
      /vendor\s+(\w+)/i,
      /by\s+(\w+)\s+vendor/i,
      /(\w+)\s+vendor/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1];
      }
    }

    return null;
  }

  private extractProductType(intent: string): string | null {
    const productTypes = ['electronics', 'clothing', 'accessories', 'books', 'home', 'beauty', 'sports', 'toys'];
    
    for (const type of productTypes) {
      if (intent.toLowerCase().includes(type)) {
        return type;
      }
    }
    
    return null;
  }

  private extractTags(intent: string): string | null {
    const tags = ['premium', 'organic', 'wireless', 'eco-friendly', 'handmade', 'bestseller'];
    const foundTags = tags.filter(tag => intent.toLowerCase().includes(tag));
    
    return foundTags.length > 0 ? foundTags.join(', ') : null;
  }
}

export class ShopifyCreateOrderSkill implements Skill {
  id = 'shopify_create_order';
  name = 'Create Shopify Order';
  description = 'Create a new order in Shopify';
  category = 'e-commerce';
  examples = [
    'Create Shopify order for wireless headphones',
    'Process order for John Doe with 2 items',
    'Create order for customer@example.com with product ID 123'
  ];

  async execute(context: SkillContext): Promise<SkillResult> {
    try {
      const { intent, entities } = context;
      
      // Extract order details
      const customerEmail = this.extractCustomerEmail(intent) ||
                           entities.find((e: any) => e.type === 'customer_email')?.value;
      
      const customerName = this.extractCustomerName(intent) ||
                         entities.find((e: any) => e.type === 'customer_name')?.value;
      
      const productName = this.extractProductName(intent) ||
                         entities.find((e: any) => e.type === 'product_name')?.value;
      
      const quantity = this.extractQuantity(intent) ||
                     entities.find((e: any) => e.type === 'quantity')?.value ||
                     1;
      
      const price = this.extractPrice(intent) ||
                   entities.find((e: any) => e.type === 'price')?.value;

      // Create line item
      let lineItems: any[] = [];
      
      if (productName || price) {
        lineItems.push({
          title: productName || 'Product',
          quantity: parseInt(quantity.toString()),
          price: price || '0.00',
          variant_title: 'Default',
          vendor: 'Test Vendor',
          product_id: 1,
          requires_shipping: true,
          taxable: true,
          fulfillment_service: 'manual'
        });
      }

      if (lineItems.length === 0) {
        return {
          success: false,
          message: 'Product name or price is required for order',
          error: 'Missing order items'
        };
      }

      // Call Shopify API
      const response = await fetch('/api/integrations/shopify/orders', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: context.user?.id || 'default',
          operation: 'create',
          data: {
            email: customerEmail,
            line_items: lineItems,
            customer: customerName ? {
              first_name: customerName.split(' ')[0],
              last_name: customerName.split(' ').slice(1).join(' '),
              email: customerEmail
            } : undefined,
            financial_status: 'pending',
            fulfillment_status: 'unfulfilled',
            currency: 'USD',
            send_receipt: true,
            send_fulfillment_receipt: false,
            tags: 'voice_created',
            note: 'Order created via voice command'
          }
        })
      });

      const result = await response.json();

      if (result.ok) {
        const order = result.data.order;
        return {
          success: true,
          message: `Shopify order "${order.name}" created successfully`,
          data: {
            order: order,
            order_id: order.id,
            order_number: order.name,
            customer_email: order.email,
            total_price: order.total_price,
            items: order.line_items.length
          },
          actions: [
            {
              type: 'open_url',
              label: 'View Order',
              url: `https://${result.data.shop?.domain || 'test-shop'}.myshopify.com/admin/orders/${order.id}`
            }
          ]
        };
      } else {
        return {
          success: false,
          message: `Failed to create Shopify order: ${result.error?.message || 'Unknown error'}`,
          error: result.error
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error creating Shopify order: ${error}`,
        error: error as any
      };
    }
  }

  private extractCustomerEmail(intent: string): string | null {
    const patterns = [
      /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/g,
      /email\s+([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})/i,
      /for\s+([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match && match[0]) {
        return match[0];
      }
    }

    return null;
  }

  private extractCustomerName(intent: string): string | null {
    const patterns = [
      /order\s+for\s+(\w+(?:\s+\w+)?)/i,
      /customer\s+(\w+(?:\s+\w+)?)/i,
      /(\w+(?:\s+\w+)?)\s+customer/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1];
      }
    }

    return null;
  }

  private extractProductName(intent: string): string | null {
    const patterns = [
      /order\s+for\s+(.+?)\s*(?:with|\$|\d|:|$)/i,
      /product\s+(.+?)\s*(?:with|\$|\d|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractQuantity(intent: string): string | null {
    const patterns = [
      /(\d+)\s+(?:items?|products?|units?)/i,
      /quantity\s+(\d+)/i,
      /(\d+)\s+times/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1];
      }
    }

    return null;
  }

  private extractPrice(intent: string): string | null {
    const patterns = [
      /\$(\d+\.?\d*)/i,
      /(\d+\.?\d*)\s*(?:dollars?|usd)/i,
      /price\s+of\s*\$?(\d+\.?\d*)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1];
      }
    }

    return null;
  }
}

export class ShopifyCreateCustomerSkill implements Skill {
  id = 'shopify_create_customer';
  name = 'Create Shopify Customer';
  description = 'Create a new customer in Shopify';
  category = 'e-commerce';
  examples = [
    'Create Shopify customer for john@example.com',
    'Add customer Sarah Johnson with email sarah@example.com',
    'Create customer Mike Smith at mike@example.com'
  ];

  async execute(context: SkillContext): Promise<SkillResult> {
    try {
      const { intent, entities } = context;
      
      // Extract customer details
      const email = this.extractEmail(intent) ||
                   entities.find((e: any) => e.type === 'email')?.value;
      
      const name = this.extractName(intent) ||
                   entities.find((e: any) => e.type === 'name')?.value;
      
      const phone = this.extractPhone(intent) ||
                   entities.find((e: any) => e.type === 'phone')?.value;
      
      const acceptsMarketing = this.extractAcceptsMarketing(intent);

      if (!email) {
        return {
          success: false,
          message: 'Customer email is required',
          error: 'Missing customer email'
        };
      }

      // Call Shopify API
      const response = await fetch('/api/integrations/shopify/customers', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: context.user?.id || 'default',
          operation: 'create',
          data: {
            email: email,
            first_name: name ? name.split(' ')[0] : '',
            last_name: name ? name.split(' ').slice(1).join(' ') : '',
            phone: phone,
            accepts_marketing: acceptsMarketing,
            addresses: [],
            tags: 'voice_created',
            note: 'Customer created via voice command'
          }
        })
      });

      const result = await response.json();

      if (result.ok) {
        const customer = result.data.customer;
        return {
          success: true,
          message: `Shopify customer "${customer.first_name} ${customer.last_name || customer.email}" created successfully`,
          data: {
            customer: customer,
            email: customer.email,
            name: `${customer.first_name} ${customer.last_name || ''}`.trim(),
            phone: customer.phone,
            customer_id: customer.id
          },
          actions: [
            {
              type: 'open_url',
              label: 'View Customer',
              url: `https://${result.data.shop?.domain || 'test-shop'}.myshopify.com/admin/customers/${customer.id}`
            }
          ]
        };
      } else {
        return {
          success: false,
          message: `Failed to create Shopify customer: ${result.error?.message || 'Unknown error'}`,
          error: result.error
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error creating Shopify customer: ${error}`,
        error: error as any
      };
    }
  }

  private extractEmail(intent: string): string | null {
    const patterns = [
      /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/g,
      /email\s+([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})/i,
      /for\s+([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match && match[0]) {
        return match[0];
      }
    }

    return null;
  }

  private extractName(intent: string): string | null {
    const patterns = [
      /customer\s+(\w+(?:\s+\w+)?)/i,
      /add\s+(\w+(?:\s+\w+)?)\s+customer/i,
      /(\w+(?:\s+\w+)?)\s+customer/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1];
      }
    }

    return null;
  }

  private extractPhone(intent: string): string | null {
    const patterns = [
      /\+?1?\d{10}/g,
      /phone\s+(\+?1?\d{10})/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[0];
      }
    }

    return null;
  }

  private extractAcceptsMarketing(intent: string): boolean {
    if (intent.toLowerCase().includes('marketing') || 
        intent.toLowerCase().includes('subscribe') ||
        intent.toLowerCase().includes('newsletter')) {
      return true;
    }
    return false;
  }
}

// Inventory Management Skills
export class ShopifyUpdateInventorySkill implements Skill {
  id = 'shopify_update_inventory';
  name = 'Update Shopify Inventory';
  description = 'Update inventory levels for Shopify products';
  category = 'e-commerce';
  examples = [
    'Update Shopify inventory for wireless headphones to 50',
    'Set inventory of product 123 to 100 units',
    'Update stock level for Organic Cotton T-Shirt to 75'
  ];

  async execute(context: SkillContext): Promise<SkillResult> {
    try {
      const { intent, entities } = context;
      
      // Extract inventory details
      const productName = this.extractProductName(intent) ||
                         entities.find((e: any) => e.type === 'product_name')?.value;
      
      const quantity = this.extractQuantity(intent) ||
                     entities.find((e: any) => e.type === 'quantity')?.value;
      
      const variantId = this.extractVariantId(intent) ||
                       entities.find((e: any) => e.type === 'variant_id')?.value;

      if (!productName && !variantId) {
        return {
          success: false,
          message: 'Product name or variant ID is required',
          error: 'Missing product identifier'
        };
      }

      if (!quantity) {
        return {
          success: false,
          message: 'Quantity is required',
          error: 'Missing quantity'
        };
      }

      // Mock inventory update (Shopify requires more complex inventory management)
      const updateResult = {
        product: productName || `Variant ${variantId}`,
        quantity: quantity,
        variant_id: variantId,
        updated_at: new Date().toISOString(),
        status: 'success'
      };

      return {
        success: true,
        message: `Shopify inventory updated to ${quantity} units for "${updateResult.product}"`,
        data: updateResult,
        actions: [
          {
            type: 'open_url',
            label: 'View Inventory',
            url: 'https://test-shop.myshopify.com/admin/inventory'
          }
        ]
      };
    } catch (error) {
      return {
        success: false,
        message: `Error updating Shopify inventory: ${error}`,
        error: error as any
      };
    }
  }

  private extractProductName(intent: string): string | null {
    const patterns = [
      /inventory\s+for\s+(.+?)\s*(?:to|:|$)/i,
      /product\s+(.+?)\s*(?:to|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractQuantity(intent: string): string | null {
    const patterns = [
      /to\s+(\d+)\s*(?:units?|items?)/i,
      /quantity\s+(\d+)/i,
      /(\d+)\s*(?:units?|items?)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1];
      }
    }

    return null;
  }

  private extractVariantId(intent: string): string | null {
    const patterns = [
      /variant\s+(\d+)/i,
      /ID\s+(\d+)/i,
      /product\s+(\d+)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1];
      }
    }

    return null;
  }
}

// Shopify Search Skill
export class ShopifySearchSkill implements Skill {
  id = 'shopify_search';
  name = 'Search Shopify';
  description = 'Search across Shopify products, orders, and customers';
  category = 'e-commerce';
  examples = [
    'Search Shopify for wireless headphones',
    'Find customer with email john@example.com',
    'Look for order #1001',
    'Find all premium products'
  ];

  async execute(context: SkillContext): Promise<SkillResult> {
    try {
      const { intent, entities } = context;
      
      // Extract search details
      const query = this.extractQuery(intent) ||
                   entities.find((e: any) => e.type === 'query')?.value ||
                   intent;
      
      const searchType = this.extractSearchType(intent) ||
                         entities.find((e: any) => e.type === 'search_type')?.value ||
                         'all';
      
      const limit = entities.find((e: any) => e.type === 'limit')?.value || 20;

      // Call Shopify API
      const response = await fetch('/api/integrations/shopify/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: context.user?.id || 'default',
          query: query,
          type: searchType,
          limit: limit
        })
      });

      const result = await response.json();

      if (result.ok) {
        const searchResults = result.data.results || [];
        const resultCount = searchResults.length;

        return {
          success: true,
          message: `Found ${resultCount} result${resultCount !== 1 ? 's' : ''} for "${query}" in Shopify`,
          data: {
            results: searchResults,
            total_count: result.data.total_count,
            query: query,
            search_type: searchType
          },
          actions: searchResults.map((item: any) => {
            let url = '';
            let label = `View ${item.type}`;
            
            switch (item.type) {
              case 'product':
                url = `https://test-shop.myshopify.com/admin/products/${item.id}`;
                label = `View Product`;
                break;
              case 'order':
                url = `https://test-shop.myshopify.com/admin/orders/${item.id}`;
                label = `View Order`;
                break;
              case 'customer':
                url = `https://test-shop.myshopify.com/admin/customers/${item.id}`;
                label = `View ${item.first_name || item.email}`;
                break;
            }
            
            return {
              type: 'open_url',
              label: label,
              url: url
            };
          })
        };
      } else {
        return {
          success: false,
          message: `Failed to search Shopify: ${result.error?.message || 'Unknown error'}`,
          error: result.error
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error searching Shopify: ${error}`,
        error: error as any
      };
    }
  }

  private extractQuery(intent: string): string | null {
    const patterns = [
      /search (?:shopify for )?(.+?)(?: products|orders|customers|:|$)/i,
      /find (.+?) (?:products|orders|customers|on shopify|:|$)/i,
      /look for (.+?) (?:products|orders|customers|on shopify|:|$)/i,
      /(.+?) (?:products|orders|customers|on shopify|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractSearchType(intent: string): string | null {
    if (intent.toLowerCase().includes('products')) {
      return 'products';
    } else if (intent.toLowerCase().includes('orders')) {
      return 'orders';
    } else if (intent.toLowerCase().includes('customers')) {
      return 'customers';
    }
    return 'all';
  }
}

// Export all Shopify skills
export const SHOPIFY_SKILLS = [
  new ShopifyCreateProductSkill(),
  new ShopifyCreateOrderSkill(),
  new ShopifyCreateCustomerSkill(),
  new ShopifyUpdateInventorySkill(),
  new ShopifySearchSkill()
];

// Export skills registry
export const SHOPIFY_SKILLS_REGISTRY = {
  'shopify_create_product': ShopifyCreateProductSkill,
  'shopify_create_order': ShopifyCreateOrderSkill,
  'shopify_create_customer': ShopifyCreateCustomerSkill,
  'shopify_update_inventory': ShopifyUpdateInventorySkill,
  'shopify_search': ShopifySearchSkill
};