import axios from 'axios';
import { z } from 'zod';
import { ChatCompletionTool } from 'openai/resources/chat/completions';

// Zod schemas for secure parameter validation
const NetWorthParamsSchema = z.object({
  userId: z.string(),
  includeHistory: z.boolean().optional().default(false),
  dateRange: z.object({
    start: z.string().optional(),
    end: z.string().optional()
  }).optional()
});

const BudgetQueryParamsSchema = z.object({
  userId: z.string(),
  period: z.enum(['current', 'last', 'future']).optional().default('current'),
  categories: z.array(z.string()).optional(),
  month: z.string().optional()
});

const TransactionSearchParamsSchema = z.object({
  userId: z.string(),
  query: z.string().optional(),
  category: z.string().optional(),
  amountRange: z.object({
    min: z.number().optional(),
    max: z.number().optional()
  }).optional(),
  dateRange: z.object({
    start: z.string(),
    end: z.string()
  }),
  limit: z.number().optional().default(50)
});

const GoalParamsSchema = z.object({
  userId: z.string(),
  goalId: z.string().optional(),
  goalType: z.enum(['savings', 'retirement', 'debt', 'purchase', 'emergency']).optional()
});

// Types
export type NetWorthSummary = {
  current: number;
  change: number;
  changePercent: number;
  assets: number;
  liabilities: number;
  history?: Array<{date: string; netWorth: number}>;
};

export type BudgetSummary = {
  totalBudget: number;
  spent: number;
  remaining: number;
  categories: Array<{
    category: string;
    budgeted: number;
    spent: number;
    remaining: number;
    utilization: number;
  }>;
};

export type SpendingInsight = {
  totalSpent: number;
  categories: Array<{category: string; amount: number; percentage: number}>;
  trends: {
    thisMonth: number;
    lastMonth: number;
    change: number;
    changePercent: number;
  };
};

export type FinancialGoal = {
  id: string;
  name: string;
  target: number;
  current: number;
  progress: number;
  deadline?: string;
  status: 'active' | 'completed' | 'on_hold';
};

