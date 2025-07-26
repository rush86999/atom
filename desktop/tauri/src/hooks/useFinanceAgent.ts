import { useState, useCallback, useEffect } from 'react';
import { invoke } from '@tauri-apps/api/tauri';
import { listen } from '@tauri-apps/api/event';

// Enhanced finance types for desktop
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

interface FinanceQueryRequest {
  query: string;
  userId: string;
  context?: {
    category?: string;
    timeframe?: string;
    amount?: number;
  };
}

interface FinanceQueryResponse {
  response: string;
  data?: any;
  suggestions?: string[];
}

// Hook for Atom agent finance integration
export function useFinanceAgent() {
  const [query, setQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [lastResponse, setLastResponse] = useState<FinanceQueryResponse | null>(null);
  const [listening, setListening] = useState(false);

  // Execute finance query through Atom agent
  const queryFinance = useCallback(async (question: string, context?: any) => {
    if (!question.trim()) return;

    setIsLoading(true);
    try {
      const response = await invoke('query_finance_agent', {
        question,
        context: context || {}
      }) as FinanceQueryResponse;

      setLastResponse(response);
      return response;
    } catch (error) {
      console.error('Finance agent error:', error);
      setLastResponse({
        response: "Sorry, I couldn't process your financial query. Please try again.",
        data: null
      });
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Voice command shortcuts
  const quickActions = {
    getNetWorth: async () => {
      return await queryFinance('What is my net worth?', { includeHistory: true });
    },

    getBudget: async () => {
      return await queryFinance('Show me my current budget summary');
    },

    getSpendingAnalysis: async (category?: string) => {
      return await queryFinance(`Show my spending${category ? ` on ${category}` : ''} this month`);
    },

    getGoals: async () => {
      return await queryFinance('Show my financial goals and progress');
    },

    getInvestments: async () => {
      return await queryFinance('Show my investment portfolio');
    },

    createBudget: async (category: string, amount: number) => {
      return await queryFinance(`Create a ${category} budget of ${amount} dollars`);
    },

    createGoal: async (name: string, targetAmount: number, type?: string, date?: string) => {
      return await queryFinance(`Create a ${type || 'savings'} goal: ${name} for ${targetAmount}${date ? ` by ${date}` : ''}`);
    }
  };

  // Listen for finance-related voice commands
  useEffect(() => {
    if (!listening) {
      const unlisten = listen('finance-voice-command', (event) => {
        const { command, parameters } = event.payload as {
          command: string;
          parameters?: any
        };

        switch (command) {
          case 'net_worth':
            quickActions.getNetWorth();
            break;
          case 'budget':
            quickActions.getBudget();
            break;
          case 'spending':
            quickActions.getSpendingAnalysis(parameters?.category);
            break;
          case 'goals':
            quickActions.getGoals();
            break;
          case 'investments':
            quickActions.getInvestments();
            break;
          default:
            if (parameters?.query) {
              queryFinance(parameters.query);
            }
        }
      });

      setListening(true);
      return () => {
        unlisten.then(unsubscribe => unsubscribe());
        setListening(false);
      };
    }
  }, [listening, quickActions, queryFinance]);

  // Data fetching utilities
  const fetchNetWorth = useCallback(async (userId: string) => {
    const result = await queryFinance(`net worth for ${userId}`, { userId });
    return result?.data?.netWorth || 0;
  }, [queryFinance]);

  const fetchBudgets = useCallback(async (userId: string) => {
    const result = await queryFinance(`budget for ${userId}`, { userId });
    return result?.data?.budgets || [];
  }, [queryFinance]);

  const fetchGoals = useCallback(async (userId: string) => {
    const result = await queryFinance(`goals for ${userId}`, { userId });
    return result?.data?.goals || [];
  }, [queryFinance]);

  const fetchInvestments = useCallback(async (userId: string) => {
    const result = await queryFinance(`investments for ${userId}`, { userId });
    return result?.data?.portfolio || [];
  }, [queryFinance]);

  // Intelligent recommendations based on patterns
  const getRecommendations = useCallback(async (userId: string) => {
    return await queryFinance('give me financial recommendations', { userId });
  }, [queryFinance]);

  return {
    queryFinance,
    quickActions,
    fetchNetWorth,
    fetchBudgets,
    fetchGoals,
    fetchInvestments,
    getRecommendations,
    isLoading,
    lastResponse,
    clearResponse: () => setLastResponse(null)
  };
}

// Hook for finance command suggestions
export function useFinanceSuggestions() {
  const [suggestions, setSuggestions] = useState<string[]>([]);

  const generateSuggestions = useCallback((input: string) => {
    const lowerInput = input.toLowerCase();

    const allSuggestions = [
      'What is my net worth?',
      'Show my budget for this month',
      'How much did I spend on dining?',
      'Create a dining budget of $500',
      'Show my investment portfolio',
      'Set up an emergency fund goal of $10000',
      'Analyze my spending this month',
      'Compare this month to last month',
      'Show my account balances',
      'Track my vacation savings goal',
      'What categories am I overspending in?',
      'Calculate my savings rate',
      'Show my retirement progress',
      'Help me optimize my budget',
      'Find large transactions this month'
    ];

    if (!lowerInput.trim()) {
      setSuggestions(allSuggestions.slice(0, 5));
      return;
    }

    const filtered = allSuggestions.filter(s =>
      s.toLowerCase().includes(lowerInput) ||
      lowerInput.includes(s.toLowerCase().split(' ')[0])\n    ).slice(0, 5);

    setSuggestions(filtered);
  }, []);

  const getPopularCommands = useCallback(() => {
    return [
      'net worth',\n      'budget', \n      'spending', \n      'goals', \n      'investments', \n      'recommendations'
n    ];\n  }, []);\n\n  return {\n    suggestions,\n    generateSuggestions,\n    getPopularCommands,\n    allSuggestions: [\n      'What is my net worth?',\n      'Show my budget',\n      'Where did I spend money?',\n      'Create a savings goal',\n      'Portfolio overview'\n    ]\n  };\n}

// Hook for tracking finance-related events
export function useFinanceEvents() {
n  const [events, setEvents] = useState<Array<{\n    type: string;\n    message: string;\n    timestamp: Date;\n  }>>([]);

  const addEvent = useCallback((type: string, message: string) => {
    setEvents(prev => [...prev.slice(-9), { type, message, timestamp: new Date() }]);\n  }, []);

  const clearEvents = useCallback(() => {\n    setEvents([]);\n  }, []);

  // Listen for finance-specific events from Tauri backend
  useEffect(() => {\n    const setupListener = async () => {\n      const unlisten = await listen('finance_event', (event) => {\n        const { type, message } = event.payload as any;\n        addEvent(type, message);\n      });\n\n      return unlisten;\n    };

    setupListener().then(unlisten => unlisten).catch(console.error);
n  }, [addEvent]);

  return {\n    events,\n    addEvent,\n    clearEvents,\n    latestEvent: events[events.length - 1]
n  };\n}\n
