
import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";

interface PreferenceState {
    theme: string;
    notifications_enabled: boolean;
    email_frequency: string;
}

const DEFAULT_PREFS: PreferenceState = {
    theme: "system",
    notifications_enabled: true,
    email_frequency: "daily"
};

export function PreferencesTab() {
    const [prefs, setPrefs] = useState<PreferenceState>(DEFAULT_PREFS);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);

    // Mock IDs for now, in real app these come from context
    const userId = "default_user";
    const workspaceId = "default";

    useEffect(() => {
        fetchPreferences();
    }, []);

    const fetchPreferences = async () => {
        try {
            setLoading(true);
            const res = await fetch(`/api/preferences?user_id=${userId}&workspace_id=${workspaceId}`);
            if (res.ok) {
                const data = await res.json();
                // Merge with defaults to handle missing keys
                setPrefs({ ...DEFAULT_PREFS, ...data });
            }
        } catch (error) {
            console.error("Failed to load preferences:", error);
            toast.error("Failed to load settings");
        } finally {
            setLoading(false);
        }
    };

    const handleSave = async (key: string, value: any) => {
        // Optimistic update
        setPrefs(prev => ({ ...prev, [key]: value }));

        // API call
        try {
            const res = await fetch("/api/preferences", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: userId,
                    workspace_id: workspaceId,
                    key,
                    value
                })
            });

            if (!res.ok) throw new Error("Failed to save");
            toast.success("Saved");
        } catch (error) {
            console.error("Save error:", error);
            toast.error("Failed to save setting");
            // Revert on error? For now simple toast is enough
        }
    };

    if (loading) {
        return (
            <div className="flex justify-center p-10">
                <Loader2 className="h-8 w-8 animate-spin" />
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <Card>
                <CardHeader>
                    <CardTitle>Appearance</CardTitle>
                    <CardDescription>Customize how ATOM looks on your device.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="flex items-center justify-between">
                        <div className="space-y-0.5">
                            <Label>Theme</Label>
                            <div className="text-sm text-muted-foreground">Select your preferred color theme.</div>
                        </div>
                        <Select
                            value={prefs.theme}
                            onValueChange={(val) => handleSave("theme", val)}
                        >
                            <SelectTrigger className="w-[180px]">
                                <SelectValue placeholder="Select theme" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="light">Light</SelectItem>
                                <SelectItem value="dark">Dark</SelectItem>
                                <SelectItem value="system">System</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>Notifications</CardTitle>
                    <CardDescription>Manage your alert preferences.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="flex items-center justify-between">
                        <div className="space-y-0.5">
                            <Label>Enable Notifications</Label>
                            <div className="text-sm text-muted-foreground">Receive alerts about critical events.</div>
                        </div>
                        <Switch
                            checked={prefs.notifications_enabled}
                            onCheckedChange={(val) => handleSave("notifications_enabled", val)}
                        />
                    </div>

                    <div className="flex items-center justify-between mt-4">
                        <div className="space-y-0.5">
                            <Label>Email Digest Frequency</Label>
                            <div className="text-sm text-muted-foreground">How often should we email you summaries?</div>
                        </div>
                        <Select
                            value={prefs.email_frequency}
                            onValueChange={(val) => handleSave("email_frequency", val)}
                        >
                            <SelectTrigger className="w-[180px]">
                                <SelectValue placeholder="Select frequency" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="daily">Daily</SelectItem>
                                <SelectItem value="weekly">Weekly</SelectItem>
                                <SelectItem value="never">Never</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
