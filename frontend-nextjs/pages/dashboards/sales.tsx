import Head from 'next/head';
import Sidebar from '@/components/layout/Sidebar';
import SalesCommandCenter from '@/components/dashboards/SalesCommandCenter';

export default function SalesDashboard() {
    return (
        <div className="flex h-screen bg-background text-foreground overflow-hidden">
            <Head>
                <title>Sales Command Center | ATOM</title>
                <meta name="description" content="Unified sales intelligence across all your CRM platforms" />
            </Head>

            <Sidebar />

            <main className="flex-1 relative overflow-y-auto bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-orange-900/10 via-background to-background">
                <SalesCommandCenter />
            </main>
        </div>
    );
}
