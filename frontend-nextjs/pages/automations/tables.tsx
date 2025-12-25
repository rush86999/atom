import React from 'react';
import Head from 'next/head';
import WorkflowTables from '@/components/Automations/WorkflowTables';

/**
 * Workflow Tables Page
 * 
 * Google Sheets-like data tables connected to workflow automations
 * Activepieces-style Tables feature
 */
export default function TablesPage() {
    const handleSelectTable = (table: any) => {
        console.log('Selected table:', table);
    };

    return (
        <>
            <Head>
                <title>Tables | Atom</title>
                <meta name="description" content="Manage data tables for your workflow automations. Store, query, and transform data like Google Sheets." />
            </Head>
            <div className="h-screen">
                <WorkflowTables
                    onSelectTable={handleSelectTable}
                    className="h-full"
                />
            </div>
        </>
    );
}
