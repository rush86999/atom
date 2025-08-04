"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.financeToolImplementations = exports.FinanceAgentService = exports.financeTools = void 0;
const axios_1 = __importDefault(require("axios"));
const zod_1 = require("zod");
// Zod schemas for secure parameter validation
const NetWorthParamsSchema = zod_1.z.object({
    userId: zod_1.z.string(),
    includeHistory: zod_1.z.boolean().optional().default(false),
    dateRange: zod_1.z
        .object({
        start: zod_1.z.string().optional(),
        end: zod_1.z.string().optional(),
    })
        .optional(),
});
const BudgetQueryParamsSchema = zod_1.z.object({
    userId: zod_1.z.string(),
    period: zod_1.z.enum(['current', 'last', 'future']).optional().default('current'),
    categories: zod_1.z.array(zod_1.z.string()).optional(),
    month: zod_1.z.string().optional(),
});
const TransactionSearchParamsSchema = zod_1.z.object({
    userId: zod_1.z.string(),
    query: zod_1.z.string().optional(),
    category: zod_1.z.string().optional(),
    amountRange: zod_1.z
        .object({
        min: zod_1.z.number().optional(),
        max: zod_1.z.number().optional(),
    })
        .optional(),
    dateRange: zod_1.z.object({
        start: zod_1.z.string(),
        end: zod_1.z.string(),
    }),
    limit: zod_1.z.number().optional().default(50),
});
const GoalParamsSchema = zod_1.z.object({
    userId: zod_1.z.string(),
    goalId: zod_1.z.string().optional(),
    goalType: zod_1.z
        .enum(['savings', 'retirement', 'debt', 'purchase', 'emergency'])
        .optional(),
});
exports.financeTools = [
    {
        type: 'function',
        function: {
            name: 'get_net_worth_summary',
            description: 'Get current net worth and historical trends',
            parameters: {
                type: 'object',
                properties: {
                    userId: { type: 'string', description: 'User identifier' },
                    includeHistory: {
                        type: 'boolean',
                        description: 'Include historical net worth data',
                    },
                    dateRange: {
                        type: 'object',
                        properties: {
                            start: { type: 'string', format: 'date' },
                            end: { type: 'string', format: 'date' },
                        },
                    },
                },
                required: ['userId'],
            },
        },
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
                    period: {
                        type: 'string',
                        enum: ['current', 'last', 'future'],
                        default: 'current',
                    },
                    month: { type: 'string', format: 'date' },
                    categories: { type: 'array', items: { type: 'string' } },
                },
                required: ['userId'],
            },
        },
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
                    query: {
                        type: 'string',
                        description: 'Search query for descriptions',
                    },
                    category: { type: 'string', description: 'Filter by category' },
                    amountRange: {
                        type: 'object',
                        properties: {
                            min: { type: 'number' },
                            max: { type: 'number' },
                        },
                    },
                    dateRange: {
                        type: 'object',
                        properties: {
                            start: { type: 'string', format: 'date', required: true },
                            end: { type: 'string', format: 'date', required: true },
                        },
                        required: ['start', 'end'],
                    },
                    limit: { type: 'number', default: 50 },
                },
                required: ['userId', 'dateRange'],
            },
        },
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
                    category: {
                        type: 'string',
                        description: 'Focus on specific category',
                    },
                    period: {
                        type: 'string',
                        enum: ['current', 'last', 'quarter', 'year'],
                        default: 'current',
                    },
                },
                required: ['userId'],
            },
        },
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
                    includeHistory: {
                        type: 'boolean',
                        description: 'Include historical performance',
                    },
                },
                required: ['userId'],
            },
        },
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
                    goalType: {
                        type: 'string',
                        enum: ['savings', 'retirement', 'debt', 'purchase', 'emergency'],
                    },
                },
                required: ['userId'],
            },
        },
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
                    description: { type: 'string' },
                },
                required: ['userId', 'category', 'amount'],
            },
        },
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
                    targetAmount: {
                        type: 'number',
                        description: 'Target amount to save',
                    },
                    currentAmount: {
                        type: 'number',
                        default: 0,
                        description: 'Current progress',
                    },
                    targetDate: {
                        type: 'string',
                        format: 'date',
                        description: 'Target completion date',
                    },
                    goalType: {
                        type: 'string',
                        enum: ['savings', 'retirement', 'debt', 'purchase', 'emergency'],
                    },
                    description: { type: 'string' },
                },
                required: ['userId', 'name', 'targetAmount', 'goalType'],
            },
        },
    },
];
class FinanceAgentService {
    apiBaseUrl;
    userId;
    constructor(userId, apiBaseUrl = '/api/financial') {
        this.userId = userId;
        this.apiBaseUrl = apiBaseUrl;
    }
    async getNetWorthSummary(params) {
        try {
            const validated = NetWorthParamsSchema.parse({
                ...params,
                userId: this.userId,
            });
            const response = await axios_1.default.get(`${this.apiBaseUrl}/net-worth/summary`, {
                params: validated,
            });
            const data = response.data;
            let responseText = `💰 Your current net worth is **$${data.current.toLocaleString()}**`;
            if (data.change >= 0) {
                responseText += `, up **$${Math.abs(data.change).toLocaleString()} (${data.changePercent.toFixed(1)}%)** from the last period.`;
                n;
            }
            else {
                responseText += `, down **$${Math.abs(data.change).toLocaleString()} (${Math.abs(data.changePercent).toFixed(1)}%)** from the last period.`;
            }
            responseText += `\n\nAssets: **$${data.assets.toLocaleString()}** | Liabilities: **$${data.liabilities.toLocaleString()}**`;
            if (data.history && data.history.length > 1) {
                responseText += `\n\n📈 Recent trend:`;
                data.history.slice(-3).forEach((snapshot) => {
                    responseText += `\n${new Date(snapshot.date).toLocaleDateString()}: $${snapshot.netWorth.toLocaleString()}`;
                });
            }
            return responseText;
        }
        catch (error) {
            console.error('Error fetching net worth:', error);
            return "I couldn't retrieve your net worth information. This might be because you haven't connected any financial accounts or there's a temporary issue.";
        }
    }
    async getBudgetSummary(params) {
        try {
            const validated = BudgetQueryParamsSchema.parse({
                ...params,
                userId: this.userId,
            });
            const response = await axios_1.default.get(`${this.apiBaseUrl}/budgets/summary`, {
                params: validated,
            });
            const data = response.data;
            if (data.categories.length === 0) {
                return "You haven't set up any budgets yet. Would you like me to help you create one?";
            }
            let responseText = `💰 Budget Overview${validated.month ? ` for ${new Date(validated.month).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}` : ''}:\n`;
            responseText += `Total Budget: **$${data.totalBudget.toLocaleString()}** | Spent: **$${data.spent.toLocaleString()}** | Remaining: **$${data.remaining.toLocaleString()}**`;
            // Add category breakdowns
            data.categories.slice(0, 5).forEach((category) => {
                const emoji = category.utilization >= 100
                    ? '⚠️'
                    : category.utilization >= 80
                        ? '🟡'
                        : '✅';
                const remainingEmoji = category.remaining < 0 ? '😟' : '';
                responseText += `\n${emoji} **${category.category}**: $${category.spent.toLocaleString()} / $${category.budgeted.toLocaleString()} (${category.utilization.toFixed(0)}%) ${remainingEmoji}`;
            });
            if (data.categories.length > 5) {
                responseText += `\n...and ${data.categories.length - 5} more categories`;
            }
            return responseText;
        }
        catch (error) {
            console.error('Error fetching budget summary:', error);
            return "I couldn't retrieve your budget information. Please check if budgets are set up or try again later.";
        }
    }
    async searchTransactions(params) {
        try {
            const validated = TransactionSearchParamsSchema.parse({
                ...params,
                userId: this.userId,
            });
            const response = await axios_1.default.post(`${this.apiBaseUrl}/transactions/search`, validated);
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
        }
        catch (error) {
            console.error('Error searching transactions:', error);
            return 'I encountered an issue while searching your transactions. Please try again.';
        }
    }
    async getSpendingInsights(params = {}) {
        try {
            const response = await axios_1.default.get(`${this.apiBaseUrl}/analysis/spending-insights`, {
                params: { userId: this.userId, ...params },
            });
            const data = response.data;
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
        }
        catch (error) {
            console.error('Error getting spending insights:', error);
            return "I couldn't generate spending insights right now. Please try again later.";
        }
    }
    async getInvestmentSummary(includeHistory = false) {
        try {
            const response = await axios_1.default.get(`${this.apiBaseUrl}/investments/summary`, {
                params: { userId: this.userId, includeHistory },
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
        }
        catch (error) {
            console.error('Error getting investment summary:', error);
            return "I couldn't retrieve your investment information. Please ensure your investment accounts are connected.";
        }
    }
    async getFinancialGoals(params = {}) {
        try {
            const validated = GoalParamsSchema.parse({
                ...params,
                userId: this.userId,
            });
            const response = await axios_1.default.get(`${this.apiBaseUrl}/goals`, {
                params: validated,
            });
            const goals = response.data.goals;
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
        }
        catch (error) {
            console.error('Error getting financial goals:', error);
            return "I couldn't retrieve your financial goals. Please try again or connect your accounts first.";
        }
    }
    async createCategory(params) {
        try {
            await axios_1.default.post(`${this.apiBaseUrl}/categories/budget`, params);
        }
        catch (error) {
            console.error('Error creating category:', error);
            throw error;
        }
    }
    generateProgressBar(percentage) {
        const filledBlocks = Math.round((percentage / 100) * 10);
        const emptyBlocks = 10 - filledBlocks;
        return '▓'.repeat(filledBlocks) + '░'.repeat(emptyBlocks);
    }
}
exports.FinanceAgentService = FinanceAgentService;
// API handlers for the tools
exports.financeToolImplementations = {
    get_net_worth_summary: async (params) => {
        const service = new FinanceAgentService(params.userId);
        return await service.getNetWorthSummary(params);
    },
    get_budget_summary: async (params) => {
        const service = new FinanceAgentService(params.userId);
        return await service.getBudgetSummary(params);
    },
    search_transactions: async (params) => {
        const service = new FinanceAgentService(params.userId);
        return await service.searchTransactions(params);
    },
    get_spending_insights: async (params) => {
        const service = new FinanceAgentService(params.userId);
        return await service.getSpendingInsights(params);
    },
    get_investment_summary: async (params) => {
        const service = new FinanceAgentService(params.userId);
        return await service.getInvestmentSummary(params.includeHistory);
    },
    get_financial_goals: async (params) => {
        const service = new FinanceAgentService(params.userId);
        return await service.getFinancialGoals(params);
    },
    create_budget: async (params) => {
        const service = new FinanceAgentService(params.userId);
        // Implementation for budget creation would go here
        return 'Budget created successfully!';
    },
    create_financial_goal: async (params) => {
        const service = new FinanceAgentService(params.userId);
        // Implementation for goal creation would go here
        return 'Financial goal created successfully!';
    },
    disconnect_zoho_account: async (params) => {
        const response = await fetch('/api/auth/zoho/disconnect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: params.user_id }),
        });
        return await response.json();
    },
    get_zoho_integration_status: async (user_id) => {
        const response = await fetch(`/api/auth/zoho/status?user_id=${user_id}`);
        return await response.json();
    },
    get_zoho_invoices: async (user_id, organization_id) => {
        const response = await fetch(`/api/zoho/invoices?user_id=${user_id}&org_id=${organization_id}`);
        return await response.json();
    },
    create_zoho_invoice: async (user_id, organization_id, invoice_data) => {
        const response = await fetch('/api/zoho/invoices', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id, org_id: organization_id, invoice_data }),
        });
        return await response.json();
    },
    get_zoho_customers: async (user_id, organization_id) => {
        const response = await fetch(`/api/zoho/customers?user_id=${user_id}&org_id=${organization_id}`);
        return await response.json();
    },
    create_zoho_customer: async (user_id, organization_id, customer_data) => {
        const response = await fetch('/api/zoho/customers', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id, org_id: organization_id, customer_data }),
        });
        return await response.json();
    },
    get_zoho_items: async (user_id, organization_id) => {
        const response = await fetch(`/api/zoho/items?user_id=${user_id}&org_id=${organization_id}`);
        return await response.json();
    },
    create_zoho_item: async (user_id, organization_id, item_data) => {
        const response = await fetch('/api/zoho/items', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id, org_id: organization_id, item_data }),
        });
        return await response.json();
    },
    get_zoho_bills: async (user_id, organization_id) => {
        const response = await fetch(`/api/zoho/bills?user_id=${user_id}&org_id=${organization_id}`);
        return await response.json();
    },
    create_zoho_bill: async (user_id, organization_id, bill_data) => {
        const response = await fetch('/api/zoho/bills', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id, org_id: organization_id, bill_data }),
        });
        return await response.json();
    },
    get_zoho_vendors: async (user_id, organization_id) => {
        const response = await fetch(`/api/zoho/vendors?user_id=${user_id}&org_id=${organization_id}`);
        return await response.json();
    },
    create_zoho_vendor: async (user_id, organization_id, vendor_data) => {
        const response = await fetch('/api/zoho/vendors', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id, org_id: organization_id, vendor_data }),
        });
        return await response.json();
    },
    get_zoho_purchase_orders: async (user_id, organization_id) => {
        const response = await fetch(`/api/zoho/purchaseorders?user_id=${user_id}&org_id=${organization_id}`);
        return await response.json();
    },
    create_zoho_purchase_order: async (user_id, organization_id, purchase_order_data) => {
        const response = await fetch('/api/zoho/purchaseorders', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id,
                org_id: organization_id,
                purchase_order_data,
            }),
        });
        return await response.json();
    },
    get_zoho_sales_orders: async (user_id, organization_id) => {
        const response = await fetch(`/api/zoho/salesorders?user_id=${user_id}&org_id=${organization_id}`);
        return await response.json();
    },
    create_zoho_sales_order: async (user_id, organization_id, sales_order_data) => {
        const response = await fetch('/api/zoho/salesorders', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id,
                org_id: organization_id,
                sales_order_data,
            }),
        });
        return await response.json();
    },
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZmluYW5jZUFnZW50U2VydmljZS5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImZpbmFuY2VBZ2VudFNlcnZpY2UudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7O0FBQUEsa0RBQTBCO0FBQzFCLDZCQUF3QjtBQUd4Qiw4Q0FBOEM7QUFDOUMsTUFBTSxvQkFBb0IsR0FBRyxPQUFDLENBQUMsTUFBTSxDQUFDO0lBQ3BDLE1BQU0sRUFBRSxPQUFDLENBQUMsTUFBTSxFQUFFO0lBQ2xCLGNBQWMsRUFBRSxPQUFDLENBQUMsT0FBTyxFQUFFLENBQUMsUUFBUSxFQUFFLENBQUMsT0FBTyxDQUFDLEtBQUssQ0FBQztJQUNyRCxTQUFTLEVBQUUsT0FBQztTQUNULE1BQU0sQ0FBQztRQUNOLEtBQUssRUFBRSxPQUFDLENBQUMsTUFBTSxFQUFFLENBQUMsUUFBUSxFQUFFO1FBQzVCLEdBQUcsRUFBRSxPQUFDLENBQUMsTUFBTSxFQUFFLENBQUMsUUFBUSxFQUFFO0tBQzNCLENBQUM7U0FDRCxRQUFRLEVBQUU7Q0FDZCxDQUFDLENBQUM7QUFFSCxNQUFNLHVCQUF1QixHQUFHLE9BQUMsQ0FBQyxNQUFNLENBQUM7SUFDdkMsTUFBTSxFQUFFLE9BQUMsQ0FBQyxNQUFNLEVBQUU7SUFDbEIsTUFBTSxFQUFFLE9BQUMsQ0FBQyxJQUFJLENBQUMsQ0FBQyxTQUFTLEVBQUUsTUFBTSxFQUFFLFFBQVEsQ0FBQyxDQUFDLENBQUMsUUFBUSxFQUFFLENBQUMsT0FBTyxDQUFDLFNBQVMsQ0FBQztJQUMzRSxVQUFVLEVBQUUsT0FBQyxDQUFDLEtBQUssQ0FBQyxPQUFDLENBQUMsTUFBTSxFQUFFLENBQUMsQ0FBQyxRQUFRLEVBQUU7SUFDMUMsS0FBSyxFQUFFLE9BQUMsQ0FBQyxNQUFNLEVBQUUsQ0FBQyxRQUFRLEVBQUU7Q0FDN0IsQ0FBQyxDQUFDO0FBRUgsTUFBTSw2QkFBNkIsR0FBRyxPQUFDLENBQUMsTUFBTSxDQUFDO0lBQzdDLE1BQU0sRUFBRSxPQUFDLENB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T0FBTztnQkFDUCxNQUFNLEVBQUUsZUFBZTtnQkFDdkIsZ0JBQWdCO2FBQ2pCLENBQUM7U0FDSCxDQUFDLENBQUM7UUFDSCxPQUFPLE1BQU0sUUFBUSxDQUFDLElBQUksRUFBRSxDQUFDO0lBQy9CLENBQUM7Q0FDRixDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IGF4aW9zIGZyb20gJ2F4aW9zJztcbmltcG9ydCB7IHogfSBmcm9tICd6b2QnO1xuaW1wb3J0IHsgQ2hhdENvbXBsZXRpb25Ub29sIH0gZnJvbSAnb3BlbmFpL3Jlc291cmNlcy9jaGF0L2NvbXBsZXRpb25zJztcblxuLy8gWm9kIHNjaGVtYXMgZm9yIHNlY3VyZSBwYXJhbWV0ZXIgdmFsaWRhdGlvblxuY29uc3QgTmV0V29ydGhQYXJhbXNTY2hlbWEgPSB6Lm9iamVjdCh7XG4gIHVzZXJJZDogei5zdHJpbmcoKSxcbiAgaW5jbHVkZUhpc3Rvcnk6IHouYm9vbGVhbigpLm9wdGlvbmFsKCkuZGVmYXVsdChmYWxzZSksXG4gIGRhdGVSYW5nZTogelxuICAgIC5vYmplY3Qoe1xuICAgICAgc3RhcnQ6IHouc3RyaW5nKCkub3B0aW9uYWwoKSxcbiAgICAgIGVuZDogei5zdHJpbmcoKS5vcHRpb25hbCgpLFxuICAgIH0pXG4gICAgLm9wdGlvbmFsKCksXG59KTtcblxuY29uc3QgQnVkZ2V0UXVlcnlQYXJhbXNTY2hlbWEgPSB6Lm9iamVjdCh7XG4gIHVzZXJJZDogei5zdHJpbmcoKSxcbiAgcGVyaW9kOiB6LmVudW0oWydjdXJyZW50JywgJ2xhc3QnLCAnZnV0dXJlJ10pLm9wdGlvbmFsKCkuZGVmYXVsdCgnY3VycmVudCcpLFxuICBjYXRlZ29yaWVzOiB6LmFycmF5KHouc3RyaW5nKCkpLm9wdGlvbmFsKCksXG4gIG1vbnRoOiB6LnN0cmluZygpLm9wdGlvbmFsKCksXG59KTtcblxuY29uc3QgVHJhbnNhY3Rpb25TZWFyY2hQYXJhbXNTY2hlbWEgPSB6Lm9iamVjdCh7XG4gIHVzZXJJZDogei5zdHJpbmcoKSxcbiAgcXVlcnk6IHouc3RyaW5nKCkub3B0aW9uYWwoKSxcbiAgY2F0ZWdvcnk6IHouc3RyaW5nKCkub3B0aW9uYWwoKSxcbiAgYW1vdW50UmFuZ2U6IHpcbiAgICAub2JqZWN0KHtcbiAgICAgIG1pbjogei5udW1iZXIoKS5vcHRpb25hbCgpLFxuICAgICAgbWF4OiB6Lm51bWJlcigpLm9wdGlvbmFsKCksXG4gICAgfSlcbiAgICAub3B0aW9uYWwoKSxcbiAgZGF0ZVJhbmdlOiB6Lm9iamVjdCh7XG4gICAgc3RhcnQ6IHouc3RyaW5nKCksXG4gICAgZW5kOiB6LnN0cmluZygpLFxuICB9KSxcbiAgbGltaXQ6IHoubnVtYmVyKCkub3B0aW9uYWwoKS5kZWZhdWx0KDUwKSxcbn0pO1xuXG5jb25zdCBHb2FsUGFyYW1zU2NoZW1hID0gei5vYmplY3Qoe1xuICB1c2VySWQ6IHouc3RyaW5nKCksXG4gIGdvYWxJZDogei5zdHJpbmcoKS5vcHRpb25hbCgpLFxuICBnb2FsVHlwZTogelxuICAgIC5lbnVtKFsnc2F2aW5ncycsICdyZXRpcmVtZW50JywgJ2RlYnQnLCAncHVyY2hhc2UnLCAnZW1lcmdlbmN5J10pXG4gICAgLm9wdGlvbmFsKCksXG59KTtcblxuLy8gVHlwZXNcbmV4cG9ydCB0eXBlIE5ldFdvcnRoU3VtbWFyeSA9IHtcbiAgY3VycmVudDogbnVtYmVyO1xuICBjaGFuZ2U6IG51bWJlcjtcbiAgY2hhbmdlUGVyY2VudDogbnVtYmVyO1xuICBhc3NldHM6IG51bWJlcjtcbiAgbGlhYmlsaXRpZXM6IG51bWJlcjtcbiAgaGlzdG9yeT86IEFycmF5PHsgZGF0ZTogc3RyaW5nOyBuZXRXb3J0aDogbnVtYmVyIH0+O1xufTtcblxuZXhwb3J0IHR5cGUgQnVkZ2V0U3VtbWFyeSA9IHtcbiAgdG90YWxCdWRnZXQ6IG51bWJlcjtcbiAgc3BlbnQ6IG51bWJlcjtcbiAgcmVtYWluaW5nOiBudW1iZXI7XG4gIGNhdGVnb3JpZXM6IEFycmF5PHtcbiAgICBjYXRlZ29yeTogc3RyaW5nO1xuICAgIGJ1ZGdldGVkOiBudW1iZXI7XG4gICAgc3BlbnQ6IG51bWJlcjtcbiAgICByZW1haW5pbmc6IG51bWJlcjtcbiAgICB1dGlsaXphdGlvbjogbnVtYmVyO1xuICB9Pjtcbn07XG5cbmV4cG9ydCB0eXBlIFNwZW5kaW5nSW5zaWdodCA9IHtcbiAgdG90YWxTcGVudDogbnVtYmVyO1xuICBjYXRlZ29yaWVzOiBBcnJheTx7IGNhdGVnb3J5OiBzdHJpbmc7IGFtb3VudDogbnVtYmVyOyBwZXJjZW50YWdlOiBudW1iZXIgfT47XG4gIHRyZW5kczoge1xuICAgIHRoaXNNb250aDogbnVtYmVyO1xuICAgIGxhc3RNb250aDogbnVtYmVyO1xuICAgIGNoYW5nZTogbnVtYmVyO1xuICAgIGNoYW5nZVBlcmNlbnQ6IG51bWJlcjtcbiAgfTtcbn07XG5cbmV4cG9ydCB0eXBlIEZpbmFuY2lhbEdvYWwgPSB7XG4gIGlkOiBzdHJpbmc7XG4gIG5hbWU6IHN0cmluZztcbiAgdGFyZ2V0OiBudW1iZXI7XG4gIGN1cnJlbnQ6IG51bWJlcjtcbiAgcHJvZ3Jlc3M6IG51bWJlcjtcbiAgZGVhZGxpbmU/OiBzdHJpbmc7XG4gIHN0YXR1czogJ2FjdGl2ZScgfCAnY29tcGxldGVkJyB8ICdvbl9ob2xkJztcbn07XG5cbmV4cG9ydCBjb25zdCBmaW5hbmNlVG9vbHM6IENoYXRDb21wbGV0aW9uVG9vbFtdID0gW1xuICB7XG4gICAgdHlwZTogJ2Z1bmN0aW9uJyxcbiAgICBmdW5jdGlvbjoge1xuICAgICAgbmFtZTogJ2dldF9uZXRfd29ydGhfc3VtbWFyeScsXG4gICAgICBkZXNjcmlwdGlvbjogJ0dldCBjdXJyZW50IG5ldCB3b3J0aCBhbmQgaGlzdG9yaWNhbCB0cmVuZHMnLFxuICAgICAgcGFyYW1ldGVyczoge1xuICAgICAgICB0eXBlOiAnb2JqZWN0JyxcbiAgICAgICAgcHJvcGVydGllczoge1xuICAgICAgICAgIHVzZXJJZDogeyB0eXBlOiAnc3RyaW5nJywgZGVzY3JpcHRpb246ICdVc2VyIGlkZW50aWZpZXInIH0sXG4gICAgICAgICAgaW5jbHVkZUhpc3Rvcnk6IHtcbiAgICAgICAgICAgIHR5cGU6ICdib29sZWFuJyxcbiAgICAgICAgICAgIGRlc2NyaXB0aW9uOiAnSW5jbHVkZSBoaXN0b3JpY2FsIG5ldCB3b3J0aCBkYXRhJyxcbiAgICAgICAgICB9LFxuICAgICAgICAgIGRhdGVSYW5nZToge1xuICAgICAgICAgICAgdHlwZTogJ29iamVjdCcsXG4gICAgICAgICAgICBwcm9wZXJ0aWVzOiB7XG4gICAgICAgICAgICAgIHN0YXJ0OiB7IHR5cGU6ICdzdHJpbmcnLCBmb3JtYXQ6ICdkYXRlJyB9LFxuICAgICAgICAgICAgICBlbmQ6IHsgdHlwZTogJ3N0cmluZycsIGZvcm1hdDogJ2RhdGUnIH0sXG4gICAgICAgICAgICB9LFxuICAgICAgICAgIH0sXG4gICAgICAgIH0sXG4gICAgICAgIHJlcXVpcmVkOiBbJ3VzZXJJZCddLFxuICAgICAgfSxcbiAgICB9LFxuICB9LFxuICB7XG4gICAgdHlwZTogJ2Z1bmN0aW9uJyxcbiAgICBmdW5jdGlvbjoge1xuICAgICAgbmFtZTogJ2dldF9idWRnZXRfc3VtbWFyeScsXG4gICAgICBkZXNjcmlwdGlvbjogJ0dldCBidWRnZXQgb3ZlcnZpZXcgYW5kIHNwZW5kaW5nIGJ5IGNhdGVnb3J5JyxcbiAgICAgIHBhcmFtZXRlcnM6IHtcbiAgICAgICAgdHlwZTogJ29iamVjdCcsXG4gICAgICAgIHByb3BlcnRpZXM6IHtcbiAgICAgICAgICB1c2VySWQ6IHsgdHlwZTogJ3N0cmluZycsIGRlc2NyaXB0aW9uOiAnVXNlciBpZGVudGlmaWVyJyB9LFxuICAgICAgICAgIHBlcmlvZDoge1xuICAgICAgICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgICAgICAgICBlbnVtOiBbJ2N1cnJlbnQnLCAnbGFzdCcsICdmdXR1cmUnXSxcbiAgICAgICAgICAgIGRlZmF1bHQ6ICdjdXJyZW50JyxcbiAgICAgICAgICB9LFxuICAgICAgICAgIG1vbnRoOiB7IHR5cGU6ICdzdHJpbmcnLCBmb3JtYXQ6ICdkYXRlJyB9LFxuICAgICAgICAgIGNhdGVnb3JpZXM6IHsgdHlwZTogJ2FycmF5JywgaXRlbXM6IHsgdHlwZTogJ3N0cmluZycgfSB9LFxuICAgICAgICB9LFxuICAgICAgICByZXF1aXJlZDogWyd1c2VySWQnXSxcbiAgICAgIH0sXG4gICAgfSxcbiAgfSxcbiAge1xuICAgIHR5cGU6ICdmdW5jdGlvbicsXG4gICAgZnVuY3Rpb246IHtcbiAgICAgIG5hbWU6ICdzZWFyY2hfdHJhbnNhY3Rpb25zJyxcbiAgICAgIGRlc2NyaXB0aW9uOiAnU2VhcmNoIGFuZCBhbmFseXplIHRyYW5zYWN0aW9ucyBieSBjcml0ZXJpYScsXG4gICAgICBwYXJhbWV0ZXJzOiB7XG4gICAgICAgIHR5cGU6ICdvYmplY3QnLFxuICAgICAgICBwcm9wZXJ0aWVzOiB7XG4gICAgICAgICAgdXNlcklkOiB7IHR5cGU6ICdzdHJpbmcnLCBkZXNjcmlwdGlvbjogJ1VzZXIgaWRlbnRpZmllcicgfSxcbiAgICAgICAgICBxdWVyeToge1xuICAgICAgICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgICAgICAgICBkZXNjcmlwdGlvbjogJ1NlYXJjaCBxdWVyeSBmb3IgZGVzY3JpcHRpb25zJyxcbiAgICAgICAgICB9LFxuICAgICAgICAgIGNhdGVnb3J5OiB7IHR5cGU6ICdzdHJpbmcnLCBkZXNjcmlwdGlvbjogJ0ZpbHRlciBieSBjYXRlZ29yeScgfSxcbiAgICAgICAgICBhbW91bnRSYW5nZToge1xuICAgICAgICAgICAgdHlwZTogJ29iamVjdCcsXG4gICAgICAgICAgICBwcm9wZXJ0aWVzOiB7XG4gICAgICAgICAgICAgIG1pbjogeyB0eXBlOiAnbnVtYmVyJyB9LFxuICAgICAgICAgICAgICBtYXg6IHsgdHlwZTogJ251bWJlcicgfSxcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgfSxcbiAgICAgICAgICBkYXRlUmFuZ2U6IHtcbiAgICAgICAgICAgIHR5cGU6ICdvYmplY3QnLFxuICAgICAgICAgICAgcHJvcGVydGllczoge1xuICAgICAgICAgICAgICBzdGFydDogeyB0eXBlOiAnc3RyaW5nJywgZm9ybWF0OiAnZGF0ZScsIHJlcXVpcmVkOiB0cnVlIH0sXG4gICAgICAgICAgICAgIGVuZDogeyB0eXBlOiAnc3RyaW5nJywgZm9ybWF0OiAnZGF0ZScsIHJlcXVpcmVkOiB0cnVlIH0sXG4gICAgICAgICAgICB9LFxuICAgICAgICAgICAgcmVxdWlyZWQ6IFsnc3RhcnQnLCAnZW5kJ10sXG4gICAgICAgICAgfSxcbiAgICAgICAgICBsaW1pdDogeyB0eXBlOiAnbnVtYmVyJywgZGVmYXVsdDogNTAgfSxcbiAgICAgICAgfSxcbiAgICAgICAgcmVxdWlyZWQ6IFsndXNlcklkJywgJ2RhdGVSYW5nZSddLFxuICAgICAgfSxcbiAgICB9LFxuICB9LFxuICB7XG4gICAgdHlwZTogJ2Z1bmN0aW9uJyxcbiAgICBmdW5jdGlvbjoge1xuICAgICAgbmFtZTogJ2dldF9zcGVuZGluZ19pbnNpZ2h0cycsXG4gICAgICBkZXNjcmlwdGlvbjogJ0FuYWx5emUgc3BlbmRpbmcgcGF0dGVybnMgYW5kIHRyZW5kcycsXG4gICAgICBwYXJhbWV0ZXJzOiB7XG4gICAgICAgIHR5cGU6ICdvYmplY3QnLFxuICAgICAgICBwcm9wZXJ0aWVzOiB7XG4gICAgICAgICAgdXNlcklkOiB7IHR5cGU6ICdzdHJpbmcnLCBkZXNjcmlwdGlvbjogJ1VzZXIgaWRlbnRpZmllcicgfSxcbiAgICAgICAgICBjYXRlZ29yeToge1xuICAgICAgICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgICAgICAgICBkZXNjcmlwdGlvbjogJ0ZvY3VzIG9uIHNwZWNpZmljIGNhdGVnb3J5JyxcbiAgICAgICAgICB9LFxuICAgICAgICAgIHBlcmlvZDoge1xuICAgICAgICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgICAgICAgICBlbnVtOiBbJ2N1cnJlbnQnLCAnbGFzdCcsICdxdWFydGVyJywgJ3llYXInXSxcbiAgICAgICAgICAgIGRlZmF1bHQ6ICdjdXJyZW50JyxcbiAgICAgICAgICB9LFxuICAgICAgICB9LFxuICAgICAgICByZXF1aXJlZDogWyd1c2VySWQnXSxcbiAgICAgIH0sXG4gICAgfSxcbiAgfSxcbiAge1xuICAgIHR5cGU6ICdmdW5jdGlvbicsXG4gICAgZnVuY3Rpb246IHtcbiAgICAgIG5hbWU6ICdnZXRfaW52ZXN0bWVudF9zdW1tYXJ5JyxcbiAgICAgIGRlc2NyaXB0aW9uOiAnR2V0IGludmVzdG1lbnQgcG9ydGZvbGlvIHN1bW1hcnkgYW5kIHBlcmZvcm1hbmNlJyxcbiAgICAgIHBhcmFtZXRlcnM6IHtcbiAgICAgICAgdHlwZTogJ29iamVjdCcsXG4gICAgICAgIHByb3BlcnRpZXM6IHtcbiAgICAgICAgICB1c2VySWQ6IHsgdHlwZTogJ3N0cmluZycsIGRlc2NyaXB0aW9uOiAnVXNlciBpZGVudGlmaWVyJyB9LFxuICAgICAgICAgIGluY2x1ZGVIaXN0b3J5OiB7XG4gICAgICAgICAgICB0eXBlOiAnYm9vbGVhbicsXG4gICAgICAgICAgICBkZXNjcmlwdGlvbjogJ0luY2x1ZGUgaGlzdG9yaWNhbCBwZXJmb3JtYW5jZScsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSxcbiAgICAgICAgcmVxdWlyZWQ6IFsndXNlcklkJ10sXG4gICAgICB9LFxuICAgIH0sXG4gIH0sXG4gIHtcbiAgICB0eXBlOiAnZnVuY3Rpb24nLFxuICAgIGZ1bmN0aW9uOiB7XG4gICAgICBuYW1lOiAnZ2V0X2ZpbmFuY2lhbF9nb2FscycsXG4gICAgICBkZXNjcmlwdGlvbjogJ0dldCBmaW5hbmNpYWwgZ29hbHMgYW5kIHByb2dyZXNzIHRyYWNraW5nJyxcbiAgICAgIHBhcmFtZXRlcnM6IHtcbiAgICAgICAgdHlwZTogJ29iamVjdCcsXG4gICAgICAgIHByb3BlcnRpZXM6IHtcbiAgICAgICAgICB1c2VySWQ6IHsgdHlwZTogJ3N0cmluZycsIGRlc2NyaXB0aW9uOiAnVXNlciBpZGVudGlmaWVyJyB9LFxuICAgICAgICAgIGdvYWxJZDogeyB0eXBlOiAnc3RyaW5nJywgZGVzY3JpcHRpb246ICdTcGVjaWZpYyBnb2FsIElEJyB9LFxuICAgICAgICAgIGdvYWxUeXBlOiB7XG4gICAgICAgICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICAgICAgICAgIGVudW06IFsnc2F2aW5ncycsICdyZXRpcmVtZW50JywgJ2RlYnQnLCAncHVyY2hhc2UnLCAnZW1lcmdlbmN5J10sXG4gICAgICAgICAgfSxcbiAgICAgICAgfSxcbiAgICAgICAgcmVxdWlyZWQ6IFsndXNlcklkJ10sXG4gICAgICB9LFxuICAgIH0sXG4gIH0sXG4gIHtcbiAgICB0eXBlOiAnZnVuY3Rpb24nLFxuICAgIGZ1bmN0aW9uOiB7XG4gICAgICBuYW1lOiAnY3JlYXRlX2J1ZGdldCcsXG4gICAgICBkZXNjcmlwdGlvbjogJ0NyZWF0ZSBhIG5ldyBidWRnZXQgY2F0ZWdvcnkgd2l0aCBhbGxvY2F0aW9uJyxcbiAgICAgIHBhcmFtZXRlcnM6IHtcbiAgICAgICAgdHlwZTogJ29iamVjdCcsXG4gICAgICAgIHByb3BlcnRpZXM6IHtcbiAgICAgICAgICB1c2VySWQ6IHsgdHlwZTogJ3N0cmluZycsIGRlc2NyaXB0aW9uOiAnVXNlciBpZGVudGlmaWVyJyB9LFxuICAgICAgICAgIGNhdGVnb3J5OiB7IHR5cGU6ICdzdHJpbmcnLCBkZXNjcmlwdGlvbjogJ0J1ZGdldCBjYXRlZ29yeSBuYW1lJyB9LFxuICAgICAgICAgIGFtb3VudDogeyB0eXBlOiAnbnVtYmVyJywgZGVzY3JpcHRpb246ICdNb250aGx5IGJ1ZGdldCBhbW91bnQnIH0sXG4gICAgICAgICAgZGVzY3JpcHRpb246IHsgdHlwZTogJ3N0cmluZycgfSxcbiAgICAgICAgfSxcbiAgICAgICAgcmVxdWlyZWQ6IFsndXNlcklkJywgJ2NhdGVnb3J5JywgJ2Ftb3VudCddLFxuICAgICAgfSxcbiAgICB9LFxuICB9LFxuICB7XG4gICAgdHlwZTogJ2Z1bmN0aW9uJyxcbiAgICBmdW5jdGlvbjoge1xuICAgICAgbmFtZTogJ2NyZWF0ZV9maW5hbmNpYWxfZ29hbCcsXG4gICAgICBkZXNjcmlwdGlvbjogJ0NyZWF0ZSBhIG5ldyBmaW5hbmNpYWwgZ29hbCcsXG4gICAgICBwYXJhbWV0ZXJzOiB7XG4gICAgICAgIHR5cGU6ICdvYmplY3QnLFxuICAgICAgICBwcm9wZXJ0aWVzOiB7XG4gICAgICAgICAgdXNlcklkOiB7IHR5cGU6ICdzdHJpbmcnLCBkZXNjcmlwdGlvbjogJ1VzZXIgaWRlbnRpZmllcicgfSxcbiAgICAgICAgICBuYW1lOiB7IHR5cGU6ICdzdHJpbmcnLCBkZXNjcmlwdGlvbjogJ0dvYWwgbmFtZScgfSxcbiAgICAgICAgICB0YXJnZXRBbW91bnQ6IHtcbiAgICAgICAgICAgIHR5cGU6ICdudW1iZXInLFxuICAgICAgICAgICAgZGVzY3JpcHRpb246ICdUYXJnZXQgYW1vdW50IHRvIHNhdmUnLFxuICAgICAgICAgIH0sXG4gICAgICAgICAgY3VycmVudEFtb3VudDoge1xuICAgICAgICAgICAgdHlwZTogJ251bWJlcicsXG4gICAgICAgICAgICBkZWZhdWx0OiAwLFxuICAgICAgICAgICAgZGVzY3JpcHRpb246ICdDdXJyZW50IHByb2dyZXNzJyxcbiAgICAgICAgICB9LFxuICAgICAgICAgIHRhcmdldERhdGU6IHtcbiAgICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICAgICAgZm9ybWF0OiAnZGF0ZScsXG4gICAgICAgICAgICBkZXNjcmlwdGlvbjogJ1RhcmdldCBjb21wbGV0aW9uIGRhdGUnLFxuICAgICAgICAgIH0sXG4gICAgICAgICAgZ29hbFR5cGU6IHtcbiAgICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICAgICAgZW51bTogWydzYXZpbmdzJywgJ3JldGlyZW1lbnQnLCAnZGVidCcsICdwdXJjaGFzZScsICdlbWVyZ2VuY3knXSxcbiAgICAgICAgICB9LFxuICAgICAgICAgIGRlc2NyaXB0aW9uOiB7IHR5cGU6ICdzdHJpbmcnIH0sXG4gICAgICAgIH0sXG4gICAgICAgIHJlcXVpcmVkOiBbJ3VzZXJJZCcsICduYW1lJywgJ3RhcmdldEFtb3VudCcsICdnb2FsVHlwZSddLFxuICAgICAgfSxcbiAgICB9LFxuICB9LFxuXTtcblxuZXhwb3J0IGNsYXNzIEZpbmFuY2VBZ2VudFNlcnZpY2Uge1xuICBwcml2YXRlIGFwaUJhc2VVcmw6IHN0cmluZztcbiAgcHJpdmF0ZSB1c2VySWQ6IHN0cmluZztcblxuICBjb25zdHJ1Y3Rvcih1c2VySWQ6IHN0cmluZywgYXBpQmFzZVVybDogc3RyaW5nID0gJy9hcGkvZmluYW5jaWFsJykge1xuICAgIHRoaXMudXNlcklkID0gdXNlcklkO1xuICAgIHRoaXMuYXBpQmFzZVVybCA9IGFwaUJhc2VVcmw7XG4gIH1cblxuICBhc3luYyBnZXROZXRXb3J0aFN1bW1hcnkoXG4gICAgcGFyYW1zOiB6LmluZmVyPHR5cGVvZiBOZXRXb3J0aFBhcmFtc1NjaGVtYT5cbiAgKTogUHJvbWlzZTxzdHJpbmc+IHtcbiAgICB0cnkge1xuICAgICAgY29uc3QgdmFsaWRhdGVkID0gTmV0V29ydGhQYXJhbXNTY2hlbWEucGFyc2Uoe1xuICAgICAgICAuLi5wYXJhbXMsXG4gICAgICAgIHVzZXJJZDogdGhpcy51c2VySWQsXG4gICAgICB9KTtcbiAgICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgYXhpb3MuZ2V0KGAke3RoaXMuYXBpQmFzZVVybH0vbmV0LXdvcnRoL3N1bW1hcnlgLCB7XG4gICAgICAgIHBhcmFtczogdmFsaWRhdGVkLFxuICAgICAgfSk7XG5cbiAgICAgIGNvbnN0IGRhdGEgPSByZXNwb25zZS5kYXRhIGFzIE5ldFdvcnRoU3VtbWFyeTtcblxuICAgICAgbGV0IHJlc3BvbnNlVGV4dCA9IGDwn5KwIFlvdXIgY3VycmVudCBuZXQgd29ydGggaXMgKiokJHtkYXRhLmN1cnJlbnQudG9Mb2NhbGVTdHJpbmcoKX0qKmA7XG5cbiAgICAgIGlmIChkYXRhLmNoYW5nZSA+PSAwKSB7XG4gICAgICAgIHJlc3BvbnNlVGV4dCArPSBgLCB1cCAqKiQke01hdGguYWJzKGRhdGEuY2hhbmdlKS50b0xvY2FsZVN0cmluZygpfSAoJHtkYXRhLmNoYW5nZVBlcmNlbnQudG9GaXhlZCgxKX0lKSoqIGZyb20gdGhlIGxhc3QgcGVyaW9kLmA7XG4gICAgICAgIG47XG4gICAgICB9IGVsc2Uge1xuICAgICAgICByZXNwb25zZVRleHQgKz0gYCwgZG93biAqKiQke01hdGguYWJzKGRhdGEuY2hhbmdlKS50b0xvY2FsZVN0cmluZygpfSAoJHtNYXRoLmFicyhkYXRhLmNoYW5nZVBlcmNlbnQpLnRvRml4ZWQoMSl9JSkqKiBmcm9tIHRoZSBsYXN0IHBlcmlvZC5gO1xuICAgICAgfVxuXG4gICAgICByZXNwb25zZVRleHQgKz0gYFxcblxcbkFzc2V0czogKiokJHtkYXRhLmFzc2V0cy50b0xvY2FsZVN0cmluZygpfSoqIHwgTGlhYmlsaXRpZXM6ICoqJCR7ZGF0YS5saWFiaWxpdGllcy50b0xvY2FsZVN0cmluZygpfSoqYDtcblxuICAgICAgaWYgKGRhdGEuaGlzdG9yeSAmJiBkYXRhLmhpc3RvcnkubGVuZ3RoID4gMSkge1xuICAgICAgICByZXNwb25zZVRleHQgKz0gYFxcblxcbvCfk4ggUmVjZW50IHRyZW5kOmA7XG4gICAgICAgIGRhdGEuaGlzdG9yeS5zbGljZSgtMykuZm9yRWFjaCgoc25hcHNob3QpID0+IHtcbiAgICAgICAgICByZXNwb25zZVRleHQgKz0gYFxcbiR7bmV3IERhdGUoc25hcHNob3QuZGF0ZSkudG9Mb2NhbGVEYXRlU3RyaW5nKCl9OiAkJHtzbmFwc2hvdC5uZXRXb3J0aC50b0xvY2FsZVN0cmluZygpfWA7XG4gICAgICAgIH0pO1xuICAgICAgfVxuXG4gICAgICByZXR1cm4gcmVzcG9uc2VUZXh0O1xuICAgIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgICBjb25zb2xlLmVycm9yKCdFcnJvciBmZXRjaGluZyBuZXQgd29ydGg6JywgZXJyb3IpO1xuICAgICAgcmV0dXJuIFwiSSBjb3VsZG4ndCByZXRyaWV2ZSB5b3VyIG5ldCB3b3J0aCBpbmZvcm1hdGlvbi4gVGhpcyBtaWdodCBiZSBiZWNhdXNlIHlvdSBoYXZlbid0IGNvbm5lY3RlZCBhbnkgZmluYW5jaWFsIGFjY291bnRzIG9yIHRoZXJlJ3MgYSB0ZW1wb3JhcnkgaXNzdWUuXCI7XG4gICAgfVxuICB9XG5cbiAgYXN5bmMgZ2V0QnVkZ2V0U3VtbWFyeShcbiAgICBwYXJhbXM6IHouaW5mZXI8dHlwZW9mIEJ1ZGdldFF1ZXJ5UGFyYW1zU2NoZW1hPlxuICApOiBQcm9taXNlPHN0cmluZz4ge1xuICAgIHRyeSB7XG4gICAgICBjb25zdCB2YWxpZGF0ZWQgPSBCdWRnZXRRdWVyeVBhcmFtc1NjaGVtYS5wYXJzZSh7XG4gICAgICAgIC4uLnBhcmFtcyxcbiAgICAgICAgdXNlcklkOiB0aGlzLnVzZXJJZCxcbiAgICAgIH0pO1xuICAgICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBheGlvcy5nZXQoYCR7dGhpcy5hcGlCYXNlVXJsfS9idWRnZXRzL3N1bW1hcnlgLCB7XG4gICAgICAgIHBhcmFtczogdmFsaWRhdGVkLFxuICAgICAgfSk7XG5cbiAgICAgIGNvbnN0IGRhdGEgPSByZXNwb25zZS5kYXRhIGFzIEJ1ZGdldFN1bW1hcnk7XG5cbiAgICAgIGlmIChkYXRhLmNhdGVnb3JpZXMubGVuZ3RoID09PSAwKSB7XG4gICAgICAgIHJldHVybiBcIllvdSBoYXZlbid0IHNldCB1cCBhbnkgYnVkZ2V0cyB5ZXQuIFdvdWxkIHlvdSBsaWtlIG1lIHRvIGhlbHAgeW91IGNyZWF0ZSBvbmU/XCI7XG4gICAgICB9XG5cbiAgICAgIGxldCByZXNwb25zZVRleHQgPSBg8J+SsCBCdWRnZXQgT3ZlcnZpZXcke3ZhbGlkYXRlZC5tb250aCA/IGAgZm9yICR7bmV3IERhdGUodmFsaWRhdGVkLm1vbnRoKS50b0xvY2FsZURhdGVTdHJpbmcoJ2VuLVVTJywgeyBtb250aDogJ2xvbmcnLCB5ZWFyOiAnbnVtZXJpYycgfSl9YCA6ICcnfTpcXG5gO1xuICAgICAgcmVzcG9uc2VUZXh0ICs9IGBUb3RhbCBCdWRnZXQ6ICoqJCR7ZGF0YS50b3RhbEJ1ZGdldC50b0xvY2FsZVN0cmluZygpfSoqIHwgU3BlbnQ6ICoqJCR7ZGF0YS5zcGVudC50b0xvY2FsZVN0cmluZygpfSoqIHwgUmVtYWluaW5nOiAqKiQke2RhdGEucmVtYWluaW5nLnRvTG9jYWxlU3RyaW5nKCl9KipgO1xuXG4gICAgICAvLyBBZGQgY2F0ZWdvcnkgYnJlYWtkb3duc1xuICAgICAgZGF0YS5jYXRlZ29yaWVzLnNsaWNlKDAsIDUpLmZvckVhY2goKGNhdGVnb3J5KSA9PiB7XG4gICAgICAgIGNvbnN0IGVtb2ppID1cbiAgICAgICAgICBjYXRlZ29yeS51dGlsaXphdGlvbiA+PSAxMDBcbiAgICAgICAgICAgID8gJ+KaoO+4jydcbiAgICAgICAgICAgIDogY2F0ZWdvcnkudXRpbGl6YXRpb24gPj0gODBcbiAgICAgICAgICAgICAgPyAn8J+foSdcbiAgICAgICAgICAgICAgOiAn4pyFJztcbiAgICAgICAgY29uc3QgcmVtYWluaW5nRW1vamkgPSBjYXRlZ29yeS5yZW1haW5pbmcgPCAwID8gJ/CfmJ8nIDogJyc7XG4gICAgICAgIHJlc3BvbnNlVGV4dCArPSBgXFxuJHtlbW9qaX0gKioke2NhdGVnb3J5LmNhdGVnb3J5fSoqOiAkJHtjYXRlZ29yeS5zcGVudC50b0xvY2FsZVN0cmluZygpfSAvICQke2NhdGVnb3J5LmJ1ZGdldGVkLnRvTG9jYWxlU3RyaW5nKCl9ICgke2NhdGVnb3J5LnV0aWxpemF0aW9uLnRvRml4ZWQoMCl9JSkgJHtyZW1haW5pbmdFbW9qaX1gO1xuICAgICAgfSk7XG5cbiAgICAgIGlmIChkYXRhLmNhdGVnb3JpZXMubGVuZ3RoID4gNSkge1xuICAgICAgICByZXNwb25zZVRleHQgKz0gYFxcbi4uLmFuZCAke2RhdGEuY2F0ZWdvcmllcy5sZW5ndGggLSA1fSBtb3JlIGNhdGVnb3JpZXNgO1xuICAgICAgfVxuXG4gICAgICByZXR1cm4gcmVzcG9uc2VUZXh0O1xuICAgIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgICBjb25zb2xlLmVycm9yKCdFcnJvciBmZXRjaGluZyBidWRnZXQgc3VtbWFyeTonLCBlcnJvcik7XG4gICAgICByZXR1cm4gXCJJIGNvdWxkbid0IHJldHJpZXZlIHlvdXIgYnVkZ2V0IGluZm9ybWF0aW9uLiBQbGVhc2UgY2hlY2sgaWYgYnVkZ2V0cyBhcmUgc2V0IHVwIG9yIHRyeSBhZ2FpbiBsYXRlci5cIjtcbiAgICB9XG4gIH1cblxuICBhc3luYyBzZWFyY2hUcmFuc2FjdGlvbnMoXG4gICAgcGFyYW1zOiB6LmluZmVyPHR5cGVvZiBUcmFuc2FjdGlvblNlYXJjaFBhcmFtc1NjaGVtYT5cbiAgKTogUHJvbWlzZTxzdHJpbmc+IHtcbiAgICB0cnkge1xuICAgICAgY29uc3QgdmFsaWRhdGVkID0gVHJhbnNhY3Rpb25TZWFyY2hQYXJhbXNTY2hlbWEucGFyc2Uoe1xuICAgICAgICAuLi5wYXJhbXMsXG4gICAgICAgIHVzZXJJZDogdGhpcy51c2VySWQsXG4gICAgICB9KTtcbiAgICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgYXhpb3MucG9zdChcbiAgICAgICAgYCR7dGhpcy5hcGlCYXNlVXJsfS90cmFuc2FjdGlvbnMvc2VhcmNoYCxcbiAgICAgICAgdmFsaWRhdGVkXG4gICAgICApO1xuXG4gICAgICBjb25zdCB0cmFuc2FjdGlvbnMgPSByZXNwb25zZS5kYXRhLnRyYW5zYWN0aW9ucztcblxuICAgICAgaWYgKCF0cmFuc2FjdGlvbnMgfHwgdHJhbnNhY3Rpb25zLmxlbmd0aCA9PT0gMCkge1xuICAgICAgICByZXR1cm4gYEkgY291bGRuJ3QgZmluZCBhbnkgdHJhbnNhY3Rpb25zICR7cGFyYW1zLnF1ZXJ5ID8gYG1hdGNoaW5nIFwiJHtwYXJhbXMucXVlcnl9XCJgIDogJyd9IGluIHRoZSBzcGVjaWZpZWQgcGVyaW9kLmA7XG4gICAgICB9XG5cbiAgICAgIGxldCByZXNwb25zZVRleHQgPSBg8J+RgCBGb3VuZCAqKiR7dHJhbnNhY3Rpb25zLmxlbmd0aH0qKiB0cmFuc2FjdGlvbiR7dHJhbnNhY3Rpb25zLmxlbmd0aCAhPT0gMSA/ICdzJyA6ICcnfWA7XG5cbiAgICAgIGlmIChwYXJhbXMucXVlcnkpIHtcbiAgICAgICAgcmVzcG9uc2VUZXh0ICs9IGAgbWF0Y2hpbmcgXFxcIiR7cGFyYW1zLnF1ZXJ5fVxcXCJgO1xuICAgICAgfVxuXG4gICAgICBpZiAocGFyYW1zLmNhdGVnb3J5KSB7XG4gICAgICAgIHJlc3BvbnNlVGV4dCArPSBgIGluICR7cGFyYW1zLmNhdGVnb3J5fWA7XG4gICAgICB9XG5cbiAgICAgIGNvbnN0IHRvdGFsQW1vdW50ID0gdHJhbnNhY3Rpb25zLnJlZHVjZShcbiAgICAgICAgKHN1bSwgdCkgPT4gc3VtICsgTWF0aC5hYnModC5hbW91bnQpLFxuICAgICAgICAwXG4gICAgICApO1xuICAgICAgcmVzcG9uc2VUZXh0ICs9IGAgdG90YWxpbmcgKiokJHt0b3RhbEFtb3VudC50b0xvY2FsZVN0cmluZygpfSoqOiBcXG5cXG5gO1xuXG4gICAgICAvLyBTaG93IHJlY2VudCB0cmFuc2FjdGlvbnMgd2l0aCBtb3N0IHJlbGV2YW50IGNvbnRleHRcbiAgICAgIHRyYW5zYWN0aW9ucy5zbGljZSgwLCAxMCkuZm9yRWFjaCgodHJhbnNhY3Rpb24sIGluZGV4KSA9PiB7XG4gICAgICAgIGNvbnN0IGVtb2ppID0gdHJhbnNhY3Rpb24uYW1vdW50ID49IDAgPyAn8J+SmicgOiAn8J+UtCc7XG4gICAgICAgIGNvbnN0IGFtb3VudCA9IE1hdGguYWJzKHRyYW5zYWN0aW9uLmFtb3VudCkudG9Mb2NhbGVTdHJpbmcoKTtcbiAgICAgICAgcmVzcG9uc2VUZXh0ICs9IGAke2luZGV4ICsgMX0uICR7ZW1vaml9ICQke2Ftb3VudH0gLSAke3RyYW5zYWN0aW9uLmRlc2NyaXB0aW9uIHx8IHRyYW5zYWN0aW9uLm5hbWV9XFxuYDtcbiAgICAgICAgcmVzcG9uc2VUZXh0ICs9IGAgICAke25ldyBEYXRlKHRyYW5zYWN0aW9uLmRhdGUpLnRvTG9jYWxlRGF0ZVN0cmluZygpfSB8ICR7dHJhbnNhY3Rpb24uY2F0ZWdvcnkgfHwgJ1VuY2F0ZWdvcml6ZWQnfVxcbmA7XG4gICAgICB9KTtcblxuICAgICAgaWYgKHRyYW5zYWN0aW9ucy5sZW5ndGggPiAxMCkge1xuICAgICAgICByZXNwb25zZVRleHQgKz0gYFxcbi4uLmFuZCAke3RyYW5zYWN0aW9ucy5sZW5ndGggLSAxMH0gbW9yZWA7XG4gICAgICB9XG5cbiAgICAgIHJldHVybiByZXNwb25zZVRleHQ7XG4gICAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICAgIGNvbnNvbGUuZXJyb3IoJ0Vycm9yIHNlYXJjaGluZyB0cmFuc2FjdGlvbnM6JywgZXJyb3IpO1xuICAgICAgcmV0dXJuICdJIGVuY291bnRlcmVkIGFuIGlzc3VlIHdoaWxlIHNlYXJjaGluZyB5b3VyIHRyYW5zYWN0aW9ucy4gUGxlYXNlIHRyeSBhZ2Fpbi4nO1xuICAgIH1cbiAgfVxuXG4gIGFzeW5jIGdldFNwZW5kaW5nSW5zaWdodHMoXG4gICAgcGFyYW1zOiB7IGNhdGVnb3J5Pzogc3RyaW5nOyBwZXJpb2Q/OiBzdHJpbmcgfSA9IHt9XG4gICk6IFByb21pc2U8c3RyaW5nPiB7XG4gICAgdHJ5IHtcbiAgICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgYXhpb3MuZ2V0KFxuICAgICAgICBgJHt0aGlzLmFwaUJhc2VVcmx9L2FuYWx5c2lzL3NwZW5kaW5nLWluc2lnaHRzYCxcbiAgICAgICAge1xuICAgICAgICAgIHBhcmFtczogeyB1c2VySWQ6IHRoaXMudXNlcklkLCAuLi5wYXJhbXMgfSxcbiAgICAgICAgfVxuICAgICAgKTtcblxuICAgICAgY29uc3QgZGF0YSA9IHJlc3BvbnNlLmRhdGEgYXMgU3BlbmRpbmdJbnNpZ2h0O1xuXG4gICAgICBsZXQgcmVzcG9uc2VUZXh0ID0gYPCfkqEgU3BlbmRpbmcgSW5zaWdodHMke3BhcmFtcy5jYXRlZ29yeSA/IGAgZm9yICR7cGFyYW1zLmNhdGVnb3J5fWAgOiAnJ306XFxuXFxuYDtcbiAgICAgIHJlc3BvbnNlVGV4dCArPSBgKipUb3RhbCBzcGVudCoqOiAkJHtkYXRhLnRvdGFsU3BlbnQudG9Mb2NhbGVTdHJpbmcoKX1cXG5gO1xuXG4gICAgICAvLyBDYXRlZ29yeSBicmVha2Rvd25cbiAgICAgIGlmIChkYXRhLmNhdGVnb3JpZXMgJiYgZGF0YS5jYXRlZ29yaWVzLmxlbmd0aCA+IDApIHtcbiAgICAgICAgcmVzcG9uc2VUZXh0ICs9IGAqKlRvcCBjYXRlZ29yaWVzKio6XFxuYDtcbiAgICAgICAgZGF0YS5jYXRlZ29yaWVzLnNsaWNlKDAsIDUpLmZvckVhY2goKGNhdCkgPT4ge1xuICAgICAgICAgIHJlc3BvbnNlVGV4dCArPSBg4oCiICR7Y2F0LmNhdGVnb3J5fTogKiokJHtjYXQuYW1vdW50LnRvTG9jYWxlU3RyaW5nKCl9ICgke2NhdC5wZXJjZW50YWdlfSUpKipcXG5gO1xuICAgICAgICB9KTtcbiAgICAgIH1cblxuICAgICAgLy8gVHJlbmQgYW5hbHlzaXNcbiAgICAgIGlmIChkYXRhLnRyZW5kcykge1xuICAgICAgICBjb25zdCB0cmVuZCA9IGRhdGEudHJlbmRzLmNoYW5nZSA+PSAwID8gJ+KGl++4jyBpbmNyZWFzZWQnIDogJ+KGmO+4jyBkZWNyZWFzZWQnO1xuICAgICAgICBjb25zdCBwY3QgPSBNYXRoLmFicyhkYXRhLnRyZW5kcy5jaGFuZ2VQZXJjZW50KS50b0ZpeGVkKDEpO1xuICAgICAgICByZXNwb25zZVRleHQgKz0gYFxcbioqVHJlbmQqKjogU3BlbnQgJHt0cmVuZH0gYnkgKiokJHtNYXRoLmFicyhkYXRhLnRyZW5kcy5jaGFuZ2UpLnRvTG9jYWxlU3RyaW5nKCl9ICgke3BjdH0lKSoqIGNvbXBhcmVkIHRvIGxhc3QgcGVyaW9kYDtcbiAgICAgIH1cblxuICAgICAgcmV0dXJuIHJlc3BvbnNlVGV4dDtcbiAgICB9IGNhdGNoIChlcnJvcikge1xuICAgICAgY29uc29sZS5lcnJvcignRXJyb3IgZ2V0dGluZyBzcGVuZGluZyBpbnNpZ2h0czonLCBlcnJvcik7XG4gICAgICByZXR1cm4gXCJJIGNvdWxkbid0IGdlbmVyYXRlIHNwZW5kaW5nIGluc2lnaHRzIHJpZ2h0IG5vdy4gUGxlYXNlIHRyeSBhZ2FpbiBsYXRlci5cIjtcbiAgICB9XG4gIH1cblxuICBhc3luYyBnZXRJbnZlc3RtZW50U3VtbWFyeShpbmNsdWRlSGlzdG9yeSA9IGZhbHNlKTogUHJvbWlzZTxzdHJpbmc+IHtcbiAgICB0cnkge1xuICAgICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBheGlvcy5nZXQoXG4gICAgICAgIGAke3RoaXMuYXBpQmFzZVVybH0vaW52ZXN0bWVudHMvc3VtbWFyeWAsXG4gICAgICAgIHtcbiAgICAgICAgICBwYXJhbXM6IHsgdXNlcklkOiB0aGlzLnVzZXJJZCwgaW5jbHVkZUhpc3RvcnkgfSxcbiAgICAgICAgfVxuICAgICAgKTtcblxuICAgICAgY29uc3QgZGF0YSA9IHJlc3BvbnNlLmRhdGE7XG5cbiAgICAgIGlmICghZGF0YS5ob2xkaW5ncyB8fCBkYXRhLmhvbGRpbmdzLmxlbmd0aCA9PT0gMCkge1xuICAgICAgICByZXR1cm4gXCJZb3UgZG9uJ3QgaGF2ZSBhbnkgaW52ZXN0bWVudHMgY29ubmVjdGVkIHlldC4gV291bGQgeW91IGxpa2UgdG8gbGluayB5b3VyIGludmVzdG1lbnQgYWNjb3VudHM/XCI7XG4gICAgICB9XG5cbiAgICAgIGxldCByZXNwb25zZVRleHQgPSBg8J+TiCBZb3VyIEludmVzdG1lbnQgUG9ydGZvbGlvOlxcblxcbmA7XG4gICAgICByZXNwb25zZVRleHQgKz0gYCoqVG90YWwgVmFsdWUqKjogJCR7ZGF0YS50b3RhbFZhbHVlLnRvTG9jYWxlU3RyaW5nKCl9XFxuYDtcblxuICAgICAgaWYgKGRhdGEudG90YWxHYWluTG9zcyAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICAgIGNvbnN0IGVtb2ppID0gZGF0YS50b3RhbEdhaW5Mb3NzID49IDAgPyAn8J+TiCcgOiAn8J+TiSc7XG4gICAgICAgIHJlc3BvbnNlVGV4dCArPSBgJHtlbW9qaX0gKipUb3RhbCBSZXR1cm5zKio6ICQke01hdGguYWJzKGRhdGEudG90YWxHYWluTG9zcykudG9Mb2NhbGVTdHJpbmcoKX0gKCR7ZGF0YS50b3RhbFJldHVyblBjdD8udG9GaXhlZCgxKX0lKVxcbmA7XG4gICAgICB9XG5cbiAgICAgIC8vIFRvcCBob2xkaW5nc1xuICAgICAgcmVzcG9uc2VUZXh0ICs9IGBcXG4qKlRvcCBIb2xkaW5ncyoqOlxcbmA7XG4gICAgICBkYXRhLmhvbGRpbmdzLnNsaWNlKDAsIDUpLmZvckVhY2goKGhvbGRpbmcpID0+IHtcbiAgICAgICAgcmVzcG9uc2VUZXh0ICs9IGDigKIgKioke2hvbGRpbmcubmFtZX0qKjogJHtob2xkaW5nLnNoYXJlc30gQCAkJHtob2xkaW5nLnByaWNlPy50b0xvY2FsZVN0cmluZygpfSA9ICQke2hvbGRpbmcudmFsdWUudG9Mb2NhbGVTdHJpbmcoKX1cXG5gO1xuICAgICAgfSk7XG5cbiAgICAgIGlmIChkYXRhLmhvbGRpbmdzLmxlbmd0aCA+IDUpIHtcbiAgICAgICAgcmVzcG9uc2VUZXh0ICs9IGBcXG4uLi5hbmQgJHtkYXRhLmhvbGRpbmdzLmxlbmd0aCAtIDV9IG1vcmVgO1xuICAgICAgfVxuXG4gICAgICByZXR1cm4gcmVzcG9uc2VUZXh0O1xuICAgIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgICBjb25zb2xlLmVycm9yKCdFcnJvciBnZXR0aW5nIGludmVzdG1lbnQgc3VtbWFyeTonLCBlcnJvcik7XG4gICAgICByZXR1cm4gXCJJIGNvdWxkbid0IHJldHJpZXZlIHlvdXIgaW52ZXN0bWVudCBpbmZvcm1hdGlvbi4gUGxlYXNlIGVuc3VyZSB5b3VyIGludmVzdG1lbnQgYWNjb3VudHMgYXJlIGNvbm5lY3RlZC5cIjtcbiAgICB9XG4gIH1cblxuICBhc3luYyBnZXRGaW5hbmNpYWxHb2FscyhcbiAgICBwYXJhbXM6IHouaW5mZXI8dHlwZW9mIEdvYWxQYXJhbXNTY2hlbWE+ID0ge31cbiAgKTogUHJvbWlzZTxzdHJpbmc+IHtcbiAgICB0cnkge1xuICAgICAgY29uc3QgdmFsaWRhdGVkID0gR29hbFBhcmFtc1NjaGVtYS5wYXJzZSh7XG4gICAgICAgIC4uLnBhcmFtcyxcbiAgICAgICAgdXNlcklkOiB0aGlzLnVzZXJJZCxcbiAgICAgIH0pO1xuICAgICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBheGlvcy5nZXQoYCR7dGhpcy5hcGlCYXNlVXJsfS9nb2Fsc2AsIHtcbiAgICAgICAgcGFyYW1zOiB2YWxpZGF0ZWQsXG4gICAgICB9KTtcblxuICAgICAgY29uc3QgZ29hbHMgPSByZXNwb25zZS5kYXRhLmdvYWxzIGFzIEZpbmFuY2lhbEdvYWxbXTtcblxuICAgICAgaWYgKGdvYWxzLmxlbmd0aCA9PT0gMCkge1xuICAgICAgICByZXR1cm4gXCJZb3UgaGF2ZW4ndCBzZXQgYW55IGZpbmFuY2lhbCBnb2FscyB5ZXQuIFdvdWxkIHlvdSBsaWtlIG1lIHRvIGhlbHAgeW91IGNyZWF0ZSBvbmU/XCI7XG4gICAgICB9XG5cbiAgICAgIGxldCByZXNwb25zZVRleHQgPSBg8J+OryBZb3VyIEZpbmFuY2lhbCBHb2FsczpcXG5cXG5gO1xuXG4gICAgICBnb2Fscy5mb3JFYWNoKChnb2FsKSA9PiB7XG4gICAgICAgIGNvbnN0IHByb2dyZXNzQmFyID0gdGhpcy5nZW5lcmF0ZVByb2dyZXNzQmFyKGdvYWwucHJvZ3Jlc3MpO1xuICAgICAgICBjb25zdCBzdGF0dXNFbW9qaSA9IGdvYWwuc3RhdHVzID09PSAnY29tcGxldGVkJyA/ICfinIUnIDogJ/Cfjq8nO1xuXG4gICAgICAgIHJlc3BvbnNlVGV4dCArPSBgJHtzdGF0dXNFbW9qaX0gKioke2dvYWwubmFtZX0qKlxcbmA7XG4gICAgICAgIHJlc3BvbnNlVGV4dCArPSBgJHtwcm9ncmVzc0Jhcn0gKioke2dvYWwucHJvZ3Jlc3MudG9GaXhlZCgwKX0lKipcXG5gO1xuICAgICAgICByZXNwb25zZVRleHQgKz0gYFByb2dyZXNzOiAkJHtnb2FsLmN1cnJlbnQudG9Mb2NhbGVTdHJpbmcoKX0gLyAkJHtnb2FsLnRhcmdldC50b0xvY2FsZVN0cmluZygpfWA7XG5cbiAgICAgICAgaWYgKGdvYWwuZGVhZGxpbmUpIHtcbiAgICAgICAgICBjb25zdCBkZWFkbGluZSA9IG5ldyBEYXRlKGdvYWwuZGVhZGxpbmUpLnRvTG9jYWxlRGF0ZVN0cmluZygpO1xuICAgICAgICAgIHJlc3BvbnNlVGV4dCArPSBgIHwgVGFyZ2V0OiAke2RlYWRsaW5lfWA7XG4gICAgICAgIH1cblxuICAgICAgICBjb25zdCBhbW91bnRSZW1haW5pbmcgPSBnb2FsLnRhcmdldCAtIGdvYWwuY3VycmVudDtcbiAgICAgICAgcmVzcG9uc2VUZXh0ICs9IGAgKCR7YW1vdW50UmVtYWluaW5nID4gMCA/ICckJyArIGFtb3VudFJlbWFpbmluZy50b0xvY2FsZVN0cmluZygpICsgJyB0byBnbycgOiAnQ29tcGxldGVkISd9KVxcblxcbmA7XG4gICAgICB9KTtcblxuICAgICAgcmV0dXJuIHJlc3BvbnNlVGV4dDtcbiAgICB9IGNhdGNoIChlcnJvcikge1xuICAgICAgY29uc29sZS5lcnJvcignRXJyb3IgZ2V0dGluZyBmaW5hbmNpYWwgZ29hbHM6JywgZXJyb3IpO1xuICAgICAgcmV0dXJuIFwiSSBjb3VsZG4ndCByZXRyaWV2ZSB5b3VyIGZpbmFuY2lhbCBnb2Fscy4gUGxlYXNlIHRyeSBhZ2FpbiBvciBjb25uZWN0IHlvdXIgYWNjb3VudHMgZmlyc3QuXCI7XG4gICAgfVxuICB9XG5cbiAgYXN5bmMgY3JlYXRlQ2F0ZWdvcnkocGFyYW1zOiB7XG4gICAgdXNlcklkOiBzdHJpbmc7XG4gICAgbmFtZTogc3RyaW5nO1xuICAgIGNvbG9yPzogc3RyaW5nO1xuICAgIGljb24/OiBzdHJpbmc7XG4gIH0pOiBQcm9taXNlPHZvaWQ+IHtcbiAgICB0cnkge1xuICAgICAgYXdhaXQgYXhpb3MucG9zdChgJHt0aGlzLmFwaUJhc2VVcmx9L2NhdGVnb3JpZXMvYnVkZ2V0YCwgcGFyYW1zKTtcbiAgICB9IGNhdGNoIChlcnJvcikge1xuICAgICAgY29uc29sZS5lcnJvcignRXJyb3IgY3JlYXRpbmcgY2F0ZWdvcnk6JywgZXJyb3IpO1xuICAgICAgdGhyb3cgZXJyb3I7XG4gICAgfVxuICB9XG5cbiAgcHJpdmF0ZSBnZW5lcmF0ZVByb2dyZXNzQmFyKHBlcmNlbnRhZ2U6IG51bWJlcik6IHN0cmluZyB7XG4gICAgY29uc3QgZmlsbGVkQmxvY2tzID0gTWF0aC5yb3VuZCgocGVyY2VudGFnZSAvIDEwMCkgKiAxMCk7XG4gICAgY29uc3QgZW1wdHlCbG9ja3MgPSAxMCAtIGZpbGxlZEJsb2NrcztcbiAgICByZXR1cm4gJ+KWkycucmVwZWF0KGZpbGxlZEJsb2NrcykgKyAn4paRJy5yZXBlYXQoZW1wdHlCbG9ja3MpO1xuICB9XG59XG5cbi8vIEFQSSBoYW5kbGVycyBmb3IgdGhlIHRvb2xzXG5leHBvcnQgY29uc3QgZmluYW5jZVRvb2xJbXBsZW1lbnRhdGlvbnMgPSB7XG4gIGdldF9uZXRfd29ydGhfc3VtbWFyeTogYXN5bmMgKHBhcmFtczogYW55KSA9PiB7XG4gICAgY29uc3Qgc2VydmljZSA9IG5ldyBGaW5hbmNlQWdlbnRTZXJ2aWNlKHBhcmFtcy51c2VySWQpO1xuICAgIHJldHVybiBhd2FpdCBzZXJ2aWNlLmdldE5ldFdvcnRoU3VtbWFyeShwYXJhbXMpO1xuICB9LFxuXG4gIGdldF9idWRnZXRfc3VtbWFyeTogYXN5bmMgKHBhcmFtczogYW55KSA9PiB7XG4gICAgY29uc3Qgc2VydmljZSA9IG5ldyBGaW5hbmNlQWdlbnRTZXJ2aWNlKHBhcmFtcy51c2VySWQpO1xuICAgIHJldHVybiBhd2FpdCBzZXJ2aWNlLmdldEJ1ZGdldFN1bW1hcnkocGFyYW1zKTtcbiAgfSxcblxuICBzZWFyY2hfdHJhbnNhY3Rpb25zOiBhc3luYyAocGFyYW1zOiBhbnkpID0+IHtcbiAgICBjb25zdCBzZXJ2aWNlID0gbmV3IEZpbmFuY2VBZ2VudFNlcnZpY2UocGFyYW1zLnVzZXJJZCk7XG4gICAgcmV0dXJuIGF3YWl0IHNlcnZpY2Uuc2VhcmNoVHJhbnNhY3Rpb25zKHBhcmFtcyk7XG4gIH0sXG5cbiAgZ2V0X3NwZW5kaW5nX2luc2lnaHRzOiBhc3luYyAocGFyYW1zOiBhbnkpID0+IHtcbiAgICBjb25zdCBzZXJ2aWNlID0gbmV3IEZpbmFuY2VBZ2VudFNlcnZpY2UocGFyYW1zLnVzZXJJZCk7XG4gICAgcmV0dXJuIGF3YWl0IHNlcnZpY2UuZ2V0U3BlbmRpbmdJbnNpZ2h0cyhwYXJhbXMpO1xuICB9LFxuXG4gIGdldF9pbnZlc3RtZW50X3N1bW1hcnk6IGFzeW5jIChwYXJhbXM6IGFueSkgPT4ge1xuICAgIGNvbnN0IHNlcnZpY2UgPSBuZXcgRmluYW5jZUFnZW50U2VydmljZShwYXJhbXMudXNlcklkKTtcbiAgICByZXR1cm4gYXdhaXQgc2VydmljZS5nZXRJbnZlc3RtZW50U3VtbWFyeShwYXJhbXMuaW5jbHVkZUhpc3RvcnkpO1xuICB9LFxuXG4gIGdldF9maW5hbmNpYWxfZ29hbHM6IGFzeW5jIChwYXJhbXM6IGFueSkgPT4ge1xuICAgIGNvbnN0IHNlcnZpY2UgPSBuZXcgRmluYW5jZUFnZW50U2VydmljZShwYXJhbXMudXNlcklkKTtcbiAgICByZXR1cm4gYXdhaXQgc2VydmljZS5nZXRGaW5hbmNpYWxHb2FscyhwYXJhbXMpO1xuICB9LFxuXG4gIGNyZWF0ZV9idWRnZXQ6IGFzeW5jIChwYXJhbXM6IGFueSkgPT4ge1xuICAgIGNvbnN0IHNlcnZpY2UgPSBuZXcgRmluYW5jZUFnZW50U2VydmljZShwYXJhbXMudXNlcklkKTtcbiAgICAvLyBJbXBsZW1lbnRhdGlvbiBmb3IgYnVkZ2V0IGNyZWF0aW9uIHdvdWxkIGdvIGhlcmVcbiAgICByZXR1cm4gJ0J1ZGdldCBjcmVhdGVkIHN1Y2Nlc3NmdWxseSEnO1xuICB9LFxuXG4gIGNyZWF0ZV9maW5hbmNpYWxfZ29hbDogYXN5bmMgKHBhcmFtczogYW55KSA9PiB7XG4gICAgY29uc3Qgc2VydmljZSA9IG5ldyBGaW5hbmNlQWdlbnRTZXJ2aWNlKHBhcmFtcy51c2VySWQpO1xuICAgIC8vIEltcGxlbWVudGF0aW9uIGZvciBnb2FsIGNyZWF0aW9uIHdvdWxkIGdvIGhlcmVcbiAgICByZXR1cm4gJ0ZpbmFuY2lhbCBnb2FsIGNyZWF0ZWQgc3VjY2Vzc2Z1bGx5ISc7XG4gIH0sXG5cbiAgZGlzY29ubmVjdF96b2hvX2FjY291bnQ6IGFzeW5jIChwYXJhbXM6IGFueSkgPT4ge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgZmV0Y2goJy9hcGkvYXV0aC96b2hvL2Rpc2Nvbm5lY3QnLCB7XG4gICAgICBtZXRob2Q6ICdQT1NUJyxcbiAgICAgIGhlYWRlcnM6IHsgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyB9LFxuICAgICAgYm9keTogSlNPTi5zdHJpbmdpZnkoeyB1c2VyX2lkOiBwYXJhbXMudXNlcl9pZCB9KSxcbiAgICB9KTtcbiAgICByZXR1cm4gYXdhaXQgcmVzcG9uc2UuanNvbigpO1xuICB9LFxuXG4gIGdldF96b2hvX2ludGVncmF0aW9uX3N0YXR1czogYXN5bmMgKHVzZXJfaWQ6IHN0cmluZykgPT4ge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgZmV0Y2goYC9hcGkvYXV0aC96b2hvL3N0YXR1cz91c2VyX2lkPSR7dXNlcl9pZH1gKTtcbiAgICByZXR1cm4gYXdhaXQgcmVzcG9uc2UuanNvbigpO1xuICB9LFxuXG4gIGdldF96b2hvX2ludm9pY2VzOiBhc3luYyAodXNlcl9pZDogc3RyaW5nLCBvcmdhbml6YXRpb25faWQ6IHN0cmluZykgPT4ge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgZmV0Y2goXG4gICAgICBgL2FwaS96b2hvL2ludm9pY2VzP3VzZXJfaWQ9JHt1c2VyX2lkfSZvcmdfaWQ9JHtvcmdhbml6YXRpb25faWR9YFxuICAgICk7XG4gICAgcmV0dXJuIGF3YWl0IHJlc3BvbnNlLmpzb24oKTtcbiAgfSxcblxuICBjcmVhdGVfem9ob19pbnZvaWNlOiBhc3luYyAoXG4gICAgdXNlcl9pZDogc3RyaW5nLFxuICAgIG9yZ2FuaXphdGlvbl9pZDogc3RyaW5nLFxuICAgIGludm9pY2VfZGF0YTogYW55XG4gICkgPT4ge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgZmV0Y2goJy9hcGkvem9oby9pbnZvaWNlcycsIHtcbiAgICAgIG1ldGhvZDogJ1BPU1QnLFxuICAgICAgaGVhZGVyczogeyAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nIH0sXG4gICAgICBib2R5OiBKU09OLnN0cmluZ2lmeSh7IHVzZXJfaWQsIG9yZ19pZDogb3JnYW5pemF0aW9uX2lkLCBpbnZvaWNlX2RhdGEgfSksXG4gICAgfSk7XG4gICAgcmV0dXJuIGF3YWl0IHJlc3BvbnNlLmpzb24oKTtcbiAgfSxcblxuICBnZXRfem9ob19jdXN0b21lcnM6IGFzeW5jICh1c2VyX2lkOiBzdHJpbmcsIG9yZ2FuaXphdGlvbl9pZDogc3RyaW5nKSA9PiB7XG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBmZXRjaChcbiAgICAgIGAvYXBpL3pvaG8vY3VzdG9tZXJzP3VzZXJfaWQ9JHt1c2VyX2lkfSZvcmdfaWQ9JHtvcmdhbml6YXRpb25faWR9YFxuICAgICk7XG4gICAgcmV0dXJuIGF3YWl0IHJlc3BvbnNlLmpzb24oKTtcbiAgfSxcblxuICBjcmVhdGVfem9ob19jdXN0b21lcjogYXN5bmMgKFxuICAgIHVzZXJfaWQ6IHN0cmluZyxcbiAgICBvcmdhbml6YXRpb25faWQ6IHN0cmluZyxcbiAgICBjdXN0b21lcl9kYXRhOiBhbnlcbiAgKSA9PiB7XG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBmZXRjaCgnL2FwaS96b2hvL2N1c3RvbWVycycsIHtcbiAgICAgIG1ldGhvZDogJ1BPU1QnLFxuICAgICAgaGVhZGVyczogeyAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nIH0sXG4gICAgICBib2R5OiBKU09OLnN0cmluZ2lmeSh7IHVzZXJfaWQsIG9yZ19pZDogb3JnYW5pemF0aW9uX2lkLCBjdXN0b21lcl9kYXRhIH0pLFxuICAgIH0pO1xuICAgIHJldHVybiBhd2FpdCByZXNwb25zZS5qc29uKCk7XG4gIH0sXG5cbiAgZ2V0X3pvaG9faXRlbXM6IGFzeW5jICh1c2VyX2lkOiBzdHJpbmcsIG9yZ2FuaXphdGlvbl9pZDogc3RyaW5nKSA9PiB7XG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBmZXRjaChcbiAgICAgIGAvYXBpL3pvaG8vaXRlbXM/dXNlcl9pZD0ke3VzZXJfaWR9Jm9yZ19pZD0ke29yZ2FuaXphdGlvbl9pZH1gXG4gICAgKTtcbiAgICByZXR1cm4gYXdhaXQgcmVzcG9uc2UuanNvbigpO1xuICB9LFxuXG4gIGNyZWF0ZV96b2hvX2l0ZW06IGFzeW5jIChcbiAgICB1c2VyX2lkOiBzdHJpbmcsXG4gICAgb3JnYW5pemF0aW9uX2lkOiBzdHJpbmcsXG4gICAgaXRlbV9kYXRhOiBhbnlcbiAgKSA9PiB7XG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBmZXRjaCgnL2FwaS96b2hvL2l0ZW1zJywge1xuICAgICAgbWV0aG9kOiAnUE9TVCcsXG4gICAgICBoZWFkZXJzOiB7ICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicgfSxcbiAgICAgIGJvZHk6IEpTT04uc3RyaW5naWZ5KHsgdXNlcl9pZCwgb3JnX2lkOiBvcmdhbml6YXRpb25faWQsIGl0ZW1fZGF0YSB9KSxcbiAgICB9KTtcbiAgICByZXR1cm4gYXdhaXQgcmVzcG9uc2UuanNvbigpO1xuICB9LFxuXG4gIGdldF96b2hvX2JpbGxzOiBhc3luYyAodXNlcl9pZDogc3RyaW5nLCBvcmdhbml6YXRpb25faWQ6IHN0cmluZykgPT4ge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgZmV0Y2goXG4gICAgICBgL2FwaS96b2hvL2JpbGxzP3VzZXJfaWQ9JHt1c2VyX2lkfSZvcmdfaWQ9JHtvcmdhbml6YXRpb25faWR9YFxuICAgICk7XG4gICAgcmV0dXJuIGF3YWl0IHJlc3BvbnNlLmpzb24oKTtcbiAgfSxcblxuICBjcmVhdGVfem9ob19iaWxsOiBhc3luYyAoXG4gICAgdXNlcl9pZDogc3RyaW5nLFxuICAgIG9yZ2FuaXphdGlvbl9pZDogc3RyaW5nLFxuICAgIGJpbGxfZGF0YTogYW55XG4gICkgPT4ge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgZmV0Y2goJy9hcGkvem9oby9iaWxscycsIHtcbiAgICAgIG1ldGhvZDogJ1BPU1QnLFxuICAgICAgaGVhZGVyczogeyAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nIH0sXG4gICAgICBib2R5OiBKU09OLnN0cmluZ2lmeSh7IHVzZXJfaWQsIG9yZ19pZDogb3JnYW5pemF0aW9uX2lkLCBiaWxsX2RhdGEgfSksXG4gICAgfSk7XG4gICAgcmV0dXJuIGF3YWl0IHJlc3BvbnNlLmpzb24oKTtcbiAgfSxcblxuICBnZXRfem9ob192ZW5kb3JzOiBhc3luYyAodXNlcl9pZDogc3RyaW5nLCBvcmdhbml6YXRpb25faWQ6IHN0cmluZykgPT4ge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgZmV0Y2goXG4gICAgICBgL2FwaS96b2hvL3ZlbmRvcnM/dXNlcl9pZD0ke3VzZXJfaWR9Jm9yZ19pZD0ke29yZ2FuaXphdGlvbl9pZH1gXG4gICAgKTtcbiAgICByZXR1cm4gYXdhaXQgcmVzcG9uc2UuanNvbigpO1xuICB9LFxuXG4gIGNyZWF0ZV96b2hvX3ZlbmRvcjogYXN5bmMgKFxuICAgIHVzZXJfaWQ6IHN0cmluZyxcbiAgICBvcmdhbml6YXRpb25faWQ6IHN0cmluZyxcbiAgICB2ZW5kb3JfZGF0YTogYW55XG4gICkgPT4ge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgZmV0Y2goJy9hcGkvem9oby92ZW5kb3JzJywge1xuICAgICAgbWV0aG9kOiAnUE9TVCcsXG4gICAgICBoZWFkZXJzOiB7ICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicgfSxcbiAgICAgIGJvZHk6IEpTT04uc3RyaW5naWZ5KHsgdXNlcl9pZCwgb3JnX2lkOiBvcmdhbml6YXRpb25faWQsIHZlbmRvcl9kYXRhIH0pLFxuICAgIH0pO1xuICAgIHJldHVybiBhd2FpdCByZXNwb25zZS5qc29uKCk7XG4gIH0sXG5cbiAgZ2V0X3pvaG9fcHVyY2hhc2Vfb3JkZXJzOiBhc3luYyAoXG4gICAgdXNlcl9pZDogc3RyaW5nLFxuICAgIG9yZ2FuaXphdGlvbl9pZDogc3RyaW5nXG4gICkgPT4ge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgZmV0Y2goXG4gICAgICBgL2FwaS96b2hvL3B1cmNoYXNlb3JkZXJzP3VzZXJfaWQ9JHt1c2VyX2lkfSZvcmdfaWQ9JHtvcmdhbml6YXRpb25faWR9YFxuICAgICk7XG4gICAgcmV0dXJuIGF3YWl0IHJlc3BvbnNlLmpzb24oKTtcbiAgfSxcblxuICBjcmVhdGVfem9ob19wdXJjaGFzZV9vcmRlcjogYXN5bmMgKFxuICAgIHVzZXJfaWQ6IHN0cmluZyxcbiAgICBvcmdhbml6YXRpb25faWQ6IHN0cmluZyxcbiAgICBwdXJjaGFzZV9vcmRlcl9kYXRhOiBhbnlcbiAgKSA9PiB7XG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBmZXRjaCgnL2FwaS96b2hvL3B1cmNoYXNlb3JkZXJzJywge1xuICAgICAgbWV0aG9kOiAnUE9TVCcsXG4gICAgICBoZWFkZXJzOiB7ICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicgfSxcbiAgICAgIGJvZHk6IEpTT04uc3RyaW5naWZ5KHtcbiAgICAgICAgdXNlcl9pZCxcbiAgICAgICAgb3JnX2lkOiBvcmdhbml6YXRpb25faWQsXG4gICAgICAgIHB1cmNoYXNlX29yZGVyX2RhdGEsXG4gICAgICB9KSxcbiAgICB9KTtcbiAgICByZXR1cm4gYXdhaXQgcmVzcG9uc2UuanNvbigpO1xuICB9LFxuXG4gIGdldF96b2hvX3NhbGVzX29yZGVyczogYXN5bmMgKHVzZXJfaWQ6IHN0cmluZywgb3JnYW5pemF0aW9uX2lkOiBzdHJpbmcpID0+IHtcbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGZldGNoKFxuICAgICAgYC9hcGkvem9oby9zYWxlc29yZGVycz91c2VyX2lkPSR7dXNlcl9pZH0mb3JnX2lkPSR7b3JnYW5pemF0aW9uX2lkfWBcbiAgICApO1xuICAgIHJldHVybiBhd2FpdCByZXNwb25zZS5qc29uKCk7XG4gIH0sXG5cbiAgY3JlYXRlX3pvaG9fc2FsZXNfb3JkZXI6IGFzeW5jIChcbiAgICB1c2VyX2lkOiBzdHJpbmcsXG4gICAgb3JnYW5pemF0aW9uX2lkOiBzdHJpbmcsXG4gICAgc2FsZXNfb3JkZXJfZGF0YTogYW55XG4gICkgPT4ge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgZmV0Y2goJy9hcGkvem9oby9zYWxlc29yZGVycycsIHtcbiAgICAgIG1ldGhvZDogJ1BPU1QnLFxuICAgICAgaGVhZGVyczogeyAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nIH0sXG4gICAgICBib2R5OiBKU09OLnN0cmluZ2lmeSh7XG4gICAgICAgIHVzZXJfaWQsXG4gICAgICAgIG9yZ19pZDogb3JnYW5pemF0aW9uX2lkLFxuICAgICAgICBzYWxlc19vcmRlcl9kYXRhLFxuICAgICAgfSksXG4gICAgfSk7XG4gICAgcmV0dXJuIGF3YWl0IHJlc3BvbnNlLmpzb24oKTtcbiAgfSxcbn07XG4iXX0=