
import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ArrowRight, Sparkles } from "lucide-react";
import Link from 'next/link';

interface PriorityItem {
    id: string;
    type: "GROWTH" | "RISK" | "STRATEGY";
    title: string;
    description: string;
    priority: "HIGH" | "MEDIUM" | "LOW";
    action_link: string;
}

interface DailyBriefingProps {
    advice: string;
    priorities: PriorityItem[];
}

export function DailyBriefingCard({ advice, priorities }: DailyBriefingProps) {
    const getBadgeColor = (type: string) => {
        switch (type) {
            case "GROWTH": return "bg-green-100 text-green-800 hover:bg-green-200 border-green-200";
            case "RISK": return "bg-red-100 text-red-800 hover:bg-red-200 border-red-200";
            case "STRATEGY": return "bg-purple-100 text-purple-800 hover:bg-purple-200 border-purple-200";
            default: return "bg-gray-100 text-gray-800 hover:bg-gray-200 border-gray-200";
        }
    };

    return (
        <Card className="border-t-4 border-t-primary shadow-sm">
            <CardHeader className="pb-3">
                <div className="flex items-center space-x-2">
                    <Sparkles className="h-5 w-5 text-primary" />
                    <CardTitle>Daily Briefing</CardTitle>
                </div>
                <p className="text-sm text-muted-foreground mt-1">
                    {advice || "Analyzing business signals..."}
                </p>
            </CardHeader>
            <CardContent>
                <div className="space-y-4">
                    {priorities.map((item) => (
                        <div key={item.id} className="group flex items-start justify-between p-3 rounded-lg border bg-card hover:bg-accent/50 transition-colors">
                            <div className="space-y-1">
                                <div className="flex items-center space-x-2">
                                    <Badge variant="outline" className={getBadgeColor(item.type)}>
                                        {item.type}
                                    </Badge>
                                    <span className="font-medium text-sm">{item.title}</span>
                                </div>
                                <p className="text-xs text-muted-foreground pl-1">
                                    {item.description}
                                </p>
                            </div>
                            <Link href={item.action_link}>
                                <button className="p-2 rounded-full hover:bg-background transition-colors opacity-0 group-hover:opacity-100">
                                    <ArrowRight className="h-4 w-4 text-primary" />
                                </button>
                            </Link>
                        </div>
                    ))}

                    {priorities.length === 0 && (
                        <div className="text-center py-6 text-muted-foreground text-sm">
                            No critical items today. Good job!
                        </div>
                    )}
                </div>
            </CardContent>
        </Card>
    );
}
