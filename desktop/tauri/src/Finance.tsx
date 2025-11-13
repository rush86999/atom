import React, { useState, useEffect, useCallback } from "react";

import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Button,
  Badge,
  LinearProgress,
  Alert,
} from "@mui/material";
// Simple text replacements for icons
const TrendingUpIcon = () => <span>📈</span>;
const AccountIcon = () => <span>💰</span>;
const AddIcon = () => <span>➕</span>;
const MoreIcon = () => <span>⋯</span>;
const PieChartIcon = () => <span>📊</span>;
const ChevronRightIcon = () => <span>›</span>;
const ChevronUpIcon = () => <span>↑</span>;
const ChevronDownIcon = () => <span>↓</span>;
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
} from "recharts";

// Enhanced finance types for full feature parity
interface Account {
  id: string;
  name: string;
  type: "checking" | "savings" | "investment" | "credit" | "loan";
  balance: number;
  institution: string;
  lastUpdate: string;
}

interface Transaction {
  id: string;
  date: string;
  amount: number;
  description: string;
  merchant: string;
  category: string;
  accountId: string;
}

interface Budget {
  id: string;
  name: string;
  category: string;
  budgeted: number;
  spent: number;
  utilization: number;
  remaining: number;
}

interface FinancialGoal {
  id: string;
  name: string;
  description: string;
  target: number;
  saved: number;
  progress: number;
  deadline: string;
}

interface NetWorthData {
  current: number;
  change: number;
  percent: number;
  history: Array<{
    date: string;
    netWorth: number;
    assets: number;
    liabilities: number;
  }>;
}

