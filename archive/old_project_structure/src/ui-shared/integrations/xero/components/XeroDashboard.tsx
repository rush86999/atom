import React from 'react';
import {
    TrendingUp,
    Users,
    CreditCard,
    Landmark
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { XeroInvoice, XeroContact, XeroTransaction, XeroBankAccount } from '../types';

interface XeroDashboardProps {
    invoices: XeroInvoice[];
    contacts: XeroContact[];
    transactions: XeroTransaction[];
    bankAccounts: XeroBankAccount[];
}

export const XeroDashboard: React.FC<XeroDashboardProps> = ({
    invoices,
    contacts,
    transactions,
    bankAccounts
}) => {
    return (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">
                        Total Invoices
                    </CardTitle>
                    <TrendingUp className="h-4 w-4 text-green-500" />
                </CardHeader>
                <CardContent>
                    <div className="text-2xl font-bold text-blue-500">{invoices.length}</div>
                    <p className="text-xs text-muted-foreground">
                        Active invoices
                    </p>
                </CardContent>
            </Card>
            <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">
                        Total Contacts
                    </CardTitle>
                    <Users className="h-4 w-4 text-blue-500" />
                </CardHeader>
                <CardContent>
                    <div className="text-2xl font-bold text-blue-500">{contacts.length}</div>
                    <p className="text-xs text-muted-foreground">
                        Customers and suppliers
                    </p>
                </CardContent>
            </Card>
            <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">
                        Total Transactions
                    </CardTitle>
                    <Landmark className="h-4 w-4 text-orange-500" />
                </CardHeader>
                <CardContent>
                    <div className="text-2xl font-bold text-blue-500">{transactions.length}</div>
                    <p className="text-xs text-muted-foreground">
                        Bank transactions
                    </p>
                </CardContent>
            </Card>
            <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">
                        Bank Accounts
                    </CardTitle>
                    <CreditCard className="h-4 w-4 text-purple-500" />
                </CardHeader>
                <CardContent>
                    <div className="text-2xl font-bold text-blue-500">{bankAccounts.length}</div>
                    <p className="text-xs text-muted-foreground">
                        Connected accounts
                    </p>
                </CardContent>
            </Card>
        </div>
    );
};
