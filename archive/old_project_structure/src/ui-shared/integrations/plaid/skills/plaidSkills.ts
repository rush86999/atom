/**
 * ATOM Plaid Skills Integration
 * Complete Plaid automation skills for ATOM's skill system
 * Financial services automation with Plaid API
 */

import {
  AtomSkill,
  AtomSkillContext,
  AtomSkillResult,
  SkillCategory,
  SkillPriority,
} from '@atom/agents';

import {
  PlaidAccount,
  PlaidTransaction,
  PlaidAccountBalance,
  PlaidTransactionSearch,
  PlaidSpendingAnalytics,
  PlaidAccountSummary,
  AtomPlaidIngestionConfig,
  PLAID_DEFAULT_CONFIG,
} from '../types';

interface PlaidSkillContext extends AtomSkillContext {
  // Plaid API client
  plaidClient?: {
    get: (endpoint: string, data?: any) => Promise<any>;
    post: (endpoint: string, data?: any) => Promise<any>;
    patch: (endpoint: string, data?: any) => Promise<any>;
  };
  
  // ATOM ingestion pipeline
  atomIngestionPipeline?: {
    processDocument: (document: any) => Promise<any>;
    searchDocuments: (query: string) => Promise<any>;
  };
  
  // Plaid configuration
  plaidConfig?: AtomPlaidIngestionConfig;
}

/**
 * Get Plaid Accounts Skill
 * Retrieve all accounts connected through Plaid
 */
export const GetPlaidAccountsSkill: AtomSkill = {
  id: 'plaid_get_accounts',
  name: 'Get Plaid Accounts',
  description: 'Retrieve all connected accounts from Plaid including balances and metadata',
  category: SkillCategory.FINANCIAL,
  priority: SkillPriority.NORMAL,
  
  input: {
    type: 'object',
    properties: {
      accountTypes: {
        type: 'array',
        items: { type: 'string' },
        description: 'Specific account types to retrieve',
      },
      includeInactive: {
        type: 'boolean',
        default: false,
        description: 'Include inactive accounts',
      },
    },
  },
  
  output: {
    type: 'object',
    properties: {
      accounts: {
        type: 'array',
        items: { $ref: '#/definitions/PlaidAccount' },
        description: 'Connected accounts from Plaid',
      },
      balances: {
        type: 'array',
        items: { $ref: '#/definitions/PlaidAccountBalance' },
        description: 'Account balances',
      },
      totalBalance: {
        type: 'number',
        description: 'Total balance across all accounts',
      },
      accountSummary: {
        $ref: '#/definitions/PlaidAccountSummary',
        description: 'Summary of all accounts',
      },
      retrievalTime: {
        type: 'number',
        description: 'Time taken to retrieve accounts in milliseconds',
      },
    },
  },
  
  definitions: {
    PlaidAccount: {
      type: 'object',
      properties: {
        account_id: { type: 'string' },
        balances: {
          type: 'object',
          properties: {
            current: { type: 'number' },
            available: { type: 'number' },
            limit: { type: 'number' },
          },
        },
        mask: { type: 'string' },
        name: { type: 'string' },
        official_name: { type: 'string' },
        subtype: { type: 'array', items: { type: 'string' } },
        type: { type: 'string' },
        verification_status: { type: 'string' },
      },
    },
    PlaidAccountBalance: {
      type: 'object',
      properties: {
        account_id: { type: 'string' },
        balances: {
          type: 'object',
          properties: {
            available: { type: 'number' },
            current: { type: 'number' },
            iso_currency_code: { type: 'string' },
            limit: { type: 'number' },
          },
        },
      },
    },
    PlaidAccountSummary: {
      type: 'object',
      properties: {
        total_balance: { type: 'number' },
        available_balance: { type: 'number' },
        total_assets: { type: 'number' },
        total_liabilities: { type: 'number' },
        net_worth: { type: 'number' },
        accounts: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              id: { type: 'string' },
              name: { type: 'string' },
              type: { type: 'string' },
              balance: { type: 'number' },
              available_balance: { type: 'number' },
            },
          },
        },
      },
    },
  },
  
  execute: async (input: any, context: PlaidSkillContext): Promise<AtomSkillResult> => {
    const startTime = Date.now();
    
    try {
      if (!context.plaidClient) {
        throw new Error('Plaid client not available');
      }

      // Retrieve accounts
      const accountsResponse = await context.plaidClient.post('/accounts/get', {});
      let accounts = accountsResponse.data.accounts;

      // Filter by account types if specified
      if (input.accountTypes && input.accountTypes.length > 0) {
        accounts = accounts.filter((account: PlaidAccount) => 
          input.accountTypes.includes(account.type) ||
          account.subtype.some((subtype: string) => input.accountTypes.includes(subtype))
        );
      }

      // Filter inactive accounts if not included
      if (!input.includeInactive) {
        // Note: Plaid doesn't provide active/inactive status directly
        // This would need to be tracked at the application level
      }

      // Retrieve balances
      const balancesResponse = await context.plaidClient.post('/accounts/balance/get', {});
      const balances = balancesResponse.data.balances;

      // Calculate totals
      const totalBalance = balances.reduce((sum: number, balance: PlaidAccountBalance) => 
        sum + balance.balances.current, 0
      );

      const availableBalance = balances.reduce((sum: number, balance: PlaidAccountBalance) => 
        sum + balance.balances.available, 0
      );

      // Create account summary
      const accountSummary: PlaidAccountSummary = {
        total_balance: totalBalance,
        available_balance: availableBalance,
        total_assets: balances
          .filter((balance: PlaidAccountBalance) => {
            const account = accounts.find((acc: PlaidAccount) => acc.account_id === balance.account_id);
            return account && ['depository', 'investment'].includes(account.type);
          })
          .reduce((sum: number, balance: PlaidAccountBalance) => 
            sum + balance.balances.current, 0
          ),
        total_liabilities: balances
          .filter((balance: PlaidAccountBalance) => {
            const account = accounts.find((acc: PlaidAccount) => acc.account_id === balance.account_id);
            return account && ['credit', 'loan'].includes(account.type);
          })
          .reduce((sum: number, balance: PlaidAccountBalance) => 
            sum + Math.abs(balance.balances.current), 0
          ),
        net_worth: 0, // Will be calculated below
        accounts: accounts.map((account: PlaidAccount) => {
          const balance = balances.find((b: PlaidAccountBalance) => b.account_id === account.account_id);
          return {
            id: account.account_id,
            name: account.name,
            type: account.type,
            balance: balance ? balance.balances.current : 0,
            available_balance: balance ? balance.balances.available : 0,
          };
        }),
      };

      accountSummary.net_worth = accountSummary.total_assets - accountSummary.total_liabilities;

      const retrievalTime = Date.now() - startTime;

      return {
        success: true,
        data: {
          accounts,
          balances,
          totalBalance,
          accountSummary,
          retrievalTime,
        },
        metadata: {
          executionTime: retrievalTime,
          accountCount: accounts.length,
          totalBalance,
        },
      };

    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to retrieve Plaid accounts',
        metadata: {
          executionTime: Date.now() - startTime,
        },
      };
    }
  },
};

