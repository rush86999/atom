/**
 * ATOM Plaid Manager Component
 * Complete financial services UI management for ATOM's Plaid integration
 * Real-time banking data sync, transaction analytics, and financial insights
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  CreditCard,
  DollarSign,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  Settings,
  Activity,
  Shield,
  FileText,
  PieChart,
  BarChart,
  Calendar,
  Laptop
} from 'lucide-react';

import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/use-toast";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

import {
  PlaidAccount,
  PlaidTransaction,
  PlaidSpendingAnalytics,
  PlaidAccountSummary,
  AtomPlaidIngestionConfig,
  PLAID_DEFAULT_CONFIG,
} from '../types';

interface PlaidManagerProps {
  accessToken?: string;
  itemId?: string;
  environment?: 'sandbox' | 'development' | 'production';
  clientId?: string;
  atomIngestionPipeline?: any;
  atomSkillRegistry?: any;
  initialConfig?: Partial<AtomPlaidIngestionConfig>;
  platform?: 'auto' | 'web' | 'desktop';
  theme?: 'auto' | 'light' | 'dark';
  onReady?: (manager: any) => void;
  onError?: (error: any) => void;
  onSyncStart?: (config: any) => void;
  onSyncComplete?: (results: any) => void;
  onSyncProgress?: (progress: any) => void;
}

interface SyncSession {
  id: string;
  startTime: string;
  status: 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';
  progress: {
    total: number;
    processed: number;
    percentage: number;
    currentItem?: string;
    errors: number;
    warnings: number;
  };
  results?: any;
  error?: string;
}

export const PlaidManager: React.FC<PlaidManagerProps> = ({
  accessToken,
  itemId,
  environment = 'sandbox',
  atomIngestionPipeline,
  atomSkillRegistry,
  initialConfig,
  onReady,
  onError,
  onSyncStart,
  onSyncComplete,
  onSyncProgress,
}) => {
  // State Management
  const [activeTab, setActiveTab] = useState('dashboard');
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [currentSyncSession, setCurrentSyncSession] = useState<SyncSession | null>(null);

  // Data State
  const [accounts, setAccounts] = useState<PlaidAccount[]>([]);
  const [transactions, setTransactions] = useState<PlaidTransaction[]>([]);
  const [analytics, setAnalytics] = useState<PlaidSpendingAnalytics | null>(null);
  const [accountSummary, setAccountSummary] = useState<PlaidAccountSummary | null>(null);

  // Configuration
  const [currentConfig, setCurrentConfig] = useState<AtomPlaidIngestionConfig>(
    () => ({ ...PLAID_DEFAULT_CONFIG, ...initialConfig })
  );
  const [configModalOpen, setConfigModalOpen] = useState(false);

  const { toast } = useToast();

  // Initialize Plaid connection
  useEffect(() => {
    if (accessToken && itemId) {
      initializePlaid();
    }
  }, [accessToken, itemId]);

  const initializePlaid = useCallback(async () => {
    setIsLoading(true);
    try {
      // Simulate Plaid connection
      await new Promise(resolve => setTimeout(resolve, 1500));

      setIsConnected(true);

      // Load initial data
      await loadDashboardData();

      // Register skills with ATOM
      if (atomSkillRegistry) {
        toast({
          title: 'Skills Registered',
          description: 'Plaid skills registered with ATOM',
        });
      }

      onReady?.({
        isConnected: true,
        hasAccounts: accounts.length > 0,
        totalAccounts: accounts.length,
      });

    } catch (error) {
      setIsConnected(false);
      onError?.(error);
      toast({
        title: 'Connection Failed',
        description: 'Failed to connect to Plaid services',
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  }, [accessToken, itemId, atomSkillRegistry, onError, onReady]);

  const loadDashboardData = useCallback(async () => {
    try {
      // Simulate data loading
      const [accountsData, transactionsData, analyticsData, summaryData] = await Promise.all([
        simulatePlaidAccounts(),
        simulatePlaidTransactions(),
        simulatePlaidAnalytics(),
        simulatePlaidAccountSummary(),
      ]);

      setAccounts(accountsData);
      setTransactions(transactionsData);
      setAnalytics(analyticsData);
      setAccountSummary(summaryData);

    } catch (error) {
      onError?.(error);
      toast({
        title: 'Data Load Failed',
        description: 'Failed to load financial data',
        variant: 'destructive',
      });
    }
  }, [onError]);

  // Start sync
  const handleStartSync = useCallback(async () => {
    if (!isConnected) {
      toast({
        title: 'Not Connected',
        description: 'Please connect to Plaid first',
        variant: 'destructive',
      });
      return;
    }

    setIsSyncing(true);
    const sessionId = `sync_${Date.now()}`;

    const session: SyncSession = {
      id: sessionId,
      startTime: new Date().toISOString(),
      status: 'running',
      progress: {
        total: transactions.length,
        processed: 0,
        percentage: 0,
        currentItem: '',
        errors: 0,
        warnings: 0,
      },
    };

    setCurrentSyncSession(session);
    onSyncStart?.(session);

    try {
      // Simulate sync process
      for (let i = 0; i < transactions.length; i++) {
        const transaction = transactions[i];
        session.progress.processed = i + 1;
        session.progress.percentage = ((i + 1) / transactions.length) * 100;
        session.progress.currentItem = transaction.name;

        setCurrentSyncSession({ ...session });
        onSyncProgress?.(session);

        await new Promise(resolve => setTimeout(resolve, 100));
      }

      session.status = 'completed';
      setCurrentSyncSession(null);
      onSyncComplete?.(session);

      toast({
        title: 'Sync Completed',
        description: `Successfully synced ${transactions.length} transactions`,
      });

      await loadDashboardData();

    } catch (error) {
      session.status = 'failed';
      session.error = error instanceof Error ? error.message : 'Sync failed';
      setCurrentSyncSession(null);
      onError?.(error);

      toast({
        title: 'Sync Failed',
        description: session.error,
        variant: 'destructive',
      });
    } finally {
      setIsSyncing(false);
    }
  }, [isConnected, transactions, onSyncStart, onSyncProgress, onSyncComplete, onError, loadDashboardData]);

  // Format utilities
  const formatCurrency = (amount: number): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(Math.abs(amount));
  };

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString();
  };

  // Simulate functions (replace with actual Plaid API calls)
  const simulatePlaidAccounts = async (): Promise<PlaidAccount[]> => {
    return [
      {
        account_id: 'acc_1',
        balances: { current: 15000, available: 12000, limit: null },
        mask: '1234',
        name: 'Checking Account',
        official_name: 'Chase Checking',
        subtype: ['checking'],
        type: 'depository',
        verification_status: null,
      },
      {
        account_id: 'acc_2',
        balances: { current: -2500, available: 5000, limit: 10000 },
        mask: '5678',
        name: 'Credit Card',
        official_name: 'Chase Sapphire',
        subtype: ['credit card'],
        type: 'credit',
        verification_status: null,
      },
      {
        account_id: 'acc_3',
        balances: { current: 85000, available: 80000, limit: null },
        mask: '9012',
        name: 'Savings Account',
        official_name: 'Ally Savings',
        subtype: ['savings'],
        type: 'depository',
        verification_status: null,
      },
    ];
  };

  const simulatePlaidTransactions = async (): Promise<PlaidTransaction[]> => {
    const transactions: PlaidTransaction[] = [];
    const categories = ['Food and Drink', 'Shops', 'Transfer', 'Travel', 'Payment', 'Income'];
    const merchants = ['Starbucks', 'Amazon', 'Walmart', 'Target', 'Uber', 'Netflix', 'Salary Deposit'];

    for (let i = 0; i < 100; i++) {
      const date = new Date();
      date.setDate(date.getDate() - Math.floor(Math.random() * 90));

      const merchant = merchants[Math.floor(Math.random() * merchants.length)];
      const category = categories[Math.floor(Math.random() * categories.length)];
      const isIncome = merchant === 'Salary Deposit';

      transactions.push({
        transaction_id: `txn_${i}`,
        pending: Math.random() < 0.1,
        amount: isIncome ? (Math.random() * 3000 + 2000) : -(Math.random() * 200 + 10),
        iso_currency_code: 'USD',
        unofficial_currency_code: null,
        category: [category],
        category_id: `cat_${Math.floor(Math.random() * 100)}`,
        date: date.toISOString().split('T')[0],
        authorized_date: null,
        location: {
          address: null,
          city: null,
          region: null,
          postal_code: null,
          country: null,
          lat: null,
          lon: null,
          store_number: null,
        },
        name: merchant,
        merchant_name: merchant,
        payment_channel: 'online',
        payment_meta: {
          by_order_of: null,
          payee: null,
          payer: null,
          payment_method: null,
          payment_processor: null,
          ppd_id: null,
          reason: null,
          reference_number: null,
        },
        account_id: `acc_${Math.floor(Math.random() * 3) + 1}`,
        account_owner: null,
        logo_url: null,
        website: null,
      });
    }

    return transactions.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
  };

  const simulatePlaidAnalytics = async (): Promise<PlaidSpendingAnalytics> => {
    return {
      total_spending: 4500,
      total_income: 7500,
      net_amount: 3000,
      spending_by_category: [
        { category: 'Food and Drink', amount: 1200, percentage: 26.7, transaction_count: 45 },
        { category: 'Shops', amount: 2000, percentage: 44.4, transaction_count: 25 },
        { category: 'Travel', amount: 800, percentage: 17.8, transaction_count: 8 },
        { category: 'Payment', amount: 500, percentage: 11.1, transaction_count: 15 },
      ],
      income_by_source: [
        { source: 'Salary', amount: 7000, percentage: 93.3 },
        { source: 'Investment', amount: 500, percentage: 6.7 },
      ],
      monthly_trends: [
        { month: '2024-01', income: 7500, spending: 4200, net: 3300 },
        { month: '2024-02', income: 7500, spending: 4800, net: 2700 },
        { month: '2024-03', income: 7500, spending: 4500, net: 3000 },
      ],
      top_merchants: [
        { merchant_name: 'Amazon', amount: 850, transaction_count: 12 },
        { merchant_name: 'Starbucks', amount: 320, transaction_count: 20 },
        { merchant_name: 'Walmart', amount: 650, transaction_count: 8 },
      ],
      recurring_transactions: [
        { name: 'Netflix', amount: 15.99, frequency: 'monthly', next_expected: '2024-02-01' },
        { name: 'Gym Membership', amount: 50.00, frequency: 'monthly', next_expected: '2024-02-01' },
        { name: 'Internet', amount: 79.99, frequency: 'monthly', next_expected: '2024-02-01' },
      ],
    };
  };

  const simulatePlaidAccountSummary = async (): Promise<PlaidAccountSummary> => {
    return {
      total_balance: 97500,
      available_balance: 87000,
      total_assets: 100000,
      total_liabilities: 2500,
      net_worth: 97500,
      accounts: [
        { id: 'acc_1', name: 'Checking Account', type: 'depository', balance: 15000, available_balance: 12000 },
        { id: 'acc_2', name: 'Credit Card', type: 'credit', balance: -2500, available_balance: 7500 },
        { id: 'acc_3', name: 'Savings Account', type: 'depository', balance: 85000, available_balance: 80000 },
      ],
    };
  };

  // Render loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center space-y-4">
          <RefreshCw className="h-12 w-12 animate-spin mx-auto text-blue-500" />
          <p className="text-muted-foreground">Initializing Plaid Manager...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-[1400px] mx-auto space-y-6">
        {/* Header */}
        <div className="flex justify-between items-center bg-card p-6 rounded-lg border shadow-sm">
          <div className="flex items-center gap-3">
            <CreditCard className="h-8 w-8 text-blue-500" />
            <div>
              <h1 className="text-2xl font-bold">Plaid Manager</h1>
              <p className="text-sm text-muted-foreground">ATOM Financial Services Integration</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Badge variant={isConnected ? 'default' : 'destructive'} className={isConnected ? 'bg-green-500 hover:bg-green-600' : ''}>
              {isConnected ? 'Connected' : 'Disconnected'}
            </Badge>

            {currentSyncSession && (
              <Badge className="bg-blue-500 hover:bg-blue-600">
                {currentSyncSession.status}
              </Badge>
            )}

            <Button
              variant="outline"
              size="sm"
              onClick={loadDashboardData}
              disabled={isLoading}
            >
              <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={() => setConfigModalOpen(true)}
            >
              <Settings className="mr-2 h-4 w-4" />
              Configure
            </Button>
          </div>
        </div>

        {/* Connection Status */}
        <Alert variant={isConnected ? 'default' : 'destructive'}>
          <Shield className="h-4 w-4" />
          <AlertTitle>{isConnected ? 'Connected' : 'Not Connected'}</AlertTitle>
          <AlertDescription>
            {isConnected
              ? 'Plaid financial services are connected and ready for use'
              : 'Configure Plaid credentials to access banking services'
            }
          </AlertDescription>
          {!isConnected && (
            <Button size="sm" onClick={initializePlaid} className="mt-2">
              Connect
            </Button>
          )}
        </Alert>

        {/* Current Sync Session */}
        {currentSyncSession && (
          <Card>
            <CardHeader>
              <div className="flex justify-between items-center">
                <CardTitle>Active Sync Session</CardTitle>
                <Badge variant={
                  currentSyncSession.status === 'running' ? 'default' :
                    currentSyncSession.status === 'paused' ? 'secondary' :
                      currentSyncSession.status === 'completed' ? 'default' : 'destructive'
                } className={currentSyncSession.status === 'running' ? 'bg-green-500 hover:bg-green-600' : ''}>
                  {currentSyncSession.status}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <Progress value={currentSyncSession.progress.percentage} className="h-2" />

              <div className="flex justify-between text-sm">
                <span>{currentSyncSession.progress.processed} / {currentSyncSession.progress.total} items</span>
                <span className="text-muted-foreground">{currentSyncSession.progress.currentItem || 'Processing...'}</span>
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div>
                  <p className="text-sm text-muted-foreground">Processed</p>
                  <p className="text-2xl font-bold">{currentSyncSession.progress.processed}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Errors</p>
                  <p className="text-2xl font-bold text-red-500">{currentSyncSession.progress.errors}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Warnings</p>
                  <p className="text-2xl font-bold text-yellow-500">{currentSyncSession.progress.warnings}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Account Summary Cards */}
        {accountSummary && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card>
              <CardContent className="pt-6">
                <div className="space-y-2">
                  <p className="text-sm text-muted-foreground">Total Balance</p>
                  <p className="text-3xl font-bold">{formatCurrency(accountSummary.total_balance)}</p>
                  <div className="flex items-center text-sm text-muted-foreground">
                    <DollarSign className="mr-1 h-4 w-4" />
                    Net Worth: {formatCurrency(accountSummary.net_worth)}
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <div className="space-y-2">
                  <p className="text-sm text-muted-foreground">Available Balance</p>
                  <p className="text-3xl font-bold">{formatCurrency(accountSummary.available_balance)}</p>
                  <div className="flex items-center text-sm text-muted-foreground">
                    <Laptop className="mr-1 h-4 w-4" />
                    Ready to use
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <div className="space-y-2">
                  <p className="text-sm text-muted-foreground">Total Assets</p>
                  <p className="text-3xl font-bold">{formatCurrency(accountSummary.total_assets)}</p>
                  <div className="flex items-center text-sm text-muted-foreground">
                    <TrendingUp className="mr-1 h-4 w-4" />
                    Positive holdings
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <div className="space-y-2">
                  <p className="text-sm text-muted-foreground">Total Liabilities</p>
                  <p className="text-3xl font-bold">{formatCurrency(accountSummary.total_liabilities)}</p>
                  <div className="flex items-center text-sm text-muted-foreground">
                    <TrendingDown className="mr-1 h-4 w-4" />
                    Outstanding debts
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Main Content Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="grid w-full grid-cols-3 lg:w-[600px]">
            <TabsTrigger value="dashboard">
              <Activity className="mr-2 h-4 w-4" />
              Dashboard
            </TabsTrigger>
            <TabsTrigger value="accounts">
              <CreditCard className="mr-2 h-4 w-4" />
              Accounts
            </TabsTrigger>
            <TabsTrigger value="analytics">
              <PieChart className="mr-2 h-4 w-4" />
              Analytics
            </TabsTrigger>
          </TabsList>

          <TabsContent value="dashboard" className="space-y-4">
            {analytics && (
              <Card>
                <CardHeader>
                  <CardTitle>Spending Overview</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex justify-between">
                    <span className="font-bold">Total Income</span>
                    <span className="font-bold text-green-600">{formatCurrency(analytics.total_income)}</span>
                  </div>

                  <div className="flex justify-between">
                    <span className="font-bold">Total Spending</span>
                    <span className="font-bold text-red-600">{formatCurrency(analytics.total_spending)}</span>
                  </div>

                  <div className="border-t pt-4" />

                  <div className="flex justify-between">
                    <span className="font-bold">Net Amount</span>
                    <span className={`font-bold ${analytics.net_amount >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {formatCurrency(analytics.net_amount)}
                    </span>
                  </div>

                  <div className="pt-4">
                    <p className="font-bold mb-2">Top Spending Categories</p>
                    <div className="space-y-2">
                      {analytics.spending_by_category.slice(0, 5).map((category, index) => (
                        <div key={index} className="flex justify-between items-center">
                          <span className="text-sm">{category.category}</span>
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-bold">{formatCurrency(category.amount)}</span>
                            <Badge variant="secondary" className="text-xs">
                              {category.percentage.toFixed(1)}%
                            </Badge>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            <Button onClick={handleStartSync} disabled={isSyncing} className="w-full">
              <RefreshCw className={`mr-2 h-4 w-4 ${isSyncing ? 'animate-spin' : ''}`} />
              {isSyncing ? 'Syncing...' : 'Start Sync'}
            </Button>
          </TabsContent>

          <TabsContent value="accounts" className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {accounts.map((account) => (
                <Card key={account.account_id} className="hover:shadow-lg transition-shadow">
                  <CardHeader>
                    <div className="flex justify-between items-start">
                      <div>
                        <CardTitle className="text-lg">{account.name}</CardTitle>
                        <p className="text-sm text-muted-foreground">****{account.mask}</p>
                      </div>
                      <Badge variant="outline">{account.type}</Badge>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      <div className="flex justify-between">
                        <span className="text-sm text-muted-foreground">Current Balance</span>
                        <span className="font-bold">{formatCurrency(account.balances.current)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm text-muted-foreground">Available</span>
                        <span className="text-sm">{formatCurrency(account.balances.available)}</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="analytics" className="space-y-4">
            {analytics && (
              <Card>
                <CardHeader>
                  <CardTitle>Top Merchants</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {analytics.top_merchants.map((merchant, index) => (
                      <div key={index} className="flex justify-between items-center">
                        <span className="font-medium">{merchant.merchant_name}</span>
                        <div className="flex items-center gap-2">
                          <span className="font-bold">{formatCurrency(merchant.amount)}</span>
                          <Badge variant="secondary" className="text-xs">
                            {merchant.transaction_count} txns
                          </Badge>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};

export default PlaidManager;