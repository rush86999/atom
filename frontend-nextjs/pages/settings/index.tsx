
import React from 'react';
import Head from 'next/head';
import { Layout } from "@/components/layout/Layout";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PreferencesTab } from "@/components/settings/PreferencesTab";

export default function SettingsPage() {
    return (
        <Layout>
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
                        <TabsTrigger value="workspace" disabled>Workspace</TabsTrigger>
                        <TabsTrigger value="account" disabled>Account</TabsTrigger>
                    </TabsList>

                    <TabsContent value="preferences" className="space-y-4">
                        <PreferencesTab />
                    </TabsContent>

                    <TabsContent value="workspace">
                        {/* Future Workspace Settings */}
                    </TabsContent>
                </Tabs>
            </div>
        </Layout>
    );
}
