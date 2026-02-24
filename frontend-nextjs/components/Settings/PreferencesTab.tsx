
import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
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

const API_URL = "http://localhost:8000";
const USER_ID = "default_user";
const WORKSPACE_ID = "default";

export function PreferencesTab() {
    const [prefs, setPrefs] = useState<PreferenceState>(DEFAULT_PREFS);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchPreferences();
    }, []);

    const applyTheme = (theme: string) => {
        const root = document.documentElement;
        if (theme === 'dark') {
            root.classList.add('dark');
        } else if (theme === 'light') {
            root.classList.remove('dark');
        } else {
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            if (prefersDark) {
                root.classList.add('dark');
            } else {
                root.classList.remove('dark');
            }
        }
    };

    const getAuthHeaders = (): Record<string, string> => {
        const token = localStorage.getItem('auth_token');
        return {
            'Content-Type': 'application/json',
            ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        };
    };

    const fetchPreferences = async () => {
        try {
            setLoading(true);
            const controller = new AbortController();
            const timeout = setTimeout(() => controller.abort(), 5000);

            const res = await fetch(
                `${API_URL}/api/v1/preferences?user_id=${USER_ID}&workspace_id=${WORKSPACE_ID}`,
                { headers: getAuthHeaders(), signal: controller.signal }
            );
            clearTimeout(timeout);

            if (res.ok) {
                const data = await res.json();
                const merged = { ...DEFAULT_PREFS, ...data };
                setPrefs(merged);
                applyTheme(merged.theme);
            }
        } catch (error: any) {
            console.warn("Preferences API not reachable, using defaults:", error?.message);
            // Graceful fallback: just use defaults
            applyTheme(DEFAULT_PREFS.theme);
        } finally {
            setLoading(false);
        }
    };

    const handleSave = async (key: string, value: any) => {
        const updated = { ...prefs, [key]: value };
        setPrefs(updated);

        if (key === 'theme') {
            applyTheme(value);
        }

        try {
            const res = await fetch(`${API_URL}/api/v1/preferences`, {
                method: "POST",
                headers: getAuthHeaders(),
                body: JSON.stringify({
                    user_id: USER_ID,
                    workspace_id: WORKSPACE_ID,
                    key,
                    value
                })
            });

            if (!res.ok) throw new Error("Failed to save");
            toast.success("Saved");
        } catch (error) {
            console.error("Save error:", error);
            toast.error("Failed to save setting");
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
