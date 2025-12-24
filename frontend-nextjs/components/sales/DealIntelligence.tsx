import React, { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../ui/table";
import { Badge } from "../ui/badge";
import { Progress } from "../ui/progress";
import { TrendingUp, AlertTriangle, Clock, DollarSign, BarChart3 } from "lucide-react";

interface Deal {
    id: string;
    name: string;
    value: number;
    stage: string;
    health_score: number;
    risk_level: string;
    expected_close_date: string;
    last_engagement_at: string;
    currency: string;
}

const DealIntelligence = () => {
    const [deals, setDeals] = useState<Deal[]>([]);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        fetchDeals();
    }, []);

    const fetchDeals = async () => {
        setIsLoading(true);
        try {
            const response = await fetch("/api/sales/deals?workspace_id=temp_ws");
            const data = await response.json();
            setDeals(data);
        } catch (error) {
            console.error("Error fetching deals:", error);
        } finally {
            setIsLoading(false);
        }
    };

    const getRiskBadge = (risk: string) => {
        switch (risk) {
            case "high":
                return <Badge variant="destructive" className="gap-1"><AlertTriangle className="h-3 w-3" /> High Risk</Badge>;
            case "medium":
                return <Badge variant="warning" className="gap-1"><Clock className="h-3 w-3" /> Medium Risk</Badge>;
            case "low":
                return <Badge variant="success" className="gap-1"><TrendingUp className="h-3 w-3" /> Healthy</Badge>;
            default:
                return <Badge variant="secondary">{risk}</Badge>;
        }
    };

    const getHealthColor = (score: number) => {
        if (score >= 70) return "bg-green-500";
        if (score >= 40) return "bg-yellow-500";
        return "bg-red-500";
    };

    return (
        <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Pipeline Value</CardTitle>
                        <DollarSign className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">$385,000</div>
                        <p className="text-xs text-muted-foreground">+12% from last month</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Average Health</CardTitle>
                        <BarChart3 className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">61.6 / 100</div>
                        <div className="mt-2 text-xs text-muted-foreground">
                            <Progress value={61.6} className="h-1" />
                        </div>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">At-Risk Value</CardTitle>
                        <AlertTriangle className="h-4 w-4 text-red-500" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-red-500">$250,000</div>
                        <p className="text-xs text-muted-foreground">1 deal requiring immediate attention</p>
                    </CardContent>
                </Card>
            </div>

            <Card>
                <CardHeader>
                    <CardTitle>Pipeline Intelligence</CardTitle>
                    <CardDescription>
                        AI monitors deal velocity, value, and engagement to identify potential risks.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Deal Name</TableHead>
                                <TableHead>Value</TableHead>
                                <TableHead>Stage</TableHead>
                                <TableHead>Health Score</TableHead>
                                <TableHead>Risk Level</TableHead>
                                <TableHead>Expected Close</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {deals.map((deal) => (
                                <TableRow key={deal.id}>
                                    <TableCell className="font-medium">{deal.name}</TableCell>
                                    <TableCell>
                                        {new Intl.NumberFormat('en-US', { style: 'currency', currency: deal.currency }).format(deal.value)}
                                    </TableCell>
                                    <TableCell>
                                        <Badge variant="secondary">{deal.stage}</Badge>
                                    </TableCell>
                                    <TableCell>
                                        <div className="w-[120px] space-y-1">
                                            <div className="flex justify-between text-xs">
                                                <span>{deal.health_score}/100</span>
                                            </div>
                                            <Progress value={deal.health_score} className={`h-1.5 ${getHealthColor(deal.health_score)}`} />
                                        </div>
                                    </TableCell>
                                    <TableCell>
                                        {getRiskBadge(deal.risk_level)}
                                    </TableCell>
                                    <TableCell>
                                        <div className="flex items-center gap-1 text-sm">
                                            <Clock className="h-3 w-3 text-muted-foreground" />
                                            {new Date(deal.expected_close_date).toLocaleDateString()}
                                        </div>
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

export default DealIntelligence;
