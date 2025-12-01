import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";
import { ArrowUpRight, ArrowDownRight, DollarSign, Wallet, CreditCard, Activity } from "lucide-react";

const FinanceOverview = () => {
    return (
        <div className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Total Balance</CardTitle>
                        <Wallet className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">$45,231.89</div>
                        <p className="text-xs text-muted-foreground">
                            +20.1% from last month
                        </p>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Income</CardTitle>
                        <ArrowUpRight className="h-4 w-4 text-green-500" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">$8,250.00</div>
                        <p className="text-xs text-muted-foreground">
                            +4.5% from last month
                        </p>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Expenses</CardTitle>
                        <ArrowDownRight className="h-4 w-4 text-red-500" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">$3,420.50</div>
                        <p className="text-xs text-muted-foreground">
                            -12.3% from last month
                        </p>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Savings Rate</CardTitle>
                        <Activity className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">58.5%</div>
                        <p className="text-xs text-muted-foreground">
                            +2.4% from last month
                        </p>
                    </CardContent>
                </Card>
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
