import { SkillResponse } from '../types';
export interface FinanceQuery {
    intent: 'net_worth' | 'budgets' | 'spending' | 'goals' | 'accounts' | 'investments' | 'insights' | 'create_budget' | 'create_goal' | 'tax_question';
    parameters: Record<string, any>;
    timeframe?: 'current' | 'last_month' | 'last_week' | 'this_quarter' | 'year_to_date' | 'custom';
    category?: string;
    amount?: number;
    goal_type?: 'emergency' | 'retirement' | 'purchase' | 'debt_payoff' | 'vacation';
}
export declare function handleFinanceQuery(userId: string, query: string, context?: any): Promise<SkillResponse<string>>;
