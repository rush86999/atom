import React from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../ui/card";
import { Button } from "../ui/button";
import { Badge } from "../ui/badge";
import { Calendar, CreditCard, AlertCircle } from "lucide-react";

const SubscriptionTracker = () => {
    const subscriptions = [
        { name: "AWS", plan: "Pro", cost: 142.00, cycle: "Monthly", nextBill: "2025-12-01", status: "Active" },
        { name: "Adobe Creative Cloud", plan: "All Apps", cost: 54.99, cycle: "Monthly", nextBill: "2025-12-05", status: "Active" },
        { name: "Slack", plan: "Business", cost: 12.50, cycle: "Monthly/User", nextBill: "2025-12-10", status: "Active" },
        { name: "GitHub", plan: "Team", cost: 40.00, cycle: "Monthly", nextBill: "2025-12-15", status: "Active" },
        { name: "Vercel", plan: "Pro", cost: 20.00, cycle: "Monthly", nextBill: "2025-12-01", status: "Active" },
        { name: "Notion", plan: "Team", cost: 8.00, cycle: "Monthly/User", nextBill: "2025-12-03", status: "Active" },
    ];

    const totalMonthly = subscriptions.reduce((acc, sub) => acc + sub.cost, 0);

    return (
        <div className="space-y-6">
            <div className="grid gap-4 md:grid-cols-3">
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium">Monthly Recurring</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">${totalMonthly.toFixed(2)}</div>
                        <p className="text-xs text-muted-foreground">Estimated for next month</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium">Active Subscriptions</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{subscriptions.length}</div>
                        <p className="text-xs text-muted-foreground">Services connected</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium">Upcoming Renewals</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">3</div>
                        <p className="text-xs text-muted-foreground">Renewing in next 7 days</p>
                    </CardContent>
                </Card>
            </div>

            <Card>
                <CardHeader>
                    <CardTitle>Subscriptions</CardTitle>
                    <CardDescription>Manage your recurring software and service payments.</CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="space-y-4">
                        {subscriptions.map((sub, index) => (
                            <div key={index} className="flex items-center justify-between p-4 border rounded-lg hover:bg-secondary/50 transition-colors">
                                <div className="flex items-center gap-4">
                                    <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
                                        <CreditCard className="h-5 w-5 text-primary" />
                                    </div>
                                    <div>
                                        <h4 className="font-semibold">{sub.name}</h4>
                                        <p className="text-sm text-muted-foreground">{sub.plan} • {sub.cycle}</p>
                                    </div>
                                </div>
                                <div className="flex items-center gap-6">
                                    <div className="text-right">
                                        <div className="font-bold">${sub.cost.toFixed(2)}</div>
                                        <div className="text-xs text-muted-foreground flex items-center gap-1 justify-end">
                                            <Calendar className="h-3 w-3" /> {sub.nextBill}
                                        </div>
                                    </div>
                                    <Badge variant="outline" className="bg-green-500/10 text-green-500 border-green-500/20">
                                        {sub.status}
                                    </Badge>
                                    <Button variant="ghost" size="sm">Manage</Button>
                                </div>
                            </div>
                        ))}
                    </div>
                </CardContent>
            </Card>
        </div>
    );
};

export default SubscriptionTracker;
