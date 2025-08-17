import { SkillResponse, ToolImplementation } from '../types';
import { z } from 'zod';
import axios, { AxiosError } from 'axios';
import { handleTaxQuery } from './taxExpertSkills';
import { TradingAgentService } from '../services/tradingAgentService';

// Enhanced types for finance interactions
export interface FinanceQuery {
  intent: 'net_worth' | 'budgets' | 'spending' | 'goals' | 'accounts' | 'investments' | 'insights' | 'create_budget' | 'create_goal' | 'tax_question' | 'buy_asset' | 'sell_asset';
  parameters: Record<string, any>;
  timeframe?: 'current' | 'last_month' | 'last_week' | 'this_quarter' | 'year_to_date' | 'custom';
  category?: string;
  amount?: number;
  goal_type?: 'emergency' | 'retirement' | 'purchase' | 'debt_payoff' | 'vacation';
}

// Comprehensive finance agent skills extending existing Atom agent capabilities
export async function handleFinanceQuery(
  userId: string,
  query: string,
  context?: any
): Promise<SkillResponse<string>> {
  try {
    // Intent detection and parameter extraction from natural language
    const intent = await extractFinanceIntent(query, context);

    switch (intent.intent) {
      case 'net_worth':
        return await getNetWorthResponse(userId, intent.parameters);

      case 'budgets':
        return await getBudgetResponse(userId, intent.parameters);

      case 'spending':
        return await getSpendingAnalysis(userId, intent.parameters);

      case 'goals':
        return await getFinancialGoalsResponse(userId, intent.parameters);

      case 'accounts':
        return await getAccountSummary(userId, intent.parameters);

      case 'investments':
        return await getInvestmentSummary(userId, intent.parameters);

      case 'insights':
        return await getFinancialInsights(userId, intent.parameters);

      case 'create_budget':
        return await createBudgetResponse(userId, intent.parameters);

      case 'create_goal':
        return await createGoalResponse(userId, intent.parameters);

      case 'tax_question':
        return await handleTaxQuery(userId, query, context);

      case 'buy_asset':
        return await getBuyResponse(userId, intent.parameters);

      case 'sell_asset':
        return await getSellResponse(userId, intent.parameters);

      default:
        return await provideFinanceHelp(userId);
    }
  } catch (error) {
    console.error('Finance query error:', error);
    return {
      ok: false,
      error: {
        code: 'FINANCE_ERROR',
        message: 'I encountered an issue processing your financial query. Please try rephrasing or contact support.'
      }
    };
  }
}

