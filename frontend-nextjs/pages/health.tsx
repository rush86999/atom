import React, { useState, useEffect, useCallback } from "react";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/use-toast";
import {
    Activity,
    AlertTriangle,
    ArrowUpRight,
    CheckCircle2,
    DollarSign,
    LayoutDashboard,
    Play,
    RefreshCw,
    Scaling,
    Stethoscope,
    TrendingUp,
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

/**
 * Risk endpoints have two published shapes: the live contracts (recorded
 * cancellations, overdue invoices, refunds) and the demo/mock mode payloads
 * that predate them. Amounts and dates must never be invented, so anything
 * unusable renders as "unavailable" instead of $0 or NaN.
 */
const formatAmount = (value: unknown): string | null => {
    let numeric: number;
    if (typeof value === "number") {
        numeric = value;
    } else if (typeof value === "string" && value.trim() !== "") {
        numeric = Number(value);
    } else {
        return null;
    }
    if (!Number.isFinite(numeric) || numeric < 0) return null;
    return `$${numeric.toLocaleString("en-US", { maximumFractionDigits: 2 })}`;
};

const formatDays = (value: unknown): number | null =>
    typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : null;

const formatProbability = (value: unknown): string | null => {
    if (typeof value !== "number" || !Number.isFinite(value)) return null;
    const percent = value >= 0 && value <= 1 ? value * 100 : value;
    if (percent < 0 || percent > 100) return null;
    return `${Math.round(percent)}%`;
};

const formatScore = (value: unknown): string | null =>
    typeof value === "number" && Number.isFinite(value) && value >= 0
        ? `${Math.round(value)}`
        : null;

const formatDate = (value: unknown): string | null => {
    let input: string | number;
    if (typeof value === "string") {
        const trimmed = value.trim();
        if (trimmed === "") return null;
        // Recorded timestamps may be naive UTC (datetime.utcnow().isoformat());
        // anchor them to UTC so the rendered day does not shift by timezone.
        const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(trimmed);
        input = /^\d{4}-\d{2}-\d{2}T/.test(trimmed) && !hasZone ? `${trimmed}Z` : trimmed;
    } else if (typeof value === "number") {
        input = value;
    } else {
        return null;
    }
    const date = new Date(input);
    if (Number.isNaN(date.getTime())) return null;
    return date.toLocaleDateString("en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
        timeZone: "UTC",
    });
};

const hasField = (item: any, field: string) =>
    item !== null && typeof item === "object" && field in item;

const isRecordedChurn = (item: any) =>
    hasField(item, "customer_name") ||
    hasField(item, "mrr_at_risk") ||
    hasField(item, "churn_probability");

const isRecordedArAlert = (item: any) =>
    hasField(item, "invoice_id") ||
    hasField(item, "due_date") ||
    hasField(item, "likelihood_late");

const isRecordedFraudAlert = (item: any) =>
    hasField(item, "transaction_id") ||
    hasField(item, "timestamp") ||
    hasField(item, "flag_reason");

const nonEmptyString = (value: unknown): string | null =>
    typeof value === "string" && value.trim() !== "" ? value.trim() : null;

const recordedFraudLabel = (type: unknown): string => {
    const label = nonEmptyString(type);
    if (!label) return "Recorded anomaly";
    const normalized = label.toUpperCase();
    if (normalized === "REFUNDED" || normalized === "REFUND") return "Refund recorded";
    if (normalized === "CHARGEBACK") return "Chargeback recorded";
    return `${label} recorded`;
};

const readRiskList = (payload: any, key: string): any[] | null =>
    Array.isArray(payload?.[key]) ? payload[key] : null;

const riskBody = async (response: Response | null): Promise<any | null> => {
    if (!response) return null;
    try {
        return await response.json();
    } catch {
        return null;
    }
};

