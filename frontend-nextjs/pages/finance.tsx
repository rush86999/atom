import Head from 'next/head';
import FinanceCommandCenter from '@/components/dashboards/FinanceCommandCenter';

export default function FinancePage() {
    return (
        <>
            <Head>
                <title>Finance | ATOM</title>
                <meta name="description" content="Financial overview and transactions management" />
            </Head>

            <div className="relative">
                {/* Optional background glow */}
                <div className="absolute -top-24 -left-24 w-96 h-96 bg-green-500/10 blur-[100px] rounded-full pointer-events-none" />
                <FinanceCommandCenter />
            </div>
        </>
    );
}
