import React from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';
import FlowVersioning from '@/components/Automations/FlowVersioning';
import { useToast } from '@/components/ui/use-toast';

/**
 * Flow Version History Page
 * 
 * View and manage workflow version history
 * Git-like version control for workflows
 */
export default function VersionHistoryPage() {
    const router = useRouter();
    const { flowId } = router.query;
    const toast = useToast();

    const handleRestoreVersion = (version: any) => {
        toast({
            title: "Version Restored",
            description: `Restored to version ${version.version}. A new version has been created.`,
        });
    };

    const handleViewVersion = (version: any) => {
        router.push(`/automations/builder?version=${version.id}&readonly=true`);
    };

    const handleCompareVersions = (v1: any, v2: any) => {
        toast({
            title: "Compare Mode",
            description: `Comparing v${v1.version} with v${v2.version}`,
        });
    };

    return (
        <>
            <Head>
                <title>Version History | Atom</title>
                <meta name="description" content="View and manage workflow version history. Compare, restore, and track changes to your automations." />
            </Head>
            <div className="h-screen">
                <FlowVersioning
                    flowId={flowId as string}
                    onRestoreVersion={handleRestoreVersion}
                    onViewVersion={handleViewVersion}
                    onCompareVersions={handleCompareVersions}
                    className="h-full"
                />
            </div>
        </>
    );
}