const BusinessHealthDashboard: React.FC = () => {
    const [loading, setLoading] = useState(true);
    const [data, setData] = useState<any>(null);
    const [prioritiesUnavailable, setPrioritiesUnavailable] = useState(false);
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
        churn: { churn_risk: any[], vip_opportunities: any[], is_mock: boolean, error: boolean };
        alerts: { ar_alerts: any[], is_mock: boolean, error: boolean };
        fraud: { anomalies: any[], is_mock: boolean, error: boolean };
    }>({
        churn: { churn_risk: [], vip_opportunities: [], is_mock: false, error: false },
        alerts: { ar_alerts: [], is_mock: false, error: false },
        fraud: { anomalies: [], is_mock: false, error: false }
    });
    const [interventions, setInterventions] = useState<any[]>([]);
    const [executing, setExecuting] = useState<string | null>(null);
    const { toast } = useToast();

    const fetchData = useCallback(async () => {
        try {
            setLoading(true);
            // Every operational endpoint requires the signed-in bearer token;
            // the page used to fetch without one and rendered a 401 as an
            // empty dashboard. Use one helper so the whole page agrees.
            const token =
                typeof window !== "undefined"
                    ? localStorage.getItem("auth_token") || localStorage.getItem("token")
                    : null;
            const auth = token ? { Authorization: `Bearer ${token}` } : {};
            const get = (url: string, init?: RequestInit) =>
                fetch(url, { ...init, headers: { ...auth, ...(init?.headers || {}) } });
            // Use Promise.allSettled so one failed endpoint doesn't blank the
            // entire dashboard — each result is checked independently (BUG-063).
            // Workspace is derived server-side from the authenticated user.
            const results = await Promise.allSettled([
                get("/api/business-health/priorities"),
                get("/api/business-health/forensics/price-drift"),
                get("/api/business-health/forensics/pricing-advisor"),
                get("/api/business-health/forensics/waste"),
                get("/api/risk/customer-protection"),
                get("/api/risk/early-warning"),
                get("/api/risk/fraud"),
                get("/api/business-health/interventions/generate", { method: "POST" })
            ]);

            const settled = (r: PromiseSettledResult<Response>) =>
                r.status === "fulfilled" && r.value.ok ? r.value : null;

            const [pR, dR, prR, wR, cR, ewR, fR, iR] = results;
            const pRes = settled(pR), dRes = settled(dR), prRes = settled(prR),
                  wRes = settled(wR), cRes = settled(cR), ewRes = settled(ewR),
                  fRes = settled(fR), iRes = settled(iR);

            // The operational endpoints return the standard envelope
            // ({ success, data, metadata?, timestamp }), while the risk
            // endpoints below return raw objects. Read each contract as-is.
            if (pRes) {
                try {
                    const body = await pRes.json();
                    // `data` is the priorities payload; keep accepting a bare
                    // payload for older servers.
                    setData(body && typeof body === "object" && "data" in body ? body.data : body);
                    setPrioritiesUnavailable(false);
                } catch {
                    setData(null);
                    setPrioritiesUnavailable(true);
                }
            } else {
                setData(null);
                setPrioritiesUnavailable(true);
            }
            if (iRes) {
                try {
                    const iData = await iRes.json();
                    // Generate returns the envelope with the intervention list
                    // directly under `data`.
                    setInterventions(Array.isArray(iData?.data) ? iData.data : []);
                } catch {}
            }

            if (dRes && prRes && wRes) {
                try {
                    const drift = await dRes.json();
                    const pricing = await prRes.json();
                    const waste = await wRes.json();
                    // Forensics mock flags live under the response metadata.
                    const list = (payload: any) =>
                        Array.isArray(payload?.data) ? payload.data : [];
                    setForensics({
                        drift: { data: list(drift), is_mock: drift?.metadata?.is_mock ?? false },
                        pricing: { data: list(pricing), is_mock: pricing?.metadata?.is_mock ?? false },
                        waste: { data: list(waste), is_mock: waste?.metadata?.is_mock ?? false }
                    });
                } catch {}
            }

            // Each risk endpoint is read independently so one failed tab does
            // not hide healthy data from the others, and an unreachable
            // endpoint is reported as unavailable rather than "no risk".
            const [churnBody, alertsBody, fraudBody] = await Promise.all([
                riskBody(cRes),
                riskBody(ewRes),
                riskBody(fRes)
            ]);
            const churnRisks = readRiskList(churnBody, "churn_risk");
            const arAlerts = readRiskList(alertsBody, "ar_alerts");
            const anomalies = readRiskList(fraudBody, "anomalies");
            setRiskData({
                churn: {
                    churn_risk: churnRisks ?? [],
                    vip_opportunities: readRiskList(churnBody, "vip_opportunities") ?? [],
                    is_mock: churnBody?.is_mock === true,
                    error: churnRisks === null
                },
                alerts: {
                    ar_alerts: arAlerts ?? [],
                    is_mock: alertsBody?.is_mock === true,
                    error: arAlerts === null
                },
                fraud: {
                    anomalies: anomalies ?? [],
                    is_mock: fraudBody?.is_mock === true,
                    error: anomalies === null
                }
            });

        } catch (error) {
            toast({
                title: "Error",
                description: "Could not load health metrics.",
                variant: "error",
            });
        } finally {
            setLoading(false);
        }
    }, [toast]);

    const runSimulation = async () => {
        try {
            setSimulating(true);
            const token = typeof window !== "undefined" ? (localStorage.getItem("auth_token") || localStorage.getItem("token")) : null;
            const res = await fetch("/api/business-health/simulate", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    ...(token ? { Authorization: `Bearer ${token}` } : {}),
                },
                body: JSON.stringify({
                    decision_type: simType,
                    data: { context: simInput }
                })
            });
            if (res.ok) {
                setSimResult(await res.json());
            } else {
                toast({ title: "Simulation failed", description: `Simulation returned ${res.status}.`, variant: "error" });
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
            const token = typeof window !== "undefined" ? (localStorage.getItem("auth_token") || localStorage.getItem("token")) : null;
            const res = await fetch(`/api/business-health/interventions/${id}/execute`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    ...(token ? { Authorization: `Bearer ${token}` } : {}),
                },
                body: JSON.stringify({ action, payload })
            });

            if (res.ok) {
                const result = await res.json();
                toast({
                    title: "Intervention Executed",
                    description: result.message || "Action completed successfully.",
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
    }, [fetchData]);

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
                            <div className="p-3 bg-black/5 dark:bg-black/20 dark:bg-white/20 rounded-xl backdrop-blur-sm">
                                <Zap className="w-6 h-6 text-yellow-300 fill-yellow-300" />
                            </div>
                            <div className="space-y-1">
                                <h3 className="text-lg font-semibold opacity-90">Daily Strategic Insight</h3>
                                <p className="text-xl font-medium leading-snug">
                                    &quot;{prioritiesUnavailable
                                        ? "Business priorities are temporarily unavailable."
                                        : data?.owner_advice || (loading
                                            ? "Analyzing business vitals..."
                                            : "No strategic advice available.")}&quot;
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
                                                    <Button size="sm" variant="ghost" className="text-gray-400 hover:text-gray-600 dark:text-gray-400">
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
                                        <div key={p.id} className="p-4 flex items-start justify-between hover:bg-gray-50 dark:bg-gray-800 dark:hover:bg-gray-800/50 transition-colors group">
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
                                    {prioritiesUnavailable && (
                                        <div className="p-12 text-center text-gray-500 dark:text-gray-400">
                                            <AlertTriangle className="w-12 h-12 text-amber-500 mx-auto mb-4" />
                                            <p className="font-medium">Priorities unavailable.</p>
                                            <p className="text-sm">We couldn&apos;t load today&apos;s priorities. Refresh Diagnostics to try again.</p>
                                        </div>
                                    )}
                                    {!prioritiesUnavailable && !data?.priorities?.length && !loading && (
                                        <div className="p-12 text-center text-gray-500 dark:text-gray-400">
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
                                                    <p className="text-xs text-gray-500 dark:text-gray-400">{d.description}</p>
                                                </div>
                                                <div className="text-right">
                                                    <Badge variant="destructive">+{d.drift_percent}%</Badge>
                                                    <p className="text-sm font-bold mt-1">${d.latest_price}</p>
                                                </div>
                                            </div>
                                        ))}
                                        {forensics.drift.data.length === 0 && <p className="text-sm text-center py-4 text-gray-500 dark:text-gray-400">No price drift detected.</p>}
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
                                        {forensics.pricing.data.length === 0 && <p className="text-sm text-center py-4 text-gray-500 dark:text-gray-400">Pricing is optimized.</p>}
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
                                        {forensics.waste.data.length === 0 && <p className="text-sm text-center py-4 text-gray-500 dark:text-gray-400">No SaaS waste detected.</p>}
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
                                        {riskData.churn.error ? (
                                            <div className="p-4 text-center text-amber-700 dark:text-amber-400">
                                                <AlertTriangle className="w-6 h-6 mx-auto mb-2" />
                                                <p className="text-sm font-medium">Customer health data is unavailable.</p>
                                                <p className="text-xs">Refresh Diagnostics to try again.</p>
                                            </div>
                                        ) : (
                                            <div className="space-y-4">
                                                <div>
                                                    <h4 className="text-xs font-bold text-gray-500 dark:text-gray-400 uppercase mb-2">
                                                        {riskData.churn.is_mock ? "At Risk (Churn Predictor)" : "At Risk (Recorded Churn Signals)"}
                                                    </h4>
                                                    {riskData.churn.churn_risk.map((c, i) => {
                                                        if (!c || typeof c !== "object") return null;
                                                        if (isRecordedChurn(c)) {
                                                            const name = nonEmptyString(c.customer_name) ?? "Recorded customer";
                                                            const probability = formatProbability(c.churn_probability);
                                                            const amount = formatAmount(c.mrr_at_risk);
                                                            const factors = Array.isArray(c.risk_factors)
                                                                ? c.risk_factors.filter((factor: any) => nonEmptyString(factor))
                                                                : [];
                                                            const recommendedAction = nonEmptyString(c.recommended_action);
                                                            return (
                                                                <div key={`churn-${i}`} className="flex justify-between items-start gap-3 p-3 mb-2 bg-red-50 dark:bg-red-900/10 rounded-lg">
                                                                    <div className="min-w-0 space-y-1">
                                                                        <div className="flex items-center gap-2 flex-wrap">
                                                                            <p className="font-semibold">{name}</p>
                                                                            <Badge variant="outline" className="text-[9px] h-4 px-1 border-red-300 text-red-700 bg-white/60 dark:bg-transparent">RECORDED</Badge>
                                                                        </div>
                                                                        <p className="text-xs text-gray-500 dark:text-gray-400">
                                                                            Recorded cancellation{probability ? ` • Churn signal ${probability}` : ""}
                                                                        </p>
                                                                        {factors.length > 0 && (
                                                                            <p className="text-xs text-gray-500 dark:text-gray-400">{factors.join(" • ")}</p>
                                                                        )}
                                                                        <p className="text-xs text-gray-600 dark:text-gray-300">
                                                                            MRR at risk: {amount ?? "unavailable"}
                                                                        </p>
                                                                        {recommendedAction && (
                                                                            <p className="text-xs text-gray-500 dark:text-gray-400">{recommendedAction}</p>
                                                                        )}
                                                                    </div>
                                                                    <Badge variant="secondary" className="bg-red-200 text-red-800 whitespace-nowrap">
                                                                        CANCELED
                                                                    </Badge>
                                                                </div>
                                                            );
                                                        }
                                                        const name = nonEmptyString(c.client_name) ?? "At-risk client";
                                                        const days = formatDays(c.days_silent);
                                                        const amount = formatAmount(c.value);
                                                        const riskLevel = nonEmptyString(c.risk_level);
                                                        return (
                                                            <div key={`churn-${i}`} className="flex justify-between items-center gap-3 p-3 mb-2 bg-red-50 dark:bg-red-900/10 rounded-lg">
                                                                <div className="min-w-0">
                                                                    <p className="font-semibold">{name}</p>
                                                                    <p className="text-xs text-gray-500 dark:text-gray-400">
                                                                        {days !== null ? `${days} days silent` : "Activity unavailable"} • {amount ?? "Amount unavailable"}
                                                                    </p>
                                                                </div>
                                                                <Badge variant="secondary" className="bg-red-200 text-red-800 whitespace-nowrap">
                                                                    {riskLevel ? `${riskLevel} RISK` : "AT RISK"}
                                                                </Badge>
                                                            </div>
                                                        );
                                                    })}
                                                    {riskData.churn.churn_risk.length === 0 && <p className="text-sm text-gray-500 dark:text-gray-400 italic">No high-risk clients detected.</p>}
                                                </div>
                                                <div>
                                                    <h4 className="text-xs font-bold text-gray-500 dark:text-gray-400 uppercase mb-2">VIP Opportunities</h4>
                                                    {riskData.churn.vip_opportunities.map((v, i) => {
                                                        if (!v || typeof v !== "object") return null;
                                                        const name = nonEmptyString(v.name) ?? "Opportunity";
                                                        const company = nonEmptyString(v.company);
                                                        const score = formatScore(v.ai_score);
                                                        return (
                                                            <div key={`vip-${i}`} className="flex justify-between items-center p-3 mb-2 bg-purple-50 dark:bg-purple-900/10 rounded-lg border border-purple-100">
                                                                <div>
                                                                    <p className="font-semibold text-purple-900 dark:text-purple-300">{name}</p>
                                                                    <p className="text-xs text-purple-700 dark:text-purple-300">
                                                                        {company ? `${company} • ` : ""}AI Score: {score ?? "unavailable"}
                                                                    </p>
                                                                </div>
                                                                <Badge className="bg-purple-600">VIP</Badge>
                                                            </div>
                                                        );
                                                    })}
                                                    {riskData.churn.vip_opportunities.length === 0 && <p className="text-sm text-gray-500 dark:text-gray-400 italic">No VIP opportunities recorded.</p>}
                                                </div>
                                            </div>
                                        )}
                                    </TabsContent>
                                    <TabsContent value="alerts" className="space-y-4 pt-4">
                                        {riskData.alerts.error ? (
                                            <div className="p-4 text-center text-amber-700 dark:text-amber-400">
                                                <AlertTriangle className="w-6 h-6 mx-auto mb-2" />
                                                <p className="text-sm font-medium">Early warning data is unavailable.</p>
                                                <p className="text-xs">Refresh Diagnostics to try again.</p>
                                            </div>
                                        ) : (
                                            <>
                                                {riskData.alerts.ar_alerts.map((a, i) => {
                                                    if (!a || typeof a !== "object") return null;
                                                    const amount = formatAmount(a.amount);
                                                    if (isRecordedArAlert(a)) {
                                                        const name = nonEmptyString(a.client_name) ?? "Recorded invoice";
                                                        const invoiceId = nonEmptyString(a.invoice_id);
                                                        const due = formatDate(a.due_date);
                                                        const reason = nonEmptyString(a.reason);
                                                        return (
                                                            <div key={`ar-${i}`} className="flex justify-between items-start gap-3 p-3 bg-amber-50 dark:bg-amber-900/10 rounded-lg border-l-4 border-amber-500">
                                                                <div className="min-w-0 space-y-1">
                                                                    <div className="flex items-center gap-2 flex-wrap">
                                                                        <p className="font-semibold">{name}</p>
                                                                        <Badge variant="outline" className="text-[9px] h-4 px-1 border-amber-400 text-amber-700 bg-white/60 dark:bg-transparent">RECORDED OVERDUE</Badge>
                                                                    </div>
                                                                    <p className="text-xs text-gray-500 dark:text-gray-400">
                                                                        {invoiceId ? `Invoice ${invoiceId} • ` : ""}
                                                                        {due ? `Due ${due}` : "Due date unavailable"}
                                                                    </p>
                                                                    {reason && <p className="text-xs text-gray-500 dark:text-gray-400">{reason}</p>}
                                                                </div>
                                                                <div className="text-right shrink-0">
                                                                    <p className="font-bold text-amber-700 dark:text-amber-400">{amount ?? "Amount unavailable"}</p>
                                                                    <Button variant="link" size="sm" className="h-4 p-0 text-amber-600 text-xs">Remind</Button>
                                                                </div>
                                                            </div>
                                                        );
                                                    }
                                                    const description = nonEmptyString(a.description) ?? "Overdue invoice";
                                                    const days = formatDays(a.days_overdue);
                                                    const date = formatDate(a.date);
                                                    return (
                                                        <div key={`ar-${i}`} className="flex justify-between items-start gap-3 p-3 bg-amber-50 dark:bg-amber-900/10 rounded-lg border-l-4 border-amber-500">
                                                            <div className="min-w-0">
                                                                <p className="font-semibold">{description}</p>
                                                                <p className="text-xs text-gray-500 dark:text-gray-400">
                                                                    {days !== null ? `Overdue by ${days} days` : "Overdue"}
                                                                    {date ? ` • Due ${date}` : ""}
                                                                </p>
                                                            </div>
                                                            <div className="text-right shrink-0">
                                                                <p className="font-bold text-amber-700 dark:text-amber-400">{amount ?? "Amount unavailable"}</p>
                                                                <Button variant="link" size="sm" className="h-4 p-0 text-amber-600 text-xs">Remind</Button>
                                                            </div>
                                                        </div>
                                                    );
                                                })}
                                                {riskData.alerts.ar_alerts.length === 0 && <p className="text-sm text-center py-4 text-gray-500 dark:text-gray-400">No early warnings.</p>}
                                            </>
                                        )}
                                    </TabsContent>
                                    <TabsContent value="fraud" className="space-y-4 pt-4">
                                        {riskData.fraud.error ? (
                                            <div className="p-4 text-center text-amber-700 dark:text-amber-400">
                                                <AlertTriangle className="w-6 h-6 mx-auto mb-2" />
                                                <p className="text-sm font-medium">Fraud watch data is unavailable.</p>
                                                <p className="text-xs">Refresh Diagnostics to try again.</p>
                                            </div>
                                        ) : (
                                            <>
                                                {riskData.fraud.anomalies.map((f, i) => {
                                                    if (!f || typeof f !== "object") return null;
                                                    const amount = formatAmount(f.amount);
                                                    if (isRecordedFraudAlert(f)) {
                                                        const title = recordedFraudLabel(f.type);
                                                        const description = nonEmptyString(f.flag_reason);
                                                        const date = formatDate(f.timestamp);
                                                        const severity = nonEmptyString(f.severity);
                                                        const transactionId = nonEmptyString(f.transaction_id);
                                                        return (
                                                            <div key={`fraud-${i}`} className="p-3 bg-gray-100 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
                                                                <div className="flex justify-between items-start gap-2 mb-1">
                                                                    <div className="flex items-center gap-2 flex-wrap">
                                                                        <AlertTriangle className="w-4 h-4 text-red-500" />
                                                                        <p className="font-bold text-red-600">{title}</p>
                                                                        <Badge variant="outline" className="text-[9px] h-4 px-1 border-red-300 text-red-700 bg-white/60 dark:bg-transparent">RECORDED</Badge>
                                                                        {severity && <Badge variant="secondary" className="text-[9px] h-4">{severity}</Badge>}
                                                                    </div>
                                                                    <p className="text-sm font-mono shrink-0">{amount ?? "Amount unavailable"}</p>
                                                                </div>
                                                                {description && <p className="text-sm text-gray-600 dark:text-gray-300">{description}</p>}
                                                                <p className="text-xs text-gray-400 mt-2">
                                                                    {transactionId ? `Transaction ${transactionId} • ` : ""}
                                                                    {date ?? "Date unavailable"}
                                                                </p>
                                                            </div>
                                                        );
                                                    }
                                                    const type = nonEmptyString(f.type) ?? "Anomaly";
                                                    const description = nonEmptyString(f.description);
                                                    const date = formatDate(f.date);
                                                    return (
                                                        <div key={`fraud-${i}`} className="p-3 bg-gray-100 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
                                                            <div className="flex justify-between items-start gap-2 mb-1">
                                                                <div className="flex items-center gap-2">
                                                                    <AlertTriangle className="w-4 h-4 text-red-500" />
                                                                    <p className="font-bold text-red-600">{type}</p>
                                                                </div>
                                                                <p className="text-sm font-mono shrink-0">{amount ?? "Amount unavailable"}</p>
                                                            </div>
                                                            {description && <p className="text-sm text-gray-600 dark:text-gray-300">{description}</p>}
                                                            <p className="text-xs text-gray-400 mt-2">{date ?? "Date unavailable"}</p>
                                                        </div>
                                                    );
                                                })}
                                                {riskData.fraud.anomalies.length === 0 && <p className="text-sm text-center py-4 text-green-600 flex items-center justify-center gap-2"><CheckCircle2 className="w-4 h-4" /> Systems Secure</p>}
                                            </>
                                        )}
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
                                                <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider font-bold">Predicted ROI</p>
                                                <p className="text-lg font-bold text-green-600">{simResult.roi || "142%"}</p>
                                            </div>
                                            <div className="p-3 bg-white dark:bg-gray-800 rounded-lg shadow-sm">
                                                <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider font-bold">Breakeven</p>
                                                <p className="text-lg font-bold text-blue-600">{simResult.breakeven || "4.5 Months"}</p>
                                            </div>
                                        </div>
                                        <p className="text-sm text-gray-700 dark:text-gray-300 italic leading-relaxed">
                                            &quot;{simResult.prediction || "The cash flow impact is positive. Recommend proceeding if current volume holds."}&quot;
                                        </p>
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </div>

                    {/* Sidebar */}
                    <div className="space-y-6">
                        <Card className="bg-gray-900 text-gray-900 dark:text-white">
                            <CardHeader>
                                <CardTitle className="text-lg flex items-center gap-2">
                                    <DollarSign className="w-4 h-4 text-green-400" />
                                    Recent Leakage
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-4">
                                    <div className="flex justify-between items-center bg-black/5 dark:bg-white/5 p-3 rounded-lg">
                                        <span className="text-xs opacity-70">Price Drift (AWS)</span>
                                        <span className="text-sm font-bold text-red-400">+$12.40</span>
                                    </div>
                                    <div className="flex justify-between items-center bg-black/5 dark:bg-white/5 p-3 rounded-lg">
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
