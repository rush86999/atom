import React from 'react';
import Head from 'next/head';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PreferencesTab } from "@/components/Settings/PreferencesTab";
import { DataPipelinesTab } from "@/components/Settings/DataPipelinesTab"; // Import

export default function SettingsPage() {
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
                            <a className="px-3 py-1.5 rounded-md bg-muted hover:bg-accent" href="/settings/ai">AI Providers</a>
                            <a className="px-3 py-1.5 rounded-md bg-muted hover:bg-accent" href="/settings/account">Account, Password & 2FA</a>
                            <a className="px-3 py-1.5 rounded-md bg-muted hover:bg-accent" href="/settings/routing">LLM Routing</a>
                            <a className="px-3 py-1.5 rounded-md bg-muted hover:bg-accent" href="/settings/local-models">Local Models (Ollama)</a>
                            <a className="px-3 py-1.5 rounded-md bg-muted hover:bg-accent" href="/settings/sessions">Sessions</a>
                            <a className="px-3 py-1.5 rounded-md bg-muted hover:bg-accent" href="/settings/bpe">BPE Workspace</a>
                            <a className="px-3 py-1.5 rounded-md bg-muted hover:bg-accent" href="/admin/learning-verification">Learning &amp; Verification</a>
                        </div>
                    </div>
                </Tabs>
            </div>
        </>
    );
}

