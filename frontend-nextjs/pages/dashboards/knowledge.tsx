import Head from 'next/head';
import Sidebar from '@/components/layout/Sidebar';
import KnowledgeCommandCenter from '@/components/dashboards/KnowledgeCommandCenter';

export default function KnowledgeDashboard() {
    return (
        <div className="flex h-screen bg-background text-foreground overflow-hidden">
            <Head>
                <title>Knowledge Command Center | ATOM</title>
                <meta name="description" content="Unified document and knowledge search across your cloud storage" />
            </Head>

            <Sidebar />

            <main className="flex-1 relative overflow-y-auto bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-zinc-900/20 via-background to-background">
                <KnowledgeCommandCenter />
            </main>
        </div>
    );
}