/**
 * Get Plaid Transactions Skill
 * Retrieve transactions from Plaid with advanced filtering
 */
export const GetPlaidTransactionsSkill: AtomSkill = {
  id: 'plaid_get_transactions',
  name: 'Get Plaid Transactions',
  description: 'Retrieve transactions from Plaid with date range, category, and amount filtering',
  category: SkillCategory.FINANCIAL,
  priority: SkillPriority.NORMAL,
  
  input: {
    type: 'object',
    properties: {
      startDate: {
        type: 'string',
        format: 'date',
        description: 'Start date for transaction retrieval',
      },
      endDate: {
        type: 'string',
        format: 'date',
        description: 'End date for transaction retrieval',
      },
      accountIds: {
        type: 'array',
        items: { type: 'string' },
        description: 'Specific account IDs to retrieve transactions from',
      },
      categories: {
        type: 'array',
        items: { type: 'string' },
        description: 'Transaction categories to filter by',
      },
      minAmount: {
        type: 'number',
        description: 'Minimum transaction amount',
      },
      maxAmount: {
        type: 'number',
        description: 'Maximum transaction amount',
      },
      includePending: {
        type: 'boolean',
        default: true,
        description: 'Include pending transactions',
      },
      count: {
        type: 'number',
        default: 100,
        description: 'Maximum number of transactions to retrieve',
      },
      offset: {
        type: 'number',
        default: 0,
        description: 'Number of transactions to skip',
      },
    },
    required: ['startDate', 'endDate'],
  },
  
  output: {
    type: 'object',
    properties: {
      transactions: {
        type: 'array',
        items: { $ref: '#/definitions/PlaidTransaction' },
        description: 'Retrieved transactions',
      },
      totalCount: {
        type: 'number',
        description: 'Total number of transactions available',
      },
      retrievedCount: {
        type: 'number',
        description: 'Number of transactions retrieved in this request',
      },
      dateRange: {
        type: 'object',
        properties: {
          startDate: { type: 'string' },
          endDate: { type: 'string' },
        },
        description: 'Actual date range covered',
      },
      summary: {
        type: 'object',
        properties: {
          totalIncome: { type: 'number' },
          totalExpenses: { type: 'number' },
          netAmount: { type: 'number' },
          averageTransaction: { type: 'number' },
          transactionCount: { type: 'number' },
        },
        description: 'Transaction summary statistics',
      },
      retrievalTime: {
        type: 'number',
        description: 'Time taken to retrieve transactions in milliseconds',
      },
    },
  },
  
  definitions: {
    PlaidTransaction: {
      type: 'object',
      properties: {
        transaction_id: { type: 'string' },
        pending: { type: 'boolean' },
        amount: { type: 'number' },
        iso_currency_code: { type: 'string' },
        category: { type: 'array', items: { type: 'string' } },
        category_id: { type: 'string' },
        date: { type: 'string', format: 'date' },
        name: { type: 'string' },
        merchant_name: { type: 'string' },
        payment_channel: { type: 'string' },
        account_id: { type: 'string' },
      },
    },
  },
  
  execute: async (input: any, context: PlaidSkillContext): Promise<AtomSkillResult> => {
    const startTime = Date.now();
    
    try {
      if (!context.plaidClient) {
        throw new Error('Plaid client not available');
      }

      // Prepare transaction request
      const transactionRequest: any = {
        start_date: input.startDate,
        end_date: input.endDate,
        count: input.count || 100,
        offset: input.offset || 0,
      };

      if (input.accountIds) {
        transactionRequest.account_ids = input.accountIds;
      }

      // Retrieve transactions
      const transactionsResponse = await context.plaidClient.post('/transactions/get', transactionRequest);
      let transactions = transactionsResponse.data.transactions;

      // Apply additional filters that Plaid API doesn't support
      if (input.categories && input.categories.length > 0) {
        transactions = transactions.filter((transaction: PlaidTransaction) =>
          transaction.category.some((cat: string) => input.categories.includes(cat))
        );
      }

      if (input.minAmount !== undefined) {
        transactions = transactions.filter((transaction: PlaidTransaction) =>
          Math.abs(transaction.amount) >= input.minAmount
        );
      }

      if (input.maxAmount !== undefined) {
        transactions = transactions.filter((transaction: PlaidTransaction) =>
          Math.abs(transaction.amount) <= input.maxAmount
        );
      }

      if (!input.includePending) {
        transactions = transactions.filter((transaction: PlaidTransaction) =>
          !transaction.pending
        );
      }

      // Calculate summary statistics
      const totalIncome = transactions
        .filter((t: PlaidTransaction) => t.amount > 0)
        .reduce((sum: number, t: PlaidTransaction) => sum + t.amount, 0);

      const totalExpenses = Math.abs(
        transactions
          .filter((t: PlaidTransaction) => t.amount < 0)
          .reduce((sum: number, t: PlaidTransaction) => sum + t.amount, 0)
      );

      const netAmount = totalIncome - totalExpenses;
      const averageTransaction = transactions.length > 0 ? 
        Math.abs(netAmount) / transactions.length : 0;

      const summary = {
        totalIncome,
        totalExpenses,
        netAmount,
        averageTransaction,
        transactionCount: transactions.length,
      };

      const retrievalTime = Date.now() - startTime;

      return {
        success: true,
        data: {
          transactions,
          totalCount: transactionsResponse.data.total_transactions || transactions.length,
          retrievedCount: transactions.length,
          dateRange: {
            startDate: input.startDate,
            endDate: input.endDate,
          },
          summary,
          retrievalTime,
        },
        metadata: {
          executionTime: retrievalTime,
          transactionCount: transactions.length,
          dateRange: `${input.startDate} to ${input.endDate}`,
        },
      };

    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to retrieve Plaid transactions',
        metadata: {
          executionTime: Date.now() - startTime,
        },
      };
    }
  },
};

