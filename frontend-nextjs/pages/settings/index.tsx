import React from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PreferencesTab } from "@/components/Settings/PreferencesTab";
import { DataPipelinesTab } from "@/components/Settings/DataPipelinesTab"; // Import
import { useUserRole } from "@/lib/user-role";

export default function SettingsPage() {
    // Admin-band links: LLM Routing reads workspace-wide model telemetry
    // (/api/chat/routing-stats is workspace_admin+) and Learning &
    // Verification is the admin verification panel. Unknown role → show
    // (backend enforces); a transient /api/auth/me failure must not hide nav.
    const { role, isAdmin } = useUserRole();
    const showAdminLinks = !role || isAdmin;

    return (
        <>
            <Head>
                <title>Settings - ATOM</title>
            </Head>

            <div className="container mx-auto py-10 max-w-4xl">
                <div className="mb-8">
                    <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
                    <p className="text-muted-foreground mt-2">
                        Manage your workspace preferences and account settings.
                    </p>
                </div>

                <Tabs defaultValue="preferences" className="space-y-4">
                    <TabsList>
                        <TabsTrigger value="preferences">Preferences</TabsTrigger>
                        <TabsTrigger value="pipelines">Data Pipelines</TabsTrigger> {/* New Tab */}
                        <TabsTrigger value="workspace" disabled>Workspace</TabsTrigger>
                        <TabsTrigger value="account">Account</TabsTrigger>
                    </TabsList>

                    <TabsContent value="preferences" className="space-y-4">
                        <PreferencesTab />
                    </TabsContent>

                    <TabsContent value="pipelines" className="space-y-4">
                        <DataPipelinesTab /> {/* New Component */}
                    </TabsContent>

                    <TabsContent value="workspace">
                        {/* Future Workspace Settings */}
                    </TabsContent>

                    {/* Advanced settings — previously URL-only orphans (UI gap #8) */}
                    <div className="pt-6 border-t border-border mt-6">
                        <h3 className="text-sm font-medium text-muted-foreground mb-2">Advanced</h3>
                        <div className="flex flex-wrap gap-3 text-sm">
                            <Link className="px-3 py-1.5 rounded-md bg-muted hover:bg-accent" href="/settings/ai">AI Providers</Link>
                            <Link className="px-3 py-1.5 rounded-md bg-muted hover:bg-accent" href="/settings/account">Account, Password & 2FA</Link>
                            {showAdminLinks && (
                                <Link className="px-3 py-1.5 rounded-md bg-muted hover:bg-accent" href="/settings/routing">LLM Routing</Link>
                            )}
                            <Link className="px-3 py-1.5 rounded-md bg-muted hover:bg-accent" href="/settings/local-models">Local Models (Ollama)</Link>
                            <Link className="px-3 py-1.5 rounded-md bg-muted hover:bg-accent" href="/settings/sessions">Sessions</Link>
                            <Link className="px-3 py-1.5 rounded-md bg-muted hover:bg-accent" href="/settings/bpe">BPE Workspace</Link>
                            {showAdminLinks && (
                                <Link className="px-3 py-1.5 rounded-md bg-muted hover:bg-accent" href="/admin/learning-verification">Learning &amp; Verification</Link>
                            )}
                        </div>
                    </div>
                </Tabs>
            </div>
        </>
    );
}

