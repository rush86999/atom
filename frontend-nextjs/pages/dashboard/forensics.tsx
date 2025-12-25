
import React, { useEffect, useState } from 'react';
import Head from 'next/head';
import { Layout } from "@/components/layout/Layout";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { trendingUp, trendingDown, alertTriangle, checkCircle, arrowRight } from "lucide-react";
import { Zap, AlertTriangle, TrendingUp, PiggyBank } from "lucide-react";

export default function ForensicsDashboard() {
    const [drift, setDrift] = useState([]);
    const [pricing, setPricing] = useState([]);
    const [waste, setWaste] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        async function fetchData() {
            try {
                const [d, p, w] = await Promise.all([
                    fetch("/api/business-health/forensics/vendor-drift").then(r => r.json()),
                    fetch("/api/business-health/forensics/pricing-opportunities").then(r => r.json()),
                    fetch("/api/business-health/forensics/subscription-waste").then(r => r.json())
                ]);
                setDrift(d.data || []);
                setPricing(p.data || []);
                setWaste(w.data || []);
            } catch (e) {
                console.error("Failed to load forensics", e);
            } finally {
                setLoading(false);
            }
        }
        fetchData();
    }, []);

    return (
        <Layout>
            <Head>
                <title>Financial Forensics - ATOM</title>
            </Head>

            <div className="container mx-auto py-8 space-y-8">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">Financial Forensics</h1>
                    <p className="text-muted-foreground mt-2">
                        AI-driven detection of money leaks and pricing opportunities.
                    </p>
                </div>

                <div className="grid gap-4 md:grid-cols-3">
                    <Card className="bg-red-50 border-red-200">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-red-700 flex items-center"><TrendingUp className="mr-2 h-5 w-5" /> Price Drift</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold text-red-900">{drift.length} Vendors</div>
                            <p className="text-xs text-red-600">Increasing costs detected</p>
                        </CardContent>
                    </Card>
                    <Card className="bg-green-50 border-green-200">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-green-700 flex items-center"><PiggyBank className="mr-2 h-5 w-5" /> Pricing Ops</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold text-green-900">{pricing.length} Opportunities</div>
                            <p className="text-xs text-green-600">To improve margins</p>
                        </CardContent>
                    </Card>
                    <Card className="bg-yellow-50 border-yellow-200">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-yellow-700 flex items-center"><AlertTriangle className="mr-2 h-5 w-5" /> Inactive Subs</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold text-yellow-900">{waste.length} Subscriptions</div>
                            <p className="text-xs text-yellow-600">Low usage detected</p>
                        </CardContent>
                    </Card>
                </div>


                <Tabs defaultValue="drift" className="space-y-4">
                    <TabsList>
                        <TabsTrigger value="drift">Vendor Watch</TabsTrigger>
                        <TabsTrigger value="pricing">Smart Pricing</TabsTrigger>
                        <TabsTrigger value="waste">Subscription Manager</TabsTrigger>
                    </TabsList>

                    <TabsContent value="drift" className="space-y-4">
                        <div className="grid gap-4">
                            {loading && <p>Loading analysis...</p>}
                            {drift.map((item: any) => (
                                <Card key={item.vendor_id}>
                                    <CardHeader>
                                        <div className="flex justify-between items-start">
                                            <div>
                                                <CardTitle>{item.vendor_name}</CardTitle>
                                                <CardDescription>{item.category}</CardDescription>
                                            </div>
                                            <Badge variant="destructive">+{item.drift_percent}% Drift</Badge>
                                        </div>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="flex justify-between text-sm">
                                            <div>
                                                <p className="text-muted-foreground">Historical Avg</p>
                                                <p className="font-medium">${item.avg_spend}</p>
                                            </div>
                                            <div>
                                                <p className="text-muted-foreground">Current Spend</p>
                                                <p className="font-bold text-red-600">${item.current_spend}</p>
                                            </div>
                                            <div>
                                                <p className="text-muted-foreground">Detected</p>
                                                <p>{new Date(item.detected_at).toLocaleDateString()}</p>
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    </TabsContent>

                    <TabsContent value="pricing" className="space-y-4">
                        <div className="grid gap-4">
                            {pricing.map((item: any) => (
                                <Card key={item.sku}>
                                    <CardHeader>
                                        <div className="flex justify-between items-start">
                                            <div>
                                                <CardTitle>{item.item}</CardTitle>
                                                <CardDescription>{item.reason}</CardDescription>
                                            </div>
                                            <Badge variant="outline" className="bg-green-100 text-green-800 border-green-200">
                                                {item.margin_impact} Margin
                                            </Badge>
                                        </div>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="flex items-center space-x-4">
                                            <span className="line-through text-muted-foreground">${item.current_price}</span>
                                            <span className="text-2xl font-bold text-green-600">${item.target_price}</span>
                                            <span className="text-sm text-muted-foreground">Confidence: {item.confidence}</span>
                                        </div>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    </TabsContent>

                    <TabsContent value="waste" className="space-y-4">
                        <div className="grid gap-4 md:grid-cols-2">
                            {waste.map((item: any) => (
                                <Card key={item.subscription_id}>
                                    <CardHeader>
                                        <div className="flex justify-between items-start">
                                            <CardTitle>{item.service_name}</CardTitle>
                                            <Badge variant="secondary">{item.status}</Badge>
                                        </div>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="space-y-2">
                                            <div className="flex justify-between text-sm">
                                                <span className="text-muted-foreground">Monthly Cost</span>
                                                <span className="font-bold">${item.mrr}</span>
                                            </div>
                                            <div className="flex justify-between text-sm">
                                                <span className="text-muted-foreground">Last Active</span>
                                                <span>{new Date(item.last_login).toLocaleDateString()}</span>
                                            </div>
                                            <div className="pt-2">
                                                <Button variant="destructive" size="sm" className="w-full">Cancel Subscription</Button>
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    </TabsContent>
                </Tabs>
            </div>
        </Layout>
    );
}
