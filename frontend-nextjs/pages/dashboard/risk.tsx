
import React, { useEffect, useState } from 'react';
import Head from 'next/head';
import { Layout } from "@/components/layout/Layout";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { ShieldAlert, Users, TrendingUp, AlertOctagon, Activity } from "lucide-react";

export default function RiskDashboard() {
    const [churn, setChurn] = useState([]);
    const [financial, setFinancial] = useState<any>(null);
    const [growth, setGrowth] = useState<any>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        async function fetchData() {
            try {
                const [c, f, g] = await Promise.all([
                    fetch("/api/risk/churn").then(r => r.json()),
                    fetch("/api/risk/financial").then(r => r.json()),
                    fetch("/api/risk/growth").then(r => r.json())
                ]);
                setChurn(c.data || []);
                setFinancial(f.data || {});
                setGrowth(g.data || {});
            } catch (e) {
                console.error("Failed to load risk data", e);
            } finally {
                setLoading(false);
            }
        }
        fetchData();
    }, []);

    const getRiskColor = (prob: number) => {
        if (prob > 0.7) return "bg-red-500";
        if (prob > 0.4) return "bg-yellow-500";
        return "bg-green-500";
    };

    return (
        <Layout>
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
                            <div className="text-2xl font-bold">{churn.filter((c: any) => c.churn_probability > 0.5).length} Customers</div>
                            <p className="text-xs text-muted-foreground">High risk of leaving</p>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium">Growth Readiness</CardTitle>
                            <Activity className="h-4 w-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">{growth?.readiness_score || 0}/100</div>
                            <p className="text-xs text-muted-foreground">Scaling health score</p>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium">Active Alerts</CardTitle>
                            <ShieldAlert className="h-4 w-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">
                                {(financial?.fraud_alerts?.length || 0) + (financial?.ar_delays?.length || 0)}
                            </div>
                            <p className="text-xs text-muted-foreground">Fraud & AR Flags</p>
                        </CardContent>
                    </Card>
                </div>

                <div className="grid gap-6 md:grid-cols-2">

                    {/* Churn Section */}
                    <Card className="col-span-1">
                        <CardHeader>
                            <CardTitle>Churn Predictions</CardTitle>
                            <CardDescription>Customers showing signs of disengagement.</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-6">
                            {churn.map((c: any) => (
                                <div key={c.customer_id} className="space-y-2">
                                    <div className="flex items-center justify-between">
                                        <span className="font-semibold">{c.customer_name}</span>
                                        <span className="text-sm text-muted-foreground">{Math.round(c.churn_probability * 100)}% Risk</span>
                                    </div>
                                    <Progress value={c.churn_probability * 100} className={`h-2 ${getRiskColor(c.churn_probability)}`} />
                                    <div className="flex justify-between items-center text-xs text-muted-foreground">
                                        <span>Risk: {c.risk_factors.join(", ")}</span>
                                        <span className="text-red-600 font-medium">${c.mrr_at_risk} MRR</span>
                                    </div>
                                    <Button variant="outline" size="sm" className="w-full mt-2">
                                        Action: {c.recommended_action}
                                    </Button>
                                </div>
                            ))}
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
                                {financial?.fraud_alerts?.map((f: any) => (
                                    <div key={f.transaction_id} className="p-3 bg-white rounded-lg border border-red-100 shadow-sm">
                                        <div className="flex justify-between font-medium text-sm">
                                            <span>#{f.transaction_id}</span>
                                            <span className="text-red-600">${f.amount}</span>
                                        </div>
                                        <p className="text-xs text-muted-foreground mt-1">{f.flag_reason}</p>
                                    </div>
                                ))}
                            </CardContent>
                        </Card>

                        {/* AR Delays */}
                        <Card>
                            <CardHeader>
                                <CardTitle>Predicted AR Delays</CardTitle>
                                <CardDescription>Invoices likely to be paid late.</CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                {financial?.ar_delays?.map((ar: any) => (
                                    <div key={ar.invoice_id} className="flex items-center justify-between border-b pb-4 last:border-0 last:pb-0">
                                        <div>
                                            <div className="font-semibold text-sm">{ar.client_name}</div>
                                            <div className="text-xs text-muted-foreground">Due: {new Date(ar.due_date).toLocaleDateString()}</div>
                                        </div>
                                        <div className="text-right">
                                            <div className="font-bold text-sm text-orange-600">${ar.amount.toLocaleString()}</div>
                                            <div className="text-xs text-muted-foreground">{Math.round(ar.likelihood_late * 100)}% Late Chance</div>
                                        </div>
                                    </div>
                                ))}
                            </CardContent>
                        </Card>

                        {/* Growth Readiness */}
                        <Card>
                            <CardHeader>
                                <CardTitle>Scaling Constraints</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="flex items-center justify-center py-4">
                                    <div className="relative flex flex-col items-center">
                                        <div className="text-4xl font-bold text-blue-600">{growth?.readiness_score}</div>
                                        <div className="text-xs text-muted-foreground uppercase tracking-wider">Readiness Score</div>
                                    </div>
                                </div>
                                <div className="space-y-2 mt-4">
                                    {growth?.bottlenecks?.map((b: any, i: number) => (
                                        <div key={i} className="flex justify-between text-sm p-2 bg-slate-50 rounded">
                                            <span className="font-medium">{b.area}</span>
                                            <span className={b.status === "strained" ? "text-red-500" : "text-green-500"}>
                                                {b.status === "strained" ? "Strained ⚠️" : "Healthy ✅"}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            </CardContent>
                        </Card>
                    </div>
                </div>
            </div>
        </Layout>
    );
}
