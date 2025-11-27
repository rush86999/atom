import React, { useState } from "react";
import {
  Plus,
  Trash2,
  ArrowUp,
  ArrowDown,
  DollarSign,
  CreditCard,
  Wallet
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Modal, ModalFooter } from "@/components/ui/modal";
import { useToast } from "@/components/ui/use-toast";

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

const FinancePage: React.FC = () => {
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

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newTransaction, setNewTransaction] = useState<Partial<Transaction>>({
    type: "expense",
    category: "Food",
    account: "Checking"
  });

  const toast = useToast();

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
        variant: "error",
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
      variant: "success",
    });
  };

  const handleDeleteTransaction = (id: string) => {
    setTransactions((prev) => prev.filter((t) => t.id !== id));

    toast({
      title: "Transaction deleted",
      description: "The transaction has been removed.",
      variant: "success",
    });
  };

  const getBudgetProgressColor = (spent: number, amount: number) => {
    const percentage = (spent / amount) * 100;
    if (percentage >= 90) return "bg-red-500";
    if (percentage >= 75) return "bg-orange-500";
    return "bg-green-500";
  };

  return (
    <div className="min-h-screen bg-gray-50 p-4 dark:bg-gray-900">
      <div className="mx-auto max-w-7xl space-y-6">
        {/* Header */}
        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
          <div className="space-y-1">
            <h1 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-gray-100">Financial Dashboard</h1>
            <p className="text-gray-500 dark:text-gray-400">
              Manage your finances and track your goals
            </p>
          </div>
          <Button onClick={() => setIsModalOpen(true)} className="flex items-center gap-2">
            <Plus className="h-4 w-4" />
            Add Transaction
          </Button>
        </div>

        {/* Navigation Tabs */}
        <Tabs defaultValue="overview" className="w-full">
          <TabsList className="grid w-full grid-cols-4 lg:w-[400px]">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="transactions">Transactions</TabsTrigger>
            <TabsTrigger value="budgets">Budgets</TabsTrigger>
            <TabsTrigger value="goals">Goals</TabsTrigger>
          </TabsList>

          {/* Overview Tab */}
          <TabsContent value="overview" className="space-y-4 mt-4">
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              <Card>
                <CardContent className="p-6">
                  <div className="flex items-center justify-between space-y-0 pb-2">
                    <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Income</p>
                    <DollarSign className="h-4 w-4 text-green-500" />
                  </div>
                  <div className="text-2xl font-bold text-green-600 dark:text-green-400">{formatCurrency(totalIncome)}</div>
                  <div className="flex items-center pt-1 text-xs text-gray-500">
                    <ArrowUp className="mr-1 h-3 w-3 text-green-500" />
                    <span className="text-green-500 font-medium">This period</span>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-6">
                  <div className="flex items-center justify-between space-y-0 pb-2">
                    <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Expenses</p>
                    <CreditCard className="h-4 w-4 text-red-500" />
                  </div>
                  <div className="text-2xl font-bold text-red-600 dark:text-red-400">{formatCurrency(totalExpenses)}</div>
                  <div className="flex items-center pt-1 text-xs text-gray-500">
                    <ArrowDown className="mr-1 h-3 w-3 text-red-500" />
                    <span className="text-red-500 font-medium">This period</span>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-6">
                  <div className="flex items-center justify-between space-y-0 pb-2">
                    <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Net Cash Flow</p>
                    <Wallet className="h-4 w-4 text-blue-500" />
                  </div>
                  <div className={`text-2xl font-bold ${netCashFlow >= 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}>
                    {formatCurrency(netCashFlow)}
                  </div>
                  <p className="text-xs text-gray-500 pt-1">
                    {savingsRate.toFixed(1)}% savings rate
                  </p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-6">
                  <div className="flex items-center justify-between space-y-0 pb-2">
                    <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Account Balance</p>
                    <Wallet className="h-4 w-4 text-purple-500" />
                  </div>
                  <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">{formatCurrency(3500)}</div>
                  <p className="text-xs text-gray-500 pt-1">Checking account</p>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Transactions Tab */}
          <TabsContent value="transactions" className="mt-4">
            <Card>
              <CardHeader>
                <CardTitle>Recent Transactions</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="relative w-full overflow-auto">
                  <table className="w-full caption-bottom text-sm">
                    <thead className="[&_tr]:border-b">
                      <tr className="border-b transition-colors hover:bg-gray-100/50 data-[state=selected]:bg-gray-100 dark:hover:bg-gray-800/50 dark:data-[state=selected]:bg-gray-800">
                        <th className="h-12 px-4 text-left align-middle font-medium text-gray-500 dark:text-gray-400">Date</th>
                        <th className="h-12 px-4 text-left align-middle font-medium text-gray-500 dark:text-gray-400">Description</th>
                        <th className="h-12 px-4 text-left align-middle font-medium text-gray-500 dark:text-gray-400">Category</th>
                        <th className="h-12 px-4 text-right align-middle font-medium text-gray-500 dark:text-gray-400">Amount</th>
                        <th className="h-12 px-4 text-left align-middle font-medium text-gray-500 dark:text-gray-400">Account</th>
                        <th className="h-12 px-4 text-left align-middle font-medium text-gray-500 dark:text-gray-400">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="[&_tr:last-child]:border-0">
                      {transactions.map((transaction) => (
                        <tr key={transaction.id} className="border-b transition-colors hover:bg-gray-100/50 data-[state=selected]:bg-gray-100 dark:hover:bg-gray-800/50 dark:data-[state=selected]:bg-gray-800">
                          <td className="p-4 align-middle">{transaction.date}</td>
                          <td className="p-4 align-middle font-medium">{transaction.description}</td>
                          <td className="p-4 align-middle">
                            <Badge variant="secondary" className="bg-blue-100 text-blue-800 hover:bg-blue-200 dark:bg-blue-900 dark:text-blue-300">
                              {transaction.category}
                            </Badge>
                          </td>
                          <td className={`p-4 align-middle text-right font-bold ${transaction.type === "income" ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}>
                            {transaction.type === "income" ? "+" : "-"}
                            {formatCurrency(transaction.amount)}
                          </td>
                          <td className="p-4 align-middle">{transaction.account}</td>
                          <td className="p-4 align-middle">
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-8 w-8 p-0 text-red-500 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-900/20"
                              onClick={() => handleDeleteTransaction(transaction.id)}
                            >
                              <Trash2 className="h-4 w-4" />
                              <span className="sr-only">Delete</span>
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Budgets Tab */}
          <TabsContent value="budgets" className="mt-4">
            <Card>
              <CardHeader>
                <CardTitle>Budget Overview</CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                {budgets.map((budget) => {
                  const spentPercentage = (budget.spent / budget.amount) * 100;
                  return (
                    <div key={budget.id} className="space-y-2 rounded-lg border p-4 dark:border-gray-700">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="font-semibold text-gray-900 dark:text-gray-100">{budget.name}</p>
                          <p className="text-sm text-gray-500 dark:text-gray-400">{budget.category}</p>
                        </div>
                        <Badge className={`${getBudgetProgressColor(budget.spent, budget.amount)} text-white`}>
                          {spentPercentage.toFixed(0)}%
                        </Badge>
                      </div>
                      <Progress value={spentPercentage} className="h-3" />
                      <div className="flex justify-between text-sm text-gray-600 dark:text-gray-400">
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
          <TabsContent value="goals" className="mt-4">
            <Card>
              <CardHeader>
                <CardTitle>Financial Goals</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4 md:grid-cols-2">
                  {goals.map((goal) => (
                    <div key={goal.id} className="space-y-3 rounded-lg border p-4 dark:border-gray-700">
                      <div className="flex items-center justify-between">
                        <p className="font-semibold text-gray-900 dark:text-gray-100">{goal.name}</p>
                        <span className="text-xs text-gray-500">{goal.progress}% complete</span>
                      </div>
                      <Progress value={goal.progress} className="h-3" />
                      <div className="flex justify-between text-sm text-gray-600 dark:text-gray-400">
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
        <Modal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          title="Add New Transaction"
        >
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">Description</label>
              <Input
                placeholder="Enter description"
                value={newTransaction.description || ""}
                onChange={(e) => setNewTransaction({ ...newTransaction, description: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">Amount</label>
              <Input
                type="number"
                placeholder="0.00"
                value={newTransaction.amount || ""}
                onChange={(e) => setNewTransaction({ ...newTransaction, amount: Number(e.target.value) })}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">Type</label>
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
              <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">Category</label>
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
          <ModalFooter>
            <Button variant="outline" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleAddTransaction}>
              Add Transaction
            </Button>
          </ModalFooter>
        </Modal>
      </div>
    </div>
  );
};

export default FinancePage;
