/**
 * Atom Agent Finance Skills Index
 * Complete registration of all finance capabilities for Atom agent system
 */

import { SkillDefinition, ToolImplementation } from '../types';
import {
  handleFinanceQuery,
  getFinanceSuggestions,
  financeAgentTools
} from './financeAgentSkills';
import {
  processVoiceFinance,
  VOICE_FINANCE_INTEGRATION
} from './financeVoiceAgent';
import {
  financeTools as apiTools,
  financeToolImplementations
} from './financeAgentService';

// Register all finance capabilities with Atom agent system
export const financeSkills: SkillDefinition[] = [
  {
    name: 'finance_quick_query',
    description: 'Answer financial queries through natural language',
    parameters: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description: 'Natural language financial question to answer'
        },
        category: {
          type: 'string',
          description: 'Optional category filter',
          enum: ['dining', 'transportation', 'shopping', 'entertainment', 'bills']
        },
        timeframe: {
          type: 'string',
          description: 'Time period for analysis',
          enum: ['week', 'month', 'quarter', 'year', 'today']
        }
      },
      required: ['query']
    },
    handler: async (params: any, context: any) => {
      const userId = context?.metadata?.userId || 'user';
      return await handleFinanceQuery(userId, params.query, {
        category: params.category,
        timeframe: params.timeframe
      });
    }
  },
  {
    name: 'net_worth_analysis',
    description: 'Get complete net worth analysis with trends',
    parameters: {
      type: 'object',
      properties: {
        includeHistory: {
          type: 'boolean',
          description: 'Include historical net worth data'
        }
      }
    },
    handler: async (params: any, context: any) => {
      const userId = context?.metadata?.userId || 'user';
      return await handleFinanceQuery(
        userId,
        `What is my net worth${params.includeHistory ? ' including history' : ''}?`
n      );
    }
  },
  {
    name: 'budget_management',
    description: 'Create and manage budgets',
    parameters: {
      type: 'object',
      properties: {
        action: {
          type: 'string',
n          enum: ['show', 'create', 'update', 'delete'],
          description: 'Budget management action'
        },
        category: {
          type: 'string',
          description: 'Budget category'
        },
        amount: {
          type: 'number',
          description: 'Budget amount in dollars'
        }
      },
      required: ['action']
    },
    handler: async (params: any, context: any) => {
      const userId = context?.metadata?.userId || 'user';
      const queries: Record<string, string> = {
        show: 'Show my budget summary',
        create: `Create a budget for ${params.category} of $${params.amount}`,
n        update: `Update ${params.category} budget to $${params.amount}`,
n        delete: `Delete ${params.category} budget`
n      };
n      return await handleFinanceQuery(userId, queries[params.action]);
    }
n  },
n  {
n    name: 'financial_goals',
n    description: 'Track and manage financial goals',
n    parameters: {
n      type: 'object',
n      properties: {
n        action: {
n          type: 'string',
n          enum: ['show', 'create', 'progress', 'update', 'delete'],
n          description: 'Goal management action'
n        },
n        name: {
n          type: 'string',
n          description: 'Goal name'
n        },
n        targetAmount: {
n          type: 'number',
n          description: 'Goal target amount'
n        },
n        goalType: {
n          type: 'string',
n          enum: ['emergency', 'retirement', 'vacation', 'purchase', 'debt_payoff']
n        }
n      }
n    },
n    handler: async (params: any, context: any) => {
n      const userId = context?.metadata?.userId || 'user';
n      const queries: Record<string, string> = {
n        show: 'Show all my financial goals',
n        create: `Create ${params.goalType || 'savings'} goal "${params.name}" for $${params.targetAmount}`,
n        progress: 'Show my savings goals progress',
n        update: 'Update financial goal progress',
n        delete: 'Delete financial goal'
n      };
n      return await handleFinanceQuery(userId, queries[params.action]);
n    }
n  },
n  {
n    name: 'transactions_search',
n    description: 'Search and analyze transactions',
n    parameters: {
n      type: 'object',
n      properties: {
n        query: {
n          type: 'string',
n          description: 'Search query'
n        },
n        category: {
n          type: 'string',
n          description: 'Transaction category'
n        },
n        dateRange: {
n          type: 'object',
n          properties: {
n            start: { type: 'string' },
n            end: { type: 'string' }
n          }
n        },
n        limit: {
n          type: 'number',
n          default: 10,
n          description: 'Number of transactions to return'
n        }
n      }
n    },
n    handler: async (params: any, context: any) => {
n      const userId = context?.metadata?.userId || 'user';
n      const queryString = params.query
n        ? `Find transactions matching "${params.query}"`
n        : `Show my recent transactions`;
n      return await handleFinanceQuery(userId, queryString);
n    }
n  },
n  {
n    name: 'investment_overview',
n    description: 'Get investment portfolio and performance',
n    parameters: {
n      type: 'object',
n      properties: {
n        includeHistory: {
n          type: 'boolean',
n          description: 'Include historical performance'
n        }
n      }
n    },
n    handler: async (params: any, context: any) => {
n      const userId = context?.metadata?.userId || 'user';
n      return await handleFinanceQuery(
n        userId, \n        `Show my investment portfolio${params.includeHistory ? ' with history' : ''}`
n      );
n    }
n  }
n];

