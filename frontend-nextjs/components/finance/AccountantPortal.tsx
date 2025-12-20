import React, { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../ui/table";
import { Download, ShieldAlert, Check, RefreshCw, Layers } from "lucide-react";
import { useToast } from "../ui/use-toast";

const AccountantPortal = () => {
    const [accounts, setAccounts] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [syncing, setSyncing] = useState<string | null>(null);
    const toast = useToast();

    // Mock workspace ID - in real app would come from context/url
    const workspaceId = "default-workspace";

    useEffect(() => {
        fetchAccounts();
    }, []);

    const fetchAccounts = async () => {
        try {
            const response = await fetch(`/api/v1/accounting/accounts?workspace_id=${workspaceId}`);
            const data = await response.json();
            setAccounts(data);
            setLoading(false);
        } catch (error) {
            console.error("Failed to fetch accounts:", error);
            setLoading(false);
        }
    };

    const handleExport = async (type: 'gl' | 'tb') => {
        const endpoint = type === 'gl' ? 'gl' : 'trial-balance';
        window.open(`/api/v1/accounting/export/${endpoint}?workspace_id=${workspaceId}`, '_blank');
        toast({
            title: "Export Started",
            description: `Downloading your ${type.toUpperCase()} report...`,
        });
    };

    const updateMapping = async (accountId: string, std: string, value: string) => {
        const account = accounts.find((a: any) => a.id === accountId);
        const newMapping = { ...(account.standards_mapping || {}), [std]: value };

        try {
            const response = await fetch(`/api/v1/accounting/accounts/${accountId}/mapping`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(newMapping)
            });

            if (response.ok) {
                setAccounts(accounts.map(a => a.id === accountId ? { ...a, standards_mapping: newMapping } : a));
                toast({ title: "Mapping Updated", description: `Updated ${std.toUpperCase()} code for ${account.name}` });
            }
        } catch (error) {
            toast({ title: "Update Failed", variant: "error" });
        }
    };

    const handleSync = async (platform: string) => {
        setSyncing(platform);
        try {
            const response = await fetch(`/api/v1/accounting/sync?workspace_id=${workspaceId}&platform=${platform}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    access_token: "MOCK_TOKEN",
                    organization_id: "MOCK_ORG",
                    tenant_id: "MOCK_TENANT",
                    realm_id: "MOCK_REALM"
                })
            });
            const data = await response.json();
            toast({
                title: `${platform.toUpperCase()} Sync Complete`,
                description: `Ingested ${data.ingested} new transactions into the master ledger.`,
            });
        } catch (error) {
            toast({ title: "Sync Failed", variant: "error" });
        } finally {
            setSyncing(null);
            fetchAccounts(); // Refresh CoA after sync
        }
    };

    return (
        <div className="space-y-6">
            <Card className="border-amber-200 bg-amber-50/50 dark:bg-amber-950/20">
                <CardHeader className="flex flex-row items-center gap-4 py-3">
                    <ShieldAlert className="h-5 w-5 text-amber-600" />
                    <div>
                        <CardTitle className="text-sm font-semibold">Regulatory Disclaimer</CardTitle>
                        <CardDescription className="text-xs text-amber-800 dark:text-amber-400">
                            ATOM's accounting features are AI-driven and for strategic guidance. We are not a licensed CPA firm.
                            Download your reports below for review by your qualified professional.
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
                            <Download className="mr-2 h-4 w-4" /> General Ledger (CSV)
                        </Button>
                        <Button onClick={() => handleExport('tb')} variant="outline" className="flex-1">
                            <Download className="mr-2 h-4 w-4" /> Trial Balance (JSON)
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
                    <CardTitle>Compliance Mapping (GAAP / IFRS)</CardTitle>
                    <CardDescription>Map your accounts to professional reporting standards.</CardDescription>
                </CardHeader>
                <CardContent>
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Account Name</TableHead>
                                <TableHead>Type</TableHead>
                                <TableHead>GAAP Code</TableHead>
                                <TableHead>IFRS Code</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {accounts.map(acc => (
                                <TableRow key={acc.id}>
                                    <TableCell className="font-medium">{acc.name}</TableCell>
                                    <TableCell className="text-xs uppercase">{acc.type}</TableCell>
                                    <TableCell>
                                        <Input
                                            placeholder="e.g. 1001"
                                            className="h-8 max-w-[100px]"
                                            defaultValue={acc.standards_mapping?.gaap}
                                            onBlur={(e) => updateMapping(acc.id, 'gaap', e.target.value)}
                                        />
                                    </TableCell>
                                    <TableCell>
                                        <Input
                                            placeholder="e.g. CASH"
                                            className="h-8 max-w-[100px]"
                                            defaultValue={acc.standards_mapping?.ifrs}
                                            onBlur={(e) => updateMapping(acc.id, 'ifrs', e.target.value)}
                                        />
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </CardContent>
            </Card>
        </div>
    );
};

export default AccountantPortal;
