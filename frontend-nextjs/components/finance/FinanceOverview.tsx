import React, { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";
import { ArrowUpRight, ArrowDownRight, DollarSign, Wallet, CreditCard, Activity, Loader2 } from "lucide-react";

interface DashboardSummary {
    total_revenue: number;
    pending_revenue: number;
    runway_months: number;
    currency: string;
}

const FinanceOverview = () => {
    const [summary, setSummary] = useState<DashboardSummary | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchSummary = async () => {
            try {
                const token = localStorage.getItem('auth_token');
                const response = await fetch('/api/accounting/summary', {
                    headers: {
                        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
                    }
                });
                if (response.ok) {
                    const data = await response.json();
                    setSummary(data.data);
                }
            } catch (error) {
                console.error("Failed to fetch finance summary:", error);
            } finally {
                setLoading(false);
            }
        };

        fetchSummary();
    }, []);

    if (loading) {
        return (
            <div className="flex justify-center p-12">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    const metrics = [
        {
            title: "Total Revenue",
            value: summary ? new Intl.NumberFormat('en-US', { style: 'currency', currency: summary.currency }).format(summary.total_revenue) : "$0.00",
            description: "+20.1% from last month",
            icon: Wallet,
            color: "text-muted-foreground"
        },
        {
            title: "Pending Revenue",
            value: summary ? new Intl.NumberFormat('en-US', { style: 'currency', currency: summary.currency }).format(summary.pending_revenue) : "$0.00",
            description: "Awaiting settlement",
            icon: ArrowUpRight,
            color: "text-green-500"
        },
        {
            title: "Runway",
            value: summary ? `${summary.runway_months} Months` : "0 Months",
            description: "Estimated survival",
            icon: Activity,
            color: "text-blue-500"
        },
        {
            title: "Gross Profit",
            value: summary ? new Intl.NumberFormat('en-US', { style: 'currency', currency: summary.currency }).format(summary.total_revenue * 0.58) : "0%",
            description: "Estimated margin",
            icon: CreditCard,
            color: "text-purple-500"
        }
    ];

    return (
        <div className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                {metrics.map((metric, idx) => (
                    <Card key={idx}>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium">{metric.title}</CardTitle>
                            <metric.icon className={`h-4 w-4 ${metric.color}`} />
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">{metric.value}</div>
                            <p className="text-xs text-muted-foreground">
                                {metric.description}
                            </p>
                        </CardContent>
                    </Card>
                ))}
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
                <Card className="col-span-4">
                    <CardHeader>
                        <CardTitle>Overview</CardTitle>
                    </CardHeader>
                    <CardContent className="pl-2">
                        <div className="h-[300px] flex items-center justify-center bg-secondary/20 rounded-md border border-dashed border-muted-foreground/25">
                            <p className="text-muted-foreground">Chart Visualization Placeholder</p>
                        </div>
                    </CardContent>
                </Card>
                <Card className="col-span-3">
                    <CardHeader>
                        <CardTitle>Recent Activity</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-8">
                            {[
                                { name: "Stripe Payout", amount: "+$2,400.00", date: "Today", icon: ArrowUpRight, color: "text-green-500" },
                                { name: "AWS Bill", amount: "-$142.00", date: "Yesterday", icon: ArrowDownRight, color: "text-red-500" },
                                { name: "Client Payment", amount: "+$850.00", date: "Yesterday", icon: ArrowUpRight, color: "text-green-500" },
                                { name: "Software Subscription", amount: "-$29.00", date: "2 days ago", icon: ArrowDownRight, color: "text-red-500" },
                                { name: "Upwork Earnings", amount: "+$1,200.00", date: "3 days ago", icon: ArrowUpRight, color: "text-green-500" },
                            ].map((item, index) => (
                                <div key={index} className="flex items-center">
                                    <div className={`h-9 w-9 rounded-full bg-secondary flex items-center justify-center mr-4`}>
                                        <item.icon className={`h-5 w-5 ${item.color}`} />
                                    </div>
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium leading-none">{item.name}</p>
                                        <p className="text-xs text-muted-foreground">{item.date}</p>
                                    </div>
                                    <div className={`ml-auto font-medium ${item.color}`}>{item.amount}</div>
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
};

export default FinanceOverview;

