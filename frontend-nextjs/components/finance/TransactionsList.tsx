import React, { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../ui/card";
import { Input } from "../ui/input";
import { Button } from "../ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../ui/table";
import { Badge } from "../ui/badge";
import { Search, Filter, MoreHorizontal, Loader2, AlertCircle, Plus, Download } from "lucide-react";
import { useToast } from "../ui/use-toast";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger, DropdownMenuCheckboxItem } from "../ui/dropdown-menu";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "../ui/dialog";
import { Label } from "../ui/label";

interface Transaction {
    id: string;
    date: string;
    amount: number;
    description: string;
    merchant?: string;
    suggested_category: string;
    confidence: number;
    reasoning: string;
}

const TransactionsList = () => {
    const [transactions, setTransactions] = useState<Transaction[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchTerm, setSearchTerm] = useState("");
    const [confidenceFilter, setConfidenceFilter] = useState({ high: true, medium: true, low: true });
    const [isCreateOpen, setIsCreateOpen] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [newTx, setNewTx] = useState({
        description: '',
        merchant: '',
        amount: '',
        date: new Date().toISOString().split('T')[0]
    });

    // Edit state
    const [isEditOpen, setIsEditOpen] = useState(false);
    const [editingTx, setEditingTx] = useState<Transaction | null>(null);
    const [editForm, setEditForm] = useState({
        description: '',
        merchant: '',
        amount: '',
        date: ''
    });

    const { toast } = useToast();

    useEffect(() => {
        const fetchTransactions = async () => {
            try {
                const token = localStorage.getItem('auth_token');
                const response = await fetch('/api/accounting/all', {
                    headers: {
                        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
                    }
                });
                if (response.ok) {
                    const json = await response.json();
                    setTransactions(json.data.transactions || []);
                }
            } catch (error) {
                console.error("Failed to fetch transactions:", error);
            } finally {
                setLoading(false);
            }
        };
        fetchTransactions();

        // Listen for global transactions created in finance/index.tsx
        window.addEventListener('transactionCreated', fetchTransactions);
        return () => window.removeEventListener('transactionCreated', fetchTransactions);
    }, []);

    const handleExportCSV = () => {
        if (transactions.length === 0) {
            toast({ title: "Export Failed", description: "No transactions to export.", variant: "error" });
            return;
        }

        const headers = ['ID', 'Date', 'Description', 'Merchant', 'Amount', 'AI Category', 'Confidence', 'Reasoning'];
        const rows = transactions.map(tx => [
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
        link.setAttribute("download", `review_queue_${new Date().toISOString().split('T')[0]}.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        toast({ title: "Export Successful", description: "Transactions downloaded as CSV." });
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
                    id: `tx_man_${Date.now()}`,
                    date: new Date(newTx.date).toISOString(),
                    amount: parseFloat(newTx.amount),
                    description: newTx.description,
                    merchant: newTx.merchant || null,
                    source: "manual"
                })
            });

            if (!response.ok) throw new Error("Failed to create transaction");

            const data = await response.json();

            if (data.data) {
                setTransactions(prev => [{
                    id: data.data.id,
                    date: new Date(newTx.date).toISOString(),
                    amount: parseFloat(newTx.amount),
                    description: newTx.description,
                    merchant: newTx.merchant || undefined,
                    suggested_category: data.data.category,
                    confidence: data.data.confidence,
                    reasoning: data.data.reasoning
                }, ...prev]);
            }

            toast({ title: "Transaction Created", description: `Successfully ingested and categorized.` });
            setIsCreateOpen(false);
            setNewTx({ description: '', merchant: '', amount: '', date: new Date().toISOString().split('T')[0] });
        } catch (error) {
            toast({ title: "Error", description: "Failed to create transaction", variant: "error" });
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleEditClick = (tx: Transaction) => {
        setEditingTx(tx);
        setEditForm({
            description: tx.description,
            merchant: tx.merchant || '',
            amount: tx.amount.toString(),
            date: tx.date.split('T')[0]
        });
        setIsEditOpen(true);
    };

    const handleUpdateTransaction = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!editingTx) return;
        setIsSubmitting(true);

        try {
            const token = localStorage.getItem('auth_token');
            const response = await fetch(`/api/accounting/${editingTx.id}`, {
                method: 'PUT',
                headers: {
                    ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    date: new Date(editForm.date).toISOString(),
                    amount: parseFloat(editForm.amount),
                    description: editForm.description,
                    merchant: editForm.merchant || null
                })
            });

            if (!response.ok) throw new Error("Failed to update transaction");

            toast({ title: "Transaction Updated", description: "Successfully updated transaction details." });
            setIsEditOpen(false);
            setEditingTx(null);

            // Refresh list
            const fetchEvent = new Event('transactionCreated');
            window.dispatchEvent(fetchEvent);
        } catch (error) {
            toast({ title: "Error", description: "Failed to update transaction", variant: "error" });
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleDeleteTransaction = async (id: string) => {
        if (!confirm("Are you sure you want to delete this transaction?")) return;

        try {
            const token = localStorage.getItem('auth_token');
            const response = await fetch(`/api/accounting/${id}`, {
                method: 'DELETE',
                headers: {
                    ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
                }
            });

            if (!response.ok) throw new Error("Failed to delete transaction");

            setTransactions(prev => prev.filter(tx => tx.id !== id));
            toast({ title: "Transaction Deleted", description: "Successfully removed transaction." });
        } catch (error) {
            toast({ title: "Error", description: "Failed to delete transaction", variant: "error" });
        }
    };

    const filteredTransactions = transactions.filter(tx => {
        const matchesSearch = tx.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
            tx.merchant?.toLowerCase().includes(searchTerm.toLowerCase());

        let matchesConfidence = false;
        if (tx.confidence >= 90 && confidenceFilter.high) matchesConfidence = true;
        else if (tx.confidence >= 70 && tx.confidence < 90 && confidenceFilter.medium) matchesConfidence = true;
        else if (tx.confidence < 70 && confidenceFilter.low) matchesConfidence = true;

        return matchesSearch && matchesConfidence;
    });

    if (loading) {
        return (
            <div className="flex justify-center p-8">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    return (
        <Card>
            <CardHeader>
                <div className="flex justify-between items-start">
                    <div>
                        <CardTitle>All Transactions</CardTitle>
                        <CardDescription>
                            Your complete transaction history and ledger.
                        </CardDescription>
                    </div>
                    {transactions.filter(tx => (tx as any).status === 'review_required').length > 0 && (
                        <Badge variant="outline" className="ml-2 bg-amber-50 text-amber-700 border-amber-200">
                            {transactions.filter(tx => (tx as any).status === 'review_required').length} Pending Review
                        </Badge>
                    )}
                </div>
            </CardHeader>
            <CardContent>
                <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                        <div className="relative w-64">
                            <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                            <Input
                                placeholder="Search transactions..."
                                className="pl-8"
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                            />
                        </div>
                        <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                                <Button variant="outline" size="icon">
                                    <Filter className="h-4 w-4" />
                                </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end" className="w-56">
                                <DropdownMenuLabel>Filter by Confidence</DropdownMenuLabel>
                                <DropdownMenuSeparator />
                                <DropdownMenuCheckboxItem
                                    checked={confidenceFilter.high}
                                    onCheckedChange={(c) => setConfidenceFilter({ ...confidenceFilter, high: !!c })}
                                >
                                    High (&ge; 90%)
                                </DropdownMenuCheckboxItem>
                                <DropdownMenuCheckboxItem
                                    checked={confidenceFilter.medium}
                                    onCheckedChange={(c) => setConfidenceFilter({ ...confidenceFilter, medium: !!c })}
                                >
                                    Medium (70% - 89%)
                                </DropdownMenuCheckboxItem>
                                <DropdownMenuCheckboxItem
                                    checked={confidenceFilter.low}
                                    onCheckedChange={(c) => setConfidenceFilter({ ...confidenceFilter, low: !!c })}
                                >
                                    Low (&lt; 70%)
                                </DropdownMenuCheckboxItem>
                            </DropdownMenuContent>
                        </DropdownMenu>
                    </div>
                </div>

                <div className="rounded-md border">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Date</TableHead>
                                <TableHead>Description</TableHead>
                                <TableHead>AI Category</TableHead>
                                <TableHead>Confidence</TableHead>
                                <TableHead className="text-right">Amount</TableHead>
                                <TableHead></TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {filteredTransactions.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={6} className="text-center py-12 text-muted-foreground">
                                        <div className="flex flex-col items-center gap-2">
                                            <AlertCircle className="h-8 w-8 opacity-20" />
                                            <p>No transactions found.</p>
                                        </div>
                                    </TableCell>
                                </TableRow>
                            ) : (
                                filteredTransactions.map((trx) => (
                                    <TableRow key={trx.id}>
                                        <TableCell>{new Date(trx.date).toLocaleDateString()}</TableCell>
                                        <TableCell>
                                            <div className="font-medium">{trx.description}</div>
                                            {trx.merchant && <div className="text-xs text-muted-foreground">{trx.merchant}</div>}
                                        </TableCell>
                                        <TableCell>
                                            <Badge variant="secondary" className="font-normal">
                                                {trx.suggested_category}
                                            </Badge>
                                        </TableCell>
                                        <TableCell>
                                            <div className="flex items-center gap-2">
                                                <div className="w-16 h-1.5 bg-secondary rounded-full overflow-hidden">
                                                    <div
                                                        className={`h-full ${trx.confidence >= 90 ? 'bg-green-500' : trx.confidence >= 70 ? 'bg-amber-500' : 'bg-red-500'}`}
                                                        style={{ width: `${trx.confidence}%` }}
                                                    />
                                                </div>
                                                <span className="text-xs">{trx.confidence}%</span>
                                            </div>
                                        </TableCell>
                                        <TableCell className={`text-right font-medium ${trx.amount > 0 ? "text-green-500" : ""}`}>
                                            {trx.amount > 0 ? "+" : ""}{trx.amount.toFixed(2)}
                                        </TableCell>
                                        <TableCell>
                                            <DropdownMenu>
                                                <DropdownMenuTrigger asChild>
                                                    <Button variant="ghost" size="icon">
                                                        <MoreHorizontal className="h-4 w-4" />
                                                    </Button>
                                                </DropdownMenuTrigger>
                                                <DropdownMenuContent align="end">
                                                    <DropdownMenuItem onClick={() => handleEditClick(trx)}>
                                                        Edit Details
                                                    </DropdownMenuItem>
                                                    <DropdownMenuSeparator />
                                                    <DropdownMenuItem className="text-red-500 focus:text-red-500 focus:bg-red-500/10" onClick={() => handleDeleteTransaction(trx.id)}>
                                                        Delete
                                                    </DropdownMenuItem>
                                                </DropdownMenuContent>
                                            </DropdownMenu>
                                        </TableCell>
                                    </TableRow>
                                ))
                            )}
                        </TableBody>
                    </Table>
                </div>
            </CardContent>

            {/* Edit Dialog */}
            <Dialog open={isEditOpen} onOpenChange={setIsEditOpen}>
                <DialogContent className="sm:max-w-[425px]">
                    <DialogHeader>
                        <DialogTitle>Edit Transaction</DialogTitle>
                        <DialogDescription>
                            Update the details of this transaction.
                        </DialogDescription>
                    </DialogHeader>
                    {editingTx && (
                        <form onSubmit={handleUpdateTransaction} className="space-y-4 pt-4">
                            <div className="space-y-2">
                                <Label htmlFor="edit-desc">Description</Label>
                                <Input
                                    id="edit-desc"
                                    value={editForm.description}
                                    onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                                    required
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="edit-merchant">Merchant (Optional)</Label>
                                <Input
                                    id="edit-merchant"
                                    value={editForm.merchant}
                                    onChange={(e) => setEditForm({ ...editForm, merchant: e.target.value })}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="edit-amount">Amount ($)</Label>
                                <Input
                                    id="edit-amount"
                                    type="number"
                                    step="0.01"
                                    value={editForm.amount}
                                    onChange={(e) => setEditForm({ ...editForm, amount: e.target.value })}
                                    required
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="edit-date">Date</Label>
                                <Input
                                    id="edit-date"
                                    type="date"
                                    value={editForm.date}
                                    onChange={(e) => setEditForm({ ...editForm, date: e.target.value })}
                                    required
                                />
                            </div>
                            <DialogFooter className="pt-4">
                                <Button type="submit" disabled={isSubmitting}>
                                    {isSubmitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                                    Save Changes
                                </Button>
                            </DialogFooter>
                        </form>
                    )}
                </DialogContent>
            </Dialog>
        </Card>
    );
};

export default TransactionsList;

