import Head from 'next/head';
import Sidebar from '@/components/layout/Sidebar';
import ProjectCommandCenter from '@/components/dashboards/ProjectCommandCenter';

export default function ProjectsDashboard() {
    return (
        <div className="flex h-screen bg-background text-foreground overflow-hidden">
            <Head>
                <title>Project Command Center | ATOM</title>
                <meta name="description" content="Unified project management across all your platforms" />
            </Head>

            <Sidebar />

            <main className="flex-1 relative overflow-y-auto bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-blue-900/10 via-background to-background">
                <ProjectCommandCenter />
            </main>
        </div>
    );
}
