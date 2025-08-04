"use strict";
/**
 * Atom Agent Finance Skills Index
 * Complete registration of all finance capabilities for Atom agent system
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.quickFinanceActions = exports.voiceEnabledFinanceSkills = exports.financeSkills = void 0;
const financeAgentSkills_1 = require("./financeAgentSkills");
const bookkeepingSkills_1 = require("./bookkeepingSkills");
const financeVoiceAgent_1 = require("./financeVoiceAgent");
// Register all finance capabilities with Atom agent system
exports.financeSkills = [
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
        handler: async (params, context) => {
            const userId = context?.metadata?.userId || 'user';
            return await (0, financeAgentSkills_1.handleFinanceQuery)(userId, params.query, {
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
        handler: async (params, context) => {
            const userId = context?.metadata?.userId || 'user';
            return await (0, financeAgentSkills_1.handleFinanceQuery)(userId, `What is my net worth${params.includeHistory ? ' including history' : ''}?`, n);
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
                    n, enum: ['show', 'create', 'update', 'delete'],
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
        handler: async (params, context) => {
            const userId = context?.metadata?.userId || 'user';
            const queries = {
                show: 'Show my budget summary',
                create: `Create a budget for ${params.category} of $${params.amount}`,
                n, update: `Update ${params.category} budget to $${params.amount}`,
                n, delete: `Delete ${params.category} budget`,
                n
            };
            n;
            return await (0, financeAgentSkills_1.handleFinanceQuery)(userId, queries[params.action]);
        },
        n
    },
    n, {
        n, name: 'financial_goals',
        n, description: 'Track and manage financial goals',
        n, parameters: {
            n, type: 'object',
            n, properties: {
                n, action: {
                    n, type: 'string',
                    n, enum: ['show', 'create', 'progress', 'update', 'delete'],
                    n, description: 'Goal management action',
                    n
                },
                n, name: {
                    n, type: 'string',
                    n, description: 'Goal name',
                    n
                },
                n, targetAmount: {
                    n, type: 'number',
                    n, description: 'Goal target amount',
                    n
                },
                n, goalType: {
                    n, type: 'string',
                    n, enum: ['emergency', 'retirement', 'vacation', 'purchase', 'debt_payoff'],
                    n
                },
                n
            },
            n
        },
        n, handler: async (params, context) => {
            n;
            const userId = context?.metadata?.userId || 'user';
            n;
            const queries = {
                n, show: 'Show all my financial goals',
                n, create: `Create ${params.goalType || 'savings'} goal "${params.name}" for $${params.targetAmount}`,
                n, progress: 'Show my savings goals progress',
                n, update: 'Update financial goal progress',
                n, delete: 'Delete financial goal',
                n
            };
            n;
            return await (0, financeAgentSkills_1.handleFinanceQuery)(userId, queries[params.action]);
            n;
        },
        n
    },
    n, {
        n, name: 'transactions_search',
        n, description: 'Search and analyze transactions',
        n, parameters: {
            n, type: 'object',
            n, properties: {
                n, query: {
                    n, type: 'string',
                    n, description: 'Search query',
                    n
                },
                n, category: {
                    n, type: 'string',
                    n, description: 'Transaction category',
                    n
                },
                n, dateRange: {
                    n, type: 'object',
                    n, properties: {
                        n, start: { type: 'string' },
                        n, end: { type: 'string' },
                        n
                    },
                    n
                },
                n, limit: {
                    n, type: 'number',
                    n, default: 10,
                    n, description: 'Number of transactions to return',
                    n
                },
                n
            },
            n
        },
        n, handler: async (params, context) => {
            n;
            const userId = context?.metadata?.userId || 'user';
            n;
            const queryString = params.query;
            n ? `Find transactions matching "${params.query}"`
                :
            ;
            n: `Show my recent transactions`;
            n;
            return await (0, financeAgentSkills_1.handleFinanceQuery)(userId, queryString);
            n;
        },
        n
    },
    n, {
        n, name: 'investment_overview',
        n, description: 'Get investment portfolio and performance',
        n, parameters: {
            n, type: 'object',
            n, properties: {
                n, includeHistory: {
                    n, type: 'boolean',
                    n, description: 'Include historical performance',
                    n
                },
                n
            },
            n
        },
        n, handler: async (params, context) => {
            n;
            const userId = context?.metadata?.userId || 'user';
            n;
            return await (0, financeAgentSkills_1.handleFinanceQuery)(n, userId, n `Show my investment portfolio${params.includeHistory ? ' with history' : ''}`, n);
            n;
        },
        n
    },
    n
];
// Finance-specific voice commands leveraging Atom's NLU
exports.voiceEnabledFinanceSkills = [
    {
        n, name: 'voice_finance_query',
        n, description: 'Process financial queries via natural language voice commands',
        n, parameters: {
            n, type: 'object',
            n, properties: {
                n, utterance: {
                    n, type: 'string',
                    n, description: 'Voice-transcribed financial query to process',
                    n
                },
                n, context: {
                    n, type: 'object',
                    n, properties: {
                        n, lastTopic: { type: 'string' },
                        n, conversationStep: { type: 'number' }, n
                    }, n
                }, n
            }, n, required: ['utterance'],
            n
        },
        n, handler: async (params, context) => { n; const userId = context?.metadata?.userId || 'user'; n; return await financeVoiceAgent_1.processVoiceFinance.processVoiceFinanceCommand(userId, params.utterance, context); n; }, n
    },
    n
];
// Quick action shortcuts for desktop voice activation
exports.quickFinanceActions = {
    n, net_worth: , "What's my net worth including all accounts and investments?\",\n  budget_status: \"Show my budget overview and spending status for this month\",\n  spending_analysis: \"Analyze my spending by category for this month\",\n  goals_overview: \"Display all my financial goals with current progress\",\n  investment_performance: \"Show my complete investment portfolio performance\",\n  finance_recommendations: \"Provide personalized financial recommendations\",\n  voice_finance_help: \"List voice commands for finance management\"\n};: 
    // Tools for LLM function calling within Atom\nexport const financeAgentTools: ToolImplementation[] = [\n  {\n    name: 'get_net_worth_finance',\n    description: 'Get complete net worth across all financial accounts',\n    handler: async (params: any, context: any) => {\n      const userId = context?.metadata?.userId || 'user';\n      const response = await handleFinanceQuery(userId, \"What's my net worth?\");\n      return response.ok ? response.data : \"Unable to calculate net worth\";\n    }\n  },\n  {\n    name: 'manage_budget',\n    description: 'Create, view, or adjust budget categories',\n    handler: async (params: any, context: any) => {\n      const userId = context?.metadata?.userId || 'user';\n      const action = params.action || 'show';\n      const category = params.category || 'general';\n      const amount = params.amount || 0;\n\n      const queries = {\n        show: \"Show my budget summary\",\n        create: `Create budget for ${category} amount ${amount}`,\n        update: `Update ${category} budget to ${amount}`,\n        delete: `Remove ${category} budget`\n      };\n\n      const response = await handleFinanceQuery(userId, queries[action] || queries.show);\n      return response.ok ? response.data : \"Budget operation failed\";\n    }\n  },\n  {\n    name: 'create_financial_goal',\n    description: 'Create new financial savings goal',\n    handler: async (params: any, context: any) => {\n      const userId = context?.metadata?.userId || 'user';\n      const goalType = params.goalType || 'savings';\n      const name = params.name || 'New Goal';\n      const target = params.targetAmount || 1000;\n\n      const response = await handleFinanceQuery(userId, `Create ${goalType} goal ${name} target ${target}`);\n      return response.ok ? response.data : \"Goal creation failed\";\n    }\n  },\n  {\n    name: 'search_transactions',\n    description: 'Find and analyze transactions by various criteria',\n    handler: async (params: any, context: any) => {\n      const userId = context?.metadata?.userId || 'user';\n      const search = params.query || 'recent transactions';\n      \n      const response = await handleFinanceQuery(userId, search);\n      return response.ok ? response.data : \"Transaction search failed\";\n    }\n  },\n  {\n    name: 'investment_summary',\n    description: 'Get complete investment portfolio overview',\n    handler: async (params: any, context: any) => {\n      const userId = context?.metadata?.userId || 'user';\n      const response = await handleFinanceQuery(userId, \"Show my investment portfolio summary\");\n      return response.ok ? response.data : \"Investment data unavailable\";\n    }\n  }\n];
    // Registration metadata for Atom agent system
    ,
    // Tools for LLM function calling within Atom\nexport const financeAgentTools: ToolImplementation[] = [\n  {\n    name: 'get_net_worth_finance',\n    description: 'Get complete net worth across all financial accounts',\n    handler: async (params: any, context: any) => {\n      const userId = context?.metadata?.userId || 'user';\n      const response = await handleFinanceQuery(userId, \"What's my net worth?\");\n      return response.ok ? response.data : \"Unable to calculate net worth\";\n    }\n  },\n  {\n    name: 'manage_budget',\n    description: 'Create, view, or adjust budget categories',\n    handler: async (params: any, context: any) => {\n      const userId = context?.metadata?.userId || 'user';\n      const action = params.action || 'show';\n      const category = params.category || 'general';\n      const amount = params.amount || 0;\n\n      const queries = {\n        show: \"Show my budget summary\",\n        create: `Create budget for ${category} amount ${amount}`,\n        update: `Update ${category} budget to ${amount}`,\n        delete: `Remove ${category} budget`\n      };\n\n      const response = await handleFinanceQuery(userId, queries[action] || queries.show);\n      return response.ok ? response.data : \"Budget operation failed\";\n    }\n  },\n  {\n    name: 'create_financial_goal',\n    description: 'Create new financial savings goal',\n    handler: async (params: any, context: any) => {\n      const userId = context?.metadata?.userId || 'user';\n      const goalType = params.goalType || 'savings';\n      const name = params.name || 'New Goal';\n      const target = params.targetAmount || 1000;\n\n      const response = await handleFinanceQuery(userId, `Create ${goalType} goal ${name} target ${target}`);\n      return response.ok ? response.data : \"Goal creation failed\";\n    }\n  },\n  {\n    name: 'search_transactions',\n    description: 'Find and analyze transactions by various criteria',\n    handler: async (params: any, context: any) => {\n      const userId = context?.metadata?.userId || 'user';\n      const search = params.query || 'recent transactions';\n      \n      const response = await handleFinanceQuery(userId, search);\n      return response.ok ? response.data : \"Transaction search failed\";\n    }\n  },\n  {\n    name: 'investment_summary',\n    description: 'Get complete investment portfolio overview',\n    handler: async (params: any, context: any) => {\n      const userId = context?.metadata?.userId || 'user';\n      const response = await handleFinanceQuery(userId, \"Show my investment portfolio summary\");\n      return response.ok ? response.data : \"Investment data unavailable\";\n    }\n  }\n];
    // Registration metadata for Atom agent system
    const: FinanceSkillRegistration = {
        n, name: , "Atom Finance Suite\",\n  version: \"2.0.0\",\n  description: \"Comprehensive financial management through natural language, voice commands, and intelligent insights\",\n  capabilities: [\n    \"Natural language finance queries\",\n    \"Voice-controlled finance management\", \n    \"Budget creation and tracking\",\n    \"Net worth calculation\",\n    \"Investment portfolio analysis\",\n    \"Financial goal management\",\n    \"Transaction search and insights\",\n    \"Multi-turn finance conversations\"\n  ],\n  activationPrefixes: [\n    \"finance\",\n    \"budget\", \n    \"spending\",\n    \"money\",\n    \"net worth\",\n    \"investment\",\n    \"savings\",\n    \"goals\",\n    \"transactions\"\n  ],\n  voiceTriggers: Object.keys(quickFinanceActions),\n  desktopCommands: Object.keys(quickFinanceActions).map(key => key.replace('_', ' ')),\n  webCommands: '/finance',\n  apiEndpoints: {\n    web: '/api/financial',\n    desktop: 'finance://',\n    mobile: 'atom://finance'\n  }\n};: 
        // Export complete skill set for Atom agent registration
        nexport, const: allFinanceSkills = [
            n, ...exports.financeSkills, n, ...exports.voiceEnabledFinanceSkills, n, ...bookkeepingSkills_1.bookkeepingSkills, n
        ], n
    }
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZmluYW5jZVNraWxsSW5kZXguanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJmaW5hbmNlU2tpbGxJbmRleC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiO0FBQUE7OztHQUdHOzs7QUFHSCw2REFJOEI7QUFDOUIsMkRBQXdEO0FBQ3hELDJEQUc2QjtBQU03QiwyREFBMkQ7QUFDOUMsUUFBQSxhQUFhLEdBQXNCO0lBQzlDO1FBQ0UsSUFBSSxFQUFFLHFCQUFxQjtRQUMzQixXQUFXLEVBQUUsbURBQW1EO1FBQ2hFLFVBQVUsRUFBRTtZQUNWLElBQUksRUFBRSxRQUFRO1lBQ2QsVUFBVSxFQUFFO2dCQUNWLEtBQUssRUFBRTtvQkFDTCxJQUFJLEVBQUUsUUFBUTtvQkFDZCxXQUFXLEVBQUUsK0NBQStDO2lCQUM3RDtnQkFDRCxRQUFRLEVBQUU7b0JBQ1IsSUFBSSxFQUFFLFFBQVE7b0JBQ2QsV0FBVyxFQUFFLDBCQUEwQjtvQkFDdkMsSUFBSSxFQUFFLENBQUMsUUFBUSxFQUFFLGdCQUFnQixFQUFFLFVBQVUsRUFBRSxlQUFlLEVBQUUsT0FBTyxDQUFDO2lCQUN6RTtnQkFDRCxTQUFTLEVBQUU7b0JBQ1QsSUFBSSxFQUFFLFFBQVE7b0JBQ2QsV0FBVyxFQUFFLDBCQUEwQjtvQkFDdkMsSUFBSSxFQUFFLENBQUMsTUFBTSxFQUFFLE9BQU8sRUFBRSxTQUFTLEVBQUUsTUFBTSxFQUFFLE9BQU8sQ0FBQztpQkFDcEQ7YUFDRjtZQUNELFFBQVEsRUFBRSxDQUFDLE9BQU8sQ0FBQztTQUNwQjtRQUNELE9BQU8sRUFBRSxLQUFLLEVBQUUsTUFBVyxFQUFFLE9BQVksRUFBRSxFQUFFO1lBQzNDLE1BQU0sTUFBTSxHQUFHLE9BQU8sRUFBRSxRQUFRLEVBQUUsTUFBTSxJQUFJLE1BQU0sQ0FBQztZQUNuRCxPQUFPLE1BQU0sSUFBQSx1Q0FBa0IsRUFBQyxNQUFNLEVBQUUsTUFBTSxDQUFDLEtBQUssRUFBRTtnQkFDcEQsUUFBUSxFQUFFLE1BQU0sQ0FBQyxRQUFR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RUFBRSxNQUFNLENBQUMsU0FBUyxFQUFFLE9BQU8sQ0FBQyxDQUFDLENBQUMsQ0FBQyxDQUFBLENBQUksQ0FBQyxFQUFDLENBQUM7S0FBRztJQUNsTyxDQUFDO0NBQUMsQ0FBQztBQUVILHNEQUFzRDtBQUN6QyxRQUFBLG1CQUFtQixHQUFHO0lBQ25DLENBQUMsRUFBRSxTQUFTLEVBQUUsQUFBRCxFQUFFLG9oQkFBb2hCLEVBS25pQixBQUxtaUI7SUFFbmlCLHNvRkFBc29GO0lBRXRvRiw4Q0FBOEM7O0lBRjlDLHNvRkFBc29GO0lBRXRvRiw4Q0FBOEM7SUFDdkMsS0FBSyxFQUFDLHdCQUF3QixHQUFHO1FBQ3hDLENBQUMsRUFBRSxJQUFJLEVBQUUsQUFBRCxFQUFFLG0rQkFBbStCO1FBRTcrQix3REFBd0Q7UUFDeEQsT0FBTyxFQUFDLEtBQUssRUFBQyxnQkFBZ0IsR0FBRztZQUNqQyxDQUFDLEVBQUUsR0FBRyxxQkFBYSxFQUFFLENBQUMsRUFBRSxHQUFHLGlDQUF5QixFQUFFLENBQUMsRUFBRSxHQUFHLHFDQUFpQixFQUFDLENBQUM7U0FBQyxFQUFFLENBQUM7S0FBQTtDQUFBLENBQUEiLCJzb3VyY2VzQ29udGVudCI6WyIvKipcbiAqIEF0b20gQWdlbnQgRmluYW5jZSBTa2lsbHMgSW5kZXhcbiAqIENvbXBsZXRlIHJlZ2lzdHJhdGlvbiBvZiBhbGwgZmluYW5jZSBjYXBhYmlsaXRpZXMgZm9yIEF0b20gYWdlbnQgc3lzdGVtXG4gKi9cblxuaW1wb3J0IHsgU2tpbGxEZWZpbml0aW9uLCBUb29sSW1wbGVtZW50YXRpb24gfSBmcm9tICcuLi90eXBlcyc7XG5pbXBvcnQge1xuICBoYW5kbGVGaW5hbmNlUXVlcnksXG4gIGdldEZpbmFuY2VTdWdnZXN0aW9ucyxcbiAgZmluYW5jZUFnZW50VG9vbHNcbn0gZnJvbSAnLi9maW5hbmNlQWdlbnRTa2lsbHMnO1xuaW1wb3J0IHsgYm9va2tlZXBpbmdTa2lsbHMgfSBmcm9tICcuL2Jvb2trZWVwaW5nU2tpbGxzJztcbmltcG9ydCB7XG4gIHByb2Nlc3NWb2ljZUZpbmFuY2UsXG4gIFZPSUNFX0ZJTkFOQ0VfSU5URUdSQVRJT05cbn0gZnJvbSAnLi9maW5hbmNlVm9pY2VBZ2VudCc7XG5pbXBvcnQge1xuICBmaW5hbmNlVG9vbHMgYXMgYXBpVG9vbHMsXG4gIGZpbmFuY2VUb29sSW1wbGVtZW50YXRpb25zXG59IGZyb20gJy4vZmluYW5jZUFnZW50U2VydmljZSc7XG5cbi8vIFJlZ2lzdGVyIGFsbCBmaW5hbmNlIGNhcGFiaWxpdGllcyB3aXRoIEF0b20gYWdlbnQgc3lzdGVtXG5leHBvcnQgY29uc3QgZmluYW5jZVNraWxsczogU2tpbGxEZWZpbml0aW9uW10gPSBbXG4gIHtcbiAgICBuYW1lOiAnZmluYW5jZV9xdWlja19xdWVyeScsXG4gICAgZGVzY3JpcHRpb246ICdBbnN3ZXIgZmluYW5jaWFsIHF1ZXJpZXMgdGhyb3VnaCBuYXR1cmFsIGxhbmd1YWdlJyxcbiAgICBwYXJhbWV0ZXJzOiB7XG4gICAgICB0eXBlOiAnb2JqZWN0JyxcbiAgICAgIHByb3BlcnRpZXM6IHtcbiAgICAgICAgcXVlcnk6IHtcbiAgICAgICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICAgICAgICBkZXNjcmlwdGlvbjogJ05hdHVyYWwgbGFuZ3VhZ2UgZmluYW5jaWFsIHF1ZXN0aW9uIHRvIGFuc3dlcidcbiAgICAgICAgfSxcbiAgICAgICAgY2F0ZWdvcnk6IHtcbiAgICAgICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICAgICAgICBkZXNjcmlwdGlvbjogJ09wdGlvbmFsIGNhdGVnb3J5IGZpbHRlcicsXG4gICAgICAgICAgZW51bTogWydkaW5pbmcnLCAndHJhbnNwb3J0YXRpb24nLCAnc2hvcHBpbmcnLCAnZW50ZXJ0YWlubWVudCcsICdiaWxscyddXG4gICAgICAgIH0sXG4gICAgICAgIHRpbWVmcmFtZToge1xuICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICAgIGRlc2NyaXB0aW9uOiAnVGltZSBwZXJpb2QgZm9yIGFuYWx5c2lzJyxcbiAgICAgICAgICBlbnVtOiBbJ3dlZWsnLCAnbW9udGgnLCAncXVhcnRlcicsICd5ZWFyJywgJ3RvZGF5J11cbiAgICAgICAgfVxuICAgICAgfSxcbiAgICAgIHJlcXVpcmVkOiBbJ3F1ZXJ5J11cbiAgICB9LFxuICAgIGhhbmRsZXI6IGFzeW5jIChwYXJhbXM6IGFueSwgY29udGV4dDogYW55KSA9PiB7XG4gICAgICBjb25zdCB1c2VySWQgPSBjb250ZXh0Py5tZXRhZGF0YT8udXNlcklkIHx8ICd1c2VyJztcbiAgICAgIHJldHVybiBhd2FpdCBoYW5kbGVGaW5hbmNlUXVlcnkodXNlcklkLCBwYXJhbXMucXVlcnksIHtcbiAgICAgICAgY2F0ZWdvcnk6IHBhcmFtcy5jYXRlZ29yeSxcbiAgICAgICAgdGltZWZyYW1lOiBwYXJhbXMudGltZWZyYW1lXG4gICAgICB9KTtcbiAgICB9XG4gIH0sXG4gIHtcbiAgICBuYW1lOiAnbmV0X3dvcnRoX2FuYWx5c2lzJyxcbiAgICBkZXNjcmlwdGlvbjogJ0dldCBjb21wbGV0ZSBuZXQgd29ydGggYW5hbHlzaXMgd2l0aCB0cmVuZHMnLFxuICAgIHBhcmFtZXRlcnM6IHtcbiAgICAgIHR5cGU6ICdvYmplY3QnLFxuICAgICAgcHJvcGVydGllczoge1xuICAgICAgICBpbmNsdWRlSGlzdG9yeToge1xuICAgICAgICAgIHR5cGU6ICdib29sZWFuJyxcbiAgICAgICAgICBkZXNjcmlwdGlvbjogJ0luY2x1ZGUgaGlzdG9yaWNhbCBuZXQgd29ydGggZGF0YSdcbiAgICAgICAgfVxuICAgICAgfVxuICAgIH0sXG4gICAgaGFuZGxlcjogYXN5bmMgKHBhcmFtczogYW55LCBjb250ZXh0OiBhbnkpID0+IHtcbiAgICAgIGNvbnN0IHVzZXJJZCA9IGNvbnRleHQ/Lm1ldGFkYXRhPy51c2VySWQgfHwgJ3VzZXInO1xuICAgICAgcmV0dXJuIGF3YWl0IGhhbmRsZUZpbmFuY2VRdWVyeShcbiAgICAgICAgdXNlcklkLFxuICAgICAgICBgV2hhdCBpcyBteSBuZXQgd29ydGgke3BhcmFtcy5pbmNsdWRlSGlzdG9yeSA/ICcgaW5jbHVkaW5nIGhpc3RvcnknIDogJyd9P2Bcbm4gICAgICApO1xuICAgIH1cbiAgfSxcbiAge1xuICAgIG5hbWU6ICdidWRnZXRfbWFuYWdlbWVudCcsXG4gICAgZGVzY3JpcHRpb246ICdDcmVhdGUgYW5kIG1hbmFnZSBidWRnZXRzJyxcbiAgICBwYXJhbWV0ZXJzOiB7XG4gICAgICB0eXBlOiAnb2JqZWN0JyxcbiAgICAgIHByb3BlcnRpZXM6IHtcbiAgICAgICAgYWN0aW9uOiB7XG4gICAgICAgICAgdHlwZTogJ3N0cmluZycsXG5uICAgICAgICAgIGVudW06IFsnc2hvdycsICdjcmVhdGUnLCAndXBkYXRlJywgJ2RlbGV0ZSddLFxuICAgICAgICAgIGRlc2NyaXB0aW9uOiAnQnVkZ2V0IG1hbmFnZW1lbnQgYWN0aW9uJ1xuICAgICAgICB9LFxuICAgICAgICBjYXRlZ29yeToge1xuICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICAgIGRlc2NyaXB0aW9uOiAnQnVkZ2V0IGNhdGVnb3J5J1xuICAgICAgICB9LFxuICAgICAgICBhbW91bnQ6IHtcbiAgICAgICAgICB0eXBlOiAnbnVtYmVyJyxcbiAgICAgICAgICBkZXNjcmlwdGlvbjogJ0J1ZGdldCBhbW91bnQgaW4gZG9sbGFycydcbiAgICAgICAgfVxuICAgICAgfSxcbiAgICAgIHJlcXVpcmVkOiBbJ2FjdGlvbiddXG4gICAgfSxcbiAgICBoYW5kbGVyOiBhc3luYyAocGFyYW1zOiBhbnksIGNvbnRleHQ6IGFueSkgPT4ge1xuICAgICAgY29uc3QgdXNlcklkID0gY29udGV4dD8ubWV0YWRhdGE/LnVzZXJJZCB8fCAndXNlcic7XG4gICAgICBjb25zdCBxdWVyaWVzOiBSZWNvcmQ8c3RyaW5nLCBzdHJpbmc+ID0ge1xuICAgICAgICBzaG93OiAnU2hvdyBteSBidWRnZXQgc3VtbWFyeScsXG4gICAgICAgIGNyZWF0ZTogYENyZWF0ZSBhIGJ1ZGdldCBmb3IgJHtwYXJhbXMuY2F0ZWdvcnl9IG9mICQke3BhcmFtcy5hbW91bnR9YCxcbm4gICAgICAgIHVwZGF0ZTogYFVwZGF0ZSAke3BhcmFtcy5jYXRlZ29yeX0gYnVkZ2V0IHRvICQke3BhcmFtcy5hbW91bnR9YCxcbm4gICAgICAgIGRlbGV0ZTogYERlbGV0ZSAke3BhcmFtcy5jYXRlZ29yeX0gYnVkZ2V0YFxubiAgICAgIH07XG5uICAgICAgcmV0dXJuIGF3YWl0IGhhbmRsZUZpbmFuY2VRdWVyeSh1c2VySWQsIHF1ZXJpZXNbcGFyYW1zLmFjdGlvbl0pO1xuICAgIH1cbm4gIH0sXG5uICB7XG5uICAgIG5hbWU6ICdmaW5hbmNpYWxfZ29hbHMnLFxubiAgICBkZXNjcmlwdGlvbjogJ1RyYWNrIGFuZCBtYW5hZ2UgZmluYW5jaWFsIGdvYWxzJyxcbm4gICAgcGFyYW1ldGVyczoge1xubiAgICAgIHR5cGU6ICdvYmplY3QnLFxubiAgICAgIHByb3BlcnRpZXM6IHtcbm4gICAgICAgIGFjdGlvbjoge1xubiAgICAgICAgICB0eXBlOiAnc3RyaW5nJyxcbm4gICAgICAgICAgZW51bTogWydzaG93JywgJ2NyZWF0ZScsICdwcm9ncmVzcycsICd1cGRhdGUnLCAnZGVsZXRlJ10sXG5uICAgICAgICAgIGRlc2NyaXB0aW9uOiAnR29hbCBtYW5hZ2VtZW50IGFjdGlvbidcbm4gICAgICAgIH0sXG5uICAgICAgICBuYW1lOiB7XG5uICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxubiAgICAgICAgICBkZXNjcmlwdGlvbjogJ0dvYWwgbmFtZSdcbm4gICAgICAgIH0sXG5uICAgICAgICB0YXJnZXRBbW91bnQ6IHtcbm4gICAgICAgICAgdHlwZTogJ251bWJlcicsXG5uICAgICAgICAgIGRlc2NyaXB0aW9uOiAnR29hbCB0YXJnZXQgYW1vdW50J1xubiAgICAgICAgfSxcbm4gICAgICAgIGdvYWxUeXBlOiB7XG5uICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxubiAgICAgICAgICBlbnVtOiBbJ2VtZXJnZW5jeScsICdyZXRpcmVtZW50JywgJ3ZhY2F0aW9uJywgJ3B1cmNoYXNlJywgJ2RlYnRfcGF5b2ZmJ11cbm4gICAgICAgIH1cbm4gICAgICB9XG5uICAgIH0sXG5uICAgIGhhbmRsZXI6IGFzeW5jIChwYXJhbXM6IGFueSwgY29udGV4dDogYW55KSA9PiB7XG5uICAgICAgY29uc3QgdXNlcklkID0gY29udGV4dD8ubWV0YWRhdGE/LnVzZXJJZCB8fCAndXNlcic7XG5uICAgICAgY29uc3QgcXVlcmllczogUmVjb3JkPHN0cmluZywgc3RyaW5nPiA9IHtcbm4gICAgICAgIHNob3c6ICdTaG93IGFsbCBteSBmaW5hbmNpYWwgZ29hbHMnLFxubiAgICAgICAgY3JlYXRlOiBgQ3JlYXRlICR7cGFyYW1zLmdvYWxUeXBlIHx8ICdzYXZpbmdzJ30gZ29hbCBcIiR7cGFyYW1zLm5hbWV9XCIgZm9yICQke3BhcmFtcy50YXJnZXRBbW91bnR9YCxcbm4gICAgICAgIHByb2dyZXNzOiAnU2hvdyBteSBzYXZpbmdzIGdvYWxzIHByb2dyZXNzJyxcbm4gICAgICAgIHVwZGF0ZTogJ1VwZGF0ZSBmaW5hbmNpYWwgZ29hbCBwcm9ncmVzcycsXG5uICAgICAgICBkZWxldGU6ICdEZWxldGUgZmluYW5jaWFsIGdvYWwnXG5uICAgICAgfTtcbm4gICAgICByZXR1cm4gYXdhaXQgaGFuZGxlRmluYW5jZVF1ZXJ5KHVzZXJJZCwgcXVlcmllc1twYXJhbXMuYWN0aW9uXSk7XG5uICAgIH1cbm4gIH0sXG5uICB7XG5uICAgIG5hbWU6ICd0cmFuc2FjdGlvbnNfc2VhcmNoJyxcbm4gICAgZGVzY3JpcHRpb246ICdTZWFyY2ggYW5kIGFuYWx5emUgdHJhbnNhY3Rpb25zJyxcbm4gICAgcGFyYW1ldGVyczoge1xubiAgICAgIHR5cGU6ICdvYmplY3QnLFxubiAgICAgIHByb3BlcnRpZXM6IHtcbm4gICAgICAgIHF1ZXJ5OiB7XG5uICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxubiAgICAgICAgICBkZXNjcmlwdGlvbjogJ1NlYXJjaCBxdWVyeSdcbm4gICAgICAgIH0sXG5uICAgICAgICBjYXRlZ29yeToge1xubiAgICAgICAgICB0eXBlOiAnc3RyaW5nJyxcbm4gICAgICAgICAgZGVzY3JpcHRpb246ICdUcmFuc2FjdGlvbiBjYXRlZ29yeSdcbm4gICAgICAgIH0sXG5uICAgICAgICBkYXRlUmFuZ2U6IHtcbm4gICAgICAgICAgdHlwZTogJ29iamVjdCcsXG5uICAgICAgICAgIHByb3BlcnRpZXM6IHtcbm4gICAgICAgICAgICBzdGFydDogeyB0eXBlOiAnc3RyaW5nJyB9LFxubiAgICAgICAgICAgIGVuZDogeyB0eXBlOiAnc3RyaW5nJyB9XG5uICAgICAgICAgIH1cbm4gICAgICAgIH0sXG5uICAgICAgICBsaW1pdDoge1xubiAgICAgICAgICB0eXBlOiAnbnVtYmVyJyxcbm4gICAgICAgICAgZGVmYXVsdDogMTAsXG5uICAgICAgICAgIGRlc2NyaXB0aW9uOiAnTnVtYmVyIG9mIHRyYW5zYWN0aW9ucyB0byByZXR1cm4nXG5uICAgICAgICB9XG5uICAgICAgfVxubiAgICB9LFxubiAgICBoYW5kbGVyOiBhc3luYyAocGFyYW1zOiBhbnksIGNvbnRleHQ6IGFueSkgPT4ge1xubiAgICAgIGNvbnN0IHVzZXJJZCA9IGNvbnRleHQ/Lm1ldGFkYXRhPy51c2VySWQgfHwgJ3VzZXInO1xubiAgICAgIGNvbnN0IHF1ZXJ5U3RyaW5nID0gcGFyYW1zLnF1ZXJ5XG5uICAgICAgICA/IGBGaW5kIHRyYW5zYWN0aW9ucyBtYXRjaGluZyBcIiR7cGFyYW1zLnF1ZXJ5fVwiYFxubiAgICAgICAgOiBgU2hvdyBteSByZWNlbnQgdHJhbnNhY3Rpb25zYDtcbm4gICAgICByZXR1cm4gYXdhaXQgaGFuZGxlRmluYW5jZVF1ZXJ5KHVzZXJJZCwgcXVlcnlTdHJpbmcpO1xubiAgICB9XG5uICB9LFxubiAge1xubiAgICBuYW1lOiAnaW52ZXN0bWVudF9vdmVydmlldycsXG5uICAgIGRlc2NyaXB0aW9uOiAnR2V0IGludmVzdG1lbnQgcG9ydGZvbGlvIGFuZCBwZXJmb3JtYW5jZScsXG5uICAgIHBhcmFtZXRlcnM6IHtcbm4gICAgICB0eXBlOiAnb2JqZWN0Jyxcbm4gICAgICBwcm9wZXJ0aWVzOiB7XG5uICAgICAgICBpbmNsdWRlSGlzdG9yeToge1xubiAgICAgICAgICB0eXBlOiAnYm9vbGVhbicsXG5uICAgICAgICAgIGRlc2NyaXB0aW9uOiAnSW5jbHVkZSBoaXN0b3JpY2FsIHBlcmZvcm1hbmNlJ1xubiAgICAgICAgfVxubiAgICAgIH1cbm4gICAgfSxcbm4gICAgaGFuZGxlcjogYXN5bmMgKHBhcmFtczogYW55LCBjb250ZXh0OiBhbnkpID0+IHtcbm4gICAgICBjb25zdCB1c2VySWQgPSBjb250ZXh0Py5tZXRhZGF0YT8udXNlcklkIHx8ICd1c2VyJztcbm4gICAgICByZXR1cm4gYXdhaXQgaGFuZGxlRmluYW5jZVF1ZXJ5KFxubiAgICAgICAgdXNlcklkLCBcXG4gICAgICAgIGBTaG93IG15IGludmVzdG1lbnQgcG9ydGZvbGlvJHtwYXJhbXMuaW5jbHVkZUhpc3RvcnkgPyAnIHdpdGggaGlzdG9yeScgOiAnJ31gXG5uICAgICAgKTtcbm4gICAgfVxubiAgfVxubl07XG5cbi8vIEZpbmFuY2Utc3BlY2lmaWMgdm9pY2UgY29tbWFuZHMgbGV2ZXJhZ2luZyBBdG9tJ3MgTkxVXG5leHBvcnQgY29uc3Qgdm9pY2VFbmFibGVkRmluYW5jZVNraWxsczogU2tpbGxEZWZpbml0aW9uW10gPSBbXG4gIHtcbm4gICAgbmFtZTogJ3ZvaWNlX2ZpbmFuY2VfcXVlcnknLFxubiAgICBkZXNjcmlwdGlvbjogJ1Byb2Nlc3MgZmluYW5jaWFsIHF1ZXJpZXMgdmlhIG5hdHVyYWwgbGFuZ3VhZ2Ugdm9pY2UgY29tbWFuZHMnLFxubiAgICBwYXJhbWV0ZXJzOiB7XG5uICAgICAgdHlwZTogJ29iamVjdCcsXG5uICAgICAgcHJvcGVydGllczoge1xubiAgICAgICAgdXR0ZXJhbmNlOiB7XG5uICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxubiAgICAgICAgICBkZXNjcmlwdGlvbjogJ1ZvaWNlLXRyYW5zY3JpYmVkIGZpbmFuY2lhbCBxdWVyeSB0byBwcm9jZXNzJ1xubiAgICAgICAgfSxcbm4gICAgICAgIGNvbnRleHQ6IHtcbm4gICAgICAgICAgdHlwZTogJ29iamVjdCcsXG5uICAgICAgICAgIHByb3BlcnRpZXM6IHtcbm4gICAgICAgICAgICBsYXN0VG9waWM6IHsgdHlwZTogJ3N0cmluZycgfSxcbm4gICAgICAgICAgICBjb252ZXJzYXRpb25TdGVwOiB7IHR5cGU6ICdudW1iZXInIH1cXG4gICAgICAgICAgfVxcbiAgICAgICAgfVxcbiAgICAgIH0sXFxuICAgICAgcmVxdWlyZWQ6IFsndXR0ZXJhbmNlJ11cbm4gICAgfSxcbm4gICAgaGFuZGxlcjogYXN5bmMgKHBhcmFtczogYW55LCBjb250ZXh0OiBhbnkpID0+IHtcXG4gICAgICBjb25zdCB1c2VySWQgPSBjb250ZXh0Py5tZXRhZGF0YT8udXNlcklkIHx8ICd1c2VyJztcXG4gICAgICByZXR1cm4gYXdhaXQgcHJvY2Vzc1ZvaWNlRmluYW5jZS5wcm9jZXNzVm9pY2VGaW5hbmNlQ29tbWFuZCh1c2VySWQsIHBhcmFtcy51dHRlcmFuY2UsIGNvbnRleHQpO1xcbiAgICB9XFxuICB9XG5uXTtcblxuLy8gUXVpY2sgYWN0aW9uIHNob3J0Y3V0cyBmb3IgZGVza3RvcCB2b2ljZSBhY3RpdmF0aW9uXG5leHBvcnQgY29uc3QgcXVpY2tGaW5hbmNlQWN0aW9ucyA9IHtcbm4gIG5ldF93b3J0aDogXFxcIldoYXQncyBteSBuZXQgd29ydGggaW5jbHVkaW5nIGFsbCBhY2NvdW50cyBhbmQgaW52ZXN0bWVudHM/XFxcIixcXG4gIGJ1ZGdldF9zdGF0dXM6IFxcXCJTaG93IG15IGJ1ZGdldCBvdmVydmlldyBhbmQgc3BlbmRpbmcgc3RhdHVzIGZvciB0aGlzIG1vbnRoXFxcIixcXG4gIHNwZW5kaW5nX2FuYWx5c2lzOiBcXFwiQW5hbHl6ZSBteSBzcGVuZGluZyBieSBjYXRlZ29yeSBmb3IgdGhpcyBtb250aFxcXCIsXFxuICBnb2Fsc19vdmVydmlldzogXFxcIkRpc3BsYXkgYWxsIG15IGZpbmFuY2lhbCBnb2FscyB3aXRoIGN1cnJlbnQgcHJvZ3Jlc3NcXFwiLFxcbiAgaW52ZXN0bWVudF9wZXJmb3JtYW5jZTogXFxcIlNob3cgbXkgY29tcGxldGUgaW52ZXN0bWVudCBwb3J0Zm9saW8gcGVyZm9ybWFuY2VcXFwiLFxcbiAgZmluYW5jZV9yZWNvbW1lbmRhdGlvbnM6IFxcXCJQcm92aWRlIHBlcnNvbmFsaXplZCBmaW5hbmNpYWwgcmVjb21tZW5kYXRpb25zXFxcIixcXG4gIHZvaWNlX2ZpbmFuY2VfaGVscDogXFxcIkxpc3Qgdm9pY2UgY29tbWFuZHMgZm9yIGZpbmFuY2UgbWFuYWdlbWVudFxcXCJcXG59O1xuXG4vLyBUb29scyBmb3IgTExNIGZ1bmN0aW9uIGNhbGxpbmcgd2l0aGluIEF0b21cXG5leHBvcnQgY29uc3QgZmluYW5jZUFnZW50VG9vbHM6IFRvb2xJbXBsZW1lbnRhdGlvbltdID0gW1xcbiAge1xcbiAgICBuYW1lOiAnZ2V0X25ldF93b3J0aF9maW5hbmNlJyxcXG4gICAgZGVzY3JpcHRpb246ICdHZXQgY29tcGxldGUgbmV0IHdvcnRoIGFjcm9zcyBhbGwgZmluYW5jaWFsIGFjY291bnRzJyxcXG4gICAgaGFuZGxlcjogYXN5bmMgKHBhcmFtczogYW55LCBjb250ZXh0OiBhbnkpID0+IHtcXG4gICAgICBjb25zdCB1c2VySWQgPSBjb250ZXh0Py5tZXRhZGF0YT8udXNlcklkIHx8ICd1c2VyJztcXG4gICAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGhhbmRsZUZpbmFuY2VRdWVyeSh1c2VySWQsIFxcXCJXaGF0J3MgbXkgbmV0IHdvcnRoP1xcXCIpO1xcbiAgICAgIHJldHVybiByZXNwb25zZS5vayA/IHJlc3BvbnNlLmRhdGEgOiBcXFwiVW5hYmxlIHRvIGNhbGN1bGF0ZSBuZXQgd29ydGhcXFwiO1xcbiAgICB9XFxuICB9LFxcbiAge1xcbiAgICBuYW1lOiAnbWFuYWdlX2J1ZGdldCcsXFxuICAgIGRlc2NyaXB0aW9uOiAnQ3JlYXRlLCB2aWV3LCBvciBhZGp1c3QgYnVkZ2V0IGNhdGVnb3JpZXMnLFxcbiAgICBoYW5kbGVyOiBhc3luYyAocGFyYW1zOiBhbnksIGNvbnRleHQ6IGFueSkgPT4ge1xcbiAgICAgIGNvbnN0IHVzZXJJZCA9IGNvbnRleHQ/Lm1ldGFkYXRhPy51c2VySWQgfHwgJ3VzZXInO1xcbiAgICAgIGNvbnN0IGFjdGlvbiA9IHBhcmFtcy5hY3Rpb24gfHwgJ3Nob3cnO1xcbiAgICAgIGNvbnN0IGNhdGVnb3J5ID0gcGFyYW1zLmNhdGVnb3J5IHx8ICdnZW5lcmFsJztcXG4gICAgICBjb25zdCBhbW91bnQgPSBwYXJhbXMuYW1vdW50IHx8IDA7XFxuXFxuICAgICAgY29uc3QgcXVlcmllcyA9IHtcXG4gICAgICAgIHNob3c6IFxcXCJTaG93IG15IGJ1ZGdldCBzdW1tYXJ5XFxcIixcXG4gICAgICAgIGNyZWF0ZTogYENyZWF0ZSBidWRnZXQgZm9yICR7Y2F0ZWdvcnl9IGFtb3VudCAke2Ftb3VudH1gLFxcbiAgICAgICAgdXBkYXRlOiBgVXBkYXRlICR7Y2F0ZWdvcnl9IGJ1ZGdldCB0byAke2Ftb3VudH1gLFxcbiAgICAgICAgZGVsZXRlOiBgUmVtb3ZlICR7Y2F0ZWdvcnl9IGJ1ZGdldGBcXG4gICAgICB9O1xcblxcbiAgICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgaGFuZGxlRmluYW5jZVF1ZXJ5KHVzZXJJZCwgcXVlcmllc1thY3Rpb25dIHx8IHF1ZXJpZXMuc2hvdyk7XFxuICAgICAgcmV0dXJuIHJlc3BvbnNlLm9rID8gcmVzcG9uc2UuZGF0YSA6IFxcXCJCdWRnZXQgb3BlcmF0aW9uIGZhaWxlZFxcXCI7XFxuICAgIH1cXG4gIH0sXFxuICB7XFxuICAgIG5hbWU6ICdjcmVhdGVfZmluYW5jaWFsX2dvYWwnLFxcbiAgICBkZXNjcmlwdGlvbjogJ0NyZWF0ZSBuZXcgZmluYW5jaWFsIHNhdmluZ3MgZ29hbCcsXFxuICAgIGhhbmRsZXI6IGFzeW5jIChwYXJhbXM6IGFueSwgY29udGV4dDogYW55KSA9PiB7XFxuICAgICAgY29uc3QgdXNlcklkID0gY29udGV4dD8ubWV0YWRhdGE/LnVzZXJJZCB8fCAndXNlcic7XFxuICAgICAgY29uc3QgZ29hbFR5cGUgPSBwYXJhbXMuZ29hbFR5cGUgfHwgJ3NhdmluZ3MnO1xcbiAgICAgIGNvbnN0IG5hbWUgPSBwYXJhbXMubmFtZSB8fCAnTmV3IEdvYWwnO1xcbiAgICAgIGNvbnN0IHRhcmdldCA9IHBhcmFtcy50YXJnZXRBbW91bnQgfHwgMTAwMDtcXG5cXG4gICAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGhhbmRsZUZpbmFuY2VRdWVyeSh1c2VySWQsIGBDcmVhdGUgJHtnb2FsVHlwZX0gZ29hbCAke25hbWV9IHRhcmdldCAke3RhcmdldH1gKTtcXG4gICAgICByZXR1cm4gcmVzcG9uc2Uub2sgPyByZXNwb25zZS5kYXRhIDogXFxcIkdvYWwgY3JlYXRpb24gZmFpbGVkXFxcIjtcXG4gICAgfVxcbiAgfSxcXG4gIHtcXG4gICAgbmFtZTogJ3NlYXJjaF90cmFuc2FjdGlvbnMnLFxcbiAgICBkZXNjcmlwdGlvbjogJ0ZpbmQgYW5kIGFuYWx5emUgdHJhbnNhY3Rpb25zIGJ5IHZhcmlvdXMgY3JpdGVyaWEnLFxcbiAgICBoYW5kbGVyOiBhc3luYyAocGFyYW1zOiBhbnksIGNvbnRleHQ6IGFueSkgPT4ge1xcbiAgICAgIGNvbnN0IHVzZXJJZCA9IGNvbnRleHQ/Lm1ldGFkYXRhPy51c2VySWQgfHwgJ3VzZXInO1xcbiAgICAgIGNvbnN0IHNlYXJjaCA9IHBhcmFtcy5xdWVyeSB8fCAncmVjZW50IHRyYW5zYWN0aW9ucyc7XFxuICAgICAgXFxuICAgICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBoYW5kbGVGaW5hbmNlUXVlcnkodXNlcklkLCBzZWFyY2gpO1xcbiAgICAgIHJldHVybiByZXNwb25zZS5vayA/IHJlc3BvbnNlLmRhdGEgOiBcXFwiVHJhbnNhY3Rpb24gc2VhcmNoIGZhaWxlZFxcXCI7XFxuICAgIH1cXG4gIH0sXFxuICB7XFxuICAgIG5hbWU6ICdpbnZlc3RtZW50X3N1bW1hcnknLFxcbiAgICBkZXNjcmlwdGlvbjogJ0dldCBjb21wbGV0ZSBpbnZlc3RtZW50IHBvcnRmb2xpbyBvdmVydmlldycsXFxuICAgIGhhbmRsZXI6IGFzeW5jIChwYXJhbXM6IGFueSwgY29udGV4dDogYW55KSA9PiB7XFxuICAgICAgY29uc3QgdXNlcklkID0gY29udGV4dD8ubWV0YWRhdGE/LnVzZXJJZCB8fCAndXNlcic7XFxuICAgICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBoYW5kbGVGaW5hbmNlUXVlcnkodXNlcklkLCBcXFwiU2hvdyBteSBpbnZlc3RtZW50IHBvcnRmb2xpbyBzdW1tYXJ5XFxcIik7XFxuICAgICAgcmV0dXJuIHJlc3BvbnNlLm9rID8gcmVzcG9uc2UuZGF0YSA6IFxcXCJJbnZlc3RtZW50IGRhdGEgdW5hdmFpbGFibGVcXFwiO1xcbiAgICB9XFxuICB9XFxuXTtcblxuLy8gUmVnaXN0cmF0aW9uIG1ldGFkYXRhIGZvciBBdG9tIGFnZW50IHN5c3RlbVxuZXhwb3J0IGNvbnN0IEZpbmFuY2VTa2lsbFJlZ2lzdHJhdGlvbiA9IHtcbm4gIG5hbWU6IFxcXCJBdG9tIEZpbmFuY2UgU3VpdGVcXFwiLFxcbiAgdmVyc2lvbjogXFxcIjIuMC4wXFxcIixcXG4gIGRlc2NyaXB0aW9uOiBcXFwiQ29tcHJlaGVuc2l2ZSBmaW5hbmNpYWwgbWFuYWdlbWVudCB0aHJvdWdoIG5hdHVyYWwgbGFuZ3VhZ2UsIHZvaWNlIGNvbW1hbmRzLCBhbmQgaW50ZWxsaWdlbnQgaW5zaWdodHNcXFwiLFxcbiAgY2FwYWJpbGl0aWVzOiBbXFxuICAgIFxcXCJOYXR1cmFsIGxhbmd1YWdlIGZpbmFuY2UgcXVlcmllc1xcXCIsXFxuICAgIFxcXCJWb2ljZS1jb250cm9sbGVkIGZpbmFuY2UgbWFuYWdlbWVudFxcXCIsIFxcbiAgICBcXFwiQnVkZ2V0IGNyZWF0aW9uIGFuZCB0cmFja2luZ1xcXCIsXFxuICAgIFxcXCJOZXQgd29ydGggY2FsY3VsYXRpb25cXFwiLFxcbiAgICBcXFwiSW52ZXN0bWVudCBwb3J0Zm9saW8gYW5hbHlzaXNcXFwiLFxcbiAgICBcXFwiRmluYW5jaWFsIGdvYWwgbWFuYWdlbWVudFxcXCIsXFxuICAgIFxcXCJUcmFuc2FjdGlvbiBzZWFyY2ggYW5kIGluc2lnaHRzXFxcIixcXG4gICAgXFxcIk11bHRpLXR1cm4gZmluYW5jZSBjb252ZXJzYXRpb25zXFxcIlxcbiAgXSxcXG4gIGFjdGl2YXRpb25QcmVmaXhlczogW1xcbiAgICBcXFwiZmluYW5jZVxcXCIsXFxuICAgIFxcXCJidWRnZXRcXFwiLCBcXG4gICAgXFxcInNwZW5kaW5nXFxcIixcXG4gICAgXFxcIm1vbmV5XFxcIixcXG4gICAgXFxcIm5ldCB3b3J0aFxcXCIsXFxuICAgIFxcXCJpbnZlc3RtZW50XFxcIixcXG4gICAgXFxcInNhdmluZ3NcXFwiLFxcbiAgICBcXFwiZ29hbHNcXFwiLFxcbiAgICBcXFwidHJhbnNhY3Rpb25zXFxcIlxcbiAgXSxcXG4gIHZvaWNlVHJpZ2dlcnM6IE9iamVjdC5rZXlzKHF1aWNrRmluYW5jZUFjdGlvbnMpLFxcbiAgZGVza3RvcENvbW1hbmRzOiBPYmplY3Qua2V5cyhxdWlja0ZpbmFuY2VBY3Rpb25zKS5tYXAoa2V5ID0+IGtleS5yZXBsYWNlKCdfJywgJyAnKSksXFxuICB3ZWJDb21tYW5kczogJy9maW5hbmNlJyxcXG4gIGFwaUVuZHBvaW50czoge1xcbiAgICB3ZWI6ICcvYXBpL2ZpbmFuY2lhbCcsXFxuICAgIGRlc2t0b3A6ICdmaW5hbmNlOi8vJyxcXG4gICAgbW9iaWxlOiAnYXRvbTovL2ZpbmFuY2UnXFxuICB9XFxufTtcblxuLy8gRXhwb3J0IGNvbXBsZXRlIHNraWxsIHNldCBmb3IgQXRvbSBhZ2VudCByZWdpc3RyYXRpb25cbm5leHBvcnQgY29uc3QgYWxsRmluYW5jZVNraWxscyA9IFtcbm4gIC4uLmZpbmFuY2VTa2lsbHMsXFxuICAuLi52b2ljZUVuYWJsZWRGaW5hbmNlU2tpbGxzLFxcbiAgLi4uYm9va2tlZXBpbmdTa2lsbHNcXG5dO1xcblxuIl19