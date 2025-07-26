import React, { useState, useEffect, useCallback } from "react";
import withSideBarWithHeader from "../../layouts/SideBarWithHeader";
import { useUser } from "../../lib/user-context";
import { useUserRole } from "../../lib/user-context";
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Button,
  Tab,
  Tabs,
} from "@mui/material";
import {
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
} from "recharts";
import {
  DollarSign,
  TrendingUp,
  PieChart as PieChartIcon,
  Target,
  Wallet,
  Calendar,
} from "@material-ui/icons";

interface Account {
  id: string;
  name: string;
  type: string;
  balance: number;
  institution?: string;
}

interface Transaction {
  id: string;
  name: string;
  amount: number;
  date: string;
  category: string;
  merchant?: string;
  description?: string;
}

interface BudgetCategory {
  category: string;
  budgeted: number;
  spent: number;
  remaining: number;
  utilization: number;
}

interface FinancialGoal {
  id: string;
  name: string;
  description: string;
  targetAmount: number;
  current: number;
  progress: number;
  goalType: string;
  targetDate?: string;
}

interface NetWorthData {
  date: string;
  netWorth: number;
  assets: number;
  liabilities: number;
}

const FinanceDashboard: React.FC = () => {
  const { user } = useUser();
  const { hasRole } = useUserRole();
  const [activeTab, setActiveTab] = useState(0);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [budgets, setBudgets] = useState<BudgetCategory[]>([]);
  const [goals, setGoals] = useState<FinancialGoal[]>([]);
  const [netWorthHistory, setNetWorthHistory] = useState<NetWorthData[]>([]);
  const [netWorth, setNetWorth] = useState(0);
  const [loading, setLoading] = useState(true);

  const fetchAllData = useCallback(async () => {
    try {
      // Mock data for demo - replace with actual API calls
      const mockAccounts: Account[] = [
        {
          id: "1",
          name: "Chase Checking",
          type: "checking",
          balance: 5234.56,
          institution: "Chase",
        },
        {
          id: "2",
          name: "High Yield Savings",
          type: "savings",
          balance: 15890.23,
          institution: "Ally",
        },
        {
          id: "3",
          name: "Investment Account",
          type: "investment",
          balance: 48750.89,
          institution: "Vanguard",
        },
        {
          id: "4",
          name: "Credit Card",
          type: "credit",
          balance: -1298.45,
          institution: "Bank of America",
        },
      ];

      const mockTransactions: Transaction[] = [
        {
          id: "1",
          name: "Whole Foods",
          amount: -127.45,
          date: "2024-12-10",
          category: "Groceries",
          merchant: "Whole Foods Market",
        },
        {
          id: "2",
          name: "Salary Deposit",
          amount: 3500.0,
          date: "2024-12-05",
          category: "Income",
          merchant: "Employer Inc.",
        },
        {
          id: "3",
          name: "Netflix Subscription",
          amount: -15.99,
          date: "2024-12-01",
          category: "Entertainment",
          merchant: "Netflix",
        },
        {
          id: "4",
          name: "Gas Station",
          amount: -45.3,
          date: "2024-11-28",
          category: "Transportation",
          merchant: "Shell",
        },
      ];

      const mockBudgets: BudgetCategory[] = [
        {
          category: "Groceries",
          budgeted: 500,
          spent: 420,
          remaining: 80,
          utilization: 84,
        },
        {
          category: "Dining",
          budgeted: 300,
          spent: 285,
          remaining: 15,
          utilization: 95,
        },
        {
          category: "Transportation",
          budgeted: 200,
          spent: 145,
          remaining: 55,
          utilization: 72.5,
        },
        {
          category: "Entertainment",
          budgeted: 150,
          spent: 180,
          remaining: -30,
          utilization: 120,
        },
        {
          category: "Shopping",
          budgeted: 250,
          spent: 190,
          remaining: 60,
          utilization: 76,
        },
      ];

      const mockGoals: FinancialGoal[] = [
        {
          id: "1",
          name: "Emergency Fund",
          description: "3-6 months living expenses",
          targetAmount: 15000,
          current: 8750,
          progress: 58.3,
          goalType: "emergency",
        },
        {
          id: "2",
          name: "Vacation Fund - Hawaii",
          description: "2-week family vacation",
          targetAmount: 8000,
          current: 2200,
          progress: 27.5,
          goalType: "vacation",
          targetDate: "2025-06-30",
        },
        {
          id: "3",
          name: "Retirement IRA",
          description: "Annual contribution",
          targetAmount: 6500,
          current: 4800,
          progress: 73.8,
          goalType: "retirement",
        },
      ];

      const mockNetWorth = [
        {
          date: "Nov 2024",
          netWorth: 125430,
          assets: 145430,
          liabilities: 20000,
        },
        {
          date: "Oct 2024",
          netWorth: 122190,
          assets: 141190,
          liabilities: 19000,
        },
        {
          date: "Sep 2024",
          netWorth: 119890,
          assets: 137890,
          liabilities: 18000,
        },
        {
          date: "Aug 2024",
          netWorth: 116290,
          assets: 133290,
          liabilities: 17000,
        },
      ];

      setAccounts(mockAccounts);
      setTransactions(mockTransactions);
      setBudgets(mockBudgets);
      setGoals(mockGoals);
      setNetWorthHistory(mockNetWorth);
      setNetWorth(netWorthHistory[netWorthHistory.length - 1]?.netWorth || 0);
    } catch (error) {
      console.error("Error fetching finance data:", error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user && hasRole("finance")) {
      fetchAllData();
    }
  }, [user, hasRole, fetchAllData]);

  const totalAssets = accounts
    .filter((acc) =>
      [
        "checking",
        "savings",
        "investment",
        "money_market",
        "certificate_of_deposit",
        "brokerage",
      ].includes(acc.type),
    )
    .reduce((sum, acc) => sum + acc.balance, 0);

  const totalLiabilities = accounts
    .filter((acc) =>
      ["credit", "loan", "mortgage", "liability"].includes(acc.type),
    )
    .reduce((sum, acc) => sum + Math.abs(acc.balance), 0);

  const spendingByCategory = transactions
    .filter((t) => t.amount < 0)
    .reduce(
      (acc, t) => {
        const cat = t.category;
        acc[cat] = (acc[cat] || 0) + Math.abs(t.amount);
        return acc;
      },
      {} as Record<string, number>,
    );

  const COLORS = ["#0088FE", "#00C49F", "#FFBB28", "#FF8042", "#8884d8"];

  if (!hasRole("finance")) {
    return (
      <div style={{ padding: 20 }}>
        <Typography variant="h4" color="error" gutterBottom>
          Access Denied
        </Typography>
        <Typography>
          You do not have permission to access financial features. Contact your
          administrator to enable finance capabilities.
        </Typography>
      </div>
    );
  }

  if (loading) {
    return <div style={{ padding: 20 }}>Loading finance dashboard...</div>;
  }

  const renderTabContent = () => {
    switch (activeTab) {
      case 0:
        return (
          <NetWorthOverview
            netWorth={netWorth}
            assets={totalAssets}
            liabilities={totalLiabilities}
            history={netWorthHistory}
          />
        );
      case 1:
        return (
          <SpendingAnalysis
            transactions={transactions}
            budgets={budgets}
            spendingByCategory={spendingByCategory}
          />
        );
      case 2:
        return <BudgetManagement budgets={budgets} />;
      case 3:
        return <FinancialGoals goals={goals} />;
      case 4:
        return (
          <InvestmentPortfolio
            accounts={accounts.filter((a) => a.type === "investment")}
          />
        );
      case 5:
        return <TransactionHistory transactions={transactions} />;
      default:
        return (
          <NetWorthOverview
            netWorth={netWorth}
            assets={totalAssets}
            liabilities={totalLiabilities}
            history={netWorthHistory}
          />
        );
    }
  };

  return (
    <div style={{ padding: 20 }}>
      <Box
        display="flex"
        justifyContent="space-between"
        alignItems="center"
        mb={3}
      >
        <Typography variant="h4" component="h2">
          💰 Atom Finance Dashboard
        </Typography>
        <Button variant="outlined" onClick={fetchAllData}>
          Refresh Data
        </Button>
      </Box>

      {/* Navigation Tabs */}
      <Tabs
        value={activeTab}
        onChange={(_, newValue) => setActiveTab(newValue)}
        variant="scrollable"
      >
        <Tab label="Net Worth" icon={<TrendingUp />} />
        <Tab label="Spending" icon={<Wallet />} />
        <Tab label="Budgets" icon={<Target />} />
        <Tab label="Goals" icon={<Target />} />
        <Tab label="Investments" icon={<PieChartIcon />} />
        <Tab label="Transactions" icon={<Calendar />} />
      </Tabs>

      {/* Quick Stats */}
      <Grid container spacing={3} style={{ marginTop: 20 }}>
        <Grid item xs={12} md={3}>
          <StatCard
            title="Net Worth"
            value={`$${netWorth.toLocaleString()}`}
            change="+1,250"
          />
        </Grid>
        <Grid item xs={12} md={3}>
          <StatCard
            title="Total Assets"
            value={`$${totalAssets.toLocaleString()}`}
          />
        </Grid>
        <Grid item xs={12} md={3}>
          <StatCard
            title="Total Liabilities"
            value={`$${totalLiabilities.toLocaleString()}`}
          />
        </Grid>
        <Grid item xs={12} md={3}>
          <StatCard
            title="Monthly Budget"
            value={budgets
              .reduce((sum, b) => sum + b.budgeted, 0)
              .toLocaleString()}
          />
        </Grid>
      </Grid>

      <Box mt={3}>{renderTabContent()}</Box>
    </div>
  );
};

const StatCard: React.FC<{ title: string; value: string; change?: string }> = ({
  title,
  value,
  change,
}) => (
  <Card elevation={3} style={{ height: 120 }}>
    <CardContent>
      <Typography color="textSecondary" gutterBottom>
        {title}
      </Typography>
      <Typography variant="h4">{value}</Typography>
      {change && (
        <Typography variant="body2" color="success.main">
          +{change}
        </Typography>
      )}
    </CardContent>
  </Card>
);

// Individual Tab Components
const NetWorthOverview: React.FC<{
  netWorth: number;
  assets: number;
  liabilities: number;
  history: NetWorthData[];
}> = ({ netWorth, assets, liabilities, history }) => (
  <Grid container spacing={3}>
    <Grid item xs={12} md={8}>
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Net Worth Trend
          </Typography>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={history}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis />
              <Tooltip />
              <Line
                type="monotone"
                dataKey="netWorth"
                stroke="#8884d8"
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </Grid>
    <Grid item xs={12} md={4}>
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Asset Allocation
          </Typography>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={[
                  { name: "Assets", value: assets },
                  { name: "Liabilities", value: liabilities },
                ]}
                cx="50%"
                cy="50%"
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
                label={({ name, value }) =>
                  `${name}: $${value.toLocaleString()}`
                }
              >
                {[
                  { name: "Assets", value: assets },
                  { name: "Liabilities", value: liabilities },
                ].map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={COLORS[index % COLORS.length]}
                  />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </Grid>
  </Grid>
);

const SpendingAnalysis: React.FC<{
  transactions: Transaction[];
  budgets: BudgetCategory[];
  spendingByCategory: Record<string, number>;
}> = ({ transactions, budgets, spendingByCategory }) => (
  <Grid container spacing={3}>
    <Grid item xs={12} md={6}>
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Spending by Category
          </Typography>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart
              data={Object.entries(spendingByCategory).map(([cat, val]) => ({
                category: cat,
                amount: val,
              }))}
            >
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="category" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="amount" fill="#82ca9d" />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </Grid>
    <Grid item xs={12} md={6}>
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Budget Status
          </Typography>
          {budgets.map((budget) => (
            <Box key={budget.category} mb={2}>
              <Typography variant="body1" gutterBottom>
                {budget.category}: ${budget.spent.toLocaleString()} / $
                {budget.budgeted.toLocaleString()}
              </Typography>
              <Box display="flex" alignItems="center" gap={1}>
                <Box flex={1} height={8} bgcolor="#f5f5f5" borderRadius={4}>
                  <Box
                    width={`${Math.min(budget.utilization, 100)}%`}
                    height="100%"
                    bgcolor={
                      budget.utilization > 100 ? "error.main" : "primary.main"
                    }
                    borderRadius={4}
                  />
                </Box>
                <Typography
                  variant="body2"
                  color={budget.utilization > 100 ? "error" : "success"}
                >
                  {budget.utilization}%
                </Typography>
              </Box>
            </Box>
          ))}
        </CardContent>
      </Card>
    </Grid>
  </Grid>
);

const BudgetManagement: React.FC<{ budgets: BudgetCategory[] }> = ({
  budgets,
}) => (
  <Card>
    <CardContent>
      <Typography variant="h6" gutterBottom>
        Current Budgets
      </Typography>
      <Grid container spacing={2}>
        {budgets.map((budget) => (
          <Grid item xs={12} md={4} key={budget.category}>
            <Card variant="outlined">
              <CardContent>
                <Typography variant="h6">{budget.category}</Typography>
                <Typography variant="body2">
                  Spent: ${budget.spent.toLocaleString()} of $
                  {budget.budgeted.toLocaleString()}
                </Typography>
                <Typography
                  variant="h5"
                  color={budget.utilization > 100 ? "error" : "success"}
                >
                  {budget.utilization > 100
                    ? `$${Math.abs(budget.remaining).toLocaleString()} over`
                    : `$${budget.remaining.toLocaleString()} left`}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    </CardContent>
  </Card>
);

const FinancialGoals: React.FC<{ goals: FinancialGoal[] }> = ({ goals }) => (
  <Grid container spacing={3}>
    {goals.map((goal) => (
      <Grid item xs={12} md={6} key={goal.id}>
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              {goal.name}
            </Typography>
            <Typography variant="body2" color="textSecondary" gutterBottom>
              {goal.description}
            </Typography>
            <Typography variant="h4">
              ${goal.current.toLocaleString()} / $
              {goal.targetAmount.toLocaleString()}
            </Typography>
            <Typography variant="body1" color="primary">
              Progress: {goal.progress.toFixed(1)}%
            </Typography>
            <Box mt={1} display="flex" alignItems="center" gap={1}>
              <Box flex={1} height={8} bgcolor="#f5f5f5" borderRadius={4}>
                <Box
                  width={`${goal.progress}%`}
                  height="100%"
                  bgcolor="primary.main"
                  borderRadius={4}
                />
              </Box>
            </Box>
            {goal.targetDate && (
              <Typography variant="body2" color="textSecondary">
                Target: {new Date(goal.targetDate).toLocaleDateString()}
              </Typography>
            )}
          </CardContent>
        </Card>
      </Grid>
    ))}
  </Grid>
);

const InvestmentPortfolio: React.FC<{ accounts: Account[] }> = ({
  accounts,
}) => (
  <Card>
    <CardContent>
      <Typography variant="h6" gutterBottom>
        Investment Holdings
      </Typography>
      <Typography variant="h4" color="primary">
        Portfolio Value: $
        {accounts.reduce((sum, acc) => sum + acc.balance, 0).toLocaleString()}
      </Typography>
      <Grid container spacing={2} style={{ marginTop: 20 }}>
        {accounts.map((account) => (
          <Grid item xs={12} key={account.id}>
            <Card variant="outlined">
              <CardContent>
                <Typography variant="h6">{account.name}</Typography>
                <Typography variant="h4">
                  ${account.balance.toLocaleString()}
                </Typography>
                <Typography variant="body2">{account.institution}</Typography>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    </CardContent>
  </Card>
);

const TransactionHistory: React.FC<{ transactions: Transaction[] }> = ({
  transactions,
}) => (
  <Card>
    <CardContent>
      <Typography variant="h6" gutterBottom>
        Recent Transactions
      </Typography>
      {transactions.map((transaction) => (
        <Box
          key={transaction.id}
          display="flex"
          justifyContent="space-between"
          py={1}
          borderBottom="1px solid #eee"
        >
          <Box>
            <Typography variant="subtitle1">{transaction.name}</Typography>
            <Typography variant="body2" color="textSecondary">
              {transaction.merchant || transaction.category}
            </Typography>
            <Typography variant="body2" color="textSecondary">
              {new Date(transaction.date).toLocaleDateString()}
            </Typography>
          </Box>
          <Box textAlign="right">
            <Typography
              variant="h6"
              color={transaction.amount < 0 ? "error.main" : "success.main"}
            >
              ${Math.abs(transaction.amount).toLocaleString()}
            </Typography>
            <Typography variant="body2" color="textSecondary">
              {transaction.category}
            </Typography>
          </Box>
        </Box>
      ))}
    </CardContent>
  </Card>
);

export default withSideBarWithHeader(FinanceDashboard);
