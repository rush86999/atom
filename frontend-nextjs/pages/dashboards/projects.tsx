import Head from 'next/head';
import ProjectCommandCenter from '@/components/dashboards/ProjectCommandCenter';

export default function ProjectsDashboard() {
    return (
        <>
            <Head>
                <title>Project Command Center | ATOM</title>
                <meta name="description" content="Unified project management across all your platforms" />
            </Head>

            <div className="relative">
                {/* Optional background glow specific to this dashboard */}
                <div className="absolute -top-24 -left-24 w-96 h-96 bg-blue-500/10 blur-[100px] rounded-full pointer-events-none" />
                <ProjectCommandCenter />
            </div>
        </>
    );
}