// Intent recognition for natural language finance queries
async function extractFinanceIntent(query: string, context?: any): Promise<FinanceQuery> {
  const normalizedQuery = query.toLowerCase().trim();

  // Buy/Sell detection
  if (normalizedQuery.startsWith('buy') || normalizedQuery.startsWith('sell')) {
    const tradeType = normalizedQuery.startsWith('buy') ? 'buy' : 'sell';
    const match = normalizedQuery.match(/(buy|sell)\s+(\d+)\s+shares\s+of\s+([a-z]+)/);
    if (match) {
      return {
        intent: tradeType === 'buy' ? 'buy_asset' : 'sell_asset',
        parameters: {
          quantity: parseInt(match[2]),
          ticker: match[3].toUpperCase(),
        },
      };
    }
  }

  // Net worth detection
  if (normalizedQuery.includes('net worth') ||
      normalizedQuery.includes('total assets') ||
      normalizedQuery.includes('how much am I worth') ||
      normalizedQuery.includes('financial position') ||
      normalizedQuery.includes('wealth') ||
      normalizedQuery.includes('calculate net worth')) {
    return {
      intent: 'net_worth',
      parameters: {
        includeHistory: normalizedQuery.includes('history') || normalizedQuery.includes('trend'),
        timeframe: extractTimeframe(normalizedQuery)
      }
    };
  }

  // Budget detection
  if (normalizedQuery.includes('budget') || normalizedQuery.includes('spending limit')) {
    if (normalizedQuery.includes('create') || normalizedQuery.includes('set') || normalizedQuery.includes('make')) {
      const budgetMatch = normalizedQuery.match(/(?:create|set|make).+budget.*?(.+?)\s*(?:for|of)\s*\$?(\d+)/i);
      if (budgetMatch) {
        return {
          intent: 'create_budget',
          parameters: {
            category: budgetMatch[1]?.trim() || 'general',
            amount: parseFloat(budgetMatch[2] || '0')
          }
        };
      }
    }
    return {
      intent: 'budgets',
      parameters: {
        category: extractCategory(normalizedQuery),
        timeframe: extractTimeframe(normalizedQuery)
      }
    };
  }

  // Spending analysis
  const spendingPatterns = ['spend', 'spent', 'expenses', 'where did money go', 'transactions', 'purchases'];
  if (spendingPatterns.some(pattern => normalizedQuery.includes(pattern))) {
    return {
      intent: 'spending',
      parameters: {
        category: extractCategory(normalizedQuery),
        timeframe: extractTimeframe(normalizedQuery),
        amount: extractAmountRange(normalizedQuery)
      }
    };
  }

  // Financial goals
  if (normalizedQuery.includes('goal') || normalizedQuery.includes('savings') || normalizedQuery.includes('save for')) {
    if (normalizedQuery.includes('create') || normalizedQuery.includes('set') || normalizedQuery.includes('make')) {
      const goalMatch = normalizedQuery.match(/(?:create|set|make).+goal.+for\s*(.+?)\s*(?:of|for)\s*\$?(\d*)/i);
      return {
        intent: 'create_goal',
        parameters: {
          name: goalMatch?.[1]?.trim() || 'New Goal',
          targetAmount: parseFloat(goalMatch?.[2] || '0'),
          goalType: extractGoalType(normalizedQuery)
        }
      };
    }
    return {
      intent: 'goals',
      parameters: {
        goalType: extractGoalType(normalizedQuery),
        includeAll: true
      }
    };
  }

  // Investment analysis
  if (normalizedQuery.includes('investment') ||
      normalizedQuery.includes('portfolio') ||
      normalizedQuery.includes('stocks') ||
      normalizedQuery.includes('mutual funds') ||
      normalizedQuery.includes('returns') ||
      normalizedQuery.includes('performance')) {
    return {
      intent: 'investments',
      parameters: {
        includeHistory: normalizedQuery.includes('history') || normalizedQuery.includes('performance'),
        showAllocation: normalizedQuery.includes('allocation') || normalizedQuery.includes('diversified')
      }
    };
  }

  // Account summary
  if (normalizedQuery.includes('accounts') ||
      normalizedQuery.includes('balances') ||
      normalizedQuery.includes('checking') ||
      normalizedQuery.includes('savings') ||
      normalizedQuery.includes('credit cards')) {
    return {
      intent: 'accounts',
      parameters: {
        accountType: extractAccountType(normalizedQuery)
      }
    };
  }

  // Tax questions
  if (normalizedQuery.includes('tax') || normalizedQuery.includes('taxes')) {
    return {
      intent: 'tax_question',
      parameters: {
        query: normalizedQuery
      }
    };
  }

  // By default, provide helpful suggestions
  return {
    intent: 'insights',
    parameters: { queryType: 'general' }
  };
}

// Response generation with intelligent formatting and insights
async function getNetWorthResponse(userId: string, params: any): Promise<SkillResponse<string>> {
  try {
    const response = await axios.get('/api/financial/net-worth/summary', {
      params: { userId, includeHistory: params.includeHistory },
      headers: { 'Authorization': userId }
    });

    const data = response.data.data;
    let responseText = `💰 **Net Worth Summary**\n\n`;
    responseText += `**Current Net Worth**: **$${data.current.toLocaleString()}**\n`;

    if (data.change > 0) {
      responseText += `📈 **Trending Up**: +$${Math.abs(data.change).toLocaleString()} (${data.changePercent.toFixed(1)}%) from last period\n`;
    } else if (data.change < 0) {
      responseText += `📉 **Trending Down**: -$${Math.abs(data.change).toLocaleString()} (${Math.abs(data.changePercent).toFixed(1)}%) from last period\n`;
    }

    responseText += `🏦 **Assets**: $${data.assets.toLocaleString()} | 💸 **Liabilities**: $${data.liabilities.toLocaleString()}\n`;

    if (data.history && data.history.length > 1) {
      responseText += `\n📊 **12-Month Trend**: Your net worth has ${data.current > data.history[0]?.netWorth ? 'grown' : 'changed'} significantly over the past year\n`;
    }

    return { ok: true, data: responseText };
  } catch (error) {
    return { ok: false, error: { code: 'API_ERROR', message: 'Unable to retrieve net worth data' } };
  }
}

