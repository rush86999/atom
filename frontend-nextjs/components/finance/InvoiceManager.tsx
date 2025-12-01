import React from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../ui/card";
import { Button } from "../ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../ui/table";
import { Badge } from "../ui/badge";
import { Plus, Download, Send, MoreHorizontal } from "lucide-react";

const InvoiceManager = () => {
    const invoices = [
        { id: "INV-2025-001", client: "Acme Corp", date: "2025-11-25", due: "2025-12-25", amount: 4500.00, status: "Sent" },
        { id: "INV-2025-002", client: "Globex Inc", date: "2025-11-20", due: "2025-12-20", amount: 2100.00, status: "Paid" },
        { id: "INV-2025-003", client: "Soylent Corp", date: "2025-11-15", due: "2025-12-15", amount: 1250.00, status: "Overdue" },
        { id: "INV-2025-004", client: "Initech", date: "2025-11-28", due: "2025-12-28", amount: 3200.00, status: "Draft" },
    ];

    return (
        <Card>
            <CardHeader className="flex flex-row items-center justify-between">
                <div>
                    <CardTitle>Invoices</CardTitle>
                    <CardDescription>Manage your client invoices and payments.</CardDescription>
                </div>
                <Button>
                    <Plus className="mr-2 h-4 w-4" /> Create Invoice
                </Button>
            </CardHeader>
            <CardContent>
                <div className="rounded-md border">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Invoice ID</TableHead>
                                <TableHead>Client</TableHead>
                                <TableHead>Issue Date</TableHead>
                                <TableHead>Due Date</TableHead>
                                <TableHead>Status</TableHead>
                                <TableHead className="text-right">Amount</TableHead>
                                <TableHead className="text-right">Actions</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {invoices.map((inv) => (
                                <TableRow key={inv.id}>
                                    <TableCell className="font-medium">{inv.id}</TableCell>
                                    <TableCell>{inv.client}</TableCell>
                                    <TableCell>{inv.date}</TableCell>
                                    <TableCell>{inv.due}</TableCell>
                                    <TableCell>
                                        <Badge variant={
                                            inv.status === "Paid" ? "default" :
                                                inv.status === "Overdue" ? "destructive" :
                                                    inv.status === "Sent" ? "secondary" : "outline"
                                        }>
                                            {inv.status}
                                        </Badge>
                                    </TableCell>
                                    <TableCell className="text-right font-medium">${inv.amount.toFixed(2)}</TableCell>
                                    <TableCell className="text-right">
                                        <div className="flex justify-end gap-2">
                                            <Button variant="ghost" size="icon" title="Download PDF">
                                                <Download className="h-4 w-4" />
                                            </Button>
                                            <Button variant="ghost" size="icon" title="Send Reminder">
                                                <Send className="h-4 w-4" />
                                            </Button>
                                            <Button variant="ghost" size="icon">
                                                <MoreHorizontal className="h-4 w-4" />
                                            </Button>
                                        </div>
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </div>
            </CardContent>
        </Card>
    );
};

export default InvoiceManager;
