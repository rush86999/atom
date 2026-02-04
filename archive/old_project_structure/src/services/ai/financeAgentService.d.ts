import { z } from 'zod';
import { ChatCompletionTool } from 'openai/resources/chat/completions';
declare const NetWorthParamsSchema: z.ZodObject<{
    userId: z.ZodString;
    includeHistory: z.ZodDefault<z.ZodOptional<z.ZodBoolean>>;
    dateRange: z.ZodOptional<z.ZodObject<{
        start: z.ZodOptional<z.ZodString>;
        end: z.ZodOptional<z.ZodString>;
    }, "strip", z.ZodTypeAny, {
        end?: string | undefined;
        start?: string | undefined;
    }, {
        end?: string | undefined;
        start?: string | undefined;
    }>>;
}, "strip", z.ZodTypeAny, {
    userId: string;
    includeHistory: boolean;
    dateRange?: {
        end?: string | undefined;
        start?: string | undefined;
    } | undefined;
}, {
    userId: string;
    includeHistory?: boolean | undefined;
    dateRange?: {
        end?: string | undefined;
        start?: string | undefined;
    } | undefined;
}>;
declare const BudgetQueryParamsSchema: z.ZodObject<{
    userId: z.ZodString;
    period: z.ZodDefault<z.ZodOptional<z.ZodEnum<["current", "last", "future"]>>>;
    categories: z.ZodOptional<z.ZodArray<z.ZodString, "many">>;
    month: z.ZodOptional<z.ZodString>;
}, "strip", z.ZodTypeAny, {
    userId: string;
    period: "last" | "current" | "future";
    month?: string | undefined;
    categories?: string[] | undefined;
}, {
    userId: string;
    month?: string | undefined;
    categories?: string[] | undefined;
    period?: "last" | "current" | "future" | undefined;
}>;
declare const TransactionSearchParamsSchema: z.ZodObject<{
    userId: z.ZodString;
    query: z.ZodOptional<z.ZodString>;
    category: z.ZodOptional<z.ZodString>;
    amountRange: z.ZodOptional<z.ZodObject<{
        min: z.ZodOptional<z.ZodNumber>;
        max: z.ZodOptional<z.ZodNumber>;
    }, "strip", z.ZodTypeAny, {
        max?: number | undefined;
        min?: number | undefined;
    }, {
        max?: number | undefined;
        min?: number | undefined;
    }>>;
    dateRange: z.ZodObject<{
        start: z.ZodString;
        end: z.ZodString;
    }, "strip", z.ZodTypeAny, {
        end: string;
        start: string;
    }, {
        end: string;
        start: string;
    }>;
    limit: z.ZodDefault<z.ZodOptional<z.ZodNumber>>;
}, "strip", z.ZodTypeAny, {
    userId: string;
    limit: number;
    dateRange: {
        end: string;
        start: string;
    };
    query?: string | undefined;
    category?: string | undefined;
    amountRange?: {
        max?: number | undefined;
        min?: number | undefined;
    } | undefined;
}, {
    userId: string;
    dateRange: {
        end: string;
        start: string;
    };
    query?: string | undefined;
    category?: string | undefined;
    limit?: number | undefined;
    amountRange?: {
        max?: number | undefined;
        min?: number | undefined;
    } | undefined;
}>;
declare const GoalParamsSchema: z.ZodObject<{
    userId: z.ZodString;
    goalId: z.ZodOptional<z.ZodString>;
    goalType: z.ZodOptional<z.ZodEnum<["savings", "retirement", "debt", "purchase", "emergency"]>>;
}, "strip", z.ZodTypeAny, {
    userId: string;
    goalType?: "savings" | "emergency" | "retirement" | "purchase" | "debt" | undefined;
    goalId?: string | undefined;
}, {
    userId: string;
    goalType?: "savings" | "emergency" | "retirement" | "purchase" | "debt" | undefined;
    goalId?: string | undefined;
}>;
export type NetWorthSummary = {
    current: number;
    change: number;
    changePercent: number;
    assets: number;
    liabilities: number;
    history?: Array<{
        date: string;
        netWorth: number;
    }>;
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
    categories: Array<{
        category: string;
        amount: number;
        percentage: number;
    }>;
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
export declare const financeTools: ChatCompletionTool[];
export declare class FinanceAgentService {
    private apiBaseUrl;
    private userId;
    constructor(userId: string, apiBaseUrl?: string);
    getNetWorthSummary(params: z.infer<typeof NetWorthParamsSchema>): Promise<string>;
    getBudgetSummary(params: z.infer<typeof BudgetQueryParamsSchema>): Promise<string>;
    searchTransactions(params: z.infer<typeof TransactionSearchParamsSchema>): Promise<string>;
    getSpendingInsights(params?: {
        category?: string;
        period?: string;
    }): Promise<string>;
    getInvestmentSummary(includeHistory?: boolean): Promise<string>;
    getFinancialGoals(params?: z.infer<typeof GoalParamsSchema>): Promise<string>;
    createCategory(params: {
        userId: string;
        name: string;
        color?: string;
        icon?: string;
    }): Promise<void>;
    private generateProgressBar;
}
export declare const financeToolImplementations: {
    get_net_worth_summary: (params: any) => Promise<string>;
    get_budget_summary: (params: any) => Promise<string>;
    search_transactions: (params: any) => Promise<string>;
    get_spending_insights: (params: any) => Promise<string>;
    get_investment_summary: (params: any) => Promise<string>;
    get_financial_goals: (params: any) => Promise<string>;
    create_budget: (params: any) => Promise<string>;
    create_financial_goal: (params: any) => Promise<string>;
    disconnect_zoho_account: (params: any) => Promise<any>;
    get_zoho_integration_status: (user_id: string) => Promise<any>;
    get_zoho_invoices: (user_id: string, organization_id: string) => Promise<any>;
    create_zoho_invoice: (user_id: string, organization_id: string, invoice_data: any) => Promise<any>;
    get_zoho_customers: (user_id: string, organization_id: string) => Promise<any>;
    create_zoho_customer: (user_id: string, organization_id: string, customer_data: any) => Promise<any>;
    get_zoho_items: (user_id: string, organization_id: string) => Promise<any>;
    create_zoho_item: (user_id: string, organization_id: string, item_data: any) => Promise<any>;
    get_zoho_bills: (user_id: string, organization_id: string) => Promise<any>;
    create_zoho_bill: (user_id: string, organization_id: string, bill_data: any) => Promise<any>;
    get_zoho_vendors: (user_id: string, organization_id: string) => Promise<any>;
    create_zoho_vendor: (user_id: string, organization_id: string, vendor_data: any) => Promise<any>;
    get_zoho_purchase_orders: (user_id: string, organization_id: string) => Promise<any>;
    create_zoho_purchase_order: (user_id: string, organization_id: string, purchase_order_data: any) => Promise<any>;
    get_zoho_sales_orders: (user_id: string, organization_id: string) => Promise<any>;
    create_zoho_sales_order: (user_id: string, organization_id: string, sales_order_data: any) => Promise<any>;
};
export {};
