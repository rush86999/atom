
import React, { useEffect, useState } from 'react';
import Head from 'next/head';
import { DailyBriefingCard } from "@/components/dashboard/DailyBriefingCard";
import { HealthMetricsGrid } from "@/components/dashboard/HealthMetricsGrid";
import { Button } from "@/components/ui/button";
import { RefreshCcw } from "lucide-react";
import { toast } from "sonner";

export default function OwnerDashboard() {
    const [data, setData] = useState<any>(null);
    const [loading, setLoading] = useState(true);

    const fetchDashboard = async () => {
        try {
            setLoading(true);
            // R82: /api/business-health/dashboard never existed — the owner
            // briefing is composed from the live daily-priorities surface
            // (the same source the business-health panel uses).
            const res = await fetch("/api/business-health/priorities");
            if (!res.ok) {
                toast.error("Failed to load dashboard data");
                return;
            }
            const json = await res.json();
            const items = Array.isArray(json) ? json : (json?.data ?? []);
            setData({
                metrics: null,
                briefing: {
                    owner_advice:
                        items.length > 0
                            ? `You have ${items.length} prioritized action${items.length > 1 ? "s" : ""} today.`
                            : "No open priorities right now.",
                    priorities: items,
                },
            });
        } catch (error) {
            console.error(error);
            toast.error("Network error");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchDashboard();
    }, []);

    return (
        <>
            <Head>
                <title>Owner Cockpit - ATOM</title>
            </Head>

            <div className="container mx-auto py-8 space-y-8">
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-3xl font-bold tracking-tight">Owner Cockpit</h1>
                        <p className="text-muted-foreground mt-2">
                            Your daily business pulse and intelligence briefing.
                        </p>
                    </div>
                    <Button variant="outline" size="sm" onClick={fetchDashboard} disabled={loading}>
                        <RefreshCcw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                        Refresh
                    </Button>
                </div>

                {data && (
                    <>
                        {data.metrics && <HealthMetricsGrid metrics={data.metrics} />}

                        <div className="grid gap-8 md:grid-cols-3">
                            <div className="md:col-span-2">
                                <DailyBriefingCard
                                    advice={data.briefing.owner_advice}
                                    priorities={data.briefing.priorities}
                                />
                            </div>
                            <div className="space-y-6">
                                {/* Placeholder for future Decision Simulator */}
                                <div className="p-6 border rounded-lg bg-muted/20">
                                    <h3 className="font-semibold mb-2">Simulate Decision</h3>
                                    <p className="text-sm text-muted-foreground mb-4">
                                        Thinking about hiring or a big purchase? Ask ATOM to simulate the impact.
                                    </p>
                                    <Button className="w-full" disabled>Open Simulator (Coming Soon)</Button>
                                </div>
                            </div>
                        </div>
                    </>
                )}
            </div>
        </>
    );
}
