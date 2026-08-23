
import React, { useEffect, useState } from 'react';
import Head from 'next/head';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ShieldAlert, Users, AlertOctagon } from "lucide-react";
import { DesktopSecurityAudit } from "@/components/desktop/DesktopSecurityAudit";
import { authHeaders } from "@/lib/auth-headers";

export default function RiskDashboard() {
    const [churn, setChurn] = useState<any[]>([]);
    const [fraudAlerts, setFraudAlerts] = useState<any[]>([]);
    const [arAlerts, setArAlerts] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        async function fetchData() {
            try {
                const headers = authHeaders({ "Content-Type": "application/json" });
                const [c, fraud, early] = await Promise.all([
                    fetch("/api/risk/customer-protection", { headers }).then(r => r.json()),
                    fetch("/api/risk/fraud", { headers }).then(r => r.json()),
                    fetch("/api/risk/early-warning", { headers }).then(r => r.json())
                ]);
                setChurn(c.churn_risk || []);
                setFraudAlerts(fraud.anomalies || []);
                setArAlerts(early.ar_alerts || []);
            } catch (e) {
                console.error("Failed to load risk data", e);
            } finally {
                setLoading(false);
            }
        }
        fetchData();
    }, []);

    const getRiskBadge = (level: string) => {
        if (level === "HIGH") return "destructive";
        if (level === "MEDIUM") return "secondary";
        return "outline";
    };

    return (
        <>
            <Head>
                <title>Risk Control Center - ATOM</title>
            </Head>

            <div className="container mx-auto py-8 space-y-8">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">Risk Control Center</h1>
                    <p className="text-muted-foreground mt-2">
                        AI-powered protection against churn, fraud, and financial instability.
                    </p>
                </div>

                {/* Top-Level Stats */}
                <div className="grid gap-4 md:grid-cols-3">
                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium">Churn Risk</CardTitle>
                            <Users className="h-4 w-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">
                                {churn.filter((c: any) => c.risk_level === "HIGH").length} Accounts
                            </div>
                            <p className="text-xs text-muted-foreground">High risk of going silent</p>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium">Active Alerts</CardTitle>
                            <ShieldAlert className="h-4 w-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">{fraudAlerts.length + arAlerts.length}</div>
                            <p className="text-xs text-muted-foreground">Fraud & AR Flags</p>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium">Value at Risk</CardTitle>
                            <AlertOctagon className="h-4 w-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">
                                ${churn.reduce((sum: number, c: any) => sum + (c.value || 0), 0).toLocaleString()}
                            </div>
                            <p className="text-xs text-muted-foreground">Across monitored deals</p>
                        </CardContent>
                    </Card>
                </div>

                <div className="grid gap-6 md:grid-cols-2">

                    {/* Churn Section */}
                    <Card className="col-span-1">
                        <CardHeader>
                            <CardTitle>Churn Predictions</CardTitle>
                            <CardDescription>Accounts showing signs of disengagement.</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            {churn.map((c: any) => (
                                <div key={c.deal_id} className="p-3 rounded-lg border bg-white dark:bg-gray-900 shadow-sm">
                                    <div className="flex items-center justify-between">
                                        <span className="font-semibold">{c.client_name}</span>
                                        <Badge variant={getRiskBadge(c.risk_level)}>{c.risk_level}</Badge>
                                    </div>
                                    <div className="flex justify-between items-center text-xs text-muted-foreground mt-2">
                                        <span>Silent for {c.days_silent} days</span>
                                        <span className="text-red-600 font-medium">${(c.value || 0).toLocaleString()}</span>
                                    </div>
                                </div>
                            ))}
                            {!loading && churn.length === 0 && (
                                <p className="text-sm text-muted-foreground">No churn signals detected.</p>
                            )}
                        </CardContent>
                    </Card>

                    {/* Financial Risk Section */}
                    <div className="col-span-1 space-y-6">
                        {/* Fraud Alerts */}
                        <Card className="border-red-200 bg-red-50/50">
                            <CardHeader>
                                <CardTitle className="flex items-center text-red-700">
                                    <AlertOctagon className="mr-2 h-5 w-5" /> Fraud Alerts
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                {fraudAlerts.map((f: any) => (
                                    <div key={f.id} className="p-3 bg-white dark:bg-gray-900 rounded-lg border border-red-100 shadow-sm">
                                        <div className="flex justify-between font-medium text-sm">
                                            <span>#{f.id}</span>
                                            <span className="text-red-600">${f.amount}</span>
                                        </div>
                                        <p className="text-xs text-muted-foreground mt-1">{f.description}</p>
                                        <Badge variant="destructive" className="mt-2">{f.severity}</Badge>
                                    </div>
                                ))}
                                {fraudAlerts.length === 0 && (
                                    <p className="text-sm text-muted-foreground">No anomalies detected.</p>
                                )}
                            </CardContent>
                        </Card>

                        {/* AR Delays */}
                        <Card>
                            <CardHeader>
                                <CardTitle>Early Warning — AR Alerts</CardTitle>
                                <CardDescription>Invoices showing delay signals.</CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                {arAlerts.map((ar: any) => (
                                    <div key={ar.id} className="flex items-center justify-between border-b pb-4 last:border-0 last:pb-0">
                                        <div>
                                            <div className="font-semibold text-sm">{ar.description}</div>
                                            <div className="text-xs text-muted-foreground">{ar.days_overdue} days overdue</div>
                                        </div>
                                        <div className="text-right">
                                            <div className="font-bold text-sm text-orange-600">${(ar.amount || 0).toLocaleString()}</div>
                                        </div>
                                    </div>
                                ))}
                                {arAlerts.length === 0 && (
                                    <p className="text-sm text-muted-foreground">No AR delay signals.</p>
                                )}
                            </CardContent>
                        </Card>

                        <DesktopSecurityAudit />
                    </div>
                </div>
            </div>
        </>
    );
}