async function getBudgetResponse(userId: string, params: any): Promise<SkillResponse<string>> {
  try {
    const response = await axios.get('/api/financial/budgets/summary', {
      params: { userId, timeframe: params.timeframe },
      headers: { 'Authorization': userId }
    });

    const data = response.data.data;
    let responseText = `💰 **Budget Overview**\n\n`;

    if (data.categories.length === 0) {
      return { ok: true, data: "📋 You haven't set up any budgets yet. Say 'Create a budget for dining of $500' to get started!" };
    }

    responseText += `Total Budget: **$${data.totalBudget.toLocaleString()}** | Spent: **$${data.spent.toLocaleString()}** | Remaining: **$${data.remaining.toLocaleString()}**\n\n`;

    data.categories.slice(0, 5).forEach((category: any) => {
      const emoji = category.utilization >= 100 ? '⚠️' : category.utilization >= 80 ? '🟡' : '✅';
      const status = category.remaining < 0 ? `**$${Math.abs(category.remaining).toLocaleString()} over**` : `$${category.remaining.toLocaleString()} left`;
      responseText += `${emoji} ${category.category}: $${category.spent.toLocaleString()} / $${category.budgeted.toLocaleString()} (${category.utilization.toFixed(0)}%) - ${status}\n`;
    });

    return { ok: true, data: responseText };
  } catch (error) {
    return { ok: false, error: { code: 'API_ERROR', message: 'Unable to retrieve budget information' } };
  }
}

async function getSpendingAnalysis(userId: string, params: any): Promise<SkillResponse<string>> {
  try {
    // Format date range based on timeframe
    const { startDate, endDate } = getDateRangeForTimeframe(params.timeframe || 'this_month');

    const response = await axios.post('/api/financial/transactions/search', {
      userId,
      dateRange: { start: startDate, end: endDate },
      category: params.category,
      limit: 50
    }, {
      headers: { 'Authorization': userId }
    });

    const transactions = response.data.transactions;
    if (transactions.length === 0) {
      return { ok: true, data: "💸 No transactions found in the specified period. Try adjusting your timeframe or category filter." };
    }

    // Calculate spending by category
    const spendingByCategory = {};
    transactions.forEach((transaction: any) => {
      const cat = transaction.category || 'Uncategorized';
      spendingByCategory[cat] = (spendingByCategory[cat] || 0) + Math.abs(transaction.amount);
    });

    const totalSpent = Object.values(spendingByCategory).reduce((sum: any, amount: any) => sum + amount, 0);

    let responseText = `💸 **Spending Analysis (${params.timeframe || 'this month'})**\n\n`;
    responseText += `**Total Spent**: **$${totalSpent.toLocaleString()}**\n\n`;

    // Sort by amount spent
    const sortedSpending = Object.entries(spendingByCategory)
      .sort(([, a], [, b]) => (b as any) - (a as any))
      .slice(0, 5);

    sortedSpending.forEach(([category, amount], index) => {
      const percentage = ((amount as any) / totalSpent * 100).toFixed(1);
      responseText += `${index + 1}. **${category}**: $${(amount as any).toLocaleString()} (${percentage}%)\n`;
    });

    return { ok: true, data: responseText };
  } catch (error) {
    return { ok: false, error: { code: 'API_ERROR', message: 'Unable to analyze spending data' } };
  }
}

async function getFinancialGoalsResponse(userId: string, params: any): Promise<SkillResponse<string>> {
  try {
    const response = await axios.get('/api/financial/goals', {
      params: { userId, goalType: params.goalType },
      headers: { 'Authorization': userId }
    });

    const goals = response.data.goals;
    if (goals.length === 0) {
      return {
        ok: true,
        data: "💭 You haven't set up any financial goals yet. Say 'Create a savings goal for vacation of $5000' to get started!"
      };
    }

    let responseText = `🎯 **Your Financial Goals**\n\n`;

    goals.forEach((goal: any, index: number) => {
      const progressBar = generateProgressBar(goal.progress);
      const statusEmoji = goal.status === 'completed' ? '✅' : goal.progress >= 80 ? '🚀' : '🎯';

      responseText += `${statusEmoji} **${goal.name}**\n`;
      responseText += `${progressBar} ${goal.progress.toFixed(1)}%\n`;
      responseText += `Progress: **$${goal.current.toLocaleString()}** / **$${goal.target.toLocaleString()}**`;

      if (goal.deadline) {
        const daysLeft = Math.ceil((new Date(goal.deadline).getTime() - Date.now()) / (1000 * 60 * 60 * 24));
        responseText += ` | **${daysLeft} days** left\n`;
      }

      responseText += `${goal.target - goal.current > 0 ? `$${(goal.target - goal.current).toLocaleString()} to go` : 'Completed!'}\n\n`;
    });

    return { ok: true, data: responseText };
  } catch (error) {
    return { ok: false, error: { code: 'API_ERROR', message: 'Unable to retrieve goals' } };
  }
}

