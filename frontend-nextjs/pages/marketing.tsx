import React, { useState, useEffect } from "react";
import { useRouter } from "next/router";
import {
    Card,
    CardContent,
    CardHeader,
    CardTitle,
    CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/use-toast";
import {
    TrendingUp,
    Target,
    MessageSquare,
    Search,
    ArrowRight,
    Zap,
    BarChart3,
    Users,
    Star,
    RefreshCw,
    Globe
} from "lucide-react";

const MarketingDashboard: React.FC = () => {
    const [loading, setLoading] = useState(true);
    const [summary, setSummary] = useState<any>(null);
    const [researchQuery, setResearchQuery] = useState("");
    const [researchResult, setResearchResult] = useState<any>(null);
    const [researching, setResearching] = useState(false);
    const toast = useToast();
    const router = useRouter();

    const fetchMarketingData = async () => {
        try {
            setLoading(true);
            const res = await fetch("/api/marketing/dashboard/summary");
            if (res.ok) {
                setSummary(await res.json());
            } else {
                throw new Error("Failed to fetch marketing summary");
            }
        } catch (error) {
            console.error(error);
            toast({
                title: "Error",
                description: "Could not load marketing intelligence.",
                variant: "error",
            });
        } finally {
            setLoading(false);
        }
    };

    const handleResearch = async () => {
        if (!researchQuery) return;
        try {
            setResearching(true);
            const res = await fetch(`/api/mcp/search?query=${encodeURIComponent(researchQuery)}`);
            if (res.ok) {
                setResearchResult(await res.json());
            }
        } catch (error) {
            toast({
                title: "Research failed",
                description: "Could not perform market research.",
                variant: "error",
            });
        } finally {
            setResearching(false);
        }
    };

    useEffect(() => {
        fetchMarketingData();
    }, []);

    return (
        <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-6">
            <div className="max-w-[1400px] mx-auto space-y-8">
                {/* Header */}
                <div className="flex justify-between items-end">
                    <div className="space-y-2">
                        <h1 className="text-4xl font-bold tracking-tight text-gray-900 dark:text-gray-100">
                            AI Marketing Blueprint
                        </h1>
                        <p className="text-xl text-gray-600 dark:text-gray-400">
                            Autonomous Growth & Reputation Engine
                        </p>
                    </div>
                    <Button onClick={fetchMarketingData} disabled={loading} className="gap-2">
                        <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
                        Refresh Strategy
                    </Button>
                </div>

                {/* Narrative Intelligence Section */}
                <Card className="border-l-4 border-l-blue-600 bg-blue-50/30 dark:bg-blue-900/10">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <Zap className="w-5 h-5 text-blue-600" />
                            Plain-English Growth Report
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <p className="text-2xl font-medium text-gray-800 dark:text-gray-200 leading-relaxed">
                            {summary?.narrative_report?.content || "Analyzing your marketing data for actionable insights..."}
                        </p>
                    </CardContent>
                </Card>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                    {/* High Intent Leads */}
                    <div className="lg:col-span-2 space-y-6">
                        <Card>
                            <CardHeader className="flex flex-row items-center justify-between">
                                <div>
                                    <CardTitle>Priority Leads</CardTitle>
                                    <CardDescription>AI-scored leads ready for conversion</CardDescription>
                                </div>
                                <Button variant="ghost" size="sm" className="gap-2">
                                    View All Leads <ArrowRight className="w-4 h-4" />
                                </Button>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                {summary?.high_intent_leads?.map((lead: any) => (
                                    <div key={lead.id} className="flex items-center justify-between p-4 border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                                        <div className="flex items-center gap-4">
                                            <div className="p-2 bg-green-100 dark:bg-green-900/30 rounded-full">
                                                <Target className="w-5 h-5 text-green-600" />
                                            </div>
                                            <div>
                                                <h4 className="font-semibold">{lead.name}</h4>
                                                <p className="text-sm text-gray-500">{lead.summary}</p>
                                            </div>
                                        </div>
                                        <div className="text-right">
                                            <Badge className="bg-green-600">{lead.score}% Intent</Badge>
                                            <p className="text-xs text-gray-400 mt-1">Found via Google</p>
                                        </div>
                                    </div>
                                ))}
                                {!summary?.high_intent_leads?.length && !loading && (
                                    <p className="text-center py-8 text-gray-500">No high-intent leads detected yet.</p>
                                )}
                            </CardContent>
                        </Card>

                        {/* Market Research Tool (MCP Integration) */}
                        <Card>
                            <CardHeader>
                                <CardTitle className="flex items-center gap-2">
                                    <Globe className="w-5 h-5 text-purple-600" />
                                    Live Market Research
                                </CardTitle>
                                <CardDescription>Latest trends and competitor analysis via MCP Web Search</CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <div className="flex gap-2">
                                    <Input
                                        placeholder="Ask about competitors, trends, or Local SEO..."
                                        value={researchQuery}
                                        onChange={(e) => setResearchQuery(e.target.value)}
                                        onKeyDown={(e) => e.key === 'Enter' && handleResearch()}
                                    />
                                    <Button onClick={handleResearch} disabled={researching}>
                                        {researching ? <RefreshCw className="animate-spin" /> : <Search className="w-4 h-4" />}
                                    </Button>
                                </div>

                                {researchResult && (
                                    <div className="p-4 bg-purple-50 dark:bg-purple-900/10 border border-purple-100 dark:border-purple-800 rounded-lg animate-in fade-in slide-in-from-top-2">
                                        <h4 className="font-bold text-purple-900 dark:text-purple-300 mb-2">AI Research Summary:</h4>
                                        <p className="text-gray-700 dark:text-gray-300 leading-relaxed italic">
                                            "{researchResult.answer}"
                                        </p>
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </div>

                    {/* Side Panels */}
                    <div className="space-y-6">
                        {/* Channel ROI */}
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-lg">Channel Performance</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-6">
                                {summary?.performance_metrics && Object.entries(summary.performance_metrics).map(([channel, data]: [string, any]) => (
                                    <div key={channel} className="space-y-2">
                                        <div className="flex justify-between items-center">
                                            <span className="capitalize font-medium">{channel.replace('_', ' ')}</span>
                                            <span className="text-sm text-gray-500">{data.calls} calls</span>
                                        </div>
                                        <div className="w-full bg-gray-200 dark:bg-gray-700 h-2 rounded-full overflow-hidden">
                                            <div
                                                className="bg-blue-600 h-full transition-all duration-1000"
                                                style={{ width: `${(data.calls / 15) * 100}%` }}
                                            ></div>
                                        </div>
                                    </div>
                                ))}
                            </CardContent>
                        </Card>

                        {/* Reputation Health */}
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-lg">Reputation Shield</CardTitle>
                            </CardHeader>
                            <CardContent className="text-center space-y-4">
                                <div className="inline-flex p-4 bg-yellow-100 dark:bg-yellow-900/30 rounded-full">
                                    <Star className="w-8 h-8 text-yellow-600 fill-yellow-600" />
                                </div>
                                <div>
                                    <h3 className="text-2xl font-bold">4.8</h3>
                                    <p className="text-sm text-gray-500">Global Review Average</p>
                                </div>
                                <div className="flex justify-between p-3 bg-gray-50 dark:bg-gray-800 rounded-lg text-sm">
                                    <span>Sentiment Score</span>
                                    <span className="text-green-600 font-bold">Positive (92%)</span>
                                </div>
                                <Button variant="outline" className="w-full gap-2 text-blue-600 border-blue-200 hover:bg-blue-50">
                                    <MessageSquare className="w-4 h-4" />
                                    Manage Reviews
                                </Button>
                            </CardContent>
                        </Card>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default MarketingDashboard;
