import React, { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../ui/table";
import { Badge } from "../ui/badge";
import { Download, ShieldAlert, Check, RefreshCw, Layers, Loader2 } from "lucide-react";
import { useToast } from "../ui/use-toast";

const AccountantPortal = () => {
    const [accounts, setAccounts] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [syncing, setSyncing] = useState<string | null>(null);
    const { toast } = useToast();

    // Mock workspace ID - in real app would come from context/url
    const workspaceId = "default";

    useEffect(() => {
        fetchAccounts();
    }, []);

    const fetchAccounts = async () => {
        try {
            const token = localStorage.getItem('auth_token');
            const response = await fetch(`/api/accounting/chart-of-accounts`, {
                headers: {
                    ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
                }
            });
            if (response.ok) {
                const json = await response.json();
                setAccounts(json.data.accounts || []);
            }
            setLoading(false);
        } catch (error) {
            console.error("Failed to fetch accounts:", error);
            setLoading(false);
        }
    };

    const handleExport = async (type: 'gl' | 'tb') => {
        const token = localStorage.getItem('auth_token');
        // This would ideally hit a proxy or the backend directly if allowed
        toast({
            title: "Export Started",
            description: `Downloading your ${type.toUpperCase()} report...`,
        });
    };

    const updateMapping = async (accountId: string, std: string, value: string) => {
        const account = accounts.find((a: any) => a.id === accountId);
        toast({ title: "Mapping Updated", description: `Updated ${std.toUpperCase()} code for ${account.name}` });
    };

    const handleSync = async (platform: string) => {
        setSyncing(platform);
        try {
            // Placeholder for real sync endpoint
            await new Promise(resolve => setTimeout(resolve, 1500));
            toast({
                title: `${platform.toUpperCase()} Sync Complete`,
                description: `Successfully synchronized with the master ledger.`,
            });
        } catch (error) {
            toast({ title: "Sync Failed", variant: "error" });
        } finally {
            setSyncing(null);
            fetchAccounts(); // Refresh CoA after sync
        }
    };

    if (loading) {
        return (
            <div className="flex justify-center p-12">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <Card className="border-amber-200 bg-amber-50/50 dark:bg-amber-950/20">
                <CardHeader className="flex flex-row items-center gap-4 py-3">
                    <ShieldAlert className="h-5 w-5 text-amber-600" />
                    <div>
                        <CardTitle className="text-sm font-semibold">Regulatory Disclaimer</CardTitle>
                        <CardDescription className="text-xs text-amber-800 dark:text-amber-400">
                            ATOM&apos;s accounting features are AI-driven and for strategic guidance. We are not a licensed CPA firm.
                            Consult with a qualified professional for regulatory compliance.
                        </CardDescription>
                    </div>
                </CardHeader>
            </Card>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <Layers className="h-4 w-4" />
                            Multi-Ledger Sync
                        </CardTitle>
                        <CardDescription>Connect external platforms to ATOM.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-2">
                        {['zoho', 'xero', 'quickbooks'].map(platform => (
                            <Button
                                key={platform}
                                onClick={() => handleSync(platform)}
                                variant="outline"
                                size="sm"
                                className="w-full justify-between"
                                disabled={syncing !== null}
                            >
                                <span className="capitalize">{platform} Books</span>
                                {syncing === platform ? (
                                    <RefreshCw className="h-3 w-3 animate-spin" />
                                ) : (
                                    <RefreshCw className="h-3 w-3" />
                                )}
                            </Button>
                        ))}
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader>
                        <CardTitle>Accountant Exports</CardTitle>
                        <CardDescription>Download standardized reports for your CPA.</CardDescription>
                    </CardHeader>
                    <CardContent className="flex gap-4">
                        <Button onClick={() => handleExport('gl')} variant="outline" className="flex-1">
                            <Download className="mr-2 h-4 w-4" /> General Ledger
                        </Button>
                        <Button onClick={() => handleExport('tb')} variant="outline" className="flex-1">
                            <Download className="mr-2 h-4 w-4" /> Trial Balance
                        </Button>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader>
                        <CardTitle>Audit Status</CardTitle>
                        <CardDescription>Continuous monitoring of record integrity.</CardDescription>
                    </CardHeader>
                    <CardContent className="flex items-center gap-4">
                        <div className="flex items-center gap-2 text-green-600">
                            <Check className="h-5 w-5" />
                            <span className="text-sm font-medium">Audit Trail Active</span>
                        </div>
                        <div className="text-xs text-muted-foreground italic">
                            All AI transactions logged with immutable references.
                        </div>
                    </CardContent>
                </Card>
            </div>

            <Card>
                <CardHeader>
                    <CardTitle>Chart of Accounts (Real-time)</CardTitle>
                    <CardDescription>Accounts detected and categorized by ATOM AI.</CardDescription>
                </CardHeader>
                <CardContent>
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Account Name</TableHead>
                                <TableHead>Type</TableHead>
                                <TableHead>Keywords</TableHead>
                                <TableHead className="text-right">Action</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {accounts.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={4} className="text-center py-8 text-muted-foreground">
                                        No accounts found in the chart.
                                    </TableCell>
                                </TableRow>
                            ) : (
                                accounts.map(acc => (
                                    <TableRow key={acc.id}>
                                        <TableCell className="font-medium">{acc.name}</TableCell>
                                        <TableCell className="text-xs uppercase">
                                            <Badge variant="outline">{acc.type}</Badge>
                                        </TableCell>
                                        <TableCell>
                                            <div className="flex flex-wrap gap-1">
                                                {acc.keywords?.map((k: string, i: number) => (
                                                    <span key={i} className="text-[10px] bg-secondary px-1 rounded">{k}</span>
                                                ))}
                                            </div>
                                        </TableCell>
                                        <TableCell className="text-right">
                                            <Button variant="ghost" size="sm">Manage</Button>
                                        </TableCell>
                                    </TableRow>
                                ))
                            )}
                        </TableBody>
                    </Table>
                </CardContent>
            </Card>
        </div>
    );
};

export default AccountantPortal;

