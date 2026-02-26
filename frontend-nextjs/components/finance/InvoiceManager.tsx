import React, { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Download, Send, Plus, Loader2, MoreHorizontal } from "lucide-react";
import { toast } from "@/components/ui/use-toast";

interface Invoice {
    id: string;
    customer?: string;
    vendor?: string;
    amount: number;
    status: string;
    type: 'AR' | 'AP';
}

const InvoiceManager = () => {
    const [invoices, setInvoices] = useState<Invoice[]>([]);
    const [loading, setLoading] = useState(true);

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

    const handleDownload = async (invoiceId: string, type: 'AR' | 'AP') => {
        try {
            const lowerType = type.toLowerCase();
            const response = await fetch(`/api/accounting/invoices?action=download&type=${lowerType}&invoice_id=${invoiceId}`);

            if (!response.ok) throw new Error("Download failed");

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `invoice_${invoiceId}.txt`;
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
                <Button className="glass-button" onClick={() => toast({ title: "New Invoice", description: "Invoice creation is coming soon." })}>
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
                                                    <Button variant="ghost" size="icon" title="Send" onClick={() => toast({ title: "Send Invoice", description: "Invoice dispatch is coming soon." })}>
                                                        <Send className="h-4 w-4" />
                                                    </Button>
                                                )}
                                                <Button variant="ghost" size="icon" onClick={() => toast({ title: "Options", description: "Invoice options coming soon." })}>
                                                    <MoreHorizontal className="h-4 w-4" />
                                                </Button>
                                            </div>
                                        </TableCell>
                                    </TableRow>
                                ))
                            )}
                        </TableBody>
                    </Table>
                </div>
            </CardContent>
        </Card>
    );
};

export default InvoiceManager;
