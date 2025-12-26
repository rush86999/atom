import React, { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";
import { TrendingUp, Calculator, AlertCircle } from "lucide-react";
import { useToast } from "../ui/use-toast";

const ForecastingSandbox = () => {
    const [forecastData, setForecastData] = useState<any[]>([]);
    const [scenarioResult, setScenarioResult] = useState<any>(null);
    const [scenarioText, setScenarioText] = useState("");
    const [loading, setLoading] = useState(true);
    const { toast } = useToast();
    const workspaceId = "default-workspace";

    useEffect(() => {
        fetchForecast();
    }, []);

    const fetchForecast = async () => {
        try {
            const response = await fetch(`/api/v1/accounting/forecast?workspace_id=${workspaceId}`);
            const data = await response.json();
            // Data looks like: { projection: [ { week_start, projected_balance, projected_income, projected_expense } ] }
            setForecastData(data.projection || []);
            setLoading(false);
        } catch (error) {
            console.error("Failed to fetch forecast:", error);
            setLoading(false);
        }
    };

    const runScenario = async () => {
        if (!scenarioText) return;
        setLoading(true);
        try {
            const response = await fetch(`/api/v1/accounting/scenario?workspace_id=${workspaceId}&scenario_description=${encodeURIComponent(scenarioText)}`, {
                method: 'POST'
            });
            const data = await response.json();
            setScenarioResult(data);
            toast({ title: "Scenario Modeled", description: "Impact analysis complete." });
        } catch (error) {
            toast({ title: "Scenario Failed", variant: "error" });
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="space-y-6">
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <TrendingUp className="h-5 w-5" />
                        13-Week Cash Flow Forecast
                    </CardTitle>
                    <CardDescription>
                        AI-projected cash balance based on current burn rate and upcoming commitments.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="h-[300px] w-full mt-4">
                        <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={forecastData}>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                <XAxis
                                    dataKey="week_start"
                                    tickFormatter={(str) => new Date(str).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                                    fontSize={12}
                                />
                                <YAxis fontSize={12} tickFormatter={(val) => `$${val.toLocaleString()}`} />
                                <Tooltip
                                    formatter={(val: number) => [`$${val.toLocaleString()}`, 'Projected Balance']}
                                    labelFormatter={(label) => new Date(label).toLocaleDateString()}
                                />
                                <ReferenceLine y={0} stroke="#ef4444" strokeDasharray="3 3" />
                                <Line
                                    type="monotone"
                                    dataKey="projected_balance"
                                    stroke="#3b82f6"
                                    strokeWidth={3}
                                    dot={{ r: 4 }}
                                    activeDot={{ r: 6 }}
                                />
                            </LineChart>
                        </ResponsiveContainer>
                    </div>
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Calculator className="h-5 w-5" />
                        Scenario Sandbox
                    </CardTitle>
                    <CardDescription>
                        Describe a potential scenario (e.g. "Hire a dev for $10k/mo" or "Lose our biggest client") to see the impact.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="flex gap-2">
                        <Input
                            value={scenarioText}
                            onChange={(e) => setScenarioText(e.target.value)}
                            placeholder="Describe a scenario..."
                            className="flex-1"
                        />
                        <Button onClick={runScenario} disabled={loading}>Analyze</Button>
                    </div>

                    {scenarioResult && (
                        <div className="mt-4 p-4 rounded-lg bg-secondary/50 border border-secondary">
                            <h4 className="font-semibold mb-2">Scenario Impact Análisis</h4>
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <p className="text-xs text-muted-foreground">Cash Impact (Weekly)</p>
                                    <p className={`text-lg font-bold ${scenarioResult.impact_value < 0 ? 'text-red-500' : 'text-green-500'}`}>
                                        {scenarioResult.impact_value < 0 ? '-' : '+'}${Math.abs(scenarioResult.impact_value).toLocaleString()}
                                    </p>
                                </div>
                                <div>
                                    <p className="text-xs text-muted-foreground">Risk Level</p>
                                    <p className="text-lg font-bold capitalize">{scenarioResult.risk_level}</p>
                                </div>
                            </div>
                            <div className="mt-4 flex gap-2 items-start text-sm">
                                <AlertCircle className="h-4 w-4 mt-0.5 text-blue-500" />
                                <p className="text-muted-foreground italic">"{scenarioResult.analysis}"</p>
                            </div>
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
};

export default ForecastingSandbox;
