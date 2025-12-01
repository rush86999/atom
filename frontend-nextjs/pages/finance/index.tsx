import React from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../../components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Button } from "../../components/ui/button";
import { Plus, Download, Filter } from "lucide-react";
import FinanceOverview from "../../components/finance/FinanceOverview";
import TransactionsList from "../../components/finance/TransactionsList";
import BudgetPlanner from "../../components/finance/BudgetPlanner";
import InvoiceManager from "../../components/finance/InvoiceManager";
import SubscriptionTracker from "../../components/finance/SubscriptionTracker";

const FinancePage = () => {
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
                    <Button variant="outline">
                        <Download className="mr-2 h-4 w-4" /> Export
                    </Button>
                    <Button>
                        <Plus className="mr-2 h-4 w-4" /> New Transaction
                    </Button>
                </div>
            </div>

            <Tabs defaultValue="overview" className="space-y-4">
                <TabsList>
                    <TabsTrigger value="overview">Overview</TabsTrigger>
                    <TabsTrigger value="transactions">Transactions</TabsTrigger>
                    <TabsTrigger value="budget">Budgeting</TabsTrigger>
                    <TabsTrigger value="invoices">Invoices</TabsTrigger>
                    <TabsTrigger value="subscriptions">Subscriptions</TabsTrigger>
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
            </Tabs>
        </div>
    );
};

export default FinancePage;