/**
 * Generate Spending Analytics Skill
 * Analyze spending patterns and generate insights
 */
export const GenerateSpendingAnalyticsSkill: AtomSkill = {
  id: 'plaid_generate_spending_analytics',
  name: 'Generate Spending Analytics',
  description: 'Analyze spending patterns and generate comprehensive financial insights',
  category: SkillCategory.ANALYTICS,
  priority: SkillPriority.HIGH,
  
  input: {
    type: 'object',
    properties: {
      startDate: {
        type: 'string',
        format: 'date',
        description: 'Start date for analysis',
      },
      endDate: {
        type: 'string',
        format: 'date',
        description: 'End date for analysis',
      },
      accountIds: {
        type: 'array',
        items: { type: 'string' },
        description: 'Specific account IDs to analyze',
      },
      includePending: {
        type: 'boolean',
        default: false,
        description: 'Include pending transactions in analysis',
      },
      generateMonthlyTrends: {
        type: 'boolean',
        default: true,
        description: 'Generate monthly spending trends',
      },
      generateMerchantAnalysis: {
        type: 'boolean',
        default: true,
        description: 'Generate top merchant analysis',
      },
      detectRecurringTransactions: {
        type: 'boolean',
        default: true,
        description: 'Detect and analyze recurring transactions',
      },
    },
    required: ['startDate', 'endDate'],
  },
  
  output: {
    type: 'object',
    properties: {
      analytics: {
        $ref: '#/definitions/PlaidSpendingAnalytics',
        description: 'Comprehensive spending analytics',
      },
      insights: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            type: { type: 'string' },
            title: { type: 'string' },
            description: { type: 'string' },
            severity: { type: 'string' },
            recommendations: { type: 'array', items: { type: 'string' } },
          },
        },
        description: 'Generated insights and recommendations',
      },
      analysisTime: {
        type: 'number',
        description: 'Time taken to generate analytics in milliseconds',
      },
    },
  },
  
  definitions: {
    PlaidSpendingAnalytics: {
      type: 'object',
      properties: {
        total_spending: { type: 'number' },
        total_income: { type: 'number' },
        net_amount: { type: 'number' },
        spending_by_category: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              category: { type: 'string' },
              amount: { type: 'number' },
              percentage: { type: 'number' },
              transaction_count: { type: 'number' },
            },
          },
        },
        income_by_source: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              source: { type: 'string' },
              amount: { type: 'number' },
              percentage: { type: 'number' },
            },
          },
        },
        monthly_trends: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              month: { type: 'string' },
              income: { type: 'number' },
              spending: { type: 'number' },
              net: { type: 'number' },
            },
          },
        },
        top_merchants: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              merchant_name: { type: 'string' },
              amount: { type: 'number' },
              transaction_count: { type: 'number' },
            },
          },
        },
        recurring_transactions: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              name: { type: 'string' },
              amount: { type: 'number' },
              frequency: { type: 'string' },
              next_expected: { type: 'string' },
            },
          },
        },
      },
    },
  },
  
  execute: async (input: any, context: PlaidSkillContext): Promise<AtomSkillResult> => {
    const startTime = Date.now();
    
    try {
      if (!context.plaidClient) {
        throw new Error('Plaid client not available');
      }

      // First, retrieve transactions for the specified period
      const transactionsResponse = await context.plaidClient.post('/transactions/get', {
        start_date: input.startDate,
        end_date: input.endDate,
        count: 1000, // Get maximum for comprehensive analysis
      });

      let transactions = transactionsResponse.data.transactions;

      // Filter by accounts if specified
      if (input.accountIds && input.accountIds.length > 0) {
        transactions = transactions.filter((transaction: PlaidTransaction) =>
          input.accountIds.includes(transaction.account_id)
        );
      }

      // Filter pending transactions if not included
      if (!input.includePending) {
        transactions = transactions.filter((transaction: PlaidTransaction) =>
          !transaction.pending
        );
      }

      // Generate analytics
      const analytics = await generateSpendingAnalytics(transactions, input);
      
      // Generate insights
      const insights = await generateSpendingInsights(analytics, transactions);

      const analysisTime = Date.now() - startTime;

      return {
        success: true,
        data: {
          analytics,
          insights,
          analysisTime,
        },
        metadata: {
          executionTime: analysisTime,
          transactionCount: transactions.length,
          dateRange: `${input.startDate} to ${input.endDate}`,
        },
      };

    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to generate spending analytics',
        metadata: {
          executionTime: Date.now() - startTime,
        },
      };
    }
  },
};

