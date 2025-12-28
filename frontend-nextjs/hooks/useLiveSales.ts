import { useState, useEffect } from 'react';

export interface UnifiedDeal {
    id: string;
    deal_name: string;
    value: number;
    status: string;
    stage: string;
    platform: 'salesforce' | 'hubspot' | 'zoho' | 'dynamics';
    company?: string;
    close_date?: string;
    owner?: string;
    probability?: number;
    url?: string;
}

export interface SalesStats {
    total_pipeline_value: number;
    active_deal_count: number;
    win_rate: number;
    avg_deal_size: number;
}

interface LivePipelineResponse {
    ok: boolean;
    stats: SalesStats;
    deals: UnifiedDeal[];
    providers: Record<string, boolean>;
}

export function useLiveSales() {
    const [deals, setDeals] = useState<UnifiedDeal[]>([]);
    const [stats, setStats] = useState<SalesStats>({
        total_pipeline_value: 0,
        active_deal_count: 0,
        win_rate: 0,
        avg_deal_size: 0
    });
    const [isLoading, setIsLoading] = useState(true);
    const [activeProviders, setActiveProviders] = useState<Record<string, boolean>>({});

    const fetchLivePipeline = async () => {
        try {
            const res = await fetch('/api/atom/sales/live/pipeline');
            if (res.ok) {
                const data: LivePipelineResponse = await res.json();
                setDeals(data.deals);
                setStats(data.stats);
                setActiveProviders(data.providers);
            }
        } catch (error) {
            console.error("Failed to fetch live sales pipeline:", error);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchLivePipeline();

        // Poll every 60s for sales data
        const interval = setInterval(fetchLivePipeline, 60000);
        return () => clearInterval(interval);
    }, []);

    return {
        deals,
        stats,
        isLoading,
        activeProviders,
        refresh: fetchLivePipeline
    };
}