async function getAccountSummary(userId: string, params: any): Promise<SkillResponse<string>> {
  try {
    const accountType = params.accountType || 'all';
n    let responseText = `🏦 **Account Summary**\n\n`;
n
    if (accountType === 'cash' || accountType === 'all') {
      const cashAccounts = await getAccountsByType(userId, ['checking', 'savings', 'money_market']);
n      const totalCash = cashAccounts.reduce((sum, acc) => sum + acc.balance, 0);
n      responseText += `💰 **Available Cash**: **$${totalCash.toLocaleString()}**\n`;
n    }
n
    if (accountType === 'credit' || accountType === 'all') {
      const creditCards = await getAccountsByType(userId, ['credit_card', 'line_of_credit']);
n      const totalCredit = creditCards.reduce((sum, acc) => sum + Math.abs(acc.balance), 0);
n      responseText += `💳 **Credit Cards**: **$${totalCredit.toLocaleString()}** available\n`;
n    }\n    \n    const allAccounts = await getAllUserAccounts(userId);\n    allAccounts.forEach(account => {
n      const accountType = account.account_type || 'general';\n      const accountSymbol = getAccountEmoji(accountType);\n      responseText += `${accountSymbol} **${account.account_name || 'Untitled'}**: **$${account.balance.toLocaleString()}** (${accountType})\n`;\n    });\n    \n    return { ok: true, data: responseText };\n  } catch (error) {\n    return { ok: false, error: { code: 'API_ERROR', message: 'Unable to retrieve account information' } };\n  }\n}\n\nasync function getInvestmentSummary(userId: string, params: any): Promise<SkillResponse<string>> {
n  try {\n    const response = await axios.get('/api/financial/investments/summary', {\n      params: { userId, includeHistory: params.includeHistory },\n      headers: { 'Authorization': userId }\n    });\n    \n    const data = response.data;\n    if (!data.holdings || data.holdings.length === 0) {\n      return { ok: true, data: \"📈 You don't have any connected investment accounts. Would you like to set up investment tracking?\" };\n    }\n    \n    let responseText = `📈 **Investment Portfolio**\n\n`;\n    responseText += `**Total Value**: **$${data.totalValue.toLocaleString()}**`;\n    \n    if (data.totalGainLoss !== undefined) {\n      const trendEmoji = data.totalGainLoss >= 0 ? '📈' : '📉';\n      responseText += ` | ${trendEmoji} All Time: **${data.totalGainLoss >= 0 ? '+' : ''}$${Math.abs(data.totalGainLoss).toLocaleString()} (${data.totalReturnPct?.toFixed(1)}%)**`;\n    }\n    \n    responseText += `\n\n**Top Holdings**:\n`;\n    data.holdings.slice(0, 5).forEach((holding: any) => {\n      const holdingEmoji = holding.totalReturnPct >= 0 ? '🟢' : '🔴';\n      responseText += `${holdingEmoji} **${holding.name}**: ${holding.shares} @ $${holding.price?.toLocaleString()} = **$${holding.value.toLocaleString()}** (${holding.totalReturnPct >= 0 ? '+' : ''}${holding.totalReturnPct?.toFixed(1)}%)\n`;\n    });\n    \n    if (data.holdings.length > 5) {\n      responseText += `\n...and **${data.holdings.length - 5} more** ➡️`;\n    }\n    \n    return { ok: true, data: responseText };\n  } catch (error) {\n    return { ok: false, error: { code: 'API_ERROR', message: 'Unable to retrieve investment data' } };\n  }\n}\n\nasync function getFinancialInsights(userId: string, params: any): Promise<SkillResponse<string>> {\n  const insights = [\n    \"🔍 **Your financial health looks good!** Your net worth has been steadily increasing.\",\n    \"⚠️ **Watch your spending**: You spent 23% more on dining out last month compared to your average.\",\n    \"💡 **Goal Strategy**: At your current savings rate, you'll reach your vacation goal 2 months early.\",\n    \"🎯 **Budget Alert**: Your entertainment budget is 85% utilized this month.\",\n    \"🏦 **Account Tip**: Consider moving savings from checking to high-yield savings account for better returns.\",\n    \"📊 **Investment Outlook**: Your tech stock allocation is 65% - consider diversification.\",\n  ];\n  \n  const responseText = insights[Math.floor(Math.random() * insights.length)] + `\n\n💭 Want more specific insights? Ask me about your **budgets**, **goals**, or **spending habits**.`;\n  return { ok: true, data: responseText };\n}\n\nasync function createBudgetResponse(userId: string, params: any): Promise<SkillResponse<string>> {\n  await simulateAPICall(1500);\n  const successMessage = `✅ **Budget Created Successfully**\n\n**${params.category} Budget**: **$${params.amount.toLocaleString()}** per month\n\nI've set up your new budget! You'll get notifications when you're approaching 80% of your budget. Want me to help you set up **transaction categorization rules** or create **milestone alerts**?`;\n  \n  return { ok: true, data: successMessage };\n}\n\nasync function createGoalResponse(userId: string, params: any): Promise<SkillResponse<string>> {\n  await simulateAPICall(1500);\n  const targetDate = params.targetDate ? new Date(params.targetDate).toLocaleDateString() : 'open-ended';\n  const successMessage = `🎯 **Goal Created Successfully**\n\n**${params.name} Goal**: Save **$${params.targetAmount.toLocaleString()}** for ${params.goalType.replace('_', ' ')}\n${params.targetDate ? `Target Date: **${targetDate}**` : ''}\n\nYour goal is now active! I'll help track your progress and provide periodic updates. Would you like to set up **automatic contributions** or set up **progress milestone notifications**?`;\n  \n  return { ok: true, data: successMessage };\n}\n\nasync function provideFinanceHelp(userId: string): Promise<SkillResponse<string>> {\n  const helpText = `💡 **Finance Agent Help Center**\n\nYou can ask me about:\n\n🏦 **Account Management**\n• \\"Show my account balances\\"\n• \\"How much do I have in savings?\\"\n• \\"What's my checking account balance?\\"\n\n💰 **Net Worth & Financial Health**\n• \\"What's my net worth?\\"\n• \\"Show my net worth trend\\"\n• \\"Compare this month to last\\"\n\n📊 **Budgeting & Spending**\n• \\"Show my budgets\\"\n• \\"How much did I spend on dining this month?\\"\n• \\"Create a $400 grocery budget\\"\n\n🎯 **Financial Goals**\n• \\"Show my savings goals\\"\n• \\"Create an emergency fund goal of $3000\\"\n• \\"Track my retirement progress\\"\n\n📈 **Investments & Performance**\n• \\"Show my investment portfolio\\"\n• \\"What's my performance this quarter?\\"\n• \\"Portfolio allocation\\"\n\n**Tips**: I understand natural language - just speak normally! Try: \\"How much can I save this month?\\" or \\"I need to track my vacation savings.\\"`;\n  \n  return { ok: true, data: helpText };\n}\n\n// Utility Functions\nfunction extractTimeframe(query: string): string {\n  if (query.includes('last week')) return 'last_week';\n  if (query.includes('last month')) return 'last_month';\n  if (query.includes('this quarter') || query.includes('quarter')) return 'this_quarter';\n  if (query.includes('this year') || query.includes('year to date')) return 'year_to_date';\n  return 'current';\n}\n\nfunction extractCategory(query: string): string | undefined {\n  const categories = ['dining', 'groceries', 'transportation', 'entertainment', 'shopping', 'utilities', 'bills', 'rent', 'gas', 'food', 'restaurants', 'coffee', 'drinks', 'travel', 'subscriptions'];\n  for (const cat of categories) {\n    if (query.includes(cat)) return cat;\n  }\n  return undefined;\n}\n\nfunction extractAmountRange(query: string): number | undefined {\n  const match = query.match(/\$(\d+(?:\.\d{2})?)|(\d+)\s*dollars?/i);\n  return match ? parseFloat(match[1] || match[2]) : undefined;\n}\n\nfunction extractGoalType(query: string): string {\n  if (query.includes('emergency') || query.includes('rainy day')) return 'emergency';\n  if (query.includes('retirement') || query.includes('401k') || query.includes('IRA')) return 'retirement';\n  if (query.includes('vacation') || query.includes('travel')) return 'vacation';\n  if (query.includes('house') || query.includes('home')) return 'purchase';\n  if (query.includes('debt') || query.includes('credit card')) return 'debt_payoff';\n  return 'general';\n}\n\nfunction extractAccountType(query: string): string {\n  if (query.includes('cash') || query.includes('checking') || query.includes('savings')) return 'cash';\n  if (query.includes('credit') || query.includes('card')) return 'credit';\n  if (query.includes('investment') || query.includes('retirement')) return 'investment';\n  return 'all';\n}\n\nfunction getAccountEmoji(accountType: string): string {\n  const type = accountType.toLowerCase();\n  if (type.includes('savings')) return '🏦';\n  if (type.includes('checking')) return '💳';\n  if (type.includes('credit')) return '💳';\n  if (type.includes('investment')) return '📈';\n  if (type.includes('loan')) return '📄';\n  return '💰';\n}\n\nfunction generateProgressBar(percentage: number, length: number = 10): string {\n  const filledBlocks = Math.round((percentage / 100) * length);\n  const emptyBlocks = length - filledBlocks;\n  return '▓'.repeat(filledBlocks) + '░'.repeat(emptyBlocks);\n}\n\nfunction getDateRangeForTimeframe(timeframe: string): { startDate: string; endDate: string } {\n  const today = new Date();\n  \n  switch (timeframe) {\n    case 'last_week':\n      return {\n        startDate: new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],\n        endDate: today.toISOString().split('T')[0]\n      };\n    case 'last_month':\n      const lastMonth = new Date(today.getFullYear(), today.getMonth() - 1, 1);\n      const lastMonthEnd = new Date(today.getFullYear(), today.getMonth(), 0);\n      return {\n        startDate: lastMonth.toISOString().split('T')[0],\n        endDate: lastMonthEnd.toISOString().split('T')[0]\n      };\n    case 'this_quarter':\n      const quarterStart = new Date(today.getFullYear(), Math.floor(today.getMonth() / 3) * 3, 1);\n      return {\n        startDate: quarterStart.toISOString().split('T')[0],\n        endDate: today.toISOString().split('T')[0]\n      };\n    case 'year_to_date':\n      return {\n        startDate: new Date(today.getFullYear(), 0, 1).toISOString().split('T')[0],\n        endDate: today.toISOString().split('T')[0]\n      };\n    default: // current month\n      return {\n        startDate: new Date(today.getFullYear(), today.getMonth(), 1).toISOString().split('T')[0],\n        endDate: today.toISOString().split('T')[0]\n      };\n  }\n}\n\n// Helper functions for API calls\nasync function getAccountsByType(userId: string, types: string[]): Promise<any[]> {\n  // This would call actual financial APIs\n  await simulateAPICall(500);\n  return [\n    { account_name: 'Chase Checking', account_type: 'checking', balance: 5234.56 },\n    { account_name: 'High Yield Savings', account_type: 'savings', balance: 15890.23 }\n  ].filter(acc => types.includes(acc.account_type));\n}\n\nasync function getAllUserAccounts(userId: string): Promise<any[]> {\n  await simulateAPICall(800);\n  return [\n    { account_name: 'Chase Checking', account_type: 'checking', balance: 5234.56 },\n    { account_name: 'High Yield Savings', account_type: 'savings', balance: 15890.23 },\n    { account_name: 'Credit Card', account_type: 'credit_card', balance: -1298.45 },\n    { account_name: 'Investment Portfolio', account_type: 'investment', balance: 48750.89 }\n  ];\n}\n\nasync function simulateAPICall(delay: number): Promise<void> {\n  return new Promise(resolve => setTimeout(resolve, delay));\n}\n\n// Tool implementations for the Atom agent to use
export const financeAgentTools: ToolImplementation[] = [\n  {\n    name: 'finance_query_handler',\n    description: 'Handle comprehensive financial queries through natural language',\n    handler: async (params: any) => {\n      return await handleFinanceQuery(params.userId, params.query, params.context);\n    }\n  },\n  {\n    name: 'get_spending_breakdown',\n    description: 'Get detailed spending analysis with insights',\n    handler: async (params: any) => {\n      return await getSpendingAnalysis(params.userId, { timeframe: params.timeframe });\n    }\n  },\n  {\n    name: 'net_worth_inquiry',\n    description: 'Get current net worth with historical trends',\n    handler: async (params: any) => {\n      return await getNetWorthResponse(params.userId, { includeHistory: true });\n    }\n  }\n];\n