/**
 * Sync Plaid Data with ATOM Memory Skill
 * Synchronize Plaid financial data with ATOM's memory system
 */
export const SyncPlaidWithAtomMemorySkill: AtomSkill = {
  id: 'plaid_sync_with_atom_memory',
  name: 'Sync Plaid Data with ATOM Memory',
  description: 'Synchronize Plaid accounts and transactions with ATOM memory system for intelligent analysis',
  category: SkillCategory.DATA_SYNCHRONIZATION,
  priority: SkillPriority.HIGH,
  
  input: {
    type: 'object',
    properties: {
      syncAccounts: {
        type: 'boolean',
        default: true,
        description: 'Sync account data with ATOM memory',
      },
      syncTransactions: {
        type: 'boolean',
        default: true,
        description: 'Sync transaction data with ATOM memory',
      },
      transactionStartDate: {
        type: 'string',
        format: 'date',
        description: 'Start date for transaction sync',
      },
      transactionEndDate: {
        type: 'string',
        format: 'date',
        description: 'End date for transaction sync',
      },
      includeIncome: {
        type: 'boolean',
        default: true,
        description: 'Include income transactions in sync',
      },
      includeExpenses: {
        type: 'boolean',
        default: true,
        description: 'Include expense transactions in sync',
      },
      batchSize: {
        type: 'number',
        default: 100,
        description: 'Number of items to process in each batch',
      },
      encryptSensitiveData: {
        type: 'boolean',
        default: true,
        description: 'Encrypt sensitive financial data',
      },
      maskAccountNumbers: {
        type: 'boolean',
        default: true,
        description: 'Mask account numbers in memory',
      },
    },
  },
  
  output: {
    type: 'object',
    properties: {
      syncResults: {
        type: 'object',
        properties: {
          accountsSynced: {
            type: 'array',
            items: { $ref: '#/definitions/PlaidAccount' },
            description: 'Accounts successfully synced with ATOM memory',
          },
          transactionsSynced: {
            type: 'array',
            items: { $ref: '#/definitions/PlaidTransaction' },
            description: 'Transactions successfully synced with ATOM memory',
          },
          failedItems: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                type: { type: 'string' },
                item: { type: 'object' },
                error: { type: 'string' },
              },
            },
            description: 'Items that failed to sync with error details',
          },
        },
      },
      syncStats: {
        type: 'object',
        properties: {
          totalAccounts: { type: 'number' },
          syncedAccounts: { type: 'number' },
          totalTransactions: { type: 'number' },
          syncedTransactions: { type: 'number' },
          failedItems: { type: 'number' },
          syncTime: { type: 'number' },
          bytesProcessed: { type: 'number' },
        },
        description: 'Synchronization statistics',
      },
    },
  },
  
  execute: async (input: any, context: PlaidSkillContext): Promise<AtomSkillResult> => {
    const startTime = Date.now();
    
    try {
      if (!context.plaidClient || !context.atomIngestionPipeline) {
        throw new Error('Plaid client and ATOM ingestion pipeline are required');
      }

      const results = {
        accountsSynced: [] as PlaidAccount[],
        transactionsSynced: [] as PlaidTransaction[],
        failedItems: [] as Array<{ type: string; item: any; error: string }>,
      };

      let totalAccounts = 0;
      let totalTransactions = 0;
      let bytesProcessed = 0;

      // Sync accounts if requested
      if (input.syncAccounts) {
        try {
          const accountsResponse = await context.plaidClient.post('/accounts/get', {});
          const accounts = accountsResponse.data.accounts;
          totalAccounts = accounts.length;

          for (const account of accounts) {
            try {
              // Prepare account data for ATOM
              const atomAccountData = {
                source: 'plaid',
                type: 'account',
                accountId: account.account_id,
                name: account.name,
                officialName: account.official_name,
                type: account.type,
                subtype: account.subtype,
                balance: account.balances.current,
                availableBalance: account.balances.available,
                currency: account.balances.iso_currency_code || 'USD',
                mask: account.mask,
                verificationStatus: account.verification_status,
                syncTimestamp: new Date().toISOString(),
              };

              // Mask account numbers if requested
              if (input.maskAccountNumbers) {
                atomAccountData.accountId = `****${account.account_id.slice(-4)}`;
                atomAccountData.mask = account.mask;
              }

              // Process through ATOM pipeline
              const atomResult = await context.atomIngestionPipeline.processDocument({
                content: JSON.stringify(atomAccountData),
                metadata: {
                  source: 'plaid',
                  documentType: 'account',
                  itemId: account.account_id,
                  encrypted: input.encryptSensitiveData,
                },
              });

              results.accountsSynced.push({
                ...account,
                atomProcessed: true,
                atomId: atomResult.id,
                atomTimestamp: atomResult.timestamp,
              });

              bytesProcessed += JSON.stringify(atomAccountData).length;

            } catch (error) {
              results.failedItems.push({
                type: 'account',
                item: account,
                error: error instanceof Error ? error.message : 'Unknown error',
              });
            }
          }

        } catch (error) {
          throw new Error(`Failed to sync accounts: ${error instanceof Error ? error.message : 'Unknown error'}`);
        }
      }

      // Sync transactions if requested
      if (input.syncTransactions && input.transactionStartDate && input.transactionEndDate) {
        try {
          const transactionsResponse = await context.plaidClient.post('/transactions/get', {
            start_date: input.transactionStartDate,
            end_date: input.transactionEndDate,
            count: 1000,
          });

          let transactions = transactionsResponse.data.transactions;
          totalTransactions = transactions.length;

          // Filter by income/expenses if requested
          if (!input.includeIncome) {
            transactions = transactions.filter((t: PlaidTransaction) => t.amount < 0);
          }
          if (!input.includeExpenses) {
            transactions = transactions.filter((t: PlaidTransaction) => t.amount > 0);
          }

          // Process transactions in batches
          const batchSize = input.batchSize || 100;
          
          for (let i = 0; i < transactions.length; i += batchSize) {
            const batch = transactions.slice(i, i + batchSize);
            
            for (const transaction of batch) {
              try {
                // Prepare transaction data for ATOM
                const atomTransactionData = {
                  source: 'plaid',
                  type: 'transaction',
                  transactionId: transaction.transaction_id,
                  amount: Math.abs(transaction.amount),
                  isIncome: transaction.amount > 0,
                  category: transaction.category,
                  categoryId: transaction.category_id,
                  date: transaction.date,
                  name: transaction.name,
                  merchantName: transaction.merchant_name,
                  paymentChannel: transaction.payment_channel,
                  accountId: transaction.account_id,
                  location: transaction.location,
                  pending: transaction.pending,
                  currency: transaction.iso_currency_code || 'USD',
                  syncTimestamp: new Date().toISOString(),
                };

                // Mask account numbers if requested
                if (input.maskAccountNumbers) {
                  atomTransactionData.accountId = `****${transaction.account_id.slice(-4)}`;
                }

                // Process through ATOM pipeline
                const atomResult = await context.atomIngestionPipeline.processDocument({
                  content: JSON.stringify(atomTransactionData),
                  metadata: {
                    source: 'plaid',
                    documentType: 'transaction',
                    itemId: transaction.transaction_id,
                    encrypted: input.encryptSensitiveData,
                  },
                });

                results.transactionsSynced.push({
                  ...transaction,
                  atomProcessed: true,
                  atomId: atomResult.id,
                  atomTimestamp: atomResult.timestamp,
                });

                bytesProcessed += JSON.stringify(atomTransactionData).length;

              } catch (error) {
                results.failedItems.push({
                  type: 'transaction',
                  item: transaction,
                  error: error instanceof Error ? error.message : 'Unknown error',
                });
              }
            }
          }

        } catch (error) {
          throw new Error(`Failed to sync transactions: ${error instanceof Error ? error.message : 'Unknown error'}`);
        }
      }

      const syncTime = Date.now() - startTime;
      const syncStats = {
        totalAccounts,
        syncedAccounts: results.accountsSynced.length,
        totalTransactions,
        syncedTransactions: results.transactionsSynced.length,
        failedItems: results.failedItems.length,
        syncTime,
        bytesProcessed,
      };

      return {
        success: true,
        data: {
          syncResults: results,
          syncStats,
        },
        metadata: {
          executionTime: syncTime,
          itemsProcessed: results.accountsSynced.length + results.transactionsSynced.length,
        },
      };

    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to sync Plaid data with ATOM memory',
        metadata: {
          executionTime: Date.now() - startTime,
        },
      };
    }
  },
};

