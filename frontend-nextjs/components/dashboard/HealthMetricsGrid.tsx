
import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ArrowUpRight, ArrowDownRight, Minus } from "lucide-react";

interface MetricData {
    value: string;
    trend: "up" | "down" | "stable";
    trend_value: string;
    status: "healthy" | "warning" | "neutral";
}

interface MetricsGridProps {
    metrics: {
        cash_runway: MetricData;
        lead_velocity: MetricData;
        active_deals: MetricData;
        churn_risk: MetricData;
    };
}

export function HealthMetricsGrid({ metrics }: MetricsGridProps) {
    const getTrendIcon = (trend: string) => {
        switch (trend) {
            case "up": return <ArrowUpRight className="h-4 w-4 text-green-500" />;
            case "down": return <ArrowDownRight className="h-4 w-4 text-red-500" />;
            default: return <Minus className="h-4 w-4 text-gray-400" />;
        }
    };

    const getStatusColor = (status: string) => {
        switch (status) {
            case "healthy": return "text-green-600";
            case "warning": return "text-red-600";
            default: return "text-muted-foreground";
        }
    };

    const renderCard = (title: string, data: MetricData) => (
        <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">
                    {title}
                </CardTitle>
                {getTrendIcon(data.trend)}
            </CardHeader>
            <CardContent>
                <div className="text-2xl font-bold">{data.value}</div>
                <p className={`text-xs ${getStatusColor(data.status)}`}>
                    {data.trend === "up" ? "+" : ""}{data.trend_value} from last month
                </p>
            </CardContent>
        </Card>
    );

    return (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {renderCard("Cash Runway", metrics.cash_runway)}
            {renderCard("Lead Velocity", metrics.lead_velocity)}
            {renderCard("Active Deals", metrics.active_deals)}
            {renderCard("Churn Risk", metrics.churn_risk)}
        </div>
    );
}
