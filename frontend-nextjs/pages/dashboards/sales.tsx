import Head from 'next/head';
import SalesCommandCenter from '@/components/dashboards/SalesCommandCenter';

export default function SalesDashboard() {
    return (
        <>
            <Head>
                <title>Sales Command Center | ATOM</title>
                <meta name="description" content="Unified sales intelligence across all your CRM platforms" />
            </Head>

            <div className="relative">
                {/* Optional background glow specific to this dashboard */}
                <div className="absolute -top-24 -left-24 w-96 h-96 bg-orange-500/10 blur-[100px] rounded-full pointer-events-none" />
                <SalesCommandCenter />
            </div>
        </>
    );
}
