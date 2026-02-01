import React, { useState } from 'react';
import {
    Search,
    Plus,
    MoreVertical,
    Eye,
    Edit,
    Trash2,
    Landmark,
    ArrowUpRight,
    ArrowDownLeft,
    RefreshCw
} from 'lucide-react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import {
    Card,
    CardContent,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { XeroTransaction, XeroBankAccount, XeroContact } from '../types';

interface XeroBankingProps {
    bankAccounts: XeroBankAccount[];
    transactions: XeroTransaction[];
    contacts: XeroContact[];
    onCreateTransaction: (transaction: any) => Promise<void>;
    loading?: boolean;
}

export const XeroBanking: React.FC<XeroBankingProps> = ({
    bankAccounts,
    transactions,
    contacts,
    onCreateTransaction,
    loading = false
}) => {
    const [searchQuery, setSearchQuery] = useState('');
    const [statusFilter, setStatusFilter] = useState('ALL');
    const [dateFilter, setDateFilter] = useState('ALL');
    const [isModalOpen, setIsModalOpen] = useState(false);

    const [transactionForm, setTransactionForm] = useState({
        type: 'SPEND',
        contactID: '',
        date: new Date().toISOString().split('T')[0],
        lineItems: [{
            description: '',
            quantity: 1,
            unitAmount: 0,
            accountCode: '400',
            taxType: 'NONE'
        }],
        reference: '',
        bankAccountID: ''
    });

    const filteredTransactions = transactions.filter(transaction => {
        const matchesSearch = !searchQuery ||
            transaction.reference?.toLowerCase().includes(searchQuery.toLowerCase()) ||
            transaction.contact?.name.toLowerCase().includes(searchQuery.toLowerCase());

        const matchesStatus = statusFilter === 'ALL' || transaction.status === statusFilter;
        const matchesDate = dateFilter === 'ALL' || transaction.date.startsWith(dateFilter);

        return matchesSearch && matchesStatus && matchesDate;
    });

    const formatCurrency = (amount: number, currency: string = 'USD') => {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: currency
        }).format(amount);
    };

    const formatDate = (dateString: string) => {
        return new Date(dateString).toLocaleDateString();
    };

    const handleSubmit = async () => {
        await onCreateTransaction(transactionForm);
        setIsModalOpen(false);
        setTransactionForm({
            type: 'SPEND',
            contactID: '',
            date: new Date().toISOString().split('T')[0],
            lineItems: [{
                description: '',
                quantity: 1,
                unitAmount: 0,
                accountCode: '400',
                taxType: 'NONE'
            }],
            reference: '',
            bankAccountID: ''
        });
    };

    return (
        <div className="space-y-6">
            <div className="flex flex-col sm:flex-row gap-4">
                <div className="relative flex-1">
                    <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                        placeholder="Search transactions..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="pl-8"
                    />
                </div>
                <Select value={statusFilter} onValueChange={setStatusFilter}>
                    <SelectTrigger className="w-[150px]">
                        <SelectValue placeholder="Status" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="ALL">All Status</SelectItem>
                        <SelectItem value="AUTHORISED">Authorised</SelectItem>
                        <SelectItem value="DELETED">Deleted</SelectItem>
                    </SelectContent>
                </Select>
                <Select value={dateFilter} onValueChange={setDateFilter}>
                    <SelectTrigger className="w-[150px]">
                        <SelectValue placeholder="Date" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="ALL">All Dates</SelectItem>
                        <SelectItem value={new Date().toISOString().split('T')[0]}>Today</SelectItem>
                        <SelectItem value={new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]}>Last 7 Days</SelectItem>
                        <SelectItem value={new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]}>Last 30 Days</SelectItem>
                    </SelectContent>
                </Select>
                <Button onClick={() => setIsModalOpen(true)}>
                    <Plus className="mr-2 h-4 w-4" />
                    Add Transaction
                </Button>
            </div>

            {/* Bank Accounts Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {bankAccounts.map((account) => (
                    <Card key={account.bankAccountID}>
                        <CardHeader className="pb-2">
                            <div className="flex justify-between items-start">
                                <CardTitle className="text-base font-medium">{account.name}</CardTitle>
                                <Badge variant="secondary">{account.type}</Badge>
                            </div>
                        </CardHeader>
                        <CardContent>
                            <div className="space-y-1">
                                <p className="text-sm text-muted-foreground">{account.bankName}</p>
                                <p className="text-xs text-muted-foreground font-mono">
                                    {account.bankAccountNumber || account.accountNumber}
                                </p>
                                <div className="pt-2">
                                    <Badge variant={account.status === 'ACTIVE' ? 'default' : 'destructive'} className={account.status === 'ACTIVE' ? 'bg-green-500 hover:bg-green-600' : ''}>
                                        {account.status}
                                    </Badge>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                ))}
            </div>

            {/* Transactions Table */}
            <div className="rounded-md border">
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead>Date</TableHead>
                            <TableHead>Type</TableHead>
                            <TableHead>Contact</TableHead>
                            <TableHead>Description</TableHead>
                            <TableHead>Account</TableHead>
                            <TableHead>Amount</TableHead>
                            <TableHead>Status</TableHead>
                            <TableHead className="text-right">Actions</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {filteredTransactions.map((transaction) => (
                            <TableRow key={transaction.transactionID}>
                                <TableCell>{formatDate(transaction.date)}</TableCell>
                                <TableCell>
                                    <Badge variant="outline">
                                        {transaction.type}
                                    </Badge>
                                </TableCell>
                                <TableCell>
                                    {transaction.contact?.name || '-'}
                                </TableCell>
                                <TableCell className="max-w-[200px] truncate">
                                    {transaction.lineItems[0]?.description || 'No description'}
                                </TableCell>
                                <TableCell className="text-sm text-muted-foreground">
                                    {transaction.lineItems[0]?.accountCode}
                                </TableCell>
                                <TableCell className={`font-medium ${transaction.type === 'SPEND' ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400'}`}>
                                    {formatCurrency(transaction.total)}
                                </TableCell>
                                <TableCell>
                                    <Badge variant={transaction.status === 'AUTHORISED' ? 'default' : 'destructive'} className={transaction.status === 'AUTHORISED' ? 'bg-green-500 hover:bg-green-600' : ''}>
                                        {transaction.status}
                                    </Badge>
                                </TableCell>
                                <TableCell className="text-right">
                                    <DropdownMenu>
                                        <DropdownMenuTrigger asChild>
                                            <Button variant="ghost" className="h-8 w-8 p-0">
                                                <span className="sr-only">Open menu</span>
                                                <MoreVertical className="h-4 w-4" />
                                            </Button>
                                        </DropdownMenuTrigger>
                                        <DropdownMenuContent align="end">
                                            <DropdownMenuItem>
                                                <Eye className="mr-2 h-4 w-4" />
                                                View Details
                                            </DropdownMenuItem>
                                            <DropdownMenuItem>
                                                <Edit className="mr-2 h-4 w-4" />
                                                Edit Transaction
                                            </DropdownMenuItem>
                                            <DropdownMenuItem>
                                                <RefreshCw className="mr-2 h-4 w-4" />
                                                Reconcile
                                            </DropdownMenuItem>
                                            <DropdownMenuItem className="text-red-600">
                                                <Trash2 className="mr-2 h-4 w-4" />
                                                Delete Transaction
                                            </DropdownMenuItem>
                                        </DropdownMenuContent>
                                    </DropdownMenu>
                                </TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </div>

            <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
                <DialogContent className="max-w-xl">
                    <DialogHeader>
                        <DialogTitle>Add Bank Transaction</DialogTitle>
                    </DialogHeader>
                    <div className="grid gap-4 py-4">
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label>Transaction Type</Label>
                                <Select
                                    value={transactionForm.type}
                                    onValueChange={(value) => setTransactionForm({ ...transactionForm, type: value })}
                                >
                                    <SelectTrigger>
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="SPEND">Spend (Payment)</SelectItem>
                                        <SelectItem value="RECEIVE">Receive (Payment)</SelectItem>
                                        <SelectItem value="TRANSFER">Transfer</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                            <div className="space-y-2">
                                <Label>Bank Account</Label>
                                <Select
                                    value={transactionForm.bankAccountID}
                                    onValueChange={(value) => setTransactionForm({ ...transactionForm, bankAccountID: value })}
                                >
                                    <SelectTrigger>
                                        <SelectValue placeholder="Select account" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {bankAccounts.map((account) => (
                                            <SelectItem key={account.bankAccountID} value={account.bankAccountID}>
                                                {account.name} ({account.currencyCode})
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label>Date</Label>
                                <Input
                                    type="date"
                                    value={transactionForm.date}
                                    onChange={(e) => setTransactionForm({ ...transactionForm, date: e.target.value })}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>Contact (Optional)</Label>
                                <Select
                                    value={transactionForm.contactID}
                                    onValueChange={(value) => setTransactionForm({ ...transactionForm, contactID: value })}
                                >
                                    <SelectTrigger>
                                        <SelectValue placeholder="Select contact" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="none">No contact</SelectItem>
                                        {contacts.map((contact) => (
                                            <SelectItem key={contact.contactID} value={contact.contactID}>
                                                {contact.name}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>

                        <div className="space-y-2">
                            <Label>Reference</Label>
                            <Input
                                value={transactionForm.reference}
                                onChange={(e) => setTransactionForm({ ...transactionForm, reference: e.target.value })}
                                placeholder="Transaction reference"
                            />
                        </div>

                        <div className="space-y-2">
                            <Label>Line Items</Label>
                            {transactionForm.lineItems.map((item, index) => (
                                <div key={index} className="flex gap-2 items-end">
                                    <div className="flex-1">
                                        <Input
                                            placeholder="Description"
                                            value={item.description}
                                            onChange={(e) => {
                                                const newItems = [...transactionForm.lineItems];
                                                newItems[index].description = e.target.value;
                                                setTransactionForm({ ...transactionForm, lineItems: newItems });
                                            }}
                                        />
                                    </div>
                                    <div className="w-32">
                                        <Input
                                            type="number"
                                            placeholder="Amount"
                                            value={item.unitAmount}
                                            onChange={(e) => {
                                                const newItems = [...transactionForm.lineItems];
                                                newItems[index].unitAmount = Number(e.target.value);
                                                setTransactionForm({ ...transactionForm, lineItems: newItems });
                                            }}
                                        />
                                    </div>
                                </div>
                            ))}
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setTransactionForm({
                                    ...transactionForm,
                                    lineItems: [...transactionForm.lineItems, {
                                        description: '',
                                        quantity: 1,
                                        unitAmount: 0,
                                        accountCode: '400',
                                        taxType: 'NONE'
                                    }]
                                })}
                                className="mt-2"
                            >
                                <Plus className="mr-2 h-4 w-4" />
                                Add Line Item
                            </Button>
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setIsModalOpen(false)}>
                            Cancel
                        </Button>
                        <Button onClick={handleSubmit} disabled={loading}>
                            {loading ? 'Adding...' : 'Add Transaction'}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
};
