export interface FinanceSummary {
    netWorth: number;
    assets: number;
    liabilities: number;
    changeToday: number;
    changePercent: number;
    lastUpdated: string;
}
export interface BudgetDetail {
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
}
export interface SpendingDetail {
    totalSpent: number;
    period: string;
    topCategories: Array<{
        category: string;
        amount: number;
        percentage: number;
    }>;
    transactions: Array<{
        id: string;
        name: string;
        amount: number;
        category: string;
        date: string;
    }>;
}
export interface InvestmentPortfolio {
    totalValue: number;
    totalGainLoss: number;
    totalReturnPct: number;
    holdings: Array<{
        id: string;
        name: string;
        value: number;
        shares: number;
        currentPrice: number;
        purchasePrice: number;
        gainLoss: number;
        returnPct: number;
    }>;
}
export interface FinancialGoal {
    id: string;
    name: string;
    targetAmount: number;
    current: number;
    progress: number;
    goalType: string;
    targetDate?: string;
    status: string;
}
interface FinanceQueryResponse {
    response: string;
    data?: any;
    suggestions?: string[];
}
export declare function useFinanceAgent(): {
    queryFinance: (question: string, context?: any) => Promise<FinanceQueryResponse | undefined>;
    quickActions: {
        getNetWorth: () => Promise<FinanceQueryResponse | undefined>;
        getBudget: () => Promise<FinanceQueryResponse | undefined>;
        getSpendingAnalysis: (category?: string) => Promise<FinanceQueryResponse | undefined>;
        getGoals: () => Promise<FinanceQueryResponse | undefined>;
        getInvestments: () => Promise<FinanceQueryResponse | undefined>;
        createBudget: (category: string, amount: number) => Promise<FinanceQueryResponse | undefined>;
        createGoal: (name: string, targetAmount: number, type?: string, date?: string) => Promise<FinanceQueryResponse | undefined>;
    };
    fetchNetWorth: (userId: string) => Promise<any>;
    fetchBudgets: (userId: string) => Promise<any>;
    fetchGoals: (userId: string) => Promise<any>;
    fetchInvestments: (userId: string) => Promise<any>;
    getRecommendations: (userId: string) => Promise<FinanceQueryResponse | undefined>;
    isLoading: boolean;
    lastResponse: FinanceQueryResponse | null;
    clearResponse: () => void;
};
export declare function useFinanceSuggestions(): {
    n: any;
    suggestions: string[];
    generateSuggestions: (input: string) => void;
    getPopularCommands: () => any[];
    allSuggestions: any[];
};
export declare function useFinanceEvents(): {
    n: any;
    events: any;
    addEvent: (type: string, message: string) => void;
    clearEvents: () => void;
    latestEvent: any;
};
export {};
