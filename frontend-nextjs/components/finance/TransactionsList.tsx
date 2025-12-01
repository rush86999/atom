import React from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../ui/card";
import { Input } from "../ui/input";
import { Button } from "../ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../ui/table";
import { Badge } from "../ui/badge";
import { Search, Filter, MoreHorizontal } from "lucide-react";

const TransactionsList = () => {
    const transactions = [
        { id: "TRX-9871", date: "2025-11-29", description: "Stripe Payout", category: "Income", amount: 2400.00, status: "Completed" },
        { id: "TRX-9872", date: "2025-11-28", description: "AWS Web Services", category: "Infrastructure", amount: -142.00, status: "Completed" },
        { id: "TRX-9873", date: "2025-11-28", description: "Client Invoice #402", category: "Income", amount: 850.00, status: "Completed" },
        { id: "TRX-9874", date: "2025-11-27", description: "Adobe Creative Cloud", category: "Software", amount: -54.99, status: "Pending" },
        { id: "TRX-9875", date: "2025-11-26", description: "WeWork Office Space", category: "Rent", amount: -450.00, status: "Completed" },
        { id: "TRX-9876", date: "2025-11-25", description: "Starbucks Coffee", category: "Meals", amount: -12.50, status: "Completed" },
        { id: "TRX-9877", date: "2025-11-24", description: "Apple Developer Program", category: "Software", amount: -99.00, status: "Completed" },
    ];

    return (
        <Card>
            <CardHeader>
                <CardTitle>Transactions</CardTitle>
                <CardDescription>
                    A list of your recent transactions.
                </CardDescription>
            </CardHeader>
            <CardContent>
                <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                        <div className="relative w-64">
                            <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                            <Input placeholder="Search transactions..." className="pl-8" />
                        </div>
                        <Button variant="outline" size="icon">
                            <Filter className="h-4 w-4" />
                        </Button>
                    </div>
                </div>

                <div className="rounded-md border">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Date</TableHead>
                                <TableHead>Description</TableHead>
                                <TableHead>Category</TableHead>
                                <TableHead>Status</TableHead>
                                <TableHead className="text-right">Amount</TableHead>
                                <TableHead></TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {transactions.map((trx) => (
                                <TableRow key={trx.id}>
                                    <TableCell>{trx.date}</TableCell>
                                    <TableCell className="font-medium">{trx.description}</TableCell>
                                    <TableCell>
                                        <Badge variant="secondary" className="font-normal">
                                            {trx.category}
                                        </Badge>
                                    </TableCell>
                                    <TableCell>
                                        <Badge variant={trx.status === "Completed" ? "default" : "outline"}>
                                            {trx.status}
                                        </Badge>
                                    </TableCell>
                                    <TableCell className={`text-right font-medium ${trx.amount > 0 ? "text-green-500" : ""}`}>
                                        {trx.amount > 0 ? "+" : ""}{trx.amount.toFixed(2)}
                                    </TableCell>
                                    <TableCell>
                                        <Button variant="ghost" size="icon">
                                            <MoreHorizontal className="h-4 w-4" />
                                        </Button>
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

export default TransactionsList;
