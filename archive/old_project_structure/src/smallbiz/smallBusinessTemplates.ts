<file_path>
atom/src/smallbiz/smallBusinessTemplates.ts
</file_path>

// Small Business Conversational Workflow Templates
// Designed specifically for budget-conscious, time-limited small businesses

interface ConversationTemplate {
  id: string;
  name: string;
  category: string;
  triggers: string[];  // Natural language triggers
  one liners: string[]; // One-sentence setups
  estimatedBenefit: string;
  setupComplexity: 'one-click' | 'guided' | 'expert' | 'custom';
  cost: string;
  timeSave: string;
  examples: ConversationExample[];
  constraints: string[];
}

interface ConversationExample {
  userMessage: string;
  aiResponse: string;
  action: string;
  followUp?: string;
}

interface SMBIntegration {
  platforms: string[];
  tools: string[];
  budgetTier: 'free' | 'low-cost' | 'premium';
  difficulty: string;
}

export const SmallBusinessTemplates: ConversationTemplate[] = [
  {
    id: 'smb-receipt-hassle',
    name: 'Receipt & Expense Manager',
    category: 'finance',
    triggers: [
      'tired of receipts',
      'spend too much time on expenses',
      'want to track spending automatically',
      'receipt scanning',
      'expense reports'
    ],
    oneLiners: [
      'Just take photos of receipts and get weekly expense summaries',
      'Never organize receipts again - AI handles everything automatically'
    ],
    estimatedBenefit: 'Save 4+ hours/week and catch more tax deductions',
    setupComplexity: 'one-click',
    cost: '$0 (max 50 receipts/month) or $9/month unlimited',
    timeSave: '4-6 hours weekly',
    examples: [
      {
        userMessage: "I'm drowning in receipts every month. Can you help automate this?",
        aiResponse: "Absolutely! I can create a system where you just take photos of receipts and everything gets organized automatically. It'll extract amounts, categorize expenses, and even catch tax deductions you might miss. This typically saves small business owners 4-6 hours per week. Want me to set this up with a 2-minute walkthrough?",
        action: 'setup_receipt_workflow'
      },
      {
        userMessage: "Set it up to categorize by expense type and sync to my accounting",
        aiResponse: "Perfect! I'll configure the receipt scanner to automatically categorize by expense type (office supplies, travel, meals, etc.) and sync directly to your accounting software. Start by taking one photo with your phone right now to test it.",
        action: 'configure_accounting_sync'
      }
    ],
    constraints: ['Need smartphone camera', 'Accounting software connection required'],
    platforms: ['mobile_app', 'xero', 'quickbooks', 'wave']
  },

  {
    id: 'smb-customer-forget',
    name: 'Customer Relationship Follow-up',
    category: 'sales',
    triggers: [
      "forgot to follow up",
      "customers slipping away",
      "want better customer service",
      "automate thank you emails"
    ],
    oneLiners: [
      'Automatically remembers birthdays and sends follow-ups',
      'Never lose a customer due to poor follow-up again'
    ],
    estimatedBenefit: 'Increase repeat sales by 25-40% through better relationships',
    setupComplexity: 'guided',
    cost: '$0 - uses your email',
    timeSave: '3-5 hours weekly',
    examples: [
      {
        userMessage: "I keep forgetting to follow up with customers after purchases",
        aiResponse: "I'll create a smart follow-up system that automatically sends personalized thank-yous, birthday wishes, and check-in emails based on purchase dates. This usually increases repeat sales by 25-40%. You just need to connect your email - I'll handle the rest.",
        action: 'setup_customer_followup'
      },
      {
        userMessage: "Make it so it remembers each customer's preferences and purchasing history",
        aiResponse: "Great! I'll build a customer profile system that learns from every interaction. It'll remember preferences, automatically segment customers by their buying behavior, and send perfectly timed follow-ups. Ready to import your customer list?",
        action: 'enhance_customer_profiles'
      }
    ],
    constraints: ['Email integration required', 'Customer data privacy'],
    platforms: ['gmail', 'outlook', 'stripe', 'shopify']
  },

  {
    id: 'smb-social-stress',
    name: 'Social Media Autopilot',
    category: 'marketing',
    triggers: [
      "don't have time for social media",
      "inconsistent posting",
      "want social media strategy",
      "improve online presence"
    ],
    oneLiners: [
      'Auto-create and schedule posts based on trending topics',
      'Maintain