// Helper function to generate spending analytics
async function generateSpendingAnalytics(transactions: PlaidTransaction[], input: any): Promise<PlaidSpendingAnalytics> {
  const totalIncome = transactions
    .filter(t => t.amount > 0)
    .reduce((sum, t) => sum + t.amount, 0);

  const totalExpenses = Math.abs(
    transactions
      .filter(t => t.amount < 0)
      .reduce((sum, t) => sum + t.amount, 0)
  );

  const netAmount = totalIncome - totalExpenses;

  // Spending by category
  const spendingByCategory: Record<string, { amount: number; count: number }> = {};
  
  transactions
    .filter(t => t.amount < 0)
    .forEach(t => {
      const categories = t.category || ['Uncategorized'];
      categories.forEach(cat => {
        if (!spendingByCategory[cat]) {
          spendingByCategory[cat] = { amount: 0, count: 0 };
        }
        spendingByCategory[cat].amount += Math.abs(t.amount);
        spendingByCategory[cat].count += 1;
      });
    });

  const spendingByCategoryArray = Object.entries(spendingByCategory)
    .map(([category, data]) => ({
      category,
      amount: data.amount,
      percentage: totalExpenses > 0 ? (data.amount / totalExpenses) * 100 : 0,
      transaction_count: data.count,
    }))
    .sort((a, b) => b.amount - a.amount);

  // Income by source
  const incomeBySource: Record<string, { amount: number }> = {};
  
  transactions
    .filter(t => t.amount > 0)
    .forEach(t => {
      const source = t.merchant_name || t.name || 'Unknown';
      if (!incomeBySource[source]) {
        incomeBySource[source] = { amount: 0 };
      }
      incomeBySource[source].amount += t.amount;
    });

  const incomeBySourceArray = Object.entries(incomeBySource)
    .map(([source, data]) => ({
      source,
      amount: data.amount,
      percentage: totalIncome > 0 ? (data.amount / totalIncome) * 100 : 0,
    }))
    .sort((a, b) => b.amount - a.amount);

  // Monthly trends
  const monthlyTrends: Record<string, { income: number; spending: number; net: number }> = {};
  
  transactions.forEach(t => {
    const month = t.date.substring(0, 7); // YYYY-MM
    if (!monthlyTrends[month]) {
      monthlyTrends[month] = { income: 0, spending: 0, net: 0 };
    }
    
    if (t.amount > 0) {
      monthlyTrends[month].income += t.amount;
      monthlyTrends[month].net += t.amount;
    } else {
      monthlyTrends[month].spending += Math.abs(t.amount);
      monthlyTrends[month].net -= Math.abs(t.amount);
    }
  });

  const monthlyTrendsArray = Object.entries(monthlyTrends)
    .map(([month, data]) => ({
      month,
      income: data.income,
      spending: data.spending,
      net: data.net,
    }))
    .sort((a, b) => a.month.localeCompare(b.month));

  // Top merchants
  const merchantSpending: Record<string, { amount: number; count: number }> = {};
  
  transactions
    .filter(t => t.amount < 0 && t.merchant_name)
    .forEach(t => {
      const merchant = t.merchant_name!;
      if (!merchantSpending[merchant]) {
        merchantSpending[merchant] = { amount: 0, count: 0 };
      }
      merchantSpending[merchant].amount += Math.abs(t.amount);
      merchantSpending[merchant].count += 1;
    });

  const topMerchants = Object.entries(merchantSpending)
    .map(([merchant_name, data]) => ({
      merchant_name,
      amount: data.amount,
      transaction_count: data.count,
    }))
    .sort((a, b) => b.amount - a.amount)
    .slice(0, 20); // Top 20 merchants

  // Detect recurring transactions (simplified)
  const recurringTransactions: Array<{ name: string; amount: number; frequency: string; next_expected: string }> = [];
  const transactionPatterns: Record<string, Array<{ date: string; amount: number }>> = {};
  
  transactions
    .filter(t => t.amount < 0)
    .forEach(t => {
      const normalized = t.name.toLowerCase().replace(/[^a-z0-9]/g, '');
      if (!transactionPatterns[normalized]) {
        transactionPatterns[normalized] = [];
      }
      transactionPatterns[normalized].push({
        date: t.date,
        amount: Math.abs(t.amount),
      });
    });

  Object.entries(transactionPatterns)
    .forEach(([name, instances]) => {
      if (instances.length >= 3) { // At least 3 occurrences to be considered recurring
        const avgAmount = instances.reduce((sum, i) => sum + i.amount, 0) / instances.length;
        const sortedDates = instances.map(i => i.date).sort();
        
        // Simple frequency detection
        let frequency = 'monthly';
        if (instances.some(i => i.date.includes('-W'))) {
          frequency = 'weekly';
        } else if (instances.some(i => i.date.includes('-Q'))) {
          frequency = 'quarterly';
        }

        recurringTransactions.push({
          name: instances[0].name, // Use original name
          amount: avgAmount,
          frequency,
          next_expected: sortedDates[sortedDates.length - 1], // Last occurrence as estimate
        });
      }
    });

  return {
    total_spending: totalExpenses,
    total_income: totalIncome,
    net_amount: netAmount,
    spending_by_category: spendingByCategoryArray,
    income_by_source: incomeBySourceArray,
    monthly_trends: monthlyTrendsArray,
    top_merchants: topMerchants,
    recurring_transactions: recurringTransactions.slice(0, 10), // Top 10 recurring
  };
}

