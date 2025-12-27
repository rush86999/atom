import Head from 'next/head';
import Sidebar from '@/components/layout/Sidebar';
import SupportCommandCenter from '@/components/dashboards/SupportCommandCenter';

export default function SupportDashboard() {
    return (
        <div className="flex h-screen bg-background text-foreground overflow-hidden">
            <Head>
                <title>Support Command Center | ATOM</title>
                <meta name="description" content="Unified support inbox across all your ticketing platforms" />
            </Head>

            <Sidebar />

            <main className="flex-1 relative overflow-y-auto bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-rose-900/10 via-background to-background">
                <SupportCommandCenter />
            </main>
        </div>
    );
}
