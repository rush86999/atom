import Head from 'next/head';
import KnowledgeCommandCenter from '@/components/dashboards/KnowledgeCommandCenter';

export default function KnowledgeDashboard() {
    return (
        <>
            <Head>
                <title>Knowledge Command Center | ATOM</title>
                <meta name="description" content="Unified document and knowledge search across your cloud storage" />
            </Head>

            <div className="relative">
                {/* Optional background glow specific to this dashboard */}
                <div className="absolute -top-24 -left-24 w-96 h-96 bg-zinc-500/10 blur-[100px] rounded-full pointer-events-none" />
                <KnowledgeCommandCenter />
            </div>
        </>
    );
}
