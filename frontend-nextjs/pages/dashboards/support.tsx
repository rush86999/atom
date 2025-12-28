import Head from 'next/head';
import SupportCommandCenter from '@/components/dashboards/SupportCommandCenter';

export default function SupportDashboard() {
    return (
        <>
            <Head>
                <title>Support Command Center | ATOM</title>
                <meta name="description" content="Unified support inbox across all your ticketing platforms" />
            </Head>

            <div className="relative">
                {/* Optional background glow specific to this dashboard */}
                <div className="absolute -top-24 -left-24 w-96 h-96 bg-rose-500/10 blur-[100px] rounded-full pointer-events-none" />
                <SupportCommandCenter />
            </div>
        </>
    );
}