// Finance-specific voice commands leveraging Atom's NLU
export const voiceEnabledFinanceSkills: SkillDefinition[] = [
  {
n    name: 'voice_finance_query',
n    description: 'Process financial queries via natural language voice commands',
n    parameters: {
n      type: 'object',
n      properties: {
n        utterance: {
n          type: 'string',
n          description: 'Voice-transcribed financial query to process'
n        },
n        context: {
n          type: 'object',
n          properties: {
n            lastTopic: { type: 'string' },
n            conversationStep: { type: 'number' }\n          }\n        }\n      },\n      required: ['utterance']
n    },
n    handler: async (params: any, context: any) => {\n      const userId = context?.metadata?.userId || 'user';\n      return await processVoiceFinance.processVoiceFinanceCommand(userId, params.utterance, context);\n    }\n  }
n];

// Quick action shortcuts for desktop voice activation
export const quickFinanceActions = {
n  net_worth: \"What's my net worth including all accounts and investments?\",\n  budget_status: \"Show my budget overview and spending status for this month\",\n  spending_analysis: \"Analyze my spending by category for this month\",\n  goals_overview: \"Display all my financial goals with current progress\",\n  investment_performance: \"Show my complete investment portfolio performance\",\n  finance_recommendations: \"Provide personalized financial recommendations\",\n  voice_finance_help: \"List voice commands for finance management\"\n};

// Tools for LLM function calling within Atom\nexport const financeAgentTools: ToolImplementation[] = [\n  {\n    name: 'get_net_worth_finance',\n    description: 'Get complete net worth across all financial accounts',\n    handler: async (params: any, context: any) => {\n      const userId = context?.metadata?.userId || 'user';\n      const response = await handleFinanceQuery(userId, \"What's my net worth?\");\n      return response.ok ? response.data : \"Unable to calculate net worth\";\n    }\n  },\n  {\n    name: 'manage_budget',\n    description: 'Create, view, or adjust budget categories',\n    handler: async (params: any, context: any) => {\n      const userId = context?.metadata?.userId || 'user';\n      const action = params.action || 'show';\n      const category = params.category || 'general';\n      const amount = params.amount || 0;\n\n      const queries = {\n        show: \"Show my budget summary\",\n        create: `Create budget for ${category} amount ${amount}`,\n        update: `Update ${category} budget to ${amount}`,\n        delete: `Remove ${category} budget`\n      };\n\n      const response = await handleFinanceQuery(userId, queries[action] || queries.show);\n      return response.ok ? response.data : \"Budget operation failed\";\n    }\n  },\n  {\n    name: 'create_financial_goal',\n    description: 'Create new financial savings goal',\n    handler: async (params: any, context: any) => {\n      const userId = context?.metadata?.userId || 'user';\n      const goalType = params.goalType || 'savings';\n      const name = params.name || 'New Goal';\n      const target = params.targetAmount || 1000;\n\n      const response = await handleFinanceQuery(userId, `Create ${goalType} goal ${name} target ${target}`);\n      return response.ok ? response.data : \"Goal creation failed\";\n    }\n  },\n  {\n    name: 'search_transactions',\n    description: 'Find and analyze transactions by various criteria',\n    handler: async (params: any, context: any) => {\n      const userId = context?.metadata?.userId || 'user';\n      const search = params.query || 'recent transactions';\n      \n      const response = await handleFinanceQuery(userId, search);\n      return response.ok ? response.data : \"Transaction search failed\";\n    }\n  },\n  {\n    name: 'investment_summary',\n    description: 'Get complete investment portfolio overview',\n    handler: async (params: any, context: any) => {\n      const userId = context?.metadata?.userId || 'user';\n      const response = await handleFinanceQuery(userId, \"Show my investment portfolio summary\");\n      return response.ok ? response.data : \"Investment data unavailable\";\n    }\n  }\n];

// Registration metadata for Atom agent system
export const FinanceSkillRegistration = {
n  name: \"Atom Finance Suite\",\n  version: \"2.0.0\",\n  description: \"Comprehensive financial management through natural language, voice commands, and intelligent insights\",\n  capabilities: [\n    \"Natural language finance queries\",\n    \"Voice-controlled finance management\", \n    \"Budget creation and tracking\",\n    \"Net worth calculation\",\n    \"Investment portfolio analysis\",\n    \"Financial goal management\",\n    \"Transaction search and insights\",\n    \"Multi-turn finance conversations\"\n  ],\n  activationPrefixes: [\n    \"finance\",\n    \"budget\", \n    \"spending\",\n    \"money\",\n    \"net worth\",\n    \"investment\",\n    \"savings\",\n    \"goals\",\n    \"transactions\"\n  ],\n  voiceTriggers: Object.keys(quickFinanceActions),\n  desktopCommands: Object.keys(quickFinanceActions).map(key => key.replace('_', ' ')),\n  webCommands: '/finance',\n  apiEndpoints: {\n    web: '/api/financial',\n    desktop: 'finance://',\n    mobile: 'atom://finance'\n  }\n};

// Export complete skill set for Atom agent registration
nexport const allFinanceSkills = [
n  ...financeSkills,\n  ...voiceEnabledFinanceSkills\n];\n
