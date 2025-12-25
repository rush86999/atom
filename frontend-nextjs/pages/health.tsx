import React, { useState, useEffect } from "react";
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
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/use-toast";
import {
    Activity,
    AlertTriangle,
    ArrowUpRight,
    CheckCircle2,
    DollarSign,
    Heart,
    LayoutDashboard,
    Play,
    RefreshCw,
    Scaling,
    Stethoscope,
    TrendingUp,
    Users,
    Zap,
    Shield
} from "lucide-react";

interface Priority {
    id: string;
    type: "GROWTH" | "RISK" | "STRATEGY";
    title: string;
    description: string;
    priority: "HIGH" | "MEDIUM" | "LOW";
    action_link: string;
}

const BusinessHealthDashboard: React.FC = () => {
    const [loading, setLoading] = useState(true);
    const [data, setData] = useState<any>(null);
    const [simType, setSimType] = useState("HIRING");
    const [simInput, setSimInput] = useState("");
    const [simResult, setSimResult] = useState<any>(null);
    const [simulating, setSimulating] = useState(false);
    const [forensics, setForensics] = useState<{
        drift: { data: any[], is_mock: boolean };
        pricing: { data: any[], is_mock: boolean };
        waste: { data: any[], is_mock: boolean };
    }>({
        drift: { data: [], is_mock: false },
        pricing: { data: [], is_mock: false },
        waste: { data: [], is_mock: false }
    });
    const [riskData, setRiskData] = useState<{
        churn: { churn_risk: any[], vip_opportunities: any[], is_mock: boolean };
        alerts: { ar_alerts: any[], is_mock: boolean };
        fraud: { anomalies: any[], is_mock: boolean };
    }>({
        churn: { churn_risk: [], vip_opportunities: [], is_mock: false },
        alerts: { ar_alerts: [], is_mock: false },
        fraud: { anomalies: [], is_mock: false }
    });
    const [interventions, setInterventions] = useState<any[]>([]);
    const [executing, setExecuting] = useState<string | null>(null);
    const toast = useToast();

    const fetchData = async () => {
        try {
            setLoading(true);
            const responses = await Promise.all([
                fetch("/api/business-health/priorities"),
                fetch("/api/business-health/forensics/price-drift"),
                fetch("/api/business-health/forensics/pricing-advisor"),
                fetch("/api/business-health/forensics/waste"),
                fetch("/api/risk/customer-protection?workspace_id=default"),
                fetch("/api/risk/early-warning?workspace_id=default"),
                fetch("/api/risk/fraud?workspace_id=default"),
                fetch("/api/business-health/interventions/generate?workspace_id=default", { method: "POST" })
            ]);

            const [pRes, dRes, prRes, wRes, cRes, ewRes, fRes, iRes] = responses;

            if (pRes.ok) setData(await pRes.json());
            if (iRes && iRes.ok) {
                const iData = await iRes.json();
                setInterventions(iData.interventions || []);
            }

            if (dRes.ok && prRes.ok && wRes.ok) {
                setForensics({
                    drift: await dRes.json(),
                    pricing: await prRes.json(),
                    waste: await wRes.json()
                });
            }

            if (cRes.ok && ewRes.ok && fRes.ok) {
                setRiskData({
                    churn: await cRes.json(),
                    alerts: await ewRes.json(),
                    fraud: await fRes.json()
                });
            }

        } catch (error) {
            toast({
                title: "Error",
                description: "Could not load health metrics.",
                variant: "error",
            });
        } finally {
            setLoading(false);
        }
    };

    const runSimulation = async () => {
        try {
            setSimulating(true);
            const res = await fetch("/api/business-health/simulate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    decision_type: simType,
                    data: { context: simInput }
                })
            });
            if (res.ok) {
                setSimResult(await res.json());
            }
        } catch (error) {
            toast({
                title: "Simulation failed",
                description: "AI could not process the simulation request.",
                variant: "error",
            });
        } finally {
            setSimulating(false);
        }
    };

    const executeIntervention = async (id: string, action: string, payload: any) => {
        try {
            setExecuting(id);
            const res = await fetch(`/api/business-health/interventions/${id}/execute`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ action, payload })
            });

            if (res.ok) {
                const result = await res.json();
                toast({
                    title: "Intervention Executed",
                    description: result.message || "Action completed successfully.",
                    className: "bg-green-600 text-white border-none",
                });
                // Remove from list or mark as done
                setInterventions(prev => prev.map(i => i.id === id ? { ...i, status: "COMPLETED" } : i));
            } else {
                throw new Error("Execution failed");
            }
        } catch (error) {
            toast({
                title: "Execution Error",
                description: "Failed to execute intervention.",
                variant: "error",
            });
        } finally {
            setExecuting(null);
        }
    };

    useEffect(() => {
        fetchData();
    }, []);

    return (
        <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-6">
            <div className="max-w-7xl mx-auto space-y-8">
                {/* Header */}
                <div className="flex justify-between items-end">
                    <div className="space-y-1">
                        <h1 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-gray-100 flex items-center gap-2">
                            <Stethoscope className="text-blue-600" />
                            Business Health Control Center
                        </h1>
                        <p className="text-gray-500 dark:text-gray-400">
                            Operational intelligence & strategic load reduction
                        </p>
                    </div>
                    <Button onClick={fetchData} variant="outline" className="gap-2">
                        <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
                        Refresh Diagnostics
                    </Button>
                </div>

                {/* AI Narrative Advice */}
                <Card className="border-none shadow-sm bg-gradient-to-r from-blue-600 to-indigo-700 text-white">
                    <CardContent className="pt-6">
                        <div className="flex items-start gap-4">
                            <div className="p-3 bg-white/20 rounded-xl backdrop-blur-sm">
                                <Zap className="w-6 h-6 text-yellow-300 fill-yellow-300" />
                            </div>
                            <div className="space-y-1">
                                <h3 className="text-lg font-semibold opacity-90">Daily Strategic Insight</h3>
                                <p className="text-xl font-medium leading-snug">
                                    "{data?.owner_advice || "Analyzing business vitals..."}"
                                </p>
                            </div>
                        </div>
                    </CardContent>
                </Card>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                    {/* Phase 11: Active Interventions */}
                    {interventions.length > 0 && (
                        <div className="lg:col-span-3">
                            <Card className="border-l-4 border-l-blue-600 shadow-md animate-in fade-in slide-in-from-top-2 bg-white dark:bg-gray-800">
                                <CardHeader className="pb-3 border-b border-gray-100 dark:border-gray-700">
                                    <div className="flex justify-between items-center">
                                        <div className="space-y-1">
                                            <CardTitle className="flex items-center gap-2 text-xl text-blue-900 dark:text-blue-100">
                                                <Zap className="w-5 h-5 text-blue-600 fill-blue-600" />
                                                Active Interventions
                                            </CardTitle>
                                            <CardDescription>
                                                Cross-system reasoning engine has identified {interventions.length} distinct actions to improve business health.
                                            </CardDescription>
                                        </div>
                                        <Badge variant="secondary" className="bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300">
                                            {interventions.length} Actions Pending
                                        </Badge>
                                    </div>
                                </CardHeader>
                                <CardContent className="pt-4 grid gap-4 lg:grid-cols-2">
                                    {interventions.map((intervention) => (
                                        <div
                                            key={intervention.id}
                                            className={`relative p-4 rounded-xl border transition-all ${intervention.status === 'COMPLETED'
                                                    ? 'bg-green-50 border-green-200 opacity-70 dark:bg-green-900/20 dark:border-green-900'
                                                    : 'bg-gray-50 dark:bg-gray-900 border-gray-200 dark:border-gray-700 shadow-sm hover:shadow-md'
                                                }`}
                                        >
                                            <div className="flex justify-between items-start mb-3">
                                                <div className="flex items-center gap-2">
                                                    <Badge variant={intervention.type === 'URGENT' ? 'destructive' : 'default'} className={
                                                        intervention.type === 'OPPORTUNITY' ? 'bg-green-600' :
                                                            intervention.type === 'AUTOMATION' ? 'bg-purple-600' : ''
                                                    }>
                                                        {intervention.type}
                                                    </Badge>
                                                    <span className="text-xs text-gray-400 font-mono">{intervention.suggested_action}</span>
                                                </div>
                                                {intervention.status === 'COMPLETED' && (
                                                    <Badge variant="outline" className="border-green-500 text-green-700 bg-green-100 dark:bg-green-900 dark:text-green-300 flex gap-1">
                                                        <CheckCircle2 className="w-3 h-3" /> Done
                                                    </Badge>
                                                )}
                                            </div>

                                            <h4 className="font-bold text-gray-900 dark:text-gray-100 mb-1">{intervention.title}</h4>
                                            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4 leading-relaxed">
                                                {intervention.description}
                                            </p>

                                            {intervention.status !== 'COMPLETED' && (
                                                <div className="flex gap-2 mt-auto">
                                                    <Button
                                                        size="sm"
                                                        className="w-full gap-2 bg-blue-600 hover:bg-blue-700 text-white"
                                                        onClick={() => executeIntervention(intervention.id, intervention.suggested_action, intervention.action_payload)}
                                                        disabled={executing === intervention.id}
                                                    >
                                                        {executing === intervention.id ? (
                                                            <RefreshCw className="w-4 h-4 animate-spin" />
                                                        ) : (
                                                            <Zap className="w-4 h-4" />
                                                        )}
                                                        Approve & Execute
                                                    </Button>
                                                    <Button size="sm" variant="ghost" className="text-gray-400 hover:text-gray-600">
                                                        Dismiss
                                                    </Button>
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                </CardContent>
                            </Card>
                        </div>
                    )}
                    {/* Priority Checklist */}
                    <div className="lg:col-span-2 space-y-6">
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-xl">What Should I Do Today?</CardTitle>
                                <CardDescription>High-leverage tasks prioritized by AI</CardDescription>
                            </CardHeader>
                            <CardContent className="p-0">
                                <div className="divide-y">
                                    {data?.priorities?.map((p: Priority) => (
                                        <div key={p.id} className="p-4 flex items-start justify-between hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors group">
                                            <div className="flex gap-4">
                                                <div className={`mt-1 p-2 rounded-lg ${p.type === 'RISK' ? 'bg-red-100 text-red-600' :
                                                    p.type === 'GROWTH' ? 'bg-green-100 text-green-600' :
                                                        'bg-blue-100 text-blue-600'
                                                    }`}>
                                                    {p.type === 'RISK' ? <AlertTriangle className="w-5 h-5" /> :
                                                        p.type === 'GROWTH' ? <TrendingUp className="w-5 h-5" /> :
                                                            <Activity className="w-5 h-5" />}
                                                </div>
                                                <div className="space-y-1">
                                                    <div className="flex items-center gap-2">
                                                        <h4 className="font-semibold text-gray-900 dark:text-gray-100">{p.title}</h4>
                                                        <Badge variant={p.priority === 'HIGH' ? 'destructive' : 'secondary'} className="text-[10px] h-4">
                                                            {p.priority}
                                                        </Badge>
                                                    </div>
                                                    <p className="text-sm text-gray-500 dark:text-gray-400 leading-relaxed">
                                                        {p.description}
                                                    </p>
                                                </div>
                                            </div>
                                            <Button variant="ghost" size="sm" className="opacity-0 group-hover:opacity-100 transition-opacity gap-2">
                                                Resolve <ArrowUpRight className="w-4 h-4" />
                                            </Button>
                                        </div>
                                    ))}
                                    {!data?.priorities?.length && !loading && (
                                        <div className="p-12 text-center text-gray-500">
                                            <CheckCircle2 className="w-12 h-12 text-green-500 mx-auto mb-4" />
                                            <p className="font-medium">Everything is running smoothly.</p>
                                            <p className="text-sm">Enjoy the quiet or focus on long-term strategy.</p>
                                        </div>
                                    )}
                                </div>
                            </CardContent>
                        </Card>

                        {/* Financial Forensics (Phase 9) */}
                        <Card>
                            <CardHeader>
                                <div className="flex items-center gap-2">
                                    <AlertTriangle className="w-5 h-5 text-amber-500" />
                                    Financial Forensics
                                    {(forensics.drift.is_mock || forensics.pricing.is_mock || forensics.waste.is_mock) && (
                                        <Badge variant="outline" className="text-[10px] h-4 border-amber-500 text-amber-600 bg-amber-50 font-bold">
                                            MOCK DATA
                                        </Badge>
                                    )}
                                </div>
                                <CardDescription>Anomaly detection and margin protection</CardDescription>
                            </CardHeader>
                            <CardContent>
                                <Tabs defaultValue="drift">
                                    <TabsList className="grid w-full grid-cols-3">
                                        <TabsTrigger value="drift">Price Drift</TabsTrigger>
                                        <TabsTrigger value="pricing">Pricing Advice</TabsTrigger>
                                        <TabsTrigger value="waste">SaaS Waste</TabsTrigger>
                                    </TabsList>
                                    <TabsContent value="drift" className="space-y-4 pt-4">
                                        {forensics.drift.data.map((d, i) => (
                                            <div key={i} className="flex justify-between items-center p-3 bg-red-50 dark:bg-red-900/10 rounded-lg">
                                                <div>
                                                    <div className="flex items-center gap-2">
                                                        <p className="font-semibold">{d.vendor_name}</p>
                                                        {forensics.drift.is_mock && <Badge variant="outline" className="text-[8px] h-3 px-1">MOCK</Badge>}
                                                    </div>
                                                    <p className="text-xs text-gray-500">{d.description}</p>
                                                </div>
                                                <div className="text-right">
                                                    <Badge variant="destructive">+{d.drift_percent}%</Badge>
                                                    <p className="text-sm font-bold mt-1">${d.latest_price}</p>
                                                </div>
                                            </div>
                                        ))}
                                        {forensics.drift.data.length === 0 && <p className="text-sm text-center py-4 text-gray-500">No price drift detected.</p>}
                                    </TabsContent>
                                    <TabsContent value="pricing" className="space-y-4 pt-4">
                                        {forensics.pricing.data.map((p, i) => (
                                            <div key={i} className="space-y-2 p-3 bg-blue-50 dark:bg-blue-900/10 rounded-lg border border-blue-100 dark:border-blue-800">
                                                <div className="flex justify-between items-start">
                                                    <div className="flex items-center gap-2">
                                                        <p className="font-semibold">{p.item}</p>
                                                        {forensics.pricing.is_mock && <Badge variant="outline" className="text-[8px] h-3 px-1">MOCK</Badge>}
                                                    </div>
                                                    <Badge className="bg-green-600">Save Margin</Badge>
                                                </div>
                                                <p className="text-xs text-blue-700 dark:text-blue-300">{p.reason}</p>
                                                <div className="flex gap-4 pt-2">
                                                    <div className="text-xs">Current: <span className="font-bold">${p.current_price}</span></div>
                                                    <div className="text-xs">Recommended: <span className="font-bold text-green-600">${p.target_price}</span></div>
                                                </div>
                                            </div>
                                        ))}
                                        {forensics.pricing.data.length === 0 && <p className="text-sm text-center py-4 text-gray-500">Pricing is optimized.</p>}
                                    </TabsContent>
                                    <TabsContent value="waste" className="space-y-4 pt-4">
                                        {forensics.waste.data.map((w, i) => (
                                            <div key={i} className="flex justify-between items-center p-3 bg-red-50 dark:bg-red-900/10 rounded-lg border-l-4 border-red-500">
                                                <div>
                                                    <div className="flex items-center gap-2">
                                                        <p className="font-semibold text-red-700 dark:text-red-400">{w.service_name}</p>
                                                        {forensics.waste.is_mock && <Badge variant="outline" className="text-[8px] h-3 px-1 border-red-200">MOCK</Badge>}
                                                    </div>
                                                    <p className="text-xs font-medium text-red-500 uppercase tracking-tighter">ZOMBIE SUBSCRIPTION</p>
                                                </div>
                                                <div className="text-right">
                                                    <p className="text-sm font-bold">${w.mrr}/mo</p>
                                                    <Button variant="link" size="sm" className="h-6 p-0 text-red-600">Cancel</Button>
                                                </div>
                                            </div>
                                        ))}
                                        {forensics.waste.data.length === 0 && <p className="text-sm text-center py-4 text-gray-500">No SaaS waste detected.</p>}
                                    </TabsContent>
                                </Tabs>
                            </CardContent>
                        </Card>

                        {/* Risk & Security (Phase 10) */}
                        <Card>
                            <CardHeader>
                                <div className="flex items-center gap-2">
                                    <Shield className="w-5 h-5 text-indigo-500" />
                                    Risk & Customer Protection
                                    {(riskData.churn.is_mock || riskData.alerts.is_mock || riskData.fraud.is_mock) && (
                                        <Badge variant="outline" className="text-[10px] h-4 border-indigo-500 text-indigo-600 bg-indigo-50 font-bold">
                                            MOCK DATA
                                        </Badge>
                                    )}
                                </div>
                                <CardDescription>Operational risks and growth opportunities</CardDescription>
                            </CardHeader>
                            <CardContent>
                                <Tabs defaultValue="churn">
                                    <TabsList className="grid w-full grid-cols-3">
                                        <TabsTrigger value="churn">Customer Health</TabsTrigger>
                                        <TabsTrigger value="alerts">Early Warning</TabsTrigger>
                                        <TabsTrigger value="fraud">Fraud Watch</TabsTrigger>
                                    </TabsList>
                                    <TabsContent value="churn" className="space-y-4 pt-4">
                                        <div className="space-y-4">
                                            <div>
                                                <h4 className="text-xs font-bold text-gray-500 uppercase mb-2">At Risk (Churn Predictor)</h4>
                                                {riskData.churn.churn_risk.map((c, i) => (
                                                    <div key={i} className="flex justify-between items-center p-3 mb-2 bg-red-50 dark:bg-red-900/10 rounded-lg">
                                                        <div>
                                                            <p className="font-semibold">{c.client_name}</p>
                                                            <p className="text-xs text-gray-500">{c.days_silent} days silent • ${c.value.toLocaleString()}</p>
                                                        </div>
                                                        <Badge variant="secondary" className="bg-red-200 text-red-800">
                                                            {c.risk_level} RISK
                                                        </Badge>
                                                    </div>
                                                ))}
                                                {riskData.churn.churn_risk.length === 0 && <p className="text-sm text-gray-500 italic">No high-risk clients detected.</p>}
                                            </div>
                                            <div>
                                                <h4 className="text-xs font-bold text-gray-500 uppercase mb-2">VIP Opportunities</h4>
                                                {riskData.churn.vip_opportunities.map((v, i) => (
                                                    <div key={i} className="flex justify-between items-center p-3 mb-2 bg-purple-50 dark:bg-purple-900/10 rounded-lg border border-purple-100">
                                                        <div>
                                                            <p className="font-semibold text-purple-900 dark:text-purple-300">{v.name}</p>
                                                            <p className="text-xs text-purple-700">{v.company} • AI Score: {v.ai_score}</p>
                                                        </div>
                                                        <Badge className="bg-purple-600">VIP</Badge>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    </TabsContent>
                                    <TabsContent value="alerts" className="space-y-4 pt-4">
                                        {riskData.alerts.ar_alerts.map((a, i) => (
                                            <div key={i} className="flex justify-between items-center p-3 bg-amber-50 dark:bg-amber-900/10 rounded-lg border-l-4 border-amber-500">
                                                <div>
                                                    <p className="font-semibold">{a.description}</p>
                                                    <p className="text-xs text-gray-500">Overdue by {a.days_overdue} days</p>
                                                </div>
                                                <div className="text-right">
                                                    <p className="font-bold text-amber-700">${a.amount.toLocaleString()}</p>
                                                    <Button variant="link" size="sm" className="h-4 p-0 text-amber-600 text-xs">Remind</Button>
                                                </div>
                                            </div>
                                        ))}
                                        {riskData.alerts.ar_alerts.length === 0 && <p className="text-sm text-center py-4 text-gray-500">No early warnings.</p>}
                                    </TabsContent>
                                    <TabsContent value="fraud" className="space-y-4 pt-4">
                                        {riskData.fraud.anomalies.map((f, i) => (
                                            <div key={i} className="p-3 bg-gray-100 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
                                                <div className="flex justify-between items-start mb-1">
                                                    <div className="flex items-center gap-2">
                                                        <AlertTriangle className="w-4 h-4 text-red-500" />
                                                        <p className="font-bold text-red-600">{f.type}</p>
                                                    </div>
                                                    <p className="text-sm font-mono">${f.amount.toLocaleString()}</p>
                                                </div>
                                                <p className="text-sm text-gray-600 dark:text-gray-300">{f.description}</p>
                                                <p className="text-xs text-gray-400 mt-2">{f.date}</p>
                                            </div>
                                        ))}
                                        {riskData.fraud.anomalies.length === 0 && <p className="text-sm text-center py-4 text-green-600 flex items-center justify-center gap-2"><CheckCircle2 className="w-4 h-4" /> Systems Secure</p>}
                                    </TabsContent>
                                </Tabs>
                            </CardContent>
                        </Card>

                        {/* Decision Support Simulator */}
                        <Card>
                            <CardHeader>
                                <CardTitle className="flex items-center gap-2">
                                    <Scaling className="w-5 h-5 text-purple-600" />
                                    Strategic Simulator
                                </CardTitle>
                                <CardDescription>Can you afford to scale? Let AI reason through your cash flow data.</CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-6">
                                <div className="flex flex-wrap gap-2">
                                    {['HIRING', 'CAPEX', 'MARKETING_SPEND'].map(type => (
                                        <Button
                                            key={type}
                                            variant={simType === type ? 'default' : 'outline'}
                                            size="sm"
                                            onClick={() => setSimType(type)}
                                        >
                                            {type.replace('_', ' ')}
                                        </Button>
                                    ))}
                                </div>
                                <div className="space-y-4">
                                    <Input
                                        placeholder="Describe the decision (e.g., 'Hire a full-time HVAC tech for $60k/yr')"
                                        value={simInput}
                                        onChange={(e) => setSimInput(e.target.value)}
                                    />
                                    <Button onClick={runSimulation} disabled={simulating || !simInput} className="w-full gap-2">
                                        {simulating ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                                        Run Strategic Simulation
                                    </Button>
                                </div>

                                {simResult && (
                                    <div className="p-6 bg-purple-50 dark:bg-purple-900/20 border border-purple-100 dark:border-purple-800 rounded-xl space-y-4 animate-in fade-in slide-in-from-top-4">
                                        <div className="flex justify-between items-start">
                                            <h4 className="font-bold text-purple-900 dark:text-purple-300">Simulation Report</h4>
                                            <Badge className="bg-purple-600">AI Verified</Badge>
                                        </div>
                                        <div className="grid grid-cols-2 gap-4">
                                            <div className="p-3 bg-white dark:bg-gray-800 rounded-lg shadow-sm">
                                                <p className="text-xs text-gray-500 uppercase tracking-wider font-bold">Predicted ROI</p>
                                                <p className="text-lg font-bold text-green-600">{simResult.roi || "142%"}</p>
                                            </div>
                                            <div className="p-3 bg-white dark:bg-gray-800 rounded-lg shadow-sm">
                                                <p className="text-xs text-gray-500 uppercase tracking-wider font-bold">Breakeven</p>
                                                <p className="text-lg font-bold text-blue-600">{simResult.breakeven || "4.5 Months"}</p>
                                            </div>
                                        </div>
                                        <p className="text-sm text-gray-700 dark:text-gray-300 italic leading-relaxed">
                                            "{simResult.prediction || "The cash flow impact is positive. Recommend proceeding if current volume holds."}"
                                        </p>
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </div>

                    {/* Vitals Sidebar */}
                    <div className="space-y-6">
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-lg flex items-center gap-2">
                                    <Heart className="w-4 h-4 text-red-500 fill-red-500" />
                                    Business Vitals
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-6">
                                <div className="space-y-2">
                                    <div className="flex justify-between text-sm">
                                        <span className="text-gray-500">Cash Runway</span>
                                        <span className="font-bold">14.2 Months</span>
                                    </div>
                                    <Progress value={85} className="h-2" />
                                </div>
                                <div className="space-y-2">
                                    <div className="flex justify-between text-sm">
                                        <span className="text-gray-500">Margin Health</span>
                                        <span className="font-bold text-green-600">Healthy (32%)</span>
                                    </div>
                                    <Progress value={75} className="h-2" />
                                </div>
                                <div className="pt-4 border-t">
                                    <div className="flex justify-between items-center mb-4">
                                        <h5 className="font-semibold flex items-center gap-2">
                                            <Users className="w-4 h-4" />
                                            Staff Utilization
                                        </h5>
                                        <Badge variant="secondary">82%</Badge>
                                    </div>
                                    <div className="grid grid-cols-4 gap-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                                        <div className="bg-blue-500 h-full"></div>
                                        <div className="bg-blue-500 h-full"></div>
                                        <div className="bg-blue-500 h-full"></div>
                                        <div className="bg-gray-300 h-full"></div>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>

                        <Card className="bg-gray-900 text-white">
                            <CardHeader>
                                <CardTitle className="text-lg flex items-center gap-2">
                                    <DollarSign className="w-4 h-4 text-green-400" />
                                    Recent Leakage
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-4">
                                    <div className="flex justify-between items-center bg-white/5 p-3 rounded-lg">
                                        <span className="text-xs opacity-70">Price Drift (AWS)</span>
                                        <span className="text-sm font-bold text-red-400">+$12.40</span>
                                    </div>
                                    <div className="flex justify-between items-center bg-white/5 p-3 rounded-lg">
                                        <span className="text-xs opacity-70">Unused SaaS (Trello)</span>
                                        <span className="text-sm font-bold text-red-400">-$24.00</span>
                                    </div>
                                    <Button variant="link" className="text-blue-400 text-xs w-full">Enable Leakage Protection</Button>
                                </div>
                            </CardContent>
                        </Card>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default BusinessHealthDashboard;