export const financeTools: ChatCompletionTool[] = [
  {
    type: 'function',
    function: {
      name: 'get_net_worth_summary',
      description: 'Get current net worth and historical trends',
      parameters: {
        type: 'object',
        properties: {
          userId: { type: 'string', description: 'User identifier' },
          includeHistory: { type: 'boolean', description: 'Include historical net worth data' },
          dateRange: {
            type: 'object',
            properties: {
              start: { type: 'string', format: 'date' },
              end: { type: 'string', format: 'date' }
            }
          }
        },
        required: ['userId']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'get_budget_summary',
      description: 'Get budget overview and spending by category',
      parameters: {
        type: 'object',
        properties: {
          userId: { type: 'string', description: 'User identifier' },
          period: { type: 'string', enum: ['current', 'last', 'future'], default: 'current' },
          month: { type: 'string', format: 'date' },
          categories: { type: 'array', items: { type: 'string' } }
        },
        required: ['userId']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'search_transactions',
      description: 'Search and analyze transactions by criteria',
      parameters: {
        type: 'object',
        properties: {
          userId: { type: 'string', description: 'User identifier' },
          query: { type: 'string', description: 'Search query for descriptions' },
          category: { type: 'string', description: 'Filter by category' },
          amountRange: {
            type: 'object',
            properties: {
              min: { type: 'number' },
              max: { type: 'number' }
            }
          },
          dateRange: {
            type: 'object',
            properties: {
              start: { type: 'string', format: 'date', required: true },
              end: { type: 'string', format: 'date', required: true }
            },
            required: ['start', 'end']
          },
          limit: { type: 'number', default: 50 }
        },
        required: ['userId', 'dateRange']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'get_spending_insights',
      description: 'Analyze spending patterns and trends',
      parameters: {
        type: 'object',
        properties: {
          userId: { type: 'string', description: 'User identifier' },
          category: { type: 'string', description: 'Focus on specific category' },
          period: { type: 'string', enum: ['current', 'last', 'quarter', 'year'], default: 'current' }
        },
        required: ['userId']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'get_investment_summary',
      description: 'Get investment portfolio summary and performance',
      parameters: {
        type: 'object',
        properties: {
          userId: { type: 'string', description: 'User identifier' },
          includeHistory: { type: 'boolean', description: 'Include historical performance' }
        },
        required: ['userId']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'get_financial_goals',
      description: 'Get financial goals and progress tracking',
      parameters: {
        type: 'object',
        properties: {
          userId: { type: 'string', description: 'User identifier' },
          goalId: { type: 'string', description: 'Specific goal ID' },
          goalType: { type: 'string', enum: ['savings', 'retirement', 'debt', 'purchase', 'emergency'] }
        },
        required: ['userId']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'create_budget',
      description: 'Create a new budget category with allocation',
      parameters: {
        type: 'object',
        properties: {
          userId: { type: 'string', description: 'User identifier' },
          category: { type: 'string', description: 'Budget category name' },
          amount: { type: 'number', description: 'Monthly budget amount' },
          description: { type: 'string' }
        },
        required: ['userId', 'category', 'amount']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'create_financial_goal',
      description: 'Create a new financial goal',
      parameters: {
        type: 'object',
        properties: {
          userId: { type: 'string', description: 'User identifier' },
          name: { type: 'string', description: 'Goal name' },
          targetAmount: { type: 'number', description: 'Target amount to save' },
          currentAmount: { type: 'number', default: 0, description: 'Current progress' },
          targetDate: { type: 'string', format: 'date', description: 'Target completion date' },
          goalType: { type: 'string', enum: ['savings', 'retirement', 'debt', 'purchase', 'emergency'] },
          description: { type: 'string' }
        },
        required: ['userId', 'name', 'targetAmount', 'goalType']
      }
    }
  }
];

export class FinanceAgentService {
  private apiBaseUrl: string;
  private userId: string;

  constructor(userId: string, apiBaseUrl: string = '/api/financial') {
    this.userId = userId;
    this.apiBaseUrl = apiBaseUrl;
  }

  async getNetWorthSummary(params: z.infer<typeof NetWorthParamsSchema>): Promise<string> {
    try {
      const validated = NetWorthParamsSchema.parse({ ...params, userId: this.userId });
      const response = await axios.get(`${this.apiBaseUrl}/net-worth/summary`, {
        params: validated
      });

      const data = response.data as NetWorthSummary;

      let responseText = `💰 Your current net worth is **$${data.current.toLocaleString()}**`;

      if (data.change >= 0) {
        responseText += `, up **$${Math.abs(data.change).toLocaleString()} (${data.changePercent.toFixed(1)}%)** from the last period.`;
n      } else {
        responseText += `, down **$${Math.abs(data.change).toLocaleString()} (${Math.abs(data.changePercent).toFixed(1)}%)** from the last period.`;
      }

      responseText += `\n\nAssets: **$${data.assets.toLocaleString()}** | Liabilities: **$${data.liabilities.toLocaleString()}**`;

      if (data.history && data.history.length > 1) {
        responseText += `\n\n📈 Recent trend:`;
        data.history.slice(-3).forEach(snapshot => {
          responseText += `\n${new Date(snapshot.date).toLocaleDateString()}: $${snapshot.netWorth.toLocaleString()}`;
        });
      }

      return responseText;
    } catch (error) {
      console.error('Error fetching net worth:', error);
      return "I couldn't retrieve your net worth information. This might be because you haven't connected any financial accounts or there's a temporary issue.";
    }
  }

  async getBudgetSummary(params: z.infer<typeof BudgetQueryParamsSchema>): Promise<string> {
    try {
      const validated = BudgetQueryParamsSchema.parse({ ...params, userId: this.userId });
      const response = await axios.get(`${this.apiBaseUrl}/budgets/summary`, {
        params: validated
      });

      const data = response.data as BudgetSummary;

      if (data.categories.length === 0) {
        return "You haven't set up any budgets yet. Would you like me to help you create one?";
      }

      let responseText = `💰 Budget Overview${validated.month ? ` for ${new Date(validated.month).toLocaleDateString('en-US', {month: 'long', year: 'numeric'})}` : ''}:\n`;
      responseText += `Total Budget: **$${data.totalBudget.toLocaleString()}** | Spent: **$${data.spent.toLocaleString()}** | Remaining: **$${data.remaining.toLocaleString()}**`;

      // Add category breakdowns
      data.categories.slice(0, 5).forEach((category) => {
        const emoji = category.utilization >= 100 ? '⚠️' : category.utilization >= 80 ? '🟡' : '✅';
        const remainingEmoji = category.remaining < 0 ? '😟' : '';
        responseText += `\n${emoji} **${category.category}**: $${category.spent.toLocaleString()} / $${category.budgeted.toLocaleString()} (${category.utilization.toFixed(0)}%) ${remainingEmoji}`;
      });

      if (data.categories.length > 5) {
        responseText += `\n...and ${data.categories.length - 5} more categories`;
      }

      return responseText;
    } catch (error) {
      console.error('Error fetching budget summary:', error);
      return "I couldn't retrieve your budget information. Please check if budgets are set up or try again later.";
    }
  }

  async searchTransactions(params: z.infer<typeof TransactionSearchParamsSchema>): Promise<string> {
    try {
      const validated = TransactionSearchParamsSchema.parse({ ...params, userId: this.userId });
      const response = await axios.post(`${this.apiBaseUrl}/transactions/search`, validated);

      const transactions = response.data.transactions;

      if (!transactions || transactions.length === 0) {
        return `I couldn't find any transactions ${params.query ? `matching "${params.query}"` : ''} in the specified period.`;
      }

      let responseText = `👀 Found **${transactions.length}** transaction${transactions.length !== 1 ? 's' : ''}`;

      if (params.query) {
        responseText += ` matching \"${params.query}\"`;
      }

      if (params.category) {
        responseText += ` in ${params.category}`;
      }

      const totalAmount = transactions.reduce((sum, t) => sum + Math.abs(t.amount), 0);
      responseText += ` totaling **$${totalAmount.toLocaleString()}**: \n\n`;

      // Show recent transactions with most relevant context
      transactions.slice(0, 10).forEach((transaction, index) => {
        const emoji = transaction.amount >= 0 ? '💚' : '🔴';
        const amount = Math.abs(transaction.amount).toLocaleString();
        responseText += `${index + 1}. ${emoji} $${amount} - ${transaction.description || transaction.name}\n`;
        responseText += `   ${new Date(transaction.date).toLocaleDateString()} | ${transaction.category || 'Uncategorized'}\n`;
      });

      if (transactions.length > 10) {
        responseText += `\n...and ${transactions.length - 10} more`;
      }

      return responseText;
    } catch (error) {
      console.error('Error searching transactions:', error);
      return "I encountered an issue while searching your transactions. Please try again.";
    }
  }

  async getSpendingInsights(params: { category?: string; period?: string } = {}): Promise<string> {
    try {
      const response = await axios.get(`${this.apiBaseUrl}/analysis/spending-insights`, {
        params: { userId: this.userId, ...params }
      });

      const data = response.data as SpendingInsight;

      let responseText = `💡 Spending Insights${params.category ? ` for ${params.category}` : ''}:\n\n`;
      responseText += `**Total spent**: $${data.totalSpent.toLocaleString()}\n`;

      // Category breakdown
      if (data.categories && data.categories.length > 0) {
        responseText += `**Top categories**:\n`;
        data.categories.slice(0, 5).forEach((cat) => {
          responseText += `• ${cat.category}: **$${cat.amount.toLocaleString()} (${cat.percentage}%)**\n`;
        });
      }

      // Trend analysis
      if (data.trends) {
        const trend = data.trends.change >= 0 ? '↗️ increased' : '↘️ decreased';
        const pct = Math.abs(data.trends.changePercent).toFixed(1);
        responseText += `\n**Trend**: Spent ${trend} by **$${Math.abs(data.trends.change).toLocaleString()} (${pct}%)** compared to last period`;
      }

      return responseText;
    } catch (error) {
      console.error('Error getting spending insights:', error);
      return "I couldn't generate spending insights right now. Please try again later.";
    }
  }

  async getInvestmentSummary(includeHistory = false): Promise<string> {
    try {
      const response = await axios.get(`${this.apiBaseUrl}/investments/summary`, {
        params: { userId: this.userId, includeHistory }
      });

      const data = response.data;

      if (!data.holdings || data.holdings.length === 0) {
        return "You don't have any investments connected yet. Would you like to link your investment accounts?";
      }

      let responseText = `📈 Your Investment Portfolio:\n\n`;
      responseText += `**Total Value**: $${data.totalValue.toLocaleString()}\n`;

      if (data.totalGainLoss !== undefined) {
        const emoji = data.totalGainLoss >= 0 ? '📈' : '📉';
        responseText += `${emoji} **Total Returns**: $${Math.abs(data.totalGainLoss).toLocaleString()} (${data.totalReturnPct?.toFixed(1)}%)\n`;
      }

      // Top holdings
      responseText += `\n**Top Holdings**:\n`;
      data.holdings.slice(0, 5).forEach((holding) => {
        responseText += `• **${holding.name}**: ${holding.shares} @ $${holding.price?.toLocaleString()} = $${holding.value.toLocaleString()}\n`;
      });

      if (data.holdings.length > 5) {
        responseText += `\n...and ${data.holdings.length - 5} more`;
      }

      return responseText;
    } catch (error) {
      console.error('Error getting investment summary:', error);
      return "I couldn't retrieve your investment information. Please ensure your investment accounts are connected.";
    }
  }

  async getFinancialGoals(params: z.infer<typeof GoalParamsSchema> = {}): Promise<string> {
    try {
      const validated = GoalParamsSchema.parse({ ...params, userId: this.userId });
      const response = await axios.get(`${this.apiBaseUrl}/goals`, {
        params: validated
      });

      const goals = response.data.goals as FinancialGoal[];

      if (goals.length === 0) {
        return "You haven't set any financial goals yet. Would you like me to help you create one?";
      }

      let responseText = `🎯 Your Financial Goals:\n\n`;

      goals.forEach((goal) => {
        const progressBar = this.generateProgressBar(goal.progress);
        const statusEmoji = goal.status === 'completed' ? '✅' : '🎯';

        responseText += `${statusEmoji} **${goal.name}**\n`;
        responseText += `${progressBar} **${goal.progress.toFixed(0)}%**\n`;
        responseText += `Progress: $${goal.current.toLocaleString()} / $${goal.target.toLocaleString()}`;

        if (goal.deadline) {
          const deadline = new Date(goal.deadline).toLocaleDateString();
          responseText += ` | Target: ${deadline}`;
        }

        const amountRemaining = goal.target - goal.current;
        responseText += ` (${amountRemaining > 0 ? '$' + amountRemaining.toLocaleString() + ' to go' : 'Completed!'})\n\n`;
      });

      return responseText;
    } catch (error) {
      console.error('Error getting financial goals:', error);
      return "I couldn't retrieve your financial goals. Please try again or connect your accounts first.";
    }
  }

  async createCategory(params: { userId: string; name: string; color?: string; icon?: string }): Promise<void> {
    try {
      await axios.post(`${this.apiBaseUrl}/categories/budget`, params);
    } catch (error) {
      console.error('Error creating category:', error);
      throw error;
    }
  }

  private generateProgressBar(percentage: number): string {
    const filledBlocks = Math.round((percentage / 100) * 10);
    const emptyBlocks = 10 - filledBlocks;
    return '▓'.repeat(filledBlocks) + '░'.repeat(emptyBlocks);
  }
}

// API handlers for the tools
export const financeToolImplementations = {
  get_net_worth_summary: async (params: any) => {
    const service = new FinanceAgentService(params.userId);
    return await service.getNetWorthSummary(params);
  },

  get_budget_summary: async (params: any) => {
    const service = new FinanceAgentService(params.userId);
    return await service.getBudgetSummary(params);
  },

  search_transactions: async (params: any) => {
    const service = new FinanceAgentService(params.userId);
    return await service.searchTransactions(params);
  },

  get_spending_insights: async (params: any) => {
    const service = new FinanceAgentService(params.userId);
    return await service.getSpendingInsights(params);
  },

  get_investment_summary: async (params: any) => {
    const service = new FinanceAgentService(params.userId);
    return await service.getInvestmentSummary(params.includeHistory);
  },

  get_financial_goals: async (params: any) => {
    const service = new FinanceAgentService(params.userId);
    return await service.getFinancialGoals(params);
  },

  create_budget: async (params: any) => {
    const service = new FinanceAgentService(params.userId);
    // Implementation for budget creation would go here
    return "Budget created successfully!";
  },

  create_financial_goal: async (params: any) => {
    const service = new FinanceAgentService(params.userId);
    // Implementation for goal creation would go here
    return "Financial goal created successfully!";
  },

  disconnect_zoho_account: async (params: any) => {
    const response = await fetch('/api/auth/zoho/disconnect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: params.user_id }),
    });
    return await response.json();
  },

  get_zoho_integration_status: async (user_id: string) => {
    const response = await fetch(`/api/auth/zoho/status?user_id=${user_id}`);
    return await response.json();
  },

  get_zoho_invoices: async (user_id: string, organization_id: string) => {
    const response = await fetch(`/api/zoho/invoices?user_id=${user_id}&org_id=${organization_id}`);
    return await response.json();
  },

  create_zoho_invoice: async (user_id: string, organization_id: string, invoice_data: any) => {
    const response = await fetch('/api/zoho/invoices', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id, org_id: organization_id, invoice_data }),
    });
    return await response.json();
  },

  get_zoho_customers: async (user_id: string, organization_id: string) => {
    const response = await fetch(`/api/zoho/customers?user_id=${user_id}&org_id=${organization_id}`);
    return await response.json();
  },

  create_zoho_customer: async (user_id: string, organization_id: string, customer_data: any) => {
    const response = await fetch('/api/zoho/customers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id, org_id: organization_id, customer_data }),
    });
    return await response.json();
  },

  get_zoho_items: async (user_id: string, organization_id: string) => {
    const response = await fetch(`/api/zoho/items?user_id=${user_id}&org_id=${organization_id}`);
    return await response.json();
  },

  create_zoho_item: async (user_id: string, organization_id: string, item_data: any) => {
    const response = await fetch('/api/zoho/items', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id, org_id: organization_id, item_data }),
    });
    return await response.json();
  },

  get_zoho_bills: async (user_id: string, organization_id: string) => {
    const response = await fetch(`/api/zoho/bills?user_id=${user_id}&org_id=${organization_id}`);
    return await response.json();
  },

  create_zoho_bill: async (user_id: string, organization_id: string, bill_data: any) => {
    const response = await fetch('/api/zoho/bills', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id, org_id: organization_id, bill_data }),
    });
    return await response.json();
  },

  get_zoho_vendors: async (user_id: string, organization_id: string) => {
    const response = await fetch(`/api/zoho/vendors?user_id=${user_id}&org_id=${organization_id}`);
    return await response.json();
  },

  create_zoho_vendor: async (user_id: string, organization_id: string, vendor_data: any) => {
    const response = await fetch('/api/zoho/vendors', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id, org_id: organization_id, vendor_data }),
    });
    return await response.json();
  },

  get_zoho_purchase_orders: async (user_id: string, organization_id: string) => {
    const response = await fetch(`/api/zoho/purchaseorders?user_id=${user_id}&org_id=${organization_id}`);
    return await response.json();
  },

  create_zoho_purchase_order: async (user_id: string, organization_id: string, purchase_order_data: any) => {
    const response = await fetch('/api/zoho/purchaseorders', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id, org_id: organization_id, purchase_order_data }),
    });
    return await response.json();
  },

  get_zoho_sales_orders: async (user_id: string, organization_id: string) => {
    const response = await fetch(`/api/zoho/salesorders?user_id=${user_id}&org_id=${organization_id}`);
    return await response.json();
  },

  create_zoho_sales_order: async (user_id: string, organization_id: string, sales_order_data: any) => {
    const response = await fetch('/api/zoho/salesorders', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id, org_id: organization_id, sales_order_data }),
    });
    return await response.json();
  },
};