// Helper function to generate insights
async function generateSpendingInsights(analytics: PlaidSpendingAnalytics, transactions: PlaidTransaction[]) {
  const insights = [];

  // Spending insight
  if (analytics.net_amount < 0) {
    insights.push({
      type: 'spending_alert',
      title: 'Spending Exceeds Income',
      description: `Your expenses exceed your income by $${Math.abs(analytics.net_amount).toFixed(2)} this period.`,
      severity: 'high',
      recommendations: [
        'Review largest spending categories',
        'Consider reducing discretionary spending',
        'Look for opportunities to increase income',
      ],
    });
  }

  // Category insights
  const topSpendingCategory = analytics.spending_by_category[0];
  if (topSpendingCategory && topSpendingCategory.percentage > 40) {
    insights.push({
      type: 'category_concentration',
      title: 'High Spending Concentration',
      description: `${topSpendingCategory.category} accounts for ${topSpendingCategory.percentage.toFixed(1)}% of your spending.`,
      severity: 'medium',
      recommendations: [
        `Analyze ${topSpendingCategory.category} spending for optimization opportunities`,
        'Consider if this concentration aligns with your financial goals',
      ],
    });
  }

  // Recurring transaction insights
  if (analytics.recurring_transactions.length > 5) {
    insights.push({
      type: 'recurring_transactions',
      title: 'Multiple Recurring Payments',
      description: `You have ${analytics.recurring_transactions.length} recurring transactions. Review for potential savings.`,
      severity: 'low',
      recommendations: [
        'Review subscription services',
        'Check for duplicate charges',
        'Consider consolidating or negotiating recurring payments',
      ],
    });
  }

  // Income stability insight
  if (analytics.income_by_source.length === 1) {
    insights.push({
      type: 'income_diversification',
      title: 'Single Income Source',
      description: 'All income comes from a single source. Consider diversification for financial stability.',
      severity: 'medium',
      recommendations: [
        'Explore additional income streams',
        'Consider investments or side businesses',
        'Build emergency savings for income security',
      ],
    });
  }

  return insights;
}

