"""
Stripe Enhanced Skills
Complete Stripe payment processing and financial management system
"""

import { Skill, SkillContext, SkillResult } from '../../../types/skillTypes';

/**
 * Stripe Enhanced Skills
 * Complete Stripe payment processing and financial management system
 */

// Payment Management Skills
export class StripeCreatePaymentSkill implements Skill {
  id = 'stripe_create_payment';
  name = 'Create Stripe Payment';
  description = 'Create a new payment in Stripe';
  category = 'financial';
  examples = [
    'Create Stripe payment for $29.99',
    'Charge customer $49.99 for premium plan',
    'Process payment of $199.99 for enterprise subscription'
  ];

  async execute(context: SkillContext): Promise<SkillResult> {
    try {
      const { intent, entities } = context;
      
      // Extract payment details
      const amount = this.extractAmount(intent) ||
                    entities.find((e: any) => e.type === 'amount')?.value;
      
      const currency = this.extractCurrency(intent) ||
                       entities.find((e: any) => e.type === 'currency')?.value ||
                       'USD';
      
      const customer = this.extractCustomer(intent) ||
                      entities.find((e: any) => e.type === 'customer')?.value;
      
      const description = this.extractDescription(intent) ||
                          entities.find((e: any) => e.type === 'description')?.value ||
                          intent;

      if (!amount) {
        return {
          success: false,
          message: 'Payment amount is required',
          error: 'Missing payment amount'
        };
      }

      // Convert amount to cents (Stripe uses smallest currency unit)
      const amountInCents = Math.round(parseFloat(amount.toString()) * 100);

      // Call Stripe API
      const response = await fetch('/api/integrations/stripe/payments', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: context.user?.id || 'default',
          operation: 'create',
          data: {
            amount: amountInCents,
            currency: currency.toLowerCase(),
            description: description,
            customer: customer,
            capture_method: 'automatic',
            metadata: {
              source: 'voice_command',
              timestamp: new Date().toISOString()
            }
          }
        })
      });

      const result = await response.json();

      if (result.ok) {
        const payment = result.data.payment;
        return {
          success: true,
          message: `Stripe payment of $${(payment.amount / 100).toFixed(2)} ${payment.currency.toUpperCase()} created successfully`,
          data: {
            payment: payment,
            client_secret: result.data.client_secret,
            amount: payment.amount,
            currency: payment.currency,
            description: payment.description,
            customer: payment.customer
          },
          actions: [
            {
              type: 'open_url',
              label: 'View Receipt',
              url: payment.receipt_url
            }
          ]
        };
      } else {
        return {
          success: false,
          message: `Failed to create Stripe payment: ${result.error?.message || 'Unknown error'}`,
          error: result.error
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error creating Stripe payment: ${error}`,
        error: error as any
      };
    }
  }

  private extractAmount(intent: string): string | null {
    const patterns = [
      /\$(\d+\.?\d*)/i,
      /(\d+\.?\d*)\s*(?:dollars?|usd)/i,
      /payment of\s*\$?(\d+\.?\d*)/i,
      /charge\s*\$?(\d+\.?\d*)/i,
      /process\s*\$?(\d+\.?\d*)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1];
      }
    }

    return null;
  }

  private extractCurrency(intent: string): string | null {
    const currencies = ['usd', 'eur', 'gbp', 'jpy', 'cad', 'aud', 'chf', 'sek', 'nok', 'dkk'];
    
    for (const currency of currencies) {
      if (intent.toLowerCase().includes(currency) || 
          intent.toLowerCase().includes(currency.toUpperCase())) {
        return currency;
      }
    }
    
    if (intent.toLowerCase().includes('dollars') || intent.toLowerCase().includes('usd')) {
      return 'USD';
    } else if (intent.toLowerCase().includes('euros') || intent.toLowerCase().includes('eur')) {
      return 'EUR';
    } else if (intent.toLowerCase().includes('pounds') || intent.toLowerCase().includes('gbp')) {
      return 'GBP';
    }
    
    return null;
  }

  private extractCustomer(intent: string): string | null {
    const patterns = [
      /customer\s+(\w+)/i,
      /for\s+(\w+)\s+customer/i,
      /(\w+)\s+customer/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1];
      }
    }

    return null;
  }

  private extractDescription(intent: string): string | null {
    const patterns = [
      /(?:for|payment|charge|process)\s+(.+?)\s*(?:\$|\d|of)/i,
      /(?:description|for)\s+(.+?)(?:\s*$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim();
      }
    }

    return intent;
  }
}

export class StripeCreateCustomerSkill implements Skill {
  id = 'stripe_create_customer';
  name = 'Create Stripe Customer';
  description = 'Create a new customer in Stripe';
  category = 'financial';
  examples = [
    'Create Stripe customer for john@example.com',
    'Add customer John Doe with email john@example.com',
    'Create customer Sarah Johnson at sarah@example.com'
  ];

  async execute(context: SkillContext): Promise<SkillResult> {
    try {
      const { intent, entities } = context;
      
      // Extract customer details
      const email = this.extractEmail(intent) ||
                   entities.find((e: any) => e.type === 'email')?.value;
      
      const name = this.extractName(intent) ||
                   entities.find((e: any) => e.type === 'name')?.value;
      
      const description = this.extractDescription(intent) ||
                         entities.find((e: any) => e.type === 'description')?.value;

      if (!email) {
        return {
          success: false,
          message: 'Customer email is required',
          error: 'Missing customer email'
        };
      }

      // Call Stripe API
      const response = await fetch('/api/integrations/stripe/customers', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: context.user?.id || 'default',
          operation: 'create',
          data: {
            email: email,
            name: name,
            description: description,
            metadata: {
              source: 'voice_command',
              created_at: new Date().toISOString()
            }
          }
        })
      });

      const result = await response.json();

      if (result.ok) {
        const customer = result.data.customer;
        return {
          success: true,
          message: `Stripe customer "${customer.name || customer.email}" created successfully`,
          data: {
            customer: customer,
            email: customer.email,
            name: customer.name,
            description: customer.description,
            customer_id: customer.id
          },
          actions: [
            {
              type: 'open_url',
              label: 'View Customer',
              url: `https://dashboard.stripe.com/customers/${customer.id}`
            }
          ]
        };
      } else {
        return {
          success: false,
          message: `Failed to create Stripe customer: ${result.error?.message || 'Unknown error'}`,
          error: result.error
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error creating Stripe customer: ${error}`,
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
      /(\w+(?:\s+\w+)?)\s+customer/i,
      /create\s+(\w+(?:\s+\w+)?)\s+with/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1];
      }
    }

    return null;
  }

  private extractDescription(intent: string): string | null {
    const patterns = [
      /(?:customer|add|create)\s+(.+?)\s*(?:with|for|email)/i,
      /(?:with|for)\s+(.+?)\s*(?:email|customer)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim();
      }
    }

    return null;
  }
}

export class StripeCreateSubscriptionSkill implements Skill {
  id = 'stripe_create_subscription';
  name = 'Create Stripe Subscription';
  description = 'Create a new subscription in Stripe';
  category = 'financial';
  examples = [
    'Create Stripe subscription for premium plan',
    'Start subscription for customer John Doe with basic plan',
    'Create monthly subscription for enterprise tier'
  ];

  async execute(context: SkillContext): Promise<SkillResult> {
    try {
      const { intent, entities } = context;
      
      // Extract subscription details
      const customer = this.extractCustomer(intent) ||
                      entities.find((e: any) => e.type === 'customer')?.value;
      
      const plan = this.extractPlan(intent) ||
                  entities.find((e: any) => e.type === 'plan')?.value;
      
      const amount = this.extractAmount(intent) ||
                    entities.find((e: any) => e.type === 'amount')?.value;
      
      const interval = this.extractInterval(intent) ||
                      entities.find((e: any) => e.type === 'interval')?.value ||
                      'month';

      if (!customer) {
        return {
          success: false,
          message: 'Customer is required for subscription',
          error: 'Missing customer'
        };
      }

      // Call Stripe API
      const response = await fetch('/api/integrations/stripe/subscriptions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: context.user?.id || 'default',
          operation: 'create',
          data: {
            customer: customer,
            items: [{
              price_data: {
                currency: 'usd',
                unit_amount: amount ? Math.round(parseFloat(amount.toString()) * 100) : 2999,
                recurring: {
                  interval: interval
                },
                product_data: {
                  name: plan || 'Premium Plan',
                  description: `Subscription for ${plan || 'premium'}`
                }
              }
            }],
            description: `${plan || 'Premium'} subscription`,
            metadata: {
              source: 'voice_command',
              plan: plan || 'premium',
              created_at: new Date().toISOString()
            }
          }
        })
      });

      const result = await response.json();

      if (result.ok) {
        const subscription = result.data.subscription;
        return {
          success: true,
          message: `Stripe subscription for "${plan || 'Premium'}" created successfully`,
          data: {
            subscription: subscription,
            customer: subscription.customer,
            plan: plan || 'Premium',
            interval: interval,
            amount: amount || '29.99',
            subscription_id: subscription.id
          },
          actions: [
            {
              type: 'open_url',
              label: 'View Subscription',
              url: `https://dashboard.stripe.com/subscriptions/${subscription.id}`
            }
          ]
        };
      } else {
        return {
          success: false,
          message: `Failed to create Stripe subscription: ${result.error?.message || 'Unknown error'}`,
          error: result.error
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error creating Stripe subscription: ${error}`,
        error: error as any
      };
    }
  }

  private extractCustomer(intent: string): string | null {
    const patterns = [
      /customer\s+(\w+)/i,
      /for\s+(\w+)\s+customer/i,
      /(\w+)\s+customer/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1];
      }
    }

    return null;
  }

  private extractPlan(intent: string): string | null {
    const plans = ['basic', 'premium', 'enterprise', 'starter', 'pro', 'business'];
    
    for (const plan of plans) {
      if (intent.toLowerCase().includes(plan)) {
        return plan;
      }
    }
    
    return null;
  }

  private extractAmount(intent: string): string | null {
    const patterns = [
      /\$(\d+\.?\d*)/i,
      /(\d+\.?\d*)\s*(?:dollars?|usd)/i,
      /plan\s+of\s*\$?(\d+\.?\d*)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1];
      }
    }

    return null;
  }

  private extractInterval(intent: string): string | null {
    if (intent.toLowerCase().includes('monthly') || intent.toLowerCase().includes('month')) {
      return 'month';
    } else if (intent.toLowerCase().includes('yearly') || intent.toLowerCase().includes('year') || intent.toLowerCase().includes('annual')) {
      return 'year';
    } else if (intent.toLowerCase().includes('weekly') || intent.toLowerCase().includes('week')) {
      return 'week';
    }
    
    return 'month';
  }
}

// Product Management Skills
export class StripeCreateProductSkill implements Skill {
  id = 'stripe_create_product';
  name = 'Create Stripe Product';
  description = 'Create a new product in Stripe';
  category = 'financial';
  examples = [
    'Create Stripe product for premium plan',
    'Add product called Enterprise Dashboard',
    'Create product Basic Software License'
  ];

  async execute(context: SkillContext): Promise<SkillResult> {
    try {
      const { intent, entities } = context;
      
      // Extract product details
      const productName = this.extractProductName(intent) ||
                         entities.find((e: any) => e.type === 'product_name')?.value;
      
      const description = this.extractDescription(intent) ||
                         entities.find((e: any) => e.type === 'description')?.value ||
                         intent;

      if (!productName) {
        return {
          success: false,
          message: 'Product name is required',
          error: 'Missing product name'
        };
      }

      // Call Stripe API
      const response = await fetch('/api/integrations/stripe/products', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: context.user?.id || 'default',
          operation: 'create',
          data: {
            name: productName,
            description: description,
            active: true,
            type: 'service',
            metadata: {
              source: 'voice_command',
              created_at: new Date().toISOString()
            }
          }
        })
      });

      const result = await response.json();

      if (result.ok) {
        const product = result.data.product;
        return {
          success: true,
          message: `Stripe product "${product.name}" created successfully`,
          data: {
            product: product,
            name: product.name,
            description: product.description,
            product_id: product.id
          },
          actions: [
            {
              type: 'open_url',
              label: 'View Product',
              url: `https://dashboard.stripe.com/products/${product.id}`
            }
          ]
        };
      } else {
        return {
          success: false,
          message: `Failed to create Stripe product: ${result.error?.message || 'Unknown error'}`,
          error: result.error
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error creating Stripe product: ${error}`,
        error: error as any
      };
    }
  }

  private extractProductName(intent: string): string | null {
    const patterns = [
      /create (?:stripe )?product (?:called|named) (.+?)(?: for|with|:|$)/i,
      /add product (?:called|named) (.+?)(?: for|with|:|$)/i,
      /product (?:called|named) (.+?)(?: for|with|:|$)/i
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
      /(?:for|with) (.+?)(?: product|:|$)/i,
      /description (.+?)(?: product|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return intent;
  }
}

// Stripe Search Skill
export class StripeSearchSkill implements Skill {
  id = 'stripe_search';
  name = 'Search Stripe';
  description = 'Search across Stripe payments, customers, subscriptions, and products';
  category = 'financial';
  examples = [
    'Search Stripe for John Doe',
    'Find customer with email john@example.com',
    'Look for subscription payment of $29.99',
    'Find all premium plan products'
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

      // Call Stripe API
      const response = await fetch('/api/integrations/stripe/search', {
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
          message: `Found ${resultCount} result${resultCount !== 1 ? 's' : ''} for "${query}" in Stripe`,
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
              case 'payment':
                url = `https://dashboard.stripe.com/payments/${item.id}`;
                break;
              case 'customer':
                url = `https://dashboard.stripe.com/customers/${item.id}`;
                label = `View ${item.name || item.email}`;
                break;
              case 'subscription':
                url = `https://dashboard.stripe.com/subscriptions/${item.id}`;
                break;
              case 'product':
                url = `https://dashboard.stripe.com/products/${item.id}`;
                label = `View ${item.name}`;
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
          message: `Failed to search Stripe: ${result.error?.message || 'Unknown error'}`,
          error: result.error
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error searching Stripe: ${error}`,
        error: error as any
      };
    }
  }

  private extractQuery(intent: string): string | null {
    const patterns = [
      /search (?:stripe for )?(.+?)(?: payments|customers|subscriptions|products|:|$)/i,
      /find (.+?) (?:payments|customers|subscriptions|products|on stripe|:|$)/i,
      /look for (.+?) (?:payments|customers|subscriptions|products|on stripe|:|$)/i,
      /(.+?) (?:payments|customers|subscriptions|products|on stripe|:|$)/i
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
    if (intent.toLowerCase().includes('payments')) {
      return 'payments';
    } else if (intent.toLowerCase().includes('customers') || intent.toLowerCase().includes('customer')) {
      return 'customers';
    } else if (intent.toLowerCase().includes('subscriptions') || intent.toLowerCase().includes('subscription')) {
      return 'subscriptions';
    } else if (intent.toLowerCase().includes('products') || intent.toLowerCase().includes('product')) {
      return 'products';
    }
    return 'all';
  }
}

// Export all Stripe skills
export const STRIPE_SKILLS = [
  new StripeCreatePaymentSkill(),
  new StripeCreateCustomerSkill(),
  new StripeCreateSubscriptionSkill(),
  new StripeCreateProductSkill(),
  new StripeSearchSkill()
];

// Export skills registry
export const STRIPE_SKILLS_REGISTRY = {
  'stripe_create_payment': StripeCreatePaymentSkill,
  'stripe_create_customer': StripeCreateCustomerSkill,
  'stripe_create_subscription': StripeCreateSubscriptionSkill,
  'stripe_create_product': StripeCreateProductSkill,
  'stripe_search': StripeSearchSkill
};