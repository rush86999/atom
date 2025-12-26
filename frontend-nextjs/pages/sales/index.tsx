import React from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../../components/ui/tabs";
import { Button } from "../../components/ui/button";
import { RefreshCw, LayoutDashboard, Target, Users, Zap } from "lucide-react";
import LeadManagement from "../../components/sales/LeadManagement";
import DealIntelligence from "../../components/sales/DealIntelligence";
import MeetingAutomation from "../../components/sales/MeetingAutomation";
import { useWebSocket } from "../../hooks/useWebSocket";
import { useToast } from "../../components/ui/use-toast";
import { useEffect } from "react";

const SalesIntelligencePage = () => {
    const { toast } = useToast();
    const { lastMessage, subscribe } = useWebSocket();
    const workspaceId = "sales-test-ws"; // This would be dynamic in a real app

    useEffect(() => {
        subscribe(`workspace:${workspaceId}`);
    }, [subscribe]);

    useEffect(() => {
        if (!lastMessage) return;

        if (lastMessage.type === "new_lead") {
            toast({
                title: "New Lead Ingested",
                description: `${lastMessage.data.first_name} ${lastMessage.data.last_name || ""} from ${lastMessage.data.company || "Unknown"} (Score: ${lastMessage.data.ai_score})`,
                variant: lastMessage.data.ai_score > 70 ? "success" : "default",
            });
        } else if (lastMessage.type === "deal_update") {
            toast({
                title: "Deal Health Updated",
                description: `${lastMessage.data.name}: Health Score ${lastMessage.data.health_score} (${lastMessage.data.risk_level} risk)`,
                variant: lastMessage.data.health_score < 40 ? "warning" : "default",
            });
        }
    }, [lastMessage, toast]);

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">Sales Intelligence</h1>
                    <p className="text-muted-foreground">
                        AI-powered lead scoring, deal health tracking, and meeting automation.
                    </p>
                </div>
                <div className="flex gap-2">
                    <Button variant="outline">
                        <RefreshCw className="mr-2 h-4 w-4" /> Sync CRM
                    </Button>
                    <Button>
                        <Zap className="mr-2 h-4 w-4" /> Forecast Report
                    </Button>
                </div>
            </div>

            <Tabs defaultValue="leads" className="space-y-4">
                <TabsList className="bg-muted/50 p-1">
                    <TabsTrigger value="leads" className="gap-2">
                        <Users className="h-4 w-4" /> Lead Intake
                    </TabsTrigger>
                    <TabsTrigger value="deals" className="gap-2">
                        <Target className="h-4 w-4" /> Pipeline Health
                    </TabsTrigger>
                    <TabsTrigger value="meetings" className="gap-2">
                        <Zap className="h-4 w-4" /> Meeting Intelligence
                    </TabsTrigger>
                    <TabsTrigger value="dashboard" className="gap-2">
                        <LayoutDashboard className="h-4 w-4" /> Executive Overview
                    </TabsTrigger>
                </TabsList>

                <TabsContent value="leads" className="space-y-4 pt-4">
                    <LeadManagement />
                </TabsContent>

                <TabsContent value="deals" className="space-y-4 pt-4">
                    <DealIntelligence />
                </TabsContent>

                <TabsContent value="meetings" className="space-y-4 pt-4">
                    <MeetingAutomation />
                </TabsContent>

                <TabsContent value="dashboard" className="space-y-4 pt-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <Card className="bg-gradient-to-br from-indigo-50 to-white dark:from-indigo-950 dark:to-slate-950">
                            <CardHeader>
                                <CardTitle>Winning More with AI</CardTitle>
                                <CardDescription>Your win rate has increased by 14% since implementing AI health scores.</CardDescription>
                            </CardHeader>
                        </Card>
                        <Card className="bg-gradient-to-br from-emerald-50 to-white dark:from-emerald-950 dark:to-slate-950">
                            <CardHeader>
                                <CardTitle>Meeting Efficiency</CardTitle>
                                <CardDescription>Talk-to-Task automation has saved 4.5 hours of admin work this week.</CardDescription>
                            </CardHeader>
                        </Card>
                    </div>
                </TabsContent>
            </Tabs>
        </div>
    );
};

// Helper card for the dashboard tab
const Card = ({ children, className }: { children: React.ReactNode, className?: string }) => (
    <div className={`rounded-xl border bg-card text-card-foreground shadow ${className}`}>
        {children}
    </div>
);

const CardHeader = ({ children }: { children: React.ReactNode }) => (
    <div className="flex flex-col space-y-1.5 p-6">{children}</div>
);

const CardTitle = ({ children }: { children: React.ReactNode }) => (
    <h3 className="font-semibold leading-none tracking-tight text-xl">{children}</h3>
);

const CardDescription = ({ children }: { children: React.ReactNode }) => (
    <p className="text-sm text-muted-foreground">{children}</p>
);

export default SalesIntelligencePage;