/**
 * Plaid Skills Bundle
 * Collection of all Plaid skills for easy registration
 */
export const PlaidSkillsBundle = {
  skills: [
    GetPlaidAccountsSkill,
    GetPlaidTransactionsSkill,
    GenerateSpendingAnalyticsSkill,
    SyncPlaidWithAtomMemorySkill,
  ],
  
  // Skill dependencies and relationships
  dependencies: {
    'plaid_api_client': 'Required for Plaid API access',
    'atom_ingestion_pipeline': 'Required for ATOM memory synchronization',
  },
  
  // Configuration recommendations
  recommendedConfig: {
    apiPermissions: [
      'transactions',
      'accounts',
      'auth',
      'assets',
      'liabilities',
    ],
    rateLimit: {
      requestsPerMinute: 100,
      requestsPerHour: 5000,
    },
    batchSize: 100,
    retryAttempts: 3,
    encryptionRequired: true,
  },
  
  // Skill integration examples
  examples: {
    getAccounts: {
      description: 'Retrieve all connected accounts with balances',
      input: {
        accountTypes: ['depository', 'credit'],
        includeInactive: false,
      },
    },
    
    getTransactions: {
      description: 'Get transactions for the last 30 days',
      input: {
        startDate: '2023-01-01',
        endDate: '2023-01-31',
        includePending: false,
        count: 500,
      },
    },
    
    generateAnalytics: {
      description: 'Generate comprehensive spending analytics',
      input: {
        startDate: '2023-01-01',
        endDate: '2023-12-31',
        generateMonthlyTrends: true,
        generateMerchantAnalysis: true,
        detectRecurringTransactions: true,
      },
    },
    
    syncWithAtom: {
      description: 'Sync all financial data with ATOM memory',
      input: {
        syncAccounts: true,
        syncTransactions: true,
        transactionStartDate: '2023-01-01',
        transactionEndDate: '2023-12-31',
        encryptSensitiveData: true,
        maskAccountNumbers: true,
      },
    },
  },
};

export default PlaidSkillsBundle;