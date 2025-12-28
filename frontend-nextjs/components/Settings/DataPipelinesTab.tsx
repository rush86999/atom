import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2, Save, Activity, RefreshCw } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";

// Helper to interact with preferences API
const usePreference = (key: string, defaultValue: any) => {
    const [value, setValue] = useState(defaultValue);
    const [loading, setLoading] = useState(true);

    // Hardcoded workspace/user for this MVP feature
    const USER_ID = "system";
    const WORKSPACE_ID = "global";

    useEffect(() => {
        fetch(`/api/preferences/${key}?user_id=${USER_ID}&workspace_id=${WORKSPACE_ID}`)
            .then(res => res.json())
            .then(data => {
                if (data.value) setValue(data.value);
                setLoading(false);
            })
            .catch(err => {
                console.error(err);
                setLoading(false);
            });
    }, [key]);

    const save = async (newValue: any) => {
        setValue(newValue);
        await fetch('/api/preferences', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: USER_ID,
                workspace_id: WORKSPACE_ID,
                key,
                value: newValue
            })
        });
    };

    return { value, save, loading };
};

export function DataPipelinesTab() {
    const { toast } = useToast();
    const [isSaving, setIsSaving] = useState(false);

    // Sales Pipeline Preference
    const salesPref = usePreference("schedule.sales", "*/30 * * * *");
    // Projects Pipeline Preference
    const projectsPref = usePreference("schedule.projects", "*/15 * * * *");
    // Finance Pipeline Preference
    const financePref = usePreference("schedule.finance", "0 * * * *");

    const handleSave = async () => {
        setIsSaving(true);
        try {
            // Save all preferences
            await Promise.all([
                salesPref.save(salesPref.value),
                projectsPref.save(projectsPref.value),
                financePref.save(financePref.value)
            ]);

            // Reload scheduler
            const res = await fetch('/api/v1/scheduler/reload', { method: 'POST' });
            if (!res.ok) throw new Error("Failed to reload scheduler");

            toast({
                title: "Schedules Updated",
                description: "Memory pipelines have been rescheduled successfully.",
            });
        } catch (error) {
            toast({
                title: "Error",
                description: "Failed to update schedules.",
                variant: "destructive"
            });
        } finally {
            setIsSaving(false);
        }
    };

    const frequencies = [
        { label: "Every 15 Minutes", value: "*/15 * * * *" },
        { label: "Every 30 Minutes", value: "*/30 * * * *" },
        { label: "Hourly", value: "0 * * * *" },
        { label: "Every 6 Hours", value: "0 */6 * * *" },
        { label: "Daily (Midnight)", value: "0 0 * * *" },
    ];

    if (salesPref.loading || projectsPref.loading || financePref.loading) {
        return <div className="flex justify-center p-8"><Loader2 className="h-8 w-8 animate-spin text-muted-foreground" /></div>;
    }

    return (
        <div className="space-y-6">
            <div>
                <h3 className="text-lg font-medium">Memory Pipeline Schedules</h3>
                <p className="text-sm text-muted-foreground">
                    Configure how often background agents ingest data from external sources into the AI memory.
                </p>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
                {/* Sales Card */}
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium flex items-center gap-2">
                            <Activity className="h-4 w-4 text-orange-500" />
                            Sales Pipeline
                        </CardTitle>
                        <CardDescription>HubSpot / Salesforce</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <Label className="text-xs mb-1.5 block">Sync Frequency</Label>
                        <Select value={salesPref.value} onValueChange={salesPref.save}>
                            <SelectTrigger>
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                {frequencies.map(f => (
                                    <SelectItem key={f.value} value={f.value}>{f.label}</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </CardContent>
                </Card>

                {/* Projects Card */}
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium flex items-center gap-2">
                            <RefreshCw className="h-4 w-4 text-blue-500" />
                            Projects Pipeline
                        </CardTitle>
                        <CardDescription>Jira / Asana</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <Label className="text-xs mb-1.5 block">Sync Frequency</Label>
                        <Select value={projectsPref.value} onValueChange={projectsPref.save}>
                            <SelectTrigger>
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                {frequencies.map(f => (
                                    <SelectItem key={f.value} value={f.value}>{f.label}</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </CardContent>
                </Card>

                {/* Finance Card */}
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium flex items-center gap-2">
                            <Badge variant="outline" className="px-1 py-0 h-4">Beta</Badge>
                            Finance Pipeline
                        </CardTitle>
                        <CardDescription>Stripe / Xero</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <Label className="text-xs mb-1.5 block">Sync Frequency</Label>
                        <Select value={financePref.value} onValueChange={financePref.save}>
                            <SelectTrigger>
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                {frequencies.map(f => (
                                    <SelectItem key={f.value} value={f.value}>{f.label}</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </CardContent>
                </Card>
            </div>

            <div className="flex justify-end">
                <Button onClick={handleSave} disabled={isSaving}>
                    {isSaving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
                    Save & Apply Changes
                </Button>
            </div>
        </div>
    );
}
