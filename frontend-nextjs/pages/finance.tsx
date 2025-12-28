import React from 'react';
import Head from 'next/head';
import { FinanceCommandCenter } from '@/components/dashboards/FinanceCommandCenter';
import Layout from '@/components/layout/Layout';

export default function FinancePage() {
    return (
        <Layout>
            <Head>
                <title>Finance Command Center | Atom</title>
            </Head>
            <FinanceCommandCenter />
        </Layout>
    );
}
