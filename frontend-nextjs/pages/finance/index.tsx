import React, { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../../components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Button } from "../../components/ui/button";
import { Plus, Download, Filter, Loader2 } from "lucide-react";
import { useToast } from "../../components/ui/use-toast";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "../../components/ui/dialog";
import { Label } from "../../components/ui/label";
import { Input } from "../../components/ui/input";
import FinanceOverview from "../../components/finance/FinanceOverview";
import TransactionsList from "../../components/finance/TransactionsList";
import BudgetPlanner from "../../components/finance/BudgetPlanner";
import InvoiceManager from "../../components/finance/InvoiceManager";
import SubscriptionTracker from "../../components/finance/SubscriptionTracker";
import CategorizationReview from "../../components/finance/CategorizationReview";
import AccountantPortal from "../../components/finance/AccountantPortal";
import ForecastingSandbox from "../../components/finance/ForecastingSandbox";

const FinancePage = () => {
    const { toast } = useToast();
    const [isCreateOpen, setIsCreateOpen] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [isExporting, setIsExporting] = useState(false);
    const [newTx, setNewTx] = useState({
        description: '',
        merchant: '',
        amount: '',
        date: new Date().toISOString().split('T')[0]
    });

    const handleExportCSV = async () => {
        setIsExporting(true);
        try {
            const token = localStorage.getItem('auth_token');
            const response = await fetch('/api/accounting/transactions', {
                headers: { ...(token ? { 'Authorization': `Bearer ${token}` } : {}) }
            });
            if (!response.ok) throw new Error("Failed to fetch");
            const json = await response.json();
            const transactions = json.data?.transactions || [];

            if (transactions.length === 0) {
                toast({ title: "Export Failed", description: "No transactions to export.", variant: "error" });
                return;
            }

            const headers = ['ID', 'Date', 'Description', 'Merchant', 'Amount', 'AI Category', 'Confidence', 'Reasoning'];
            const rows = transactions.map((tx: any) => [
                tx.id,
                tx.date,
                `"${tx.description.replace(/"/g, '""')}"`,
                `"${(tx.merchant || '').replace(/"/g, '""')}"`,
                tx.amount,
                tx.suggested_category,
                tx.confidence,
                `"${(tx.reasoning || '').replace(/"/g, '""')}"`
            ]);

            const csvContent = "data:text/csv;charset=utf-8,"
                + headers.join(',') + "\n"
                + rows.map(e => e.join(',')).join("\n");

            const encodedUri = encodeURI(csvContent);
            const link = document.createElement("a");
            link.setAttribute("href", encodedUri);
            link.setAttribute("download", `finance_export_${new Date().toISOString().split('T')[0]}.csv`);
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            toast({ title: "Export Successful", description: "Transactions downloaded as CSV." });
        } catch (err) {
            toast({ title: "Export Failed", description: "Could not export data." });
        } finally {
            setIsExporting(false);
        }
    };

    const handleCreateTransaction = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsSubmitting(true);
        try {
            const token = localStorage.getItem('auth_token');
            const response = await fetch('/api/accounting/transactions', {
                method: 'POST',
                headers: {
                    ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    id: `tx_global_${Date.now()}`,
                    date: new Date(newTx.date).toISOString(),
                    amount: parseFloat(newTx.amount),
                    description: newTx.description,
                    merchant: newTx.merchant || null,
                    source: "manual"
                })
            });

            if (!response.ok) throw new Error("Failed to create transaction");

            toast({ title: "Transaction Created", description: `Successfully added new transaction.` });
            setIsCreateOpen(false);
            setNewTx({ description: '', merchant: '', amount: '', date: new Date().toISOString().split('T')[0] });

            // Trigger a global custom event to tell TransactionsList to refresh
            window.dispatchEvent(new Event('transactionCreated'));

        } catch (error) {
            toast({ title: "Error", description: "Failed to create transaction", variant: "error" });
        } finally {
            setIsSubmitting(false);
        }
    };
    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">Finance</h1>
                    <p className="text-muted-foreground">
                        Manage your finances, track expenses, and handle invoices.
                    </p>
                </div>
                <div className="flex gap-2">
                    <Button variant="outline" onClick={handleExportCSV} disabled={isExporting}>
                        {isExporting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Download className="mr-2 h-4 w-4" />}
                        Export
                    </Button>
                    <Button onClick={() => setIsCreateOpen(true)}>
                        <Plus className="mr-2 h-4 w-4" /> New Transaction
                    </Button>

                    <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
                        <DialogContent className="sm:max-w-[425px]">
                            <DialogHeader>
                                <DialogTitle>Add Transaction</DialogTitle>
                                <DialogDescription>
                                    Manually record a transaction into the ledger.
                                </DialogDescription>
                            </DialogHeader>
                            <form onSubmit={handleCreateTransaction} className="space-y-4 pt-4">
                                <div className="space-y-2">
                                    <Label htmlFor="tx-desc">Description</Label>
                                    <Input
                                        id="tx-desc"
                                        value={newTx.description}
                                        onChange={(e) => setNewTx({ ...newTx, description: e.target.value })}
                                        placeholder="Office Supplies"
                                        required
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="tx-merchant">Merchant (Optional)</Label>
                                    <Input
                                        id="tx-merchant"
                                        value={newTx.merchant}
                                        onChange={(e) => setNewTx({ ...newTx, merchant: e.target.value })}
                                        placeholder="Staples"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="tx-amount">Amount ($)</Label>
                                    <Input
                                        id="tx-amount"
                                        type="number"
                                        step="0.01"
                                        value={newTx.amount}
                                        onChange={(e) => setNewTx({ ...newTx, amount: e.target.value })}
                                        placeholder="-50.00 or 1500.00"
                                        required
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="tx-date">Date</Label>
                                    <Input
                                        id="tx-date"
                                        type="date"
                                        value={newTx.date}
                                        onChange={(e) => setNewTx({ ...newTx, date: e.target.value })}
                                        required
                                    />
                                </div>
                                <DialogFooter className="pt-4">
                                    <Button type="submit" disabled={isSubmitting}>
                                        {isSubmitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                                        Save Transaction
                                    </Button>
                                </DialogFooter>
                            </form>
                        </DialogContent>
                    </Dialog>
                </div>
            </div>

            <Tabs defaultValue="overview" className="space-y-4">
                <TabsList>
                    <TabsTrigger value="overview">Overview</TabsTrigger>
                    <TabsTrigger value="transactions">Transactions</TabsTrigger>
                    <TabsTrigger value="budget">Budgeting</TabsTrigger>
                    <TabsTrigger value="invoices">Invoices</TabsTrigger>
                    <TabsTrigger value="review">Accounting Review</TabsTrigger>
                    <TabsTrigger value="compliance">Accountant Portal</TabsTrigger>
                    <TabsTrigger value="forecasting">Forecasting</TabsTrigger>
                </TabsList>

                <TabsContent value="overview" className="space-y-4">
                    <FinanceOverview />
                </TabsContent>

                <TabsContent value="transactions" className="space-y-4">
                    <TransactionsList />
                </TabsContent>

                <TabsContent value="budget" className="space-y-4">
                    <BudgetPlanner />
                </TabsContent>

                <TabsContent value="invoices" className="space-y-4">
                    <InvoiceManager />
                </TabsContent>

                <TabsContent value="subscriptions" className="space-y-4">
                    <SubscriptionTracker />
                </TabsContent>

                <TabsContent value="review" className="space-y-4">
                    <CategorizationReview />
                </TabsContent>

                <TabsContent value="compliance" className="space-y-4">
                    <AccountantPortal />
                </TabsContent>

                <TabsContent value="forecasting" className="space-y-4">
                    <ForecastingSandbox />
                </TabsContent>
            </Tabs>
        </div>
    );
};

export default FinancePage;
