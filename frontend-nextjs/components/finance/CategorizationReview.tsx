import React, { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { Button } from "../ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../ui/table";
import { Badge } from "../ui/badge";
import { Check, X, BrainCircuit, Info } from "lucide-react";
import { useToast } from "../ui/use-toast";

const CategorizationReview = () => {
    const [proposals, setProposals] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const { toast } = useToast();
    const workspaceId = "default-workspace";

    useEffect(() => {
        fetchProposals();
    }, []);

    const fetchProposals = async () => {
        try {
            const response = await fetch(`/api/v1/accounting/proposals?workspace_id=${workspaceId}`);
            const data = await response.json();
            setProposals(data);
            setLoading(false);
        } catch (error) {
            console.error("Failed to fetch proposals:", error);
            setLoading(false);
        }
    };

    const approveProposal = async (proposalId: string) => {
        try {
            const response = await fetch(`/api/v1/accounting/proposals/${proposalId}/approve`, {
                method: 'POST'
            });
            if (response.ok) {
                setProposals(proposals.filter(p => p.id !== proposalId));
                toast({
                    title: "Categorization Applied",
                    description: "Transaction has been posted to the ledger and a new rule has been learned.",
                });
            }
        } catch (error) {
            toast({ title: "Update Failed", variant: "error" });
        }
    };

    if (proposals.length === 0 && !loading) {
        return (
            <Card className="flex flex-col items-center justify-center py-12">
                <BrainCircuit className="h-12 w-12 text-muted-foreground/50 mb-4" />
                <p className="text-muted-foreground">All transactions are categorized. AI is learning well!</p>
            </Card>
        );
    }

    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    <BrainCircuit className="h-5 w-5" />
                    Pending AI Categorizations
                </CardTitle>
                <CardDescription>
                    Review and approve transactions where AI confidence is below the automatic threshold.
                </CardDescription>
            </CardHeader>
            <CardContent>
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead>Transaction</TableHead>
                            <TableHead>Suggested Account</TableHead>
                            <TableHead>Confidence</TableHead>
                            <TableHead>Reasoning</TableHead>
                            <TableHead className="text-right">Action</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {proposals.map(prop => (
                            <TableRow key={prop.id}>
                                <TableCell>
                                    <div className="font-medium">{prop.transaction.description}</div>
                                    <div className="text-xs text-muted-foreground">
                                        {new Date(prop.transaction.transaction_date).toLocaleDateString()}
                                    </div>
                                </TableCell>
                                <TableCell>
                                    <Badge variant="secondary">{prop.suggested_account_id}</Badge>
                                </TableCell>
                                <TableCell>
                                    <div className="flex items-center gap-2">
                                        <div className="w-16 h-2 bg-secondary rounded-full overflow-hidden">
                                            <div
                                                className={`h-full ${prop.confidence > 0.7 ? 'bg-green-500' : 'bg-amber-500'}`}
                                                style={{ width: `${prop.confidence * 100}%` }}
                                            />
                                        </div>
                                        <span className="text-xs font-mono">{(prop.confidence * 100).toFixed(0)}%</span>
                                    </div>
                                </TableCell>
                                <TableCell>
                                    <div className="text-xs italic text-muted-foreground max-w-[200px] truncate" title={prop.reasoning}>
                                        "{prop.reasoning}"
                                    </div>
                                </TableCell>
                                <TableCell className="text-right">
                                    <div className="flex justify-end gap-2">
                                        <Button size="sm" variant="ghost" className="h-8 w-8 p-0">
                                            <X className="h-4 w-4 text-red-500" />
                                        </Button>
                                        <Button size="sm" onClick={() => approveProposal(prop.id)} className="h-8 gap-1">
                                            <Check className="h-4 w-4" /> Approve
                                        </Button>
                                    </div>
                                </TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </CardContent>
        </Card>
    );
};

export default CategorizationReview;
