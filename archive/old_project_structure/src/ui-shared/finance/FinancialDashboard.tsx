import React, { useState } from "react";
import {
  Plus,
  Trash2,
  ArrowUp,
  ArrowDown,
  DollarSign,
  CreditCard,
  Wallet,
  TrendingUp,
  TrendingDown,
  MoreVertical
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { useToast } from "@/components/ui/use-toast";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface Transaction {
  id: string;
  date: string;
  description: string;
  amount: number;
  type: "income" | "expense";
  category: string;
  account: string;
}

interface Budget {
  id: string;
  name: string;
  category: string;
  amount: number;
  spent: number;
  period: "monthly";
}

interface FinancialGoal {
  id: string;
  name: string;
  targetAmount: number;
  currentAmount: number;
  progress: number;
}

interface FinancialDashboardProps {
  showNavigation?: boolean;
  compactView?: boolean;
}

const FinancialDashboard: React.FC<FinancialDashboardProps> = ({
  showNavigation = true,
  compactView = false,
}) => {
  const [transactions, setTransactions] = useState<Transaction[]>([
    {
      id: "1",
      date: "2024-01-15",
      description: "Salary",
      amount: 5000,
      type: "income",
      category: "Salary",
      account: "Checking",
    },
    {
      id: "2",
      date: "2024-01-14",
      description: "Grocery Store",
      amount: 150.75,
      type: "expense",
      category: "Food",
      account: "Credit Card",
    },
    {
      id: "3",
      date: "2024-01-13",
      description: "Electric Bill",
      amount: 89.99,
      type: "expense",
      category: "Utilities",
      account: "Checking",
    },
  ]);

  const [budgets, setBudgets] = useState<Budget[]>([
    {
      id: "1",
      name: "Groceries",
      category: "Food",
      amount: 600,
      spent: 450,
      period: "monthly",
    },
    {
      id: "2",
      name: "Entertainment",
      category: "Entertainment",
      amount: 200,
      spent: 180,
      period: "monthly",
    },
  ]);

  const [goals, setGoals] = useState<FinancialGoal[]>([
    {
      id: "1",
      name: "Emergency Fund",
      targetAmount: 10000,
      currentAmount: 3500,
      progress: 35,
    },
    {
      id: "2",
      name: "Vacation",
      targetAmount: 3000,
      currentAmount: 1200,
      progress: 40,
    },
  ]);

  const [activeTab, setActiveTab] = useState("overview");
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newTransaction, setNewTransaction] = useState<Partial<Transaction>>({
    type: "expense",
    category: "Food",
    account: "Checking"
  });

  const { toast } = useToast();

  const totalIncome = transactions
    .filter((t) => t.type === "income")
    .reduce((sum, t) => sum + t.amount, 0);

  const totalExpenses = transactions
    .filter((t) => t.type === "expense")
    .reduce((sum, t) => sum + t.amount, 0);

  const netCashFlow = totalIncome - totalExpenses;
  const savingsRate = totalIncome > 0 ? (netCashFlow / totalIncome) * 100 : 0;

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
    }).format(amount);
  };

  const handleAddTransaction = () => {
    if (!newTransaction.description || !newTransaction.amount) {
      toast({
        title: "Missing fields",
        description: "Please fill in all required fields",
        variant: "destructive",
      });
      return;
    }

    const transaction: Transaction = {
      id: Date.now().toString(),
      date: new Date().toISOString().split("T")[0],
      description: newTransaction.description || "",
      amount: Number(newTransaction.amount),
      type: newTransaction.type as "income" | "expense",
      category: newTransaction.category || "Other",
      account: newTransaction.account || "Checking",
    };

    setTransactions((prev) => [...prev, transaction]);
    setIsModalOpen(false);
    setNewTransaction({ type: "expense", category: "Food", account: "Checking" });

    toast({
      title: "Transaction added",
      description: "Your transaction has been recorded successfully.",
    });
  };

  const handleDeleteTransaction = (id: string) => {
    setTransactions((prev) => prev.filter((t) => t.id !== id));

    toast({
      title: "Transaction deleted",
      description: "The transaction has been removed.",
    });
  };

  const getBudgetProgressColor = (spent: number, amount: number) => {
    const percentage = (spent / amount) * 100;
    if (percentage >= 90) return "bg-red-500";
    if (percentage >= 75) return "bg-orange-500";
    return "bg-green-500";
  };

  return (
    <div className={`p-4 ${compactView ? "p-2" : "p-4"}`}>
      {/* Header */}
      {showNavigation && (
        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center mb-6">
          <div className="space-y-1">
            <h1 className={`font-bold tracking-tight ${compactView ? "text-xl" : "text-3xl"}`}>
              Financial Dashboard
            </h1>
            <p className={`text-muted-foreground ${compactView ? "text-sm" : "text-base"}`}>
              Manage your finances and track your goals
            </p>
          </div>
          <Button onClick={() => setIsModalOpen(true)} size={compactView ? "sm" : "default"}>
            <Plus className="mr-2 h-4 w-4" />
            Add Transaction
          </Button>
        </div>
      )}

      {/* Navigation Tabs */}
      <Tabs defaultValue="overview" value={activeTab} onValueChange={setActiveTab} className="w-full">
        {showNavigation && (
          <TabsList className="grid w-full grid-cols-4 lg:w-[400px] mb-6">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="transactions">Transactions</TabsTrigger>
            <TabsTrigger value="budgets">Budgets</TabsTrigger>
            <TabsTrigger value="goals">Goals</TabsTrigger>
          </TabsList>
        )}

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardContent className="p-6">
                <div className="flex items-center justify-between space-y-0 pb-2">
                  <p className="text-sm font-medium text-muted-foreground">Total Income</p>
                  <DollarSign className="h-4 w-4 text-green-500" />
                </div>
                <div className="text-2xl font-bold text-green-600 dark:text-green-400">{formatCurrency(totalIncome)}</div>
                <div className="flex items-center pt-1 text-xs text-muted-foreground">
                  <ArrowUp className="mr-1 h-3 w-3 text-green-500" />
                  <span className="text-green-500 font-medium">This period</span>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-6">
                <div className="flex items-center justify-between space-y-0 pb-2">
                  <p className="text-sm font-medium text-muted-foreground">Total Expenses</p>
                  <CreditCard className="h-4 w-4 text-red-500" />
                </div>
                <div className="text-2xl font-bold text-red-600 dark:text-red-400">{formatCurrency(totalExpenses)}</div>
                <div className="flex items-center pt-1 text-xs text-muted-foreground">
                  <ArrowDown className="mr-1 h-3 w-3 text-red-500" />
                  <span className="text-red-500 font-medium">This period</span>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-6">
                <div className="flex items-center justify-between space-y-0 pb-2">
                  <p className="text-sm font-medium text-muted-foreground">Net Cash Flow</p>
                  <Wallet className="h-4 w-4 text-blue-500" />
                </div>
                <div className={`text-2xl font-bold ${netCashFlow >= 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}>
                  {formatCurrency(netCashFlow)}
                </div>
                <p className="text-xs text-muted-foreground pt-1">
                  {savingsRate.toFixed(1)}% savings rate
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-6">
                <div className="flex items-center justify-between space-y-0 pb-2">
                  <p className="text-sm font-medium text-muted-foreground">Account Balance</p>
                  <Wallet className="h-4 w-4 text-purple-500" />
                </div>
                <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">{formatCurrency(3500)}</div>
                <p className="text-xs text-muted-foreground pt-1">Checking account</p>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Transactions Tab */}
        <TabsContent value="transactions">
          <Card>
            <CardHeader>
              <CardTitle className={compactView ? "text-lg" : "text-xl"}>Recent Transactions</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="relative w-full overflow-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Date</TableHead>
                      <TableHead>Description</TableHead>
                      <TableHead>Category</TableHead>
                      <TableHead className="text-right">Amount</TableHead>
                      <TableHead>Account</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {transactions.map((transaction) => (
                      <TableRow key={transaction.id}>
                        <TableCell>{transaction.date}</TableCell>
                        <TableCell className="font-medium">{transaction.description}</TableCell>
                        <TableCell>
                          <Badge variant="secondary" className="bg-blue-100 text-blue-800 hover:bg-blue-200 dark:bg-blue-900 dark:text-blue-300">
                            {transaction.category}
                          </Badge>
                        </TableCell>
                        <TableCell className={`text-right font-bold ${transaction.type === "income" ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}>
                          {transaction.type === "income" ? "+" : "-"}
                          {formatCurrency(transaction.amount)}
                        </TableCell>
                        <TableCell>{transaction.account}</TableCell>
                        <TableCell>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-8 w-8 p-0 text-red-500 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-900/20"
                            onClick={() => handleDeleteTransaction(transaction.id)}
                          >
                            <Trash2 className="h-4 w-4" />
                            <span className="sr-only">Delete</span>
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Budgets Tab */}
        <TabsContent value="budgets">
          <Card>
            <CardHeader>
              <CardTitle className={compactView ? "text-lg" : "text-xl"}>Budget Overview</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {budgets.map((budget) => {
                const spentPercentage = (budget.spent / budget.amount) * 100;
                return (
                  <div key={budget.id} className="space-y-2 rounded-lg border p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-semibold">{budget.name}</p>
                        <p className="text-sm text-muted-foreground">{budget.category}</p>
                      </div>
                      <Badge className={`${getBudgetProgressColor(budget.spent, budget.amount)} text-white`}>
                        {spentPercentage.toFixed(0)}%
                      </Badge>
                    </div>
                    <Progress value={spentPercentage} className="h-3" />
                    <div className="flex justify-between text-sm text-muted-foreground">
                      <span>Spent: {formatCurrency(budget.spent)}</span>
                      <span>Budget: {formatCurrency(budget.amount)}</span>
                      <span>Remaining: {formatCurrency(budget.amount - budget.spent)}</span>
                    </div>
                  </div>
                );
              })}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Goals Tab */}
        <TabsContent value="goals">
          <Card>
            <CardHeader>
              <CardTitle className={compactView ? "text-lg" : "text-xl"}>Financial Goals</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-2">
                {goals.map((goal) => (
                  <div key={goal.id} className="space-y-3 rounded-lg border p-4">
                    <div className="flex items-center justify-between">
                      <p className="font-semibold">{goal.name}</p>
                      <span className="text-xs text-muted-foreground">{goal.progress}% complete</span>
                    </div>
                    <Progress value={goal.progress} className="h-3" />
                    <div className="flex justify-between text-sm text-muted-foreground">
                      <span>{formatCurrency(goal.currentAmount)}</span>
                      <span>Target: {formatCurrency(goal.targetAmount)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Add Transaction Modal */}
      <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add New Transaction</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Description</Label>
              <Input
                placeholder="Enter description"
                value={newTransaction.description || ""}
                onChange={(e) => setNewTransaction({ ...newTransaction, description: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>Amount</Label>
              <Input
                type="number"
                placeholder="0.00"
                value={newTransaction.amount || ""}
                onChange={(e) => setNewTransaction({ ...newTransaction, amount: Number(e.target.value) })}
              />
            </div>
            <div className="space-y-2">
              <Label>Type</Label>
              <Select
                value={newTransaction.type}
                onValueChange={(value) => setNewTransaction({ ...newTransaction, type: value as "income" | "expense" })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="income">Income</SelectItem>
                  <SelectItem value="expense">Expense</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Category</Label>
              <Select
                value={newTransaction.category}
                onValueChange={(value) => setNewTransaction({ ...newTransaction, category: value })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select category" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="Salary">Salary</SelectItem>
                  <SelectItem value="Food">Food</SelectItem>
                  <SelectItem value="Utilities">Utilities</SelectItem>
                  <SelectItem value="Entertainment">Entertainment</SelectItem>
                  <SelectItem value="Other">Other</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleAddTransaction}>
              Add Transaction
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default FinancialDashboard;