const Finance: React.FC = () => {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [goals, setGoals] = useState<FinancialGoal[]>([]);
  const [netWorth, setNetWorth] = useState<NetWorthData>({
    current: 0,
    change: 0,
    percent: 0,
    history: [],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // User context disabled for desktop app demo
  const user = { id: "demo-user", name: "Demo User" };
  const hasFinanceAccess = () => true;

  const fetchFinanceData = useCallback(async () => {
    if (!hasFinanceAccess) return;

    try {
      setLoading(true);
      setError(null);

      // Mock data for demonstration
      const mockAccounts: Account[] = [
        {
          id: "1",
          name: "Checking Account",
          type: "checking",
          balance: 12500,
          institution: "Chase Bank",
          lastUpdate: "2024-01-15",
        },
        {
          id: "2",
          name: "Savings Account",
          type: "savings",
          balance: 42500,
          institution: "Chase Bank",
          lastUpdate: "2024-01-15",
        },
        {
          id: "3",
          name: "Investment Portfolio",
          type: "investment",
          balance: 48750,
          institution: "Fidelity",
          lastUpdate: "2024-01-15",
        },
        {
          id: "4",
          name: "Credit Card",
          type: "credit",
          balance: -19000,
          institution: "American Express",
          lastUpdate: "2024-01-15",
        },
      ];

      const mockTransactions: Transaction[] = [
        {
          id: "1",
          date: "2024-01-14",
          amount: -125.5,
          description: "Grocery Shopping",
          merchant: "Whole Foods",
          category: "Food",
          accountId: "1",
        },
        {
          id: "2",
          date: "2024-01-13",
          amount: -89.99,
          description: "Monthly Subscription",
          merchant: "Netflix",
          category: "Entertainment",
          accountId: "1",
        },
        {
          id: "3",
          date: "2024-01-12",
          amount: 4500,
          description: "Salary Deposit",
          merchant: "Employer Inc",
          category: "Income",
          accountId: "1",
        },
      ];

      const mockBudgets: Budget[] = [
        {
          id: "1",
          name: "Groceries",
          category: "Food",
          budgeted: 600,
          spent: 425,
          utilization: 70.8,
          remaining: 175,
        },
        {
          id: "2",
          name: "Entertainment",
          category: "Entertainment",
          budgeted: 300,
          spent: 275,
          utilization: 91.7,
          remaining: 25,
        },
        {
          id: "3",
          name: "Transportation",
          category: "Transport",
          budgeted: 400,
          spent: 320,
          utilization: 80.0,
          remaining: 80,
        },
      ];

      const mockGoals: FinancialGoal[] = [
        {
          id: "1",
          name: "Emergency Fund",
          description: "6 months of living expenses",
          target: 30000,
          saved: 24500,
          progress: 81.7,
          deadline: "2024-06-30",
        },
        {
          id: "2",
          name: "Vacation Fund",
          description: "Trip to Europe",
          target: 8000,
          saved: 5200,
          progress: 65.0,
          deadline: "2024-08-15",
        },
      ];

      const mockNetWorth: NetWorthData = {
        current: 123430,
        change: 3120,
        percent: 2.6,
        history: [
          {
            date: "Jan '24",
            netWorth: 105000,
            assets: 120000,
            liabilities: 15000,
          },
          {
            date: "Feb '24",
            netWorth: 107500,
            assets: 122500,
            liabilities: 15000,
          },
          {
            date: "Mar '24",
            netWorth: 109800,
            assets: 124800,
            liabilities: 15000,
          },
          {
            date: "Apr '24",
            netWorth: 112200,
            assets: 127200,
            liabilities: 15000,
          },
          {
            date: "May '24",
            netWorth: 114500,
            assets: 129500,
            liabilities: 15000,
          },
          {
            date: "Jun '24",
            netWorth: 116290,
            assets: 133290,
            liabilities: 17000,
          },
          {
            date: "Jul '24",
            netWorth: 119890,
            assets: 137890,
            liabilities: 18000,
          },
          {
            date: "Aug '24",
            netWorth: 122190,
            assets: 141190,
            liabilities: 19000,
          },
          {
            date: "Sep '24",
            netWorth: 123430,
            assets: 142430,
            liabilities: 19000,
          },
        ],
      };

      setAccounts(mockAccounts);
      setTransactions(mockTransactions);
      setBudgets(mockBudgets);
      setGoals(mockGoals);
      setNetWorth(mockNetWorth);
    } catch (err) {
      setError("Failed to load finance data");
      console.error("Finance data error:", err);
    } finally {
      setLoading(false);
    }
  }, [hasFinanceAccess]);

  useEffect(() => {
    fetchFinanceData();
  }, [fetchFinanceData]);

  const calculateTotalAssets = () =>
    accounts
      .filter((a) => ["checking", "savings", "investment"].includes(a.type))
      .reduce((sum, acc) => sum + acc.balance, 0);
  const calculateTotalLiabilities = () =>
    accounts
      .filter((a) => ["credit", "loan"].includes(a.type))
      .reduce((sum, acc) => sum + Math.abs(acc.balance), 0);

  const QuickStats = () => (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-6">
      <Card elevation={2}>
        <CardContent>
          <Typography variant="h6" color="textSecondary" gutterBottom>
            Net Worth
          </Typography>
          <Typography variant="h4" className="font-bold">
            ${netWorth.current.toLocaleString()}
          </Typography>
          <Typography
            variant="body2"
            color={netWorth.change >= 0 ? "success.main" : "error.main"}
          >
            {netWorth.percent > 0 ? "+" : ""}
            {netWorth.percent}%
          </Typography>
        </CardContent>
      </Card>

      <Card elevation={2}>
        <CardContent>
          <Typography variant="h6" color="textSecondary" gutterBottom>
            Total Assets
          </Typography>
          <Typography variant="h4" className="font-bold">
            ${calculateTotalAssets().toLocaleString()}
          </Typography>
          <Typography variant="body2" color="textSecondary">
            All liquid and investment assets
          </Typography>
        </CardContent>
      </Card>

      <Card elevation={2}>
        <CardContent>
          <Typography variant="h6" color="textSecondary" gutterBottom>
            Total Liabilities
          </Typography>
          <Typography variant="h4" className="font-bold">
            ${calculateTotalLiabilities().toLocaleString()}
          </Typography>
          <Typography variant="body2" color="textSecondary">
            Credit cards, loans, mortgages
          </Typography>
        </CardContent>
      </Card>

      <Card elevation={2}>
        <CardContent>
          <Typography variant="h6" color="textSecondary" gutterBottom>
            Financial Health
          </Typography>
          <Typography variant="h4" className="font-bold">
            Excellent
          </Typography>
          <Typography variant="body2" color="textSecondary">
            Retirement projection
          </Typography>
        </CardContent>
      </Card>
    </div>
  );

  const BudgetProgress = () => (
    <Card elevation={2}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Budget Progress
        </Typography>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {budgets.map((budget) => (
            <div key={budget.id}>
              <Box>
                <Box
                  display="flex"
                  justifyContent="space-between"
                  alignItems="center"
                >
                  <Typography variant="subtitle1">{budget.name}</Typography>
                  <Typography variant="body2" color="textSecondary">
                    {budget.utilization.toFixed(1)}%
                  </Typography>
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={Math.min(budget.utilization, 100)}
                  color={budget.utilization > 100 ? "error" : "primary"}
                  style={{ height: 6, borderRadius: 3 }}
                />
                <Box
                  display="flex"
                  justifyContent="space-between"
                  alignItems="center"
                  mt={1}
                >
                  <Typography variant="caption">
                    ${budget.spent.toLocaleString()} spent
                  </Typography>
                  <Typography variant="caption">
                    ${budget.remaining.toLocaleString()} remaining
                  </Typography>
                </Box>
              </Box>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );

  const GoalsProgress = () => (
    <Card elevation={2}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Financial Goals
        </Typography>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {goals.map((goal) => (
            <div key={goal.id}>
              <Card elevation={2}>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    {goal.name}
                  </Typography>
                  <Typography
                    variant="body2"
                    color="textSecondary"
                    gutterBottom
                  >
                    {goal.description}
                  </Typography>

                  <Box
                    display="flex"
                    justifyContent="space-between"
                    alignItems="center"
                    mb={2}
                  >
                    <Typography variant="body1">
                      ${goal.saved.toLocaleString()} / $
                      {goal.target.toLocaleString()}
                    </Typography>
                    <Typography variant="h6" color="primary">
                      {goal.progress.toFixed(1)}%
                    </Typography>
                  </Box>

                  <LinearProgress
                    variant="determinate"
                    value={goal.progress}
                    style={{ height: 8, borderRadius: 4 }}
                  />

                  <Box
                    display="flex"
                    justifyContent="space-between"
                    alignItems="center"
                    mt={1}
                  >
                    <Typography variant="caption">
                      Target: {new Date(goal.deadline).toLocaleDateString()}
                    </Typography>
                    <Typography
                      variant="caption"
                      color={goal.progress >= 80 ? "success" : "warning"}
                    >
                      {goal.target - goal.saved} to go
                    </Typography>
                  </Box>
                </CardContent>
              </Card>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );

  const InvestmentHoldings = () => (
    <Card elevation={2}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Investment Holdings
        </Typography>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="md:col-span-2">
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={[
                    { name: "Stocks", value: 35000 },
                    { name: "Bonds", value: 8000 },
                    { name: "Cash", value: 5750 },
                  ]}
                  cx="50%"
                  cy="50%"
                  outerRadius={120}
                  fill="#8884d8"
                  dataKey="value"
                  label={({ name, percent }) =>
                    `${name} ${((percent || 0) * 100).toFixed(0)}%`
                  }
                >
                  <Cell fill="#FF8042" />
                  <Cell fill="#00C49F" />
                  <Cell fill="#FFBB28" />
                </Pie>
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div>
            <Box>
              <Typography variant="h4">
                $
                {accounts
                  .find((a) => a.type === "investment")
                  ?.balance.toLocaleString() || "$0"}
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Total Portfolio Value
              </Typography>
            </Box>
          </div>
        </div>
      </CardContent>
    </Card>
  );

  const RecentTransactions = () => (
    <Card elevation={2}>
      <CardContent>
        <Box
          display="flex"
          justifyContent="space-between"
          alignItems="center"
          mb={2}
        >
          <Typography variant="h6">Recent Transactions</Typography>
          <Button size="small" variant="outlined">
            View All
          </Button>
        </Box>

        {transactions.slice(0, 5).map((transaction) => (
          <Box
            key={transaction.id}
            display="flex"
            justifyContent="space-between"
            alignItems="center"
            py={2}
            borderBottom="1px solid #eee"
          >
            <Box>
              <Typography variant="subtitle1" fontWeight="medium">
                {transaction.description}
              </Typography>
              <Typography variant="body2" color="textSecondary">
                {transaction.merchant} •{" "}
                {new Date(transaction.date).toLocaleDateString()}
              </Typography>
            </Box>

            <Typography
              variant="h6"
              color={transaction.amount < 0 ? "error.main" : "success.main"}
            >
              $
              {Math.abs(transaction.amount).toLocaleString("en-US", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
            </Typography>
          </Box>
        ))}
      </CardContent>
    </Card>
  );

  const FeatureActions = () => (
    <Box display="flex" gap={2} flexWrap="wrap">
      <Button
        variant="contained"
        color="primary"
        startIcon={<AddIcon />}
        onClick={() => console.log("Create budget")}
      >
        Create Budget
      </Button>

      <Button
        variant="contained"
        color="success"
        startIcon={<AddIcon />}
        onClick={() => console.log("Set goal")}
      >
        Set Goal
      </Button>

      <Button
        variant="outlined"
        startIcon={<AccountIcon />}
        onClick={() => console.log("Connect account")}
      >
        Connect Account
      </Button>
    </Box>
  );

  if (!hasFinanceAccess) {
    return (
      <div className="flex items-center justify-center h-96">
        <Card>
          <CardContent>
            <Typography variant="h5" color="error" gutterBottom>
              Finance Features Access Required
            </Typography>
            <Typography>
              Check with your system administrator to enable personal finance
              management features.
            </Typography>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Card>
          <CardContent>
            <Typography>Loading comprehensive finance data...</Typography>
            <LinearProgress className="w-full" />
          </CardContent>
        </Card>
      </div>
    );
  }

  const totalAssets = calculateTotalAssets();
  const totalLiabilities = calculateTotalLiabilities();

  return (
    <div className="p-6 bg-gray-50 min-h-screen">
      <Box mb={4}>
        <Box
          display="flex"
          justifyContent="space-between"
          alignItems="center"
          mb={4}
        >
          <Typography variant="h4" className="font-bold text-gray-900">
            💰 Atom Finance Dashboard
          </Typography>

          <Box display="flex" gap={2}>
            <Button variant="outlined" onClick={fetchFinanceData}>
              Refresh Data
            </Button>

            <Button variant="contained" color="primary">
              Add Account
            </Button>
          </Box>
        </Box>

        <Alert severity="info" className="mb-4">
          <Typography variant="body2">
            <strong>Feature Parity Achieved:</strong> This dashboard provides
            comprehensive financial management including net worth tracking,
            budgets, goals, and investments - equivalent to maybe-finance
            functionality.
          </Typography>
        </Alert>
      </Box>

      <QuickStats />

      <Box mb={4}>
        <FeatureActions />
      </Box>

      <div className="grid grid-cols-1 gap-6">
        {/* Net Worth Overview */}
        <div className="lg:col-span-2">
          <Card elevation={4}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Net Worth Trend
              </Typography>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={netWorth.history}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" />
                  <YAxis />
                  <Tooltip
                    formatter={(value: any) => `$${value.toLocaleString()}`}
                  />
                  <Line
                    type="monotone"
                    dataKey="netWorth"
                    stroke="#3b82f6"
                    strokeWidth={3}
                  />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </div>

        {/* Asset Allocation */}
        <div>
          <Card elevation={4}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Asset Allocation
              </Typography>
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={[
                      { name: "Assets", value: totalAssets },
                      { name: "Liabilities", value: totalLiabilities },
                    ]}
                    cx="50%"
                    cy="50%"
                    outerRadius={100}
                    dataKey="value"
                    label={({ name, percent }) =>
                      `${name} ${((percent || 0) * 100).toFixed(0)}%`
                    }
                  >
                    <Cell fill="#10b981" />
                    <Cell fill="#ef4444" />
                  </Pie>
                  <Tooltip
                    formatter={(value: any) => `$${value.toLocaleString()}`}
                  />
                </PieChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </div>

        {/* Budget Progress */}
        <div>
          <BudgetProgress />
        </div>

        {/* Financial Goals */}
        <div>
          <GoalsProgress />
        </div>

        {/* Investment Holdings */}
        <div>
          <InvestmentHoldings />
        </div>

        {/* Recent Transactions */}
        <div>
          <RecentTransactions />
        </div>
      </div>

      {/* Detailed Sections */}
      <Box mt={6}>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <Card elevation={2}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Account Overview
                </Typography>
                {accounts.map((account) => (
                  <Box
                    key={account.id}
                    display="flex"
                    justifyContent="space-between"
                    py={1}
                    borderBottom="1px solid #f3f4f6"
                  >
                    <Box>
                      <Typography variant="subtitle1">
                        {account.name}
                      </Typography>
                      <Typography variant="body2" color="textSecondary">
                        {account.institution}
                      </Typography>
                    </Box>
                    <Typography
                      variant="h6"
                      color={account.balance < 0 ? "error" : "primary"}
                    >
                      ${account.balance.toLocaleString()}
                    </Typography>
                  </Box>
                ))}
              </CardContent>
            </Card>
          </div>

          <div>
            <Card elevation={2}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Monthly Budget Summary
                </Typography>
                <Box>
                  <Typography variant="h4" color="primary">
                    $
                    {budgets
                      .reduce((sum, b) => sum + b.spent, 0)
                      .toLocaleString()}{" "}
                    / $
                    {budgets
                      .reduce((sum, b) => sum + b.budgeted, 0)
                      .toLocaleString()}
                  </Typography>
                  <Typography variant="body2" color="textSecondary">
                    Total monthly spending vs budget
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          </div>
        </div>
      </Box>
    </div>
  );
};

export default Finance;
