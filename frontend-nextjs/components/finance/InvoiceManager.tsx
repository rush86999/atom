import React, { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Download, Send, Plus, Loader2, MoreHorizontal, Edit, Trash, CheckCircle } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, DropdownMenuSeparator } from "@/components/ui/dropdown-menu";

interface Invoice {
    id: string;
    customer?: string;
    vendor?: string;
    amount: number;
    status: string;
    type: 'AR' | 'AP';
}

const InvoiceManager = () => {
    const { toast } = useToast();
    const [invoices, setInvoices] = useState<Invoice[]>([]);
    const [loading, setLoading] = useState(true);
    const [isCreateOpen, setIsCreateOpen] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [newInvoice, setNewInvoice] = useState({
        customer: '',
        amount: '',
        due_date: ''
    });

    // Edit state
    const [isEditOpen, setIsEditOpen] = useState(false);
    const [editingInvoice, setEditingInvoice] = useState<Invoice | null>(null);
    const [editForm, setEditForm] = useState({
        customer: '',
        amount: '',
        due_date: ''
    });

    useEffect(() => {
        const fetchInvoices = async () => {
            try {
                const response = await fetch('/api/accounting/invoices');
                if (response.ok) {
                    const data = await response.json();
                    const mappedInvoices = (data.data?.invoices || []).map((inv: any) => ({
                        ...inv,
                        type: inv.customer ? 'AR' : 'AP'
                    }));
                    setInvoices(mappedInvoices);
                }
            } catch (error) {
                console.error("Failed to fetch invoices:", error);
            } finally {
                setLoading(false);
            }
        };

        fetchInvoices();
    }, []);

    const handleCreateInvoice = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsSubmitting(true);
        try {
            const response = await fetch('/api/accounting/invoices?action=generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    customer: newInvoice.customer,
                    amount: parseFloat(newInvoice.amount),
                    due_date: newInvoice.due_date,
                    source: "manual"
                })
            });

            if (!response.ok) throw new Error("Failed to create invoice");

            const data = await response.json();

            // Add new invoice to state
            setInvoices(prev => [{
                id: data.data.id,
                customer: data.data.customer,
                amount: data.data.amount,
                status: 'pending',
                type: 'AR'
            }, ...prev]);

            toast({ title: "Invoice Created", description: `Successfully created invoice for ${newInvoice.customer}` });
            setIsCreateOpen(false);
            setNewInvoice({ customer: '', amount: '', due_date: '' });
        } catch (error) {
            toast({ title: "Error", description: "Failed to create invoice", variant: "error" });
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleSendInvoice = async (invoiceId: string) => {
        try {
            const response = await fetch(`/api/accounting/invoices?action=send&invoice_id=${invoiceId}`, {
                method: 'POST'
            });

            if (!response.ok) throw new Error("Failed to send invoice");

            setInvoices(prev => prev.map(inv =>
                inv.id === invoiceId ? { ...inv, status: 'sent' } : inv
            ));

            toast({ title: "Invoice Sent", description: "The invoice has been dispatched to the customer." });
        } catch (error) {
            toast({ title: "Error", description: "Failed to send invoice", variant: "error" });
        }
    };

    const handleDownload = async (invoiceId: string, type: 'AR' | 'AP') => {
        try {
            const lowerType = type.toLowerCase();
            const response = await fetch(`/api/accounting/invoices?action=download&type=${lowerType}&invoice_id=${invoiceId}`);

            if (!response.ok) throw new Error("Download failed");

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `invoice_${invoiceId}.pdf`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);

            toast({
                title: "Success",
                description: "Invoice downloaded successfully",
            });
        } catch (error) {
            toast({
                title: "Error",
                description: "Failed to download invoice",
                variant: "error",
            });
        }
    };

    const handleMarkAsPaid = async (invoiceId: string) => {
        try {
            // Placeholder: hitting a real endpoint would look like
            // await fetch(`/api/accounting/invoices/${invoiceId}`, { method: 'PUT', body: JSON.stringify({ status: 'paid' }) })
            setInvoices(prev => prev.map(inv =>
                inv.id === invoiceId ? { ...inv, status: 'paid' } : inv
            ));
            toast({ title: "Invoice Updated", description: "Marked as Paid." });
        } catch (error) {
            toast({ title: "Error", description: "Failed to update invoice", variant: "error" });
        }
    };

    const handleDelete = async (invoiceId: string) => {
        if (!confirm("Are you sure you want to delete this invoice?")) return;
        try {
            // Placeholder for real endpoint deletion
            setInvoices(prev => prev.filter(inv => inv.id !== invoiceId));
            toast({ title: "Invoice Deleted", description: "Invoice removed successfully." });
        } catch (error) {
            toast({ title: "Error", description: "Failed to delete invoice", variant: "error" });
        }
    };

    const handleEditClick = (invoice: Invoice) => {
        setEditingInvoice(invoice);
        setEditForm({
            customer: invoice.customer || invoice.vendor || '',
            amount: invoice.amount.toString(),
            due_date: new Date().toISOString().split('T')[0] // We don't have due_date in the interface right now
        });
        setIsEditOpen(true);
    };

    const handleUpdateInvoice = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!editingInvoice) return;
        setIsSubmitting(true);
        try {
            // Placeholder for real endpoint update
            setInvoices(prev => prev.map(inv =>
                inv.id === editingInvoice.id ? {
                    ...inv,
                    customer: editingInvoice.type === 'AR' ? editForm.customer : undefined,
                    vendor: editingInvoice.type === 'AP' ? editForm.customer : undefined,
                    amount: parseFloat(editForm.amount)
                } : inv
            ));
            toast({ title: "Invoice Updated", description: "Successfully updated invoice details." });
            setIsEditOpen(false);
            setEditingInvoice(null);
        } catch (error) {
            toast({ title: "Error", description: "Failed to update invoice", variant: "error" });
        } finally {
            setIsSubmitting(false);
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center p-8">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
        );
    }

    return (
        <Card className="glass-morphism h-full">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
                <div>
                    <CardTitle className="gradient-text text-xl">Invoice Manager</CardTitle>
                    <CardDescription className="text-white/60">Manage your client invoices and payments.</CardDescription>
                </div>
                <Button className="glass-button" onClick={() => setIsCreateOpen(true)}>
                    <Plus className="h-4 w-4 mr-2" />
                    New Invoice
                </Button>
            </CardHeader>
            <CardContent>
                <div className="rounded-md border border-white/10 overflow-hidden">
                    <Table>
                        <TableHeader className="bg-white/5">
                            <TableRow>
                                <TableHead>Invoice #</TableHead>
                                <TableHead>Entity</TableHead>
                                <TableHead>Amount</TableHead>
                                <TableHead>Status</TableHead>
                                <TableHead className="text-right">Actions</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {invoices.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={5} className="text-center py-8 text-white/40">
                                        No invoices found.
                                    </TableCell>
                                </TableRow>
                            ) : (
                                invoices.map((invoice) => (
                                    <TableRow key={invoice.id} className="hover:bg-white/5 transition-colors">
                                        <TableCell className="font-mono text-xs">{invoice.id}</TableCell>
                                        <TableCell>{invoice.customer || invoice.vendor}</TableCell>
                                        <TableCell>
                                            {new Intl.NumberFormat('en-US', {
                                                style: 'currency',
                                                currency: 'USD'
                                            }).format(invoice.amount)}
                                        </TableCell>
                                        <TableCell>
                                            <Badge variant="outline" className="border-white/20 capitalize">
                                                {invoice.status}
                                            </Badge>
                                        </TableCell>
                                        <TableCell className="text-right">
                                            <div className="flex justify-end gap-2">
                                                <Button
                                                    variant="ghost"
                                                    size="icon"
                                                    title="Download"
                                                    onClick={() => handleDownload(invoice.id, invoice.type)}
                                                >
                                                    <Download className="h-4 w-4" />
                                                </Button>
                                                {invoice.type === 'AR' && (
                                                    <Button variant="ghost" size="icon" title="Send" onClick={() => handleSendInvoice(invoice.id)}>
                                                        <Send className="h-4 w-4" />
                                                    </Button>
                                                )}

                                                <DropdownMenu>
                                                    <DropdownMenuTrigger asChild>
                                                        <Button variant="ghost" size="icon">
                                                            <MoreHorizontal className="h-4 w-4" />
                                                        </Button>
                                                    </DropdownMenuTrigger>
                                                    <DropdownMenuContent align="end">
                                                        <DropdownMenuItem onClick={() => handleMarkAsPaid(invoice.id)}>
                                                            <CheckCircle className="h-4 w-4 mr-2 text-green-500" />
                                                            Mark as Paid
                                                        </DropdownMenuItem>
                                                        <DropdownMenuItem onClick={() => handleEditClick(invoice)}>
                                                            <Edit className="h-4 w-4 mr-2" />
                                                            Edit Details
                                                        </DropdownMenuItem>
                                                        <DropdownMenuSeparator />
                                                        <DropdownMenuItem className="text-red-500 focus:text-red-500 focus:bg-red-500/10" onClick={() => handleDelete(invoice.id)}>
                                                            <Trash className="h-4 w-4 mr-2" />
                                                            Delete Invoice
                                                        </DropdownMenuItem>
                                                    </DropdownMenuContent>
                                                </DropdownMenu>
                                            </div>
                                        </TableCell>
                                    </TableRow>
                                ))
                            )}
                        </TableBody>
                    </Table>
                </div>
            </CardContent>

            {/* Edit Invoice Dialog */}
            <Dialog open={isEditOpen} onOpenChange={setIsEditOpen}>
                <DialogContent className="sm:max-w-[425px]">
                    <DialogHeader>
                        <DialogTitle>Edit Invoice</DialogTitle>
                        <DialogDescription>
                            Update the details of this invoice.
                        </DialogDescription>
                    </DialogHeader>
                    {editingInvoice && (
                        <form onSubmit={handleUpdateInvoice} className="space-y-4 pt-4">
                            <div className="space-y-2">
                                <Label htmlFor="edit-customer">{editingInvoice.type === 'AR' ? 'Customer Name' : 'Vendor Name'}</Label>
                                <Input
                                    id="edit-customer"
                                    value={editForm.customer}
                                    onChange={(e) => setEditForm({ ...editForm, customer: e.target.value })}
                                    required
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
                                <Label htmlFor="edit-dueDate">Due Date</Label>
                                <Input
                                    id="edit-dueDate"
                                    type="date"
                                    value={editForm.due_date}
                                    onChange={(e) => setEditForm({ ...editForm, due_date: e.target.value })}
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

            {/* Create Invoice Dialog */}
            <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
                <DialogContent className="sm:max-w-[425px]">
                    <DialogHeader>
                        <DialogTitle>Create New Invoice</DialogTitle>
                        <DialogDescription>
                            Enter the details to generate an accounts receivable invoice.
                        </DialogDescription>
                    </DialogHeader>
                    <form onSubmit={handleCreateInvoice} className="space-y-4 pt-4">
                        <div className="space-y-2">
                            <Label htmlFor="customer">Customer Name</Label>
                            <Input
                                id="customer"
                                value={newInvoice.customer}
                                onChange={(e) => setNewInvoice({ ...newInvoice, customer: e.target.value })}
                                placeholder="Acme Corp"
                                required
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="amount">Amount ($)</Label>
                            <Input
                                id="amount"
                                type="number"
                                step="0.01"
                                value={newInvoice.amount}
                                onChange={(e) => setNewInvoice({ ...newInvoice, amount: e.target.value })}
                                placeholder="1500.00"
                                required
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="dueDate">Due Date</Label>
                            <Input
                                id="dueDate"
                                type="date"
                                value={newInvoice.due_date}
                                onChange={(e) => setNewInvoice({ ...newInvoice, due_date: e.target.value })}
                                required
                            />
                        </div>
                        <DialogFooter className="pt-4">
                            <Button type="submit" disabled={isSubmitting}>
                                {isSubmitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                                Generate Invoice
                            </Button>
                        </DialogFooter>
                    </form>
                </DialogContent>
            </Dialog>
        </Card>
    );
};

export default InvoiceManager;
