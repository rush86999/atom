import React, { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../ui/card";
import { Input } from "../ui/input";
import { Button } from "../ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../ui/table";
import { Badge } from "../ui/badge";
import { Search, Filter, MoreHorizontal, Loader2, AlertCircle } from "lucide-react";
import { useToast } from "../ui/use-toast";

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
    const { toast } = useToast();

    useEffect(() => {
        const fetchTransactions = async () => {
            try {
                const token = localStorage.getItem('auth_token');
                const response = await fetch('/api/accounting/transactions', {
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
    }, []);

    const filteredTransactions = transactions.filter(tx =>
        tx.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
        tx.merchant?.toLowerCase().includes(searchTerm.toLowerCase())
    );

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
                        <CardTitle>Transactions Review Queue</CardTitle>
                        <CardDescription>
                            AI suggested categorizations pending your review.
                        </CardDescription>
                    </div>
                    {transactions.length > 0 && (
                        <Badge variant="outline" className="ml-2 bg-amber-50 text-amber-700 border-amber-200">
                            {transactions.length} Pending
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
                        <Button variant="outline" size="icon" onClick={() => toast({ title: "Filter", description: "Advanced filtering coming soon." })}>
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
                                            <p>No transactions found in review queue.</p>
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
                                            <Button variant="ghost" size="icon" onClick={() => toast({ title: "Options", description: "Transaction options coming soon." })}>
                                                <MoreHorizontal className="h-4 w-4" />
                                            </Button>
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

export default TransactionsList;

